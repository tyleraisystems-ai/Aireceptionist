from app.db.models import CallLog, Lead
from tests.test_functions.helpers import post_signed


def _event(event: str, call_id: str, **call_overrides) -> dict:
    call = {"call_id": call_id, "from_number": "+15555550199", "to_number": "+15555550100"}
    call.update(call_overrides)
    return {"event": event, "call": call}


def test_call_started_creates_call_log(client, sign_body, db_session, retell_call_id):
    resp = post_signed(
        client,
        sign_body,
        "/webhooks/retell-post-call",
        _event("call_started", retell_call_id, start_timestamp=1_700_000_000_000),
    )
    assert resp.status_code == 200

    call_log = db_session.query(CallLog).filter_by(retell_call_id=retell_call_id).one()
    assert call_log.caller_number == "+15555550199"
    assert call_log.started_at is not None
    assert call_log.post_call_processed is False


def test_call_ended_stores_transcript(client, sign_body, db_session, retell_call_id):
    post_signed(client, sign_body, "/webhooks/retell-post-call", _event("call_started", retell_call_id))
    resp = post_signed(
        client,
        sign_body,
        "/webhooks/retell-post-call",
        _event(
            "call_ended",
            retell_call_id,
            end_timestamp=1_700_000_300_000,
            transcript="Agent: Hello. Caller: Hi, my furnace is broken.",
        ),
    )
    assert resp.status_code == 200

    call_log = db_session.query(CallLog).filter_by(retell_call_id=retell_call_id).one()
    assert call_log.ended_at is not None
    assert "furnace" in call_log.transcript.text


def test_call_analyzed_matches_lead_and_sends_sms(
    client, sign_body, db_session, retell_call_id, fake_twilio, fake_jobber
):
    lead = Lead(
        full_name="Pat Kim",
        callback_number="+15555550199",
        service_address="22 Birch St",
        issue_summary="No heat",
        urgency="URGENT",
        disposition="EMERGENCY_FLAGGED",
    )
    db_session.add(lead)
    db_session.commit()

    resp = post_signed(
        client,
        sign_body,
        "/webhooks/retell-post-call",
        _event(
            "call_analyzed",
            retell_call_id,
            transcript="Agent: Hello. Caller: My furnace is broken.",
            call_analysis={"call_summary": "Furnace outage", "user_sentiment": "Negative"},
        ),
    )
    assert resp.status_code == 200

    call_log = db_session.query(CallLog).filter_by(retell_call_id=retell_call_id).one()
    assert call_log.post_call_processed is True
    assert call_log.lead_id == lead.id
    assert call_log.urgency == "URGENT"

    # one confirmation SMS to the caller, one urgent alert SMS to on-call number
    assert len(fake_twilio.sent) == 2
    recipients = {to for to, _ in fake_twilio.sent}
    assert "+15555550199" in recipients

    assert "+15555550199" in fake_jobber.clients


def test_call_analyzed_is_idempotent(client, sign_body, db_session, retell_call_id, fake_twilio, fake_jobber):
    payload = _event(
        "call_analyzed",
        retell_call_id,
        transcript="Agent: Hello. Caller: Routine maintenance question.",
    )
    resp1 = post_signed(client, sign_body, "/webhooks/retell-post-call", payload)
    resp2 = post_signed(client, sign_body, "/webhooks/retell-post-call", payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert len(fake_twilio.sent) == 1  # not re-sent on redelivery


def test_bad_signature_returns_401(client):
    resp = client.post(
        "/webhooks/retell-post-call",
        data=b'{"event": "call_started", "call": {"call_id": "x"}}',
        headers={"X-Retell-Signature": "v=1,d=bad"},
    )
    assert resp.status_code == 401
