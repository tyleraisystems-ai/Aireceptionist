from typing import Any, Optional

from ..config import settings
from ..interfaces.sequencer import NormalizedEvent, Sequencer


class InstantlySequencer(Sequencer):
    """Stub alternate Sequencer backend (Instantly). Not wired up by default;
    same Phase 6 caveat as Smartlead applies -- confirm API field names
    before implementing.
    """

    def __init__(self) -> None:
        self._api_key = settings.instantly_api_key

    def create_or_update_campaign(self, name: str, daily_cap: int, sending_domains: list[str]) -> str:
        raise NotImplementedError("InstantlySequencer.create_or_update_campaign: implement in Phase 6")

    def upload_leads(self, campaign_id: str, leads: list[dict]) -> Any:
        raise NotImplementedError("InstantlySequencer.upload_leads: implement in Phase 6")

    def pause_campaign(self, campaign_id: str) -> None:
        raise NotImplementedError("InstantlySequencer.pause_campaign: implement in Phase 6")

    def parse_webhook_event(self, payload: dict) -> Optional[NormalizedEvent]:
        raise NotImplementedError("InstantlySequencer.parse_webhook_event: implement in Phase 6")
