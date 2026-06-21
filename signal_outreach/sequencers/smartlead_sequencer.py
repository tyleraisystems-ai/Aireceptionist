from typing import Any, Optional

from ..config import settings
from ..interfaces.sequencer import NormalizedEvent, Sequencer


class SmartleadSequencer(Sequencer):
    """Default Sequencer. NOT YET IMPLEMENTED -- built out in Phase 6.

    Needs from you before then: confirmation of Smartlead's campaign-create,
    lead-upload, and webhook payload field names against their current API
    docs/version (these change between API versions and I don't want to
    guess them). Also: which custom-variable names you want the personalized
    subject/body/footer fields mapped to in the Smartlead UI.
    """

    def __init__(self) -> None:
        self._api_key = settings.smartlead_api_key

    def create_or_update_campaign(self, name: str, daily_cap: int, sending_domains: list[str]) -> str:
        raise NotImplementedError("SmartleadSequencer.create_or_update_campaign: implement in Phase 6")

    def upload_leads(self, campaign_id: str, leads: list[dict]) -> Any:
        raise NotImplementedError("SmartleadSequencer.upload_leads: implement in Phase 6")

    def pause_campaign(self, campaign_id: str) -> None:
        raise NotImplementedError("SmartleadSequencer.pause_campaign: implement in Phase 6")

    def parse_webhook_event(self, payload: dict) -> Optional[NormalizedEvent]:
        raise NotImplementedError("SmartleadSequencer.parse_webhook_event: implement in Phase 6")
