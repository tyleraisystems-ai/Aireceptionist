import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class FunctionCallLog(Base):
    """Idempotency cache: dedupes Retell's retries (up to 2x) of the same
    Custom Function call within the same conversation turn, keyed on the
    Retell call_id + function name. The cached result is replayed verbatim
    instead of re-running the side effect (booking, lead capture, etc.).
    """

    __tablename__ = "function_call_logs"
    __table_args__ = (UniqueConstraint("call_id", "function_name", name="uq_call_id_function_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id: Mapped[str] = mapped_column(String(255))
    function_name: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(255))
    callback_number: Mapped[str] = mapped_column(String(32))
    service_address: Mapped[str] = mapped_column(Text)
    issue_summary: Mapped[str] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String(16))  # URGENT | ROUTINE
    disposition: Mapped[str] = mapped_column(String(32), default="NEW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="lead")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("leads.id"))
    external_calendar_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="BOOKED")  # BOOKED | RESCHEDULED | CANCELLED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    lead: Mapped["Lead"] = relationship(back_populates="appointments")


class CallLog(Base):
    __tablename__ = "call_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    retell_call_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    caller_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("leads.id"), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transcript: Mapped["Transcript"] = relationship(back_populates="call_log", uselist=False)


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_log_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("call_logs.id"), unique=True)
    text: Mapped[str] = mapped_column(Text)
    analysis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    call_log: Mapped["CallLog"] = relationship(back_populates="transcript")
