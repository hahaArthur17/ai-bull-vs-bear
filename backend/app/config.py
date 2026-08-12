from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Runtime configuration.

    The application intentionally defaults to deterministic demo mode so a new
    contributor can run the project without credentials.
    """

    app_name: str = "AI Bull vs Bear API"
    environment: str = "development"
    auth_mode: str = "demo"
    demo_user_id: str = "demo-user"
    persistence_mode: str = "demo"
    analysis_provider: str = "demo"
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_secret_key: str | None = None
    sec_user_agent: str | None = None
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    gemini_model: str = "gemini-2.0-flash"
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
