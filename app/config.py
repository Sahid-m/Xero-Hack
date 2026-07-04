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

    anthropic_api_key: str = ""
    ai_default_model: str = "anthropic:claude-sonnet-4-6"

    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    voca_phone_number: str = ""
    public_base_url: str = ""

    database_url: str = ""

    @property
    def xero_app_configured(self) -> bool:
        return bool(self.xero_client_id and self.xero_client_secret)

    @property
    def ai_configured(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def voice_configured(self) -> bool:
        return bool(self.elevenlabs_api_key and self.voca_phone_number)


@lru_cache
def get_settings() -> Settings:
    return Settings()
