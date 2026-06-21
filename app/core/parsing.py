import json
from typing import TypeVar

from pydantic import BaseModel

from app.schemas import RetellFunctionCall

T = TypeVar("T", bound=BaseModel)


def parse_call_args(body: bytes, args_model: type[T]) -> T:
    call = RetellFunctionCall.model_validate(json.loads(body))
    return args_model.model_validate(call.args)


def parse_call_id(body: bytes) -> str | None:
    call = RetellFunctionCall.model_validate(json.loads(body))
    if call.call:
        return call.call.get("call_id")
    return None
