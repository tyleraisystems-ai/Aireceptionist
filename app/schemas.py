from pydantic import BaseModel


class RetellFunctionCall(BaseModel):
    """Common envelope Retell sends to a Custom Function webhook.

    Retell's exact payload nests call args under `args` alongside call
    metadata; we keep this loose (extra="allow" via model default) since the
    args shape differs per function and is parsed by each endpoint.
    """

    call: dict | None = None
    name: str | None = None
    args: dict = {}


class CheckAvailabilityArgs(BaseModel):
    preferred_window: str | None = None  # e.g. "this week", "tomorrow morning"


class AvailabilitySlot(BaseModel):
    start: str  # ISO 8601
    end: str  # ISO 8601


class CheckAvailabilityResult(BaseModel):
    slots: list[AvailabilitySlot]
