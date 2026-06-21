import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Appointment, Lead


def create_lead(
    db: Session,
    *,
    full_name: str,
    callback_number: str,
    service_address: str,
    issue_summary: str,
    urgency: str,
    disposition: str = "NEW",
) -> Lead:
    lead = Lead(
        full_name=full_name,
        callback_number=callback_number,
        service_address=service_address,
        issue_summary=issue_summary,
        urgency=urgency,
        disposition=disposition,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def create_appointment(
    db: Session,
    *,
    lead_id: uuid.UUID,
    scheduled_start: datetime,
    scheduled_end: datetime,
    external_calendar_event_id: str | None = None,
) -> Appointment:
    appointment = Appointment(
        lead_id=lead_id,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        external_calendar_event_id=external_calendar_event_id,
        status="BOOKED",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    return appointment


def get_active_appointment_by_phone(db: Session, callback_number: str) -> Appointment | None:
    stmt = (
        select(Appointment)
        .join(Lead)
        .where(Lead.callback_number == callback_number, Appointment.status == "BOOKED")
        .order_by(Appointment.scheduled_start.desc())
    )
    return db.execute(stmt).scalars().first()


def get_appointment(db: Session, appointment_id: uuid.UUID) -> Appointment | None:
    return db.get(Appointment, appointment_id)


def update_appointment_schedule(
    db: Session, appointment: Appointment, *, scheduled_start: datetime, scheduled_end: datetime
) -> Appointment:
    appointment.scheduled_start = scheduled_start
    appointment.scheduled_end = scheduled_end
    appointment.status = "RESCHEDULED"
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, appointment: Appointment) -> Appointment:
    appointment.status = "CANCELLED"
    db.commit()
    db.refresh(appointment)
    return appointment


def update_lead_disposition(db: Session, lead: Lead, *, disposition: str, urgency: str | None = None) -> Lead:
    lead.disposition = disposition
    if urgency is not None:
        lead.urgency = urgency
    db.commit()
    db.refresh(lead)
    return lead
