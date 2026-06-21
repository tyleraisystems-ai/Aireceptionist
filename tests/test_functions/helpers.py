import json


def post_signed(client, sign_body, path: str, body: dict):
    raw = json.dumps(body).encode("utf-8")
    signature = sign_body(raw)
    return client.post(
        path,
        data=raw,
        headers={"X-Retell-Signature": signature, "Content-Type": "application/json"},
    )


def call_envelope(call_id: str, name: str, args: dict) -> dict:
    return {"call": {"call_id": call_id}, "name": name, "args": args}
