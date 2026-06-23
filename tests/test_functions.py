from datetime import datetime, timedelta, timezone

from tests.test_signature import post_function


def test_check_availability_returns_two_windows(client):
    resp = post_function(client, "/retell/functions/check_availability", "call-avail", {})
    assert resp.status_code == 200
    windows = resp.json()["result"]["available_windows"]
    assert len(windows) == 2


def test_reschedule_visit_no_existing_appointment_degrades_gracefully(client):
    resp = post_function(
        client,
        "/retell/functions/reschedule_visit",
        "call-no-appt",
        {
            "new_start_time": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
            "new_end_time": (datetime.now(timezone.utc) + timedelta(days=5, hours=2)).isoformat(),
        },
    )
    assert resp.status_code == 200
    assert resp.json()["result"] == {"rescheduled": False, "reason": "no_existing_appointment"}


def test_capture_lead_idempotent_on_call_id(client):
    args = {"customer_name": "Bob", "phone": "+15555550199", "urgency": "urgent"}
    r1 = post_function(client, "/retell/functions/capture_lead", "call-lead-1", args)
    r2 = post_function(client, "/retell/functions/capture_lead", "call-lead-1", args)
    assert r1.json()["result"] == r2.json()["result"]


def test_flag_emergency_idempotent_on_call_id(client):
    args = {"reason": "smells like gas", "callback_number": "+15555550111"}
    r1 = post_function(client, "/retell/functions/flag_emergency", "call-emg-1", args)
    r2 = post_function(client, "/retell/functions/flag_emergency", "call-emg-1", args)
    assert r1.json()["result"] == r2.json()["result"]


def test_transfer_to_human_reports_unconfigured_destination(client):
    resp = post_function(client, "/retell/functions/transfer_to_human", "call-xfer-1", {"reason": "upset"})
    assert resp.status_code == 200
    assert resp.json()["result"]["transferred"] is False
    assert resp.json()["result"]["reason"] == "destination_not_configured"
