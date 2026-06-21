from datetime import datetime, timedelta, timezone

from app.db.models import Appointment
from tests.test_functions.helpers import call_envelope, post_signed


def _book(client, sign_body, fake_calendar, call_id, phone="+15555550123"):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)
    args = {
        "full_name": "Jane Doe",
        "callback_number": phone,
        "service_address": "123 Main St",
        "issue_summary": "Furnace won't turn on",
        "urgency": "ROUTINE",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    resp = post_signed(client, sign_body, "/functions/book-visit", call_envelope(call_id, "book_visit", args))
    return resp.json()["result"]


def test_reschedule_by_phone_updates_appointment_and_calendar(client, sign_body, fake_calendar, db_session, retell_call_id):
    booked = _book(client, sign_body, fake_calendar, retell_call_id + "-book")

    new_start = datetime.now(timezone.utc) + timedelta(days=3)
    new_end = new_start + timedelta(hours=2)
    args = {"callback_number": "+15555550123", "new_start": new_start.isoformat(), "new_end": new_end.isoformat()}
    resp = post_signed(
        client, sign_body, "/functions/reschedule-visit",
        call_envelope(retell_call_id + "-reschedule", "reschedule_visit", args),
    )

    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["appointment_id"] == booked["appointment_id"]

    import uuid

    appointment = db_session.get(Appointment, uuid.UUID(data["appointment_id"]))
    assert appointment.status == "RESCHEDULED"
    event = fake_calendar.events[appointment.external_calendar_event_id]
    assert event["start"] == new_start


def test_reschedule_unknown_phone_returns_404(client, sign_body, retell_call_id):
    args = {
        "callback_number": "+19999999999",
        "new_start": datetime.now(timezone.utc).isoformat(),
        "new_end": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    resp = post_signed(
        client, sign_body, "/functions/reschedule-visit",
        call_envelope(retell_call_id, "reschedule_visit", args),
    )
    assert resp.status_code == 404


def test_bad_signature_returns_401(client):
    resp = client.post(
        "/functions/reschedule-visit",
        data=b'{"args": {}}',
        headers={"X-Retell-Signature": "v=1,d=bad"},
    )
    assert resp.status_code == 401
