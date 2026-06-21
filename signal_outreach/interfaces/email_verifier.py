from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from ..models import EmailStatus


@dataclass
class EmailVerificationResult:
    email: str
    status: EmailStatus
    is_disposable: bool = False
    is_catch_all: bool = False
    raw_response: Optional[dict[str, Any]] = None


class EmailVerifier(ABC):
    """Verifies a single email address (MX + validation)."""

    @abstractmethod
    def verify(self, email: str) -> EmailVerificationResult:
        raise NotImplementedError
