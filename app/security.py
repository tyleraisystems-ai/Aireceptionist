from fastapi import Header, HTTPException, Request
from retell import Retell

from app.config import get_settings

_client: Retell | None = None


def _get_client() -> Retell:
    global _client
    if _client is None:
        _client = Retell(api_key=get_settings().retell_api_key)
    return _client


async def verify_signature(
    request: Request,
    x_retell_signature: str | None = Header(default=None),
) -> bytes:
    """FastAPI dependency: verifies X-Retell-Signature, 401 on failure.

    Returns the raw request body bytes so the route handler can parse the
    exact same byte string that was signed.
    """
    body = await request.body()
    if not x_retell_signature:
        raise HTTPException(status_code=401, detail="Missing X-Retell-Signature header")

    settings = get_settings()
    valid = _get_client().verify(
        body.decode("utf-8"),
        api_key=settings.retell_api_key,
        signature=x_retell_signature,
    )
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid Retell signature")
    return body
