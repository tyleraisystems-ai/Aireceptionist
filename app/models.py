import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class IdempotencyKey(Base):
    """Generic cache of (function_call, args) -> result, so a retried or
    redelivered Retell request never re-runs a side effect."""

    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        # The DB-level guarantee behind the "same call_id+slot twice -> one
        # booking" requirement: a duplicate insert fails fast and the caller
        # falls back to the cached IdempotencyKey result.
        UniqueConstraint("call_id", "slot_hash", name="uq_appointment_call_slot"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    call_id: Mapped[str] = mapped_column(String, index=True)
    slot_hash: Mapped[str] = mapped_column(String, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    customer_name: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String)
    issue_description: Mapped[str] = mapped_column(Text, default="")
    # booked | cancelled
    status: Mapped[str] = mapped_column(String, default="booked")
    google_calendar_event_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint("call_id", name="uq_lead_call_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    call_id: Mapped[str] = mapped_column(String, index=True)
    customer_name: Mapped[str] = mapped_column(String)
    phone: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String, default="")
    issue_description: Mapped[str] = mapped_column(Text, default="")
    urgency: Mapped[str] = mapped_column(String, default="routine")  # routine | urgent
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmergencyFlag(Base):
    __tablename__ = "emergency_flags"
    __table_args__ = (UniqueConstraint("call_id", name="uq_emergency_call_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    call_id: Mapped[str] = mapped_column(String, index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    callback_number: Mapped[str] = mapped_column(String, default="")
    acknowledged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
