from abc import ABC, abstractmethod
from typing import Literal

ModelTier = Literal["fast", "strong"]


class LLMClient(ABC):
    """Wraps the LLM provider. tier='fast' is used for high-volume passes
    (qualification); tier='strong' for final personalization drafting.
    Model names are centralized in config so they can be swapped."""

    @abstractmethod
    def complete(self, system: str, user: str, tier: ModelTier = "fast", max_tokens: int = 1024) -> str:
        raise NotImplementedError
