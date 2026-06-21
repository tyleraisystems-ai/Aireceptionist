import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.core.retell_verify import verify_retell_signature
from app.schemas import AvailabilitySlot, CheckAvailabilityResult, RetellFunctionCall

router = APIRouter()


@router.post("/functions/check-availability")
async def check_availability(body: bytes = Depends(verify_retell_signature)) -> dict:
    """M1 stub: returns two fake upcoming slots so the flow can be wired
    end-to-end through Retell before the real Google Calendar integration
    lands in M2.
    """
    RetellFunctionCall.model_validate(json.loads(body))

    now = datetime.now(timezone.utc)
    first_start = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    second_start = (now + timedelta(days=1)).replace(hour=13, minute=0, second=0, microsecond=0)

    result = CheckAvailabilityResult(
        slots=[
            AvailabilitySlot(start=first_start.isoformat(), end=(first_start + timedelta(hours=2)).isoformat()),
            AvailabilitySlot(start=second_start.isoformat(), end=(second_start + timedelta(hours=2)).isoformat()),
        ]
    )
    return {"result": result.model_dump()}
