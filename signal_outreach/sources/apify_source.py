from typing import Iterable

from ..config import settings
from ..interfaces.prospect_source import ProspectSource


class ApifyProspectSource(ProspectSource):
    """Default ProspectSource backed by Apify's Google Maps Scraper actor.

    NOT YET IMPLEMENTED -- built out in Phase 1. Needs from you:
      - the exact Apify actor id (e.g. "compass/google-maps-scraper" or similar)
      - confirmation of the actor's input schema (search query format, field names
        in its output it gives for hours/rating/reviewsCount/placeId)
    Flagging rather than guessing actor ids/schemas per your instruction.
    """

    def __init__(self) -> None:
        self._api_token = settings.apify_api_token

    def search(self, vertical: str, geo: str, limit: int = 100) -> Iterable[dict]:
        raise NotImplementedError("ApifyProspectSource.search: implement in Phase 1")
