from fastapi import APIRouter, Depends

from app.core.business_config import get_business_config
from app.core.parsing import parse_call_args
from app.core.retell_verify import verify_retell_signature
from app.schemas import TransferToHumanArgs, TransferToHumanResult

router = APIRouter()


@router.post("/functions/transfer-to-human")
async def transfer_to_human(body: bytes = Depends(verify_retell_signature)) -> dict:
    parse_call_args(body, TransferToHumanArgs)

    transfer_to = get_business_config()["on_call_transfer_number"]
    result = TransferToHumanResult(transfer_to=transfer_to)
    return {"result": result.model_dump()}
