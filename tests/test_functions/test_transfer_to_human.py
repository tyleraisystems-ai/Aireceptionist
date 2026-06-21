from tests.test_functions.helpers import call_envelope, post_signed


def test_happy_path_returns_configured_transfer_number(client, sign_body, retell_call_id):
    args = {"caller_number": "+15555550100", "reason": "Caller upset"}
    resp = post_signed(client, sign_body, "/functions/transfer-to-human", call_envelope(retell_call_id, "transfer_to_human", args))
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["transfer_to"] == "+15555550100"


def test_bad_signature_returns_401(client):
    resp = client.post(
        "/functions/transfer-to-human",
        data=b'{"args": {}}',
        headers={"X-Retell-Signature": "v=1,d=bad"},
    )
    assert resp.status_code == 401
