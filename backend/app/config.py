from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
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
    # The legacy /analysis API remains the public default until V2 receives a
    # deliberate production deployment smoke test and rollback plan.
    debate_workflow_v2: bool = False
    # Queue admission remains separately default-off. Its hosted migration and
    # Worker lifecycle checks pass, but production enablement is explicit.
    debate_queue_enabled: bool = False
    debate_worker_visibility_timeout_seconds: int = Field(default=900, ge=30, le=3600)
    debate_worker_concurrency: int = Field(default=1, ge=1, le=2)
    debate_worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=10)
    # Redis is an optional optimization/coordination layer. Canonical state
    # remains in Supabase and every operation has a bounded local fallback.
    redis_enabled: bool = False
    redis_url: str | None = Field(default=None, repr=False)
    redis_connect_timeout_seconds: float = Field(default=0.75, ge=0.1, le=5)
    redis_socket_timeout_seconds: float = Field(default=0.75, ge=0.1, le=5)
    debate_rate_limit_per_window: int = Field(default=3, ge=1, le=100)
    debate_rate_limit_window_seconds: int = Field(default=3600, ge=60, le=86400)
    debate_active_ttl_seconds: int = Field(default=1200, ge=60, le=86400)
    debate_idempotency_lock_ttl_seconds: int = Field(default=120, ge=5, le=3600)
    explanation_rate_limit_per_window: int = Field(default=12, ge=1, le=100)
    explanation_rate_limit_window_seconds: int = Field(default=3600, ge=60, le=86400)
    # Explanation follows its own explicit provider selection. The safe default
    # remains credential-free even when the V2 HTTP route is enabled.
    explanation_provider: str = "deterministic"
    # The async Debate provider is an independent, explicit opt-in. Keeping it
    # deterministic prevents a feature-flag change from spending model quota.
    debate_streaming_provider: str = "deterministic"
    supabase_url: str | None = Field(default=None, repr=False)
    supabase_anon_key: str | None = Field(default=None, repr=False)
    supabase_secret_key: str | None = Field(default=None, repr=False)
    supabase_rls_user_a_email: str | None = Field(default=None, repr=False)
    supabase_rls_user_a_password: str | None = Field(default=None, repr=False)
    supabase_rls_user_b_email: str | None = Field(default=None, repr=False)
    supabase_rls_user_b_password: str | None = Field(default=None, repr=False)
    sec_user_agent: str | None = Field(default=None, repr=False)
    alpha_vantage_api_key: str | None = Field(default=None, repr=False)
    fred_api_key: str | None = Field(default=None, repr=False)
    eia_api_key: str | None = Field(default=None, repr=False)
    apify_user_id: str | None = Field(default=None, repr=False)
    apify_api_token: str | None = Field(default=None, repr=False)
    finnhub_api_key: str | None = Field(default=None, repr=False)
    # This app currently presents a single, verified Apple price series. Keeping
    # the default batch to one symbol makes each scheduled refresh one API call.
    price_tickers: str = "AAPL"
    price_max_calls_per_run: int = Field(default=1, ge=1, le=3)
    price_stale_after_days: int = 5
    live_evidence_tickers: str = "AAPL"
    macro_history_points: int = Field(default=400, ge=30, le=1000)
    weekly_price_history_points: int = Field(default=60, ge=52, le=260)
    groq_api_key: str | None = Field(default=None, repr=False)
    gemini_api_key: str | None = Field(default=None, repr=False)
    groq_model: str = "openai/gpt-oss-20b"
    debate_groq_model: str = "openai/gpt-oss-20b"
    debate_provider_timeout_seconds: float = Field(default=45, ge=5, le=120)
    gemini_model: str = "gemini-2.0-flash"
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def validate_redis_configuration(self) -> "Settings":
        if self.redis_enabled and not self.redis_url:
            raise ValueError("REDIS_URL is required when REDIS_ENABLED=true")
        if self.redis_url and not self.redis_url.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must use redis:// or rediss://")
        return self

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
