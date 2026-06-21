import uuid
from datetime import datetime, timedelta, timezone

from app.db.models import Appointment, Lead
from tests.test_functions.helpers import call_envelope, post_signed


def _args():
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)
    return {
        "full_name": "Jane Doe",
        "callback_number": "+15555550123",
        "service_address": "123 Main St",
        "issue_summary": "Furnace won't turn on",
        "urgency": "ROUTINE",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


def test_happy_path_creates_lead_appointment_and_calendar_event(client, sign_body, fake_calendar, db_session, retell_call_id):
    body = call_envelope(retell_call_id, "book_visit", _args())
    resp = post_signed(client, sign_body, "/functions/book-visit", body)

    assert resp.status_code == 200
    data = resp.json()["result"]
    assert "appointment_id" in data
    assert len(fake_calendar.events) == 1

    appointment = db_session.get(Appointment, uuid.UUID(data["appointment_id"]))
    assert appointment is not None
    assert appointment.status == "BOOKED"
    lead = db_session.get(Lead, appointment.lead_id)
    assert lead.full_name == "Jane Doe"


def test_bad_signature_returns_401(client):
    resp = client.post(
        "/functions/book-visit",
        data=b'{"args": {}}',
        headers={"X-Retell-Signature": "v=1,d=bad"},
    )
    assert resp.status_code == 401


def test_idempotent_double_call_does_not_duplicate(client, sign_body, fake_calendar, db_session, retell_call_id):
    body = call_envelope(retell_call_id, "book_visit", _args())

    resp1 = post_signed(client, sign_body, "/functions/book-visit", body)
    resp2 = post_signed(client, sign_body, "/functions/book-visit", body)

    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json() == resp2.json()
    assert len(fake_calendar.events) == 1
    assert db_session.query(Appointment).count() == 1
