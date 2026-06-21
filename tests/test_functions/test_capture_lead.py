from app.db.models import Lead
from tests.test_functions.helpers import call_envelope, post_signed


def _args():
    return {
        "full_name": "Sam Lee",
        "callback_number": "+15555550111",
        "service_address": "789 Pine Rd",
        "issue_summary": "AC making a rattling noise",
        "urgency": "ROUTINE",
    }


def test_happy_path_creates_lead(client, sign_body, db_session, retell_call_id):
    resp = post_signed(client, sign_body, "/functions/capture-lead", call_envelope(retell_call_id, "capture_lead", _args()))
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert "lead_id" in data
    assert db_session.query(Lead).count() == 1


def test_idempotent_double_call_creates_one_lead(client, sign_body, db_session, retell_call_id):
    envelope = call_envelope(retell_call_id, "capture_lead", _args())
    resp1 = post_signed(client, sign_body, "/functions/capture-lead", envelope)
    resp2 = post_signed(client, sign_body, "/functions/capture-lead", envelope)

    assert resp1.json() == resp2.json()
    assert db_session.query(Lead).count() == 1


def test_bad_signature_returns_401(client):
    resp = client.post(
        "/functions/capture-lead",
        data=b'{"args": {}}',
        headers={"X-Retell-Signature": "v=1,d=bad"},
    )
    assert resp.status_code == 401
