from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000

    xero_client_id: str = ""
    xero_client_secret: str = ""
    xero_tenant_id: str = ""
    xero_redirect_uri: str = "http://localhost:8000/auth/xero/callback"
    xero_webhook_key: str = ""

    anthropic_api_key: str = ""
    ai_default_model: str = "anthropic:claude-sonnet-4-6"
    # Model for WhatsApp turns (voice-note transcripts + text)
    voice_ai_model: str = "anthropic:claude-haiku-4-5"

    public_base_url: str = ""

    # Wassist BYOA — https://docs.wassist.app/concepts/bring-your-own-agent
    wassist_api_key: str = ""
    wassist_api_base: str = "https://backend.wassist.app"
    wassist_default_connection_id: str = "conv_9501kwqfmzf0frwsza9pakj5spjz"

    database_url: str = ""
    xero_mcp_url: str = "https://builders.xero.com/beta/mcp"

    @property
    def xero_app_configured(self) -> bool:
        return bool(self.xero_client_id and self.xero_client_secret)

    @property
    def ai_configured(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
