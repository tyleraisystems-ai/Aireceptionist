import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Appointment, CallLog, Lead, Transcript


def create_lead(
    db: Session,
    *,
    full_name: str,
    callback_number: str,
    service_address: str,
    issue_summary: str,
    urgency: str,
    disposition: str = "NEW",
) -> Lead:
    lead = Lead(
        full_name=full_name,
        callback_number=callback_number,
        service_address=service_address,
        issue_summary=issue_summary,
        urgency=urgency,
        disposition=disposition,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def create_appointment(
    db: Session,
    *,
    lead_id: uuid.UUID,
    scheduled_start: datetime,
    scheduled_end: datetime,
    external_calendar_event_id: str | None = None,
) -> Appointment:
    appointment = Appointment(
        lead_id=lead_id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        external_calendar_event_id=external_calendar_event_id,
        status="BOOKED",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def get_active_appointment_by_phone(db: Session, callback_number: str) -> Appointment | None:
    stmt = (
        select(Appointment)
        .join(Lead)
        .where(Lead.callback_number == callback_number, Appointment.status == "BOOKED")
        .order_by(Appointment.scheduled_start.desc())
    )
    return db.execute(stmt).scalars().first()


def get_appointment(db: Session, appointment_id: uuid.UUID) -> Appointment | None:
    return db.get(Appointment, appointment_id)


def update_appointment_schedule(
    db: Session, appointment: Appointment, *, scheduled_start: datetime, scheduled_end: datetime
) -> Appointment:
    appointment.scheduled_start = scheduled_start
    appointment.scheduled_end = scheduled_end
    appointment.status = "RESCHEDULED"
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, appointment: Appointment) -> Appointment:
    appointment.status = "CANCELLED"
    db.commit()
    db.refresh(appointment)
    return appointment


def update_lead_disposition(db: Session, lead: Lead, *, disposition: str, urgency: str | None = None) -> Lead:
    lead.disposition = disposition
    if urgency is not None:
        lead.urgency = urgency
    db.commit()
    db.refresh(lead)
    return lead


def get_latest_lead_by_phone(db: Session, callback_number: str) -> Lead | None:
    stmt = (
        select(Lead)
        .where(Lead.callback_number == callback_number)
        .order_by(Lead.created_at.desc())
    )
    return db.execute(stmt).scalars().first()


def get_call_log_by_retell_id(db: Session, retell_call_id: str) -> CallLog | None:
    return db.query(CallLog).filter_by(retell_call_id=retell_call_id).one_or_none()


def upsert_call_log_started(
    db: Session, *, retell_call_id: str, caller_number: str | None, started_at: datetime | None
) -> CallLog:
    call_log = get_call_log_by_retell_id(db, retell_call_id)
    if call_log is None:
        call_log = CallLog(retell_call_id=retell_call_id, caller_number=caller_number, started_at=started_at)
        db.add(call_log)
    else:
        call_log.caller_number = caller_number or call_log.caller_number
        call_log.started_at = started_at or call_log.started_at
    db.commit()
    db.refresh(call_log)
    return call_log


def update_call_log_ended(
    db: Session, call_log: CallLog, *, ended_at: datetime | None, transcript_text: str | None
) -> CallLog:
    call_log.ended_at = ended_at
    if transcript_text:
        _upsert_transcript(db, call_log, text=transcript_text)
    db.commit()
    db.refresh(call_log)
    return call_log


def _upsert_transcript(db: Session, call_log: CallLog, *, text: str, analysis_json: str | None = None) -> Transcript:
    transcript = db.query(Transcript).filter_by(call_log_id=call_log.id).one_or_none()
    if transcript is None:
        transcript = Transcript(call_log_id=call_log.id, text=text, analysis_json=analysis_json)
        db.add(transcript)
    else:
        transcript.text = text
        if analysis_json is not None:
            transcript.analysis_json = analysis_json
    return transcript


def record_call_analysis(
    db: Session,
    call_log: CallLog,
    *,
    transcript_text: str | None,
    analysis_json: str | None,
    disposition: str | None,
    urgency: str | None,
    lead_id,
) -> CallLog:
    if transcript_text is not None:
        _upsert_transcript(db, call_log, text=transcript_text, analysis_json=analysis_json)
    if disposition is not None:
        call_log.disposition = disposition
    if urgency is not None:
        call_log.urgency = urgency
    if lead_id is not None:
        call_log.lead_id = lead_id
    db.commit()
    db.refresh(call_log)
    return call_log


def mark_call_log_processed(db: Session, call_log: CallLog) -> CallLog:
    call_log.post_call_processed = True
    db.commit()
    db.refresh(call_log)
    return call_log
