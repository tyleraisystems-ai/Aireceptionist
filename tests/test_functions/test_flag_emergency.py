from app.db.models import Lead
from tests.test_functions.helpers import call_envelope, post_signed


def _args():
    return {
        "full_name": "Pat Kim",
        "callback_number": "+15555550122",
        "service_address": "22 Birch St",
        "issue_summary": "No heat, it's freezing inside",
        "reason": "Fully down system in cold weather",
    }


def test_happy_path_creates_urgent_lead(client, sign_body, db_session, retell_call_id):
    resp = post_signed(client, sign_body, "/functions/flag-emergency", call_envelope(retell_call_id, "flag_emergency", _args()))
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["disposition"] == "EMERGENCY_FLAGGED"

    lead = db_session.query(Lead).one()
    assert lead.urgency == "URGENT"
    assert lead.disposition == "EMERGENCY_FLAGGED"


def test_idempotent_double_call(client, sign_body, db_session, retell_call_id):
    envelope = call_envelope(retell_call_id, "flag_emergency", _args())
    resp1 = post_signed(client, sign_body, "/functions/flag-emergency", envelope)
    resp2 = post_signed(client, sign_body, "/functions/flag-emergency", envelope)

    assert resp1.json() == resp2.json()
    assert db_session.query(Lead).count() == 1


def test_bad_signature_returns_401(client):
    resp = client.post(
        "/functions/flag-emergency",
        data=b'{"args": {}}',
        headers={"X-Retell-Signature": "v=1,d=bad"},
    )
    assert resp.status_code == 401
