from anthropic import Anthropic

from ..config import settings
from ..interfaces.llm_client import LLMClient, ModelTier


class AnthropicLLMClient(LLMClient):
    def __init__(self) -> None:
        self._client = Anthropic(api_key=settings.anthropic_api_key)

    def complete(self, system: str, user: str, tier: ModelTier = "fast", max_tokens: int = 1024) -> str:
        model = settings.anthropic_model_fast if tier == "fast" else settings.anthropic_model_strong
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text
