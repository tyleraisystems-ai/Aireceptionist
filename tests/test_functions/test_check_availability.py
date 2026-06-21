import json


def _post(client, sign_body, body: dict):
    raw = json.dumps(body).encode("utf-8")
    signature = sign_body(raw)
    return client.post(
        "/functions/check-availability",
        data=raw,
        headers={"X-Retell-Signature": signature, "Content-Type": "application/json"},
    )


def test_happy_path_returns_two_slots(client, sign_body):
    resp = _post(client, sign_body, {"name": "check_availability", "args": {}})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["result"]["slots"]) == 2


def test_bad_signature_returns_401(client):
    raw = json.dumps({"name": "check_availability", "args": {}}).encode("utf-8")
    resp = client.post(
        "/functions/check-availability",
        data=raw,
        headers={"X-Retell-Signature": "v=1,d=bogus", "Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_missing_signature_returns_401(client):
    raw = json.dumps({"name": "check_availability", "args": {}}).encode("utf-8")
    resp = client.post("/functions/check-availability", data=raw)
    assert resp.status_code == 401


def test_idempotent_double_call_returns_consistent_shape(client, sign_body):
    resp1 = _post(client, sign_body, {"name": "check_availability", "args": {}})
    resp2 = _post(client, sign_body, {"name": "check_availability", "args": {}})
    assert resp1.status_code == resp2.status_code == 200
    assert set(resp1.json()["result"].keys()) == set(resp2.json()["result"].keys())
