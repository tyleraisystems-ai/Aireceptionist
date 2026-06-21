import httpx

from ..config import settings
from ..interfaces.email_verifier import EmailVerificationResult, EmailVerifier
from ..models import EmailStatus

_VALID_STATUSES = {"valid"}
_RISKY_STATUSES = {"catch-all", "unknown", "spamtrap", "abuse"}
_INVALID_STATUSES = {"invalid", "do_not_mail"}


class ZeroBounceVerifier(EmailVerifier):
    """Default EmailVerifier, using ZeroBounce's single-email validate endpoint.
    Wired up but not yet exercised end-to-end -- that happens in Phase 3
    alongside enrichment.
    """

    BASE_URL = "https://api.zerobounce.net/v2/validate"

    def __init__(self) -> None:
        self._api_key = settings.zerobounce_api_key

    def verify(self, email: str) -> EmailVerificationResult:
        response = httpx.get(
            self.BASE_URL,
            params={"api_key": self._api_key, "email": email},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        zb_status = data.get("status", "unknown")
        sub_status = data.get("sub_status", "")

        if zb_status in _VALID_STATUSES:
            status = EmailStatus.VALID
        elif zb_status in _INVALID_STATUSES:
            status = EmailStatus.INVALID
        else:
            status = EmailStatus.RISKY

        return EmailVerificationResult(
            email=email,
            status=status,
            is_disposable=sub_status == "disposable",
            is_catch_all=zb_status == "catch-all",
            raw_response=data,
        )
