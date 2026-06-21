from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    retell_api_key: str = ""

    database_url: str = "postgresql+psycopg://aireceptionist:aireceptionist@localhost:5432/aireceptionist"

    google_calendar_credentials_json: str = ""
    google_calendar_id: str = ""

    jobber_client_id: str = ""
    jobber_client_secret: str = ""
    jobber_refresh_token: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    environment: str = "development"

    business_config_path: Path = Path("config/business.yaml")


@lru_cache
def get_settings() -> Settings:
    return Settings()
