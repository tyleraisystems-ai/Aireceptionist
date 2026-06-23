import hashlib
import hmac
import json
import time


def sign(body: str, secret: str = "test_secret_key") -> str:
    ts = int(time.time() * 1000)
    digest = hmac.new(secret.encode(), (body + str(ts)).encode(), hashlib.sha256).hexdigest()
    return f"v={ts},d={digest}"


def post_function(client, path: str, call_id: str, args: dict, *, signature: str | None = "use-valid"):
    body = json.dumps({"call": {"call_id": call_id}, "args": args})
    headers = {"Content-Type": "application/json"}
    if signature == "use-valid":
        headers["X-Retell-Signature"] = sign(body)
    elif signature is not None:
        headers["X-Retell-Signature"] = signature
    return client.post(path, content=body, headers=headers)


def test_missing_signature_is_rejected(client):
    resp = post_function(
        client, "/retell/functions/capture_lead", "call-1", {"customer_name": "A", "phone": "1"}, signature=None
    )
    assert resp.status_code == 401


def test_invalid_signature_is_rejected(client):
    resp = post_function(
        client,
        "/retell/functions/capture_lead",
        "call-1",
        {"customer_name": "A", "phone": "1"},
        signature="v=1,d=deadbeef",
    )
    assert resp.status_code == 401


def test_valid_signature_is_accepted(client):
    resp = post_function(
        client, "/retell/functions/capture_lead", "call-valid-sig", {"customer_name": "A", "phone": "1"}
    )
    assert resp.status_code == 200
