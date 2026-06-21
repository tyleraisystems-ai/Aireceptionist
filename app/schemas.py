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


class BookVisitArgs(BaseModel):
    full_name: str
    callback_number: str
    service_address: str
    issue_summary: str
    urgency: str  # URGENT | ROUTINE
    start: str  # ISO 8601, must match one of the slots check_availability offered
    end: str  # ISO 8601


class BookVisitResult(BaseModel):
    appointment_id: str
    confirmed_start: str
    confirmed_end: str


class RescheduleVisitArgs(BaseModel):
    callback_number: str
    appointment_id: str | None = None
    new_start: str
    new_end: str


class RescheduleVisitResult(BaseModel):
    appointment_id: str
    confirmed_start: str
    confirmed_end: str


class CancelVisitArgs(BaseModel):
    callback_number: str
    appointment_id: str | None = None


class CancelVisitResult(BaseModel):
    appointment_id: str
    status: str


class CaptureLeadArgs(BaseModel):
    full_name: str
    callback_number: str
    service_address: str
    issue_summary: str
    urgency: str  # URGENT | ROUTINE


class CaptureLeadResult(BaseModel):
    lead_id: str


class FlagEmergencyArgs(BaseModel):
    full_name: str
    callback_number: str
    service_address: str
    issue_summary: str
    reason: str


class FlagEmergencyResult(BaseModel):
    lead_id: str
    disposition: str


class TransferToHumanArgs(BaseModel):
    caller_number: str
    reason: str | None = None


class TransferToHumanResult(BaseModel):
    transfer_to: str
