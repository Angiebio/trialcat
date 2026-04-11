"""Runtime configuration loaded from environment variables.

Uses pydantic-settings so every config value has a type, a default, and a
single source of truth. Anything that touches secrets or environment-specific
behavior lives here — the rest of the app just imports `settings`.

Philosophy: configuration is the seam between the code and the world. Keep it
narrow, typed, and observable. When something is wrong with the environment,
we want it to fail loud at startup, not mysteriously at request time.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the repo root (two levels up from this file: backend/app/config.py)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """All trialcat runtime settings, loaded from .env or environment variables."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars so .env can host multiple projects
    )

    # --- App identity ---
    app_name: str = Field(default="trialcat")
    app_env: Literal["development", "staging", "production"] = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # --- Database ---
    database_url: str = Field(default=f"sqlite:///{REPO_ROOT / 'data' / 'trialcat.db'}")

    # --- ClinicalTrials.gov API ---
    ctgov_api_base: str = Field(default="https://clinicaltrials.gov/api/v2")
    ctgov_user_agent: str = Field(
        default="trialcat/0.1 (https://trialcat.ai; contact@therealcat.ai)"
    )
    ctgov_fetch_page_size: int = Field(default=100, ge=1, le=1000)

    # --- AI services (Phase 7+) ---
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    # --- Rate limiting (Phase 6) ---
    rate_limit_detail_per_day: int = Field(default=1, ge=0)
    rate_limit_basic_per_hour: int = Field(default=60, ge=0)

    # --- Monetization (Phase 6) ---
    kofi_url: str = Field(default="https://ko-fi.com/therealcatai")
    buttondown_api_key: str = Field(default="")
    buttondown_newsletter: str = Field(default="trialcat")

    # --- Observability ---
    sentry_dsn: str = Field(default="")

    # --- Future: AI workers (v2) ---
    runpod_endpoint_url: str = Field(default="")
    runpod_api_key: str = Field(default="")

    @property
    def is_dev(self) -> bool:
        """Convenience for "are we in dev mode" checks."""
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor. Reads .env exactly once per process.

    Using lru_cache here means every module that imports `get_settings()` gets
    the same singleton — no risk of inconsistent config between components.
    """
    return Settings()


# Import-time convenience: most code can just `from app.config import settings`
settings = get_settings()
