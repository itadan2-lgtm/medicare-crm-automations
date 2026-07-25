"""Application settings, loaded from the environment.

Nothing in this module may be imported by the frontend build. Everything here is
server-side only.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Task types that must not run without a human releasing them. Publishing a page or
# moving money is irreversible from the user's point of view, so the gate is on the
# task type rather than on any agent's judgement.
HUMAN_APPROVAL_REQUIRED: frozenset[str] = frozenset(
    {
        "publish_funnel",
        "publish_page",
        "send_broadcast",
        "create_payment",
        "create_coupon",
        "apply_optimization",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- Core ---
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://aibo:aibo@localhost:5432/aibo"
    redis_url: str = "redis://localhost:6379/0"

    # --- Auth ---
    # Deliberately an obvious placeholder, and rejected outright in production
    # (see get_settings below) so it can never ship as a real signing key.
    jwt_secret: str = "change-me-before-first-run"  # noqa: S105
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- LLM ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # --- systeme.io ---
    systemeio_mcp_key: str = ""
    systemeio_api_key: str = ""
    systemeio_api_base: str = "https://api.systeme.io/api"
    systemeio_mcp_base: str = "https://mcp.systeme.io"

    # --- Safety rails ---
    dry_run: bool = True
    require_human_approval: bool = True
    max_browser_sessions: int = 2

    # --- Orchestration ---
    max_task_attempts: int = 2
    agent_error_threshold: int = 5
    agent_error_window_seconds: int = 300
    worker_poll_interval_seconds: float = 2.0

    # --- Memory ---
    memory_ttl_days: int = 365
    memory_top_k: int = 5

    # --- systeme.io client tuning ---
    rate_limit_floor: int = 3
    max_retries: int = 4

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


PLACEHOLDER_SECRET = "change-me-before-first-run"  # noqa: S105 - sentinel, not a credential


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.is_production and settings.jwt_secret == PLACEHOLDER_SECRET:
        raise RuntimeError("JWT_SECRET must be set in production")
    return settings
