from fastapi import HTTPException, Request
from retell.lib.webhook_auth import verify as retell_verify

from app.core.settings import get_settings


async def verify_retell_signature(request: Request) -> bytes:
    """FastAPI dependency: verifies X-Retell-Signature on the raw request body.

    Retell's signature scheme verifies against the account API key, not a
    separate webhook secret (see retell.lib.webhook_auth.verify). Raises 401
    on any missing header or failed verification.
    """
    settings = get_settings()
    signature = request.headers.get("X-Retell-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Retell-Signature header")

    body = await request.body()
    valid = retell_verify(body.decode("utf-8"), settings.retell_api_key, signature)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid Retell signature")

    return body
