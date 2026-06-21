import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.idempotency import cache_result, get_cached_result
from app.core.parsing import parse_call_args, parse_call_id
from app.core.retell_verify import verify_retell_signature
from app.db import crud
from app.db.session import get_db
from app.integrations.google_calendar import GoogleCalendarClient, get_calendar_client
from app.schemas import CancelVisitArgs, CancelVisitResult

router = APIRouter()

FUNCTION_NAME = "cancel_visit"


@router.post("/functions/cancel-visit")
async def cancel_visit(
    body: bytes = Depends(verify_retell_signature),
    db: Session = Depends(get_db),
    calendar: GoogleCalendarClient = Depends(get_calendar_client),
) -> dict:
    call_id = parse_call_id(body)
    if call_id:
        cached = get_cached_result(db, call_id=call_id, function_name=FUNCTION_NAME)
        if cached is not None:
            return {"result": cached}

    args = parse_call_args(body, CancelVisitArgs)

    appointment = None
    if args.appointment_id:
        appointment = crud.get_appointment(db, uuid.UUID(args.appointment_id))
    if appointment is None:
        appointment = crud.get_active_appointment_by_phone(db, args.callback_number)
    if appointment is None:
        raise HTTPException(status_code=404, detail="No active appointment found for that phone number")

    if appointment.external_calendar_event_id:
        calendar.delete_event(appointment.external_calendar_event_id)

    appointment = crud.cancel_appointment(db, appointment)

    result = CancelVisitResult(appointment_id=str(appointment.id), status=appointment.status)
    result_dict = result.model_dump()
    if call_id:
        cache_result(db, call_id=call_id, function_name=FUNCTION_NAME, result=result_dict)
    return {"result": result_dict}
