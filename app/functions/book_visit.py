from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.idempotency import cache_result, get_cached_result
from app.core.parsing import parse_call_args, parse_call_id
from app.core.retell_verify import verify_retell_signature
from app.db import crud
from app.db.session import get_db
from app.integrations.google_calendar import GoogleCalendarClient, get_calendar_client
from app.schemas import BookVisitArgs, BookVisitResult

router = APIRouter()

FUNCTION_NAME = "book_visit"


@router.post("/functions/book-visit")
async def book_visit(
    body: bytes = Depends(verify_retell_signature),
    db: Session = Depends(get_db),
    calendar: GoogleCalendarClient = Depends(get_calendar_client),
) -> dict:
    call_id = parse_call_id(body)
    if call_id:
        cached = get_cached_result(db, call_id=call_id, function_name=FUNCTION_NAME)
        if cached is not None:
            return {"result": cached}

    args = parse_call_args(body, BookVisitArgs)

    start = datetime.fromisoformat(args.start)
    end = datetime.fromisoformat(args.end)

    lead = crud.create_lead(
        db,
        full_name=args.full_name,
        callback_number=args.callback_number,
        service_address=args.service_address,
        issue_summary=args.issue_summary,
        urgency=args.urgency,
        disposition="BOOKED",
    )

    event_id = calendar.create_event(
        summary=f"HVAC visit: {args.full_name}",
        description=f"{args.issue_summary}\nAddress: {args.service_address}\nPhone: {args.callback_number}",
        start=start,
        end=end,
    )

    appointment = crud.create_appointment(
        db,
        lead_id=lead.id,
        scheduled_start=start,
        scheduled_end=end,
        external_calendar_event_id=event_id,
    )

    result = BookVisitResult(
        appointment_id=str(appointment.id),
        confirmed_start=appointment.scheduled_start.isoformat(),
        confirmed_end=appointment.scheduled_end.isoformat(),
    )
    result_dict = result.model_dump()
    if call_id:
        cache_result(db, call_id=call_id, function_name=FUNCTION_NAME, result=result_dict)
    return {"result": result_dict}
