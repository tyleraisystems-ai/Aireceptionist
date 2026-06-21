from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.idempotency import cache_result, get_cached_result
from app.core.parsing import parse_call_args, parse_call_id
from app.core.retell_verify import verify_retell_signature
from app.db import crud
from app.db.session import get_db
from app.schemas import CaptureLeadArgs, CaptureLeadResult

router = APIRouter()

FUNCTION_NAME = "capture_lead"


@router.post("/functions/capture-lead")
async def capture_lead(
    body: bytes = Depends(verify_retell_signature),
    db: Session = Depends(get_db),
) -> dict:
    call_id = parse_call_id(body)
    if call_id:
        cached = get_cached_result(db, call_id=call_id, function_name=FUNCTION_NAME)
        if cached is not None:
            return {"result": cached}

    args = parse_call_args(body, CaptureLeadArgs)

    lead = crud.create_lead(
        db,
        full_name=args.full_name,
        callback_number=args.callback_number,
        service_address=args.service_address,
        issue_summary=args.issue_summary,
        urgency=args.urgency,
        disposition="LEAD_CAPTURED",
    )

    result = CaptureLeadResult(lead_id=str(lead.id))
    result_dict = result.model_dump()
    if call_id:
        cache_result(db, call_id=call_id, function_name=FUNCTION_NAME, result=result_dict)
    return {"result": result_dict}
