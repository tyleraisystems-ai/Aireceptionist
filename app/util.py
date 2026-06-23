import hashlib
import json
import logging
from datetime import datetime

from fastapi import HTTPException

logger = logging.getLogger("retell.functions")

RESULT_CHAR_CAP = 15_000


def slot_hash(start: datetime, end: datetime) -> str:
    raw = f"{start.isoformat()}|{end.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def parse_function_call(body: bytes) -> tuple[str, dict]:
    """Extract (call_id, args) from a Retell custom-function webhook body.

    Handles both documented payload shapes defensively: the full envelope
    `{"call": {"call_id": ...}, "name": ..., "args": {...}}` and the
    "args only" mode where parameters sit at the top level alongside the
    call_id. Confirm the live shape against the dashboard in Phase 4.
    """
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

    call = payload.get("call") or {}
    call_id = call.get("call_id") or payload.get("call_id")
    if not call_id:
        raise HTTPException(status_code=400, detail="Missing call_id in function-call payload")

    args = payload.get("args")
    if args is None:
        reserved = {"call", "name", "call_id"}
        args = {k: v for k, v in payload.items() if k not in reserved}
    return call_id, args


def respond(result: dict) -> dict:
    payload = {"result": result}
    if len(json.dumps(payload)) > RESULT_CHAR_CAP:
        logger.warning("Function result exceeded %s char cap; truncating", RESULT_CHAR_CAP)
        payload = {"result": {"error": "result_too_large"}}
    return payload
