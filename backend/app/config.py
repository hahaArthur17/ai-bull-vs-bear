from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
    supabase_rls_user_a_email: str | None = None
    supabase_rls_user_a_password: str | None = None
    supabase_rls_user_b_email: str | None = None
    supabase_rls_user_b_password: str | None = None
    sec_user_agent: str | None = None
    alpha_vantage_api_key: str | None = None
    fred_api_key: str | None = None
    eia_api_key: str | None = None
    apify_user_id: str | None = None
    apify_api_token: str | None = None
    finnhub_api_key: str | None = None
    # This app currently presents a single, verified Apple price series. Keeping
    # the default batch to one symbol makes each scheduled refresh one API call.
    price_tickers: str = "AAPL"
    price_max_calls_per_run: int = Field(default=1, ge=1, le=3)
    price_stale_after_days: int = 5
    live_evidence_tickers: str = "AAPL"
    macro_history_points: int = Field(default=400, ge=30, le=1000)
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

    @property
    def price_ticker_list(self) -> tuple[str, ...]:
        tickers = dict.fromkeys(
            ticker.strip().upper()
            for ticker in self.price_tickers.split(",")
            if ticker.strip()
        )
        return tuple(tickers)[: self.price_max_calls_per_run]

    @property
    def live_evidence_ticker_list(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                ticker.strip().upper()
                for ticker in self.live_evidence_tickers.split(",")
                if ticker.strip()
            )
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
