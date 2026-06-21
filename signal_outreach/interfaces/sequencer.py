from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class NormalizedEvent:
    """A sequencer webhook event normalized to our Event.type vocabulary
    (open/reply/bounce/unsubscribe/spam_complaint)."""

    lead_external_id: str
    type: str
    payload: dict[str, Any]


class Sequencer(ABC):
    """Pluggable warmed-sequencer backend (Smartlead, Instantly, ...).

    The app never sends raw email itself -- this interface is the only
    path approved messages take to reach an inbox.
    """

    @abstractmethod
    def create_or_update_campaign(
        self, name: str, daily_cap: int, sending_domains: list[str]
    ) -> str:
        """Returns the sequencer's campaign id."""
        raise NotImplementedError

    @abstractmethod
    def upload_leads(self, campaign_id: str, leads: list[dict]) -> Any:
        """leads: dicts with contact email + custom variables for the
        personalized copy (subject/body per step) + required compliance
        fields (unsubscribe + footer address)."""
        raise NotImplementedError

    @abstractmethod
    def pause_campaign(self, campaign_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def parse_webhook_event(self, payload: dict) -> Optional[NormalizedEvent]:
        raise NotImplementedError
