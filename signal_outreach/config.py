from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    anthropic_api_key: str = ""
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    anthropic_model_strong: str = "claude-sonnet-4-6"

    # Prospect sourcing
    apify_api_token: str = ""

    # Email verification
    zerobounce_api_key: str = ""

    # Sequencer
    smartlead_api_key: str = ""
    instantly_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./signal_outreach.db"

    # Pipeline defaults
    default_geo: str = "Portland, OR"
    default_vertical: str = "HVAC"
    pain_score_threshold: int = 55

    # Compliance / sending caps
    daily_cap_per_inbox: int = 30
    spam_rate_pause_threshold: float = 0.001
    bounce_rate_pause_threshold: float = 0.03

    # CAN-SPAM footer (placeholders until filled before Phase 6)
    footer_mailing_address: str = "<<FILL: your physical mailing address>>"
    sending_domains: str = "<<FILL: comma-separated dedicated sending domains>>"


settings = Settings()
