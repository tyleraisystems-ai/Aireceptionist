"""Retell Custom Function endpoints.

Every endpoint here: verifies X-Retell-Signature (401 on failure), is
idempotent on call_id (+ slot hash for bookings), returns fast against
Postgres only (no outbound network calls in the live turn — Google Calendar
wiring lands in Phase 2 behind the same function contracts), and replies with
a compact `result` under Retell's 15k char cap.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.config import get_settings, is_unresolved
from app.db import get_db
from app.idempotency import run_idempotent
from app.models import Appointment, EmergencyFlag, Lead
from app.security import verify_signature
from app.util import parse_function_call, respond, slot_hash

logger = logging.getLogger("retell.functions")

router = APIRouter()


def _bad_args(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail=exc.errors())


def _overlapping_booked_query(db: Session, start: datetime, end: datetime, exclude_call_id: Optional[str] = None):
    q = db.query(Appointment).filter(
        Appointment.status == "booked",
        Appointment.start_time < end,
        Appointment.end_time > start,
    )
    if exclude_call_id is not None:
        q = q.filter(Appointment.call_id != exclude_call_id)
    return q


_BUSINESS_HOURS_START = [9, 11, 13, 15]


def _next_open_windows(db: Session, count: int, window_hours: int = 2) -> list[tuple[datetime, datetime]]:
    """Candidate-slot generator backed by Postgres only.

    TODO(phase2): replace the busy-slot source with a merge of this table
    and a live Google Calendar free/busy query.
    """
    windows: list[tuple[datetime, datetime]] = []
    now = datetime.now().astimezone()
    for day_offset in range(1, 15):
        candidate_day = now + timedelta(days=day_offset)
        if candidate_day.weekday() >= 5:  # skip Sat/Sun
            continue
        for hour in _BUSINESS_HOURS_START:
            start = candidate_day.replace(hour=hour, minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=window_hours)
            if _overlapping_booked_query(db, start, end).first() is None:
                windows.append((start, end))
                if len(windows) == count:
                    return windows
    return windows


# ---------------------------------------------------------------- schemas --


class CheckAvailabilityArgs(BaseModel):
    preferred_date: Optional[str] = None


class BookVisitArgs(BaseModel):
    start_time: datetime
    end_time: datetime
    customer_name: str
    phone: str
    address: str
    issue_description: str = ""


class RescheduleVisitArgs(BaseModel):
    new_start_time: datetime
    new_end_time: datetime
    appointment_id: Optional[str] = None


class CancelVisitArgs(BaseModel):
    appointment_id: Optional[str] = None


class CaptureLeadArgs(BaseModel):
    customer_name: str
    phone: str
    address: str = ""
    issue_description: str = ""
    urgency: str = "routine"  # routine | urgent


class FlagEmergencyArgs(BaseModel):
    reason: str
    callback_number: str = ""


class TransferToHumanArgs(BaseModel):
    reason: Optional[str] = ""


# ---------------------------------------------------------------- routes --


@router.post("/check_availability")
def check_availability(body: bytes = Depends(verify_signature), db: Session = Depends(get_db)):
    call_id, raw_args = parse_function_call(body)
    try:
        CheckAvailabilityArgs(**raw_args)
    except ValidationError as exc:
        raise _bad_args(exc)

    windows = _next_open_windows(db, count=2)
    return respond(
        {
            "available_windows": [
                {"start": s.isoformat(), "end": e.isoformat()} for s, e in windows
            ]
        }
    )


@router.post("/book_visit")
def book_visit(body: bytes = Depends(verify_signature), db: Session = Depends(get_db)):
    call_id, raw_args = parse_function_call(body)
    try:
        args = BookVisitArgs(**raw_args)
    except ValidationError as exc:
        raise _bad_args(exc)
    if args.end_time <= args.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")

    hash_ = slot_hash(args.start_time, args.end_time)
    key = f"book_visit:{call_id}:{hash_}"

    def compute() -> dict:
        conflict = _overlapping_booked_query(
            db, args.start_time, args.end_time, exclude_call_id=call_id
        ).first()
        if conflict is not None:
            return {"booked": False, "reason": "slot_unavailable"}

        appt = Appointment(
            call_id=call_id,
            slot_hash=hash_,
            start_time=args.start_time,
            end_time=args.end_time,
            customer_name=args.customer_name,
            phone=args.phone,
            address=args.address,
            issue_description=args.issue_description,
            status="booked",
        )
        db.add(appt)
        db.flush()
        return {
            "booked": True,
            "appointment_id": appt.id,
            "start_time": args.start_time.isoformat(),
            "end_time": args.end_time.isoformat(),
        }

    result, _ = run_idempotent(db, key, compute)
    return respond(result)


@router.post("/reschedule_visit")
def reschedule_visit(body: bytes = Depends(verify_signature), db: Session = Depends(get_db)):
    call_id, raw_args = parse_function_call(body)
    try:
        args = RescheduleVisitArgs(**raw_args)
    except ValidationError as exc:
        raise _bad_args(exc)
    if args.new_end_time <= args.new_start_time:
        raise HTTPException(status_code=400, detail="new_end_time must be after new_start_time")

    existing = _find_callers_appointment(db, call_id, args.appointment_id)
    if existing is None:
        return respond({"rescheduled": False, "reason": "no_existing_appointment"})

    new_hash = slot_hash(args.new_start_time, args.new_end_time)
    key = f"reschedule_visit:{call_id}:{existing.id}:{new_hash}"

    def compute() -> dict:
        conflict = db.query(Appointment).filter(
            Appointment.status == "booked",
            Appointment.id != existing.id,
            Appointment.start_time < args.new_end_time,
            Appointment.end_time > args.new_start_time,
        ).first()
        if conflict is not None:
            return {"rescheduled": False, "reason": "slot_unavailable"}

        existing.start_time = args.new_start_time
        existing.end_time = args.new_end_time
        existing.slot_hash = new_hash
        db.flush()
        return {
            "rescheduled": True,
            "appointment_id": existing.id,
            "start_time": args.new_start_time.isoformat(),
            "end_time": args.new_end_time.isoformat(),
        }

    result, _ = run_idempotent(db, key, compute)
    return respond(result)


@router.post("/cancel_visit")
def cancel_visit(body: bytes = Depends(verify_signature), db: Session = Depends(get_db)):
    call_id, raw_args = parse_function_call(body)
    try:
        args = CancelVisitArgs(**raw_args)
    except ValidationError as exc:
        raise _bad_args(exc)

    existing = _find_callers_appointment(db, call_id, args.appointment_id)
    if existing is None:
        return respond({"cancelled": False, "reason": "no_existing_appointment"})

    key = f"cancel_visit:{call_id}:{existing.id}"

    def compute() -> dict:
        existing.status = "cancelled"
        db.flush()
        return {"cancelled": True, "appointment_id": existing.id}

    result, _ = run_idempotent(db, key, compute)
    return respond(result)


def _find_callers_appointment(
    db: Session, call_id: str, appointment_id: Optional[str]
) -> Optional[Appointment]:
    q = db.query(Appointment).filter(Appointment.call_id == call_id, Appointment.status == "booked")
    if appointment_id is not None:
        q = q.filter(Appointment.id == appointment_id)
    return q.order_by(Appointment.created_at.desc()).first()


@router.post("/capture_lead")
def capture_lead(body: bytes = Depends(verify_signature), db: Session = Depends(get_db)):
    call_id, raw_args = parse_function_call(body)
    try:
        args = CaptureLeadArgs(**raw_args)
    except ValidationError as exc:
        raise _bad_args(exc)

    key = f"capture_lead:{call_id}"

    def compute() -> dict:
        lead = Lead(
            call_id=call_id,
            customer_name=args.customer_name,
            phone=args.phone,
            address=args.address,
            issue_description=args.issue_description,
            urgency=args.urgency,
        )
        db.add(lead)
        db.flush()
        return {"captured": True, "lead_id": lead.id}

    result, _ = run_idempotent(db, key, compute)
    return respond(result)


@router.post("/flag_emergency")
def flag_emergency(body: bytes = Depends(verify_signature), db: Session = Depends(get_db)):
    call_id, raw_args = parse_function_call(body)
    try:
        args = FlagEmergencyArgs(**raw_args)
    except ValidationError as exc:
        raise _bad_args(exc)

    key = f"flag_emergency:{call_id}"

    def compute() -> dict:
        flag = EmergencyFlag(
            call_id=call_id, reason=args.reason, callback_number=args.callback_number
        )
        db.add(flag)
        db.flush()
        return {"flagged": True, "emergency_id": flag.id}

    result, _ = run_idempotent(db, key, compute)
    return respond(result)


@router.post("/transfer_to_human")
def transfer_to_human(body: bytes = Depends(verify_signature), db: Session = Depends(get_db)):
    call_id, raw_args = parse_function_call(body)
    try:
        args = TransferToHumanArgs(**raw_args)
    except ValidationError as exc:
        raise _bad_args(exc)

    destination = get_settings().human_transfer_destination
    if is_unresolved(destination):
        logger.warning("transfer_to_human called for call_id=%s but destination is unset", call_id)
        return respond(
            {
                "transferred": False,
                "reason": "destination_not_configured",
            }
        )

    return respond({"transferred": True, "destination": destination, "reason": args.reason})
