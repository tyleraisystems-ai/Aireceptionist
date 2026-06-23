from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    retell_api_key: str
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/aireceptionist"

    # TODO(intake) placeholders — client-specific, never fabricate real values.
    business_legal_name: str = "TODO(intake: business_identity.legal_name)"
    business_service_area: str = "TODO(intake: business_identity.service_area)"
    business_hours: str = "TODO(intake: business_identity.hours)"
    business_after_hours_policy: str = "TODO(intake: business_identity.after_hours_policy)"
    greeting_wording: str = "TODO(intake: greeting_wording)"
    human_transfer_destination: str = "TODO(intake: human_transfer_destination)"
    sms_sender_number: str = "TODO(intake: sms_sender)"
    sms_confirmation_copy: str = "TODO(intake: confirmation_copy)"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def is_unresolved(value: str) -> bool:
    """True if a config value is still a TODO(intake) placeholder."""
    return value.startswith("TODO(intake")
