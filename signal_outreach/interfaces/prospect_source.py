from abc import ABC, abstractmethod
from typing import Iterable


class ProspectSource(ABC):
    """Sources raw prospect records for a vertical + geo.

    Implementations return plain dicts (not ORM rows) so the sourcing
    stage can map fields, dedupe, and upsert into Lead independently
    of where the data came from.
    """

    @abstractmethod
    def search(self, vertical: str, geo: str, limit: int = 100) -> Iterable[dict]:
        """Yield dicts with keys: business_name, category, address, city,
        region, country, phone, website, place_id, rating, reviews_count,
        hours_json, lat, lng, source, source_url.
        """
        raise NotImplementedError
