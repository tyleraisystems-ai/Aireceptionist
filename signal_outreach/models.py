from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LeadStatus(StrEnum):
    SOURCED = "sourced"
    QUALIFIED = "qualified"
    ENRICHED = "enriched"
    DRAFTED = "drafted"
    APPROVED = "approved"
    QUEUED = "queued"
    SENT = "sent"
    REPLIED = "replied"
    BOUNCED = "bounced"
    SUPPRESSED = "suppressed"
    REJECTED = "rejected"


class EmailStatus(StrEnum):
    UNVERIFIED = "unverified"
    VALID = "valid"
    RISKY = "risky"
    INVALID = "invalid"


class MessageStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    EDITED = "edited"
    QUEUED = "queued"
    SENT = "sent"


class EventType(StrEnum):
    OPEN = "open"
    REPLY = "reply"
    BOUNCE = "bounce"
    UNSUBSCRIBE = "unsubscribe"
    SPAM_COMPLAINT = "spam_complaint"


class StatusHistoryEntry(SQLModel):
    """Single timestamped status transition, stored inside Lead.status_history_json."""

    status: str
    changed_at: str


class Lead(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    business_name: str
    category: Optional[str] = None
    vertical: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = Field(default=None, index=True)
    website: Optional[str] = None
    domain: Optional[str] = Field(default=None, index=True)
    place_id: Optional[str] = Field(default=None, index=True)
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    hours_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    source: Optional[str] = None
    source_url: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

    status: LeadStatus = Field(default=LeadStatus.SOURCED, index=True)
    status_history_json: list = Field(default_factory=list, sa_column=Column(JSON))

    pain_score: Optional[int] = None
    pain_evidence_json: Optional[list] = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=utcnow)


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="lead.id", index=True)

    full_name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = Field(default=None, index=True)
    email_status: EmailStatus = Field(default=EmailStatus.UNVERIFIED)
    phone: Optional[str] = None
    source: Optional[str] = None
    verified_at: Optional[datetime] = None


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="lead.id", index=True)
    contact_id: Optional[int] = Field(default=None, foreign_key="contact.id")

    step: int  # 1 = intro, 2/3 = follow-ups
    subject: Optional[str] = None
    body: str
    edited_body: Optional[str] = None
    model_used: Optional[str] = None
    status: MessageStatus = Field(default=MessageStatus.DRAFT)
    approved_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)


class Campaign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    vertical: Optional[str] = None
    geo: Optional[str] = None
    sequencer_campaign_id: Optional[str] = None
    status: Optional[str] = "draft"
    daily_cap: int = 30
    sending_domains_json: Optional[list] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Event(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="lead.id", index=True)
    type: EventType
    payload_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    received_at: datetime = Field(default_factory=utcnow)


class Suppression(SQLModel, table=True):
    email: str = Field(primary_key=True)
    reason: str
    created_at: datetime = Field(default_factory=utcnow)
