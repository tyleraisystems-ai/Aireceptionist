import uuid
from datetime import datetime, timedelta, timezone

from app.db.models import Appointment
from tests.test_functions.helpers import call_envelope, post_signed


def _book(client, sign_body, call_id, phone="+15555550199"):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=2)
    args = {
        "full_name": "John Roe",
        "callback_number": phone,
        "service_address": "456 Oak Ave",
        "issue_summary": "AC blowing warm air",
        "urgency": "ROUTINE",
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    resp = post_signed(client, sign_body, "/functions/book-visit", call_envelope(call_id, "book_visit", args))
    return resp.json()["result"]


def test_cancel_by_appointment_id_marks_cancelled_and_removes_event(client, sign_body, fake_calendar, db_session, retell_call_id):
    booked = _book(client, sign_body, retell_call_id + "-book")
    event_id_before = list(fake_calendar.events.keys())[0]

    args = {"callback_number": "+15555550199", "appointment_id": booked["appointment_id"]}
    resp = post_signed(
        client, sign_body, "/functions/cancel-visit",
        call_envelope(retell_call_id + "-cancel", "cancel_visit", args),
    )

    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["status"] == "CANCELLED"
    assert event_id_before not in fake_calendar.events

    appointment = db_session.get(Appointment, uuid.UUID(booked["appointment_id"]))
    assert appointment.status == "CANCELLED"


def test_cancel_unknown_phone_returns_404(client, sign_body, retell_call_id):
    args = {"callback_number": "+10000000000"}
    resp = post_signed(client, sign_body, "/functions/cancel-visit", call_envelope(retell_call_id, "cancel_visit", args))
    assert resp.status_code == 404


def test_idempotent_double_cancel(client, sign_body, retell_call_id):
    booked = _book(client, sign_body, retell_call_id + "-book")
    args = {"callback_number": "+15555550199", "appointment_id": booked["appointment_id"]}
    envelope = call_envelope(retell_call_id + "-cancel", "cancel_visit", args)

    resp1 = post_signed(client, sign_body, "/functions/cancel-visit", envelope)
    resp2 = post_signed(client, sign_body, "/functions/cancel-visit", envelope)

    assert resp1.status_code == resp2.status_code == 200
    assert resp1.json() == resp2.json()
