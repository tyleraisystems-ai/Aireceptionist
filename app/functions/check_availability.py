from fastapi import APIRouter, Depends

from app.core.business_config import get_business_config
from app.core.parsing import parse_call_args
from app.core.retell_verify import verify_retell_signature
from app.integrations.google_calendar import GoogleCalendarClient, get_calendar_client
from app.schemas import AvailabilitySlot, CheckAvailabilityArgs, CheckAvailabilityResult

router = APIRouter()


@router.post("/functions/check-availability")
async def check_availability(
    body: bytes = Depends(verify_retell_signature),
    calendar: GoogleCalendarClient = Depends(get_calendar_client),
) -> dict:
    parse_call_args(body, CheckAvailabilityArgs)

    business_hours = get_business_config()["hours"]
    slots = calendar.find_open_slots(business_hours=business_hours, max_results=2)

    result = CheckAvailabilityResult(
        slots=[AvailabilitySlot(start=s.isoformat(), end=e.isoformat()) for s, e in slots]
    )
    return {"result": result.model_dump()}
