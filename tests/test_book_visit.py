from datetime import datetime, timedelta, timezone

from app.db import get_sessionmaker
from app.models import Appointment
from tests.test_signature import post_function


def _slot(days_ahead: int = 1):
    start = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).replace(
        minute=0, second=0, microsecond=0
    )
    end = start + timedelta(hours=2)
    return start, end


def _book_args(start, end, **overrides):
    args = {
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "customer_name": "Jane Doe",
        "phone": "+15555550100",
        "address": "123 Main St",
        "issue_description": "AC not cooling",
    }
    args.update(overrides)
    return args


def test_book_visit_retry_same_call_id_is_idempotent(client):
    start, end = _slot()
    args = _book_args(start, end)

    r1 = post_function(client, "/retell/functions/book_visit", "call-abc", args)
    assert r1.status_code == 200
    result1 = r1.json()["result"]
    assert result1["booked"] is True

    # Simulate a Retell webhook retry: identical call_id + identical slot.
    r2 = post_function(client, "/retell/functions/book_visit", "call-abc", args)
    assert r2.status_code == 200
    result2 = r2.json()["result"]
    assert result2 == result1

    db = get_sessionmaker()()
    try:
        count = db.query(Appointment).filter(Appointment.call_id == "call-abc").count()
    finally:
        db.close()
    assert count == 1, "retry must not create a second appointment row"


def test_book_visit_conflict_across_different_calls(client):
    start, end = _slot(days_ahead=2)
    args = _book_args(start, end)

    r1 = post_function(client, "/retell/functions/book_visit", "call-first", args)
    assert r1.json()["result"]["booked"] is True

    r2 = post_function(client, "/retell/functions/book_visit", "call-second", args)
    result2 = r2.json()["result"]
    assert result2["booked"] is False
    assert result2["reason"] == "slot_unavailable"


def test_cancel_then_rebook_same_slot_succeeds(client):
    start, end = _slot(days_ahead=3)
    args = _book_args(start, end)

    r1 = post_function(client, "/retell/functions/book_visit", "call-cancel-flow", args)
    appointment_id = r1.json()["result"]["appointment_id"]

    r2 = post_function(
        client, "/retell/functions/cancel_visit", "call-cancel-flow", {"appointment_id": appointment_id}
    )
    assert r2.json()["result"]["cancelled"] is True

    r3 = post_function(client, "/retell/functions/book_visit", "call-rebook", args)
    assert r3.json()["result"]["booked"] is True
