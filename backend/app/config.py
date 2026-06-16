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

    # --- openFDA enrichment (Phase 8 v2) ---
    # openFDA is the public FDA data API (devices, drugs, NDC, Drugs@FDA).
    # No key is required, but the no-key tier is throttled hard: ~240 req/min
    # and 1,000 req/day. A free key (https://open.fda.gov/apis/authentication/)
    # lifts the daily ceiling to 120,000. We default the key to empty so the
    # enrichment works out of the box; production should set OPENFDA_API_KEY.
    openfda_api_key: str = Field(default="")
    openfda_api_base: str = Field(default="https://api.fda.gov")

    # --- AI services (Phase 7+) ---
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    # --- Game LLM: the FDA reviewer NPC (v2, OpenRouter, cheap + hard-capped) ---
    # The reviewer is the ONLY LLM touch in the game and it is deliberately tiny:
    # a short, in-character verdict. Cheap model, hard token cap, a per-day call
    # ceiling so a public side-project can NEVER surprise us with a bill. Empty
    # key → the scripted Dr. Vance fallback carries the whole feature, so the
    # game is fully playable at $0. (Prices verified 2026-06-16: primary
    # ~$0.10/$0.40 per M tok → ~1,960 games per $1.)
    openrouter_api_key: str = Field(default="")
    openrouter_base: str = Field(default="https://openrouter.ai/api/v1")
    openrouter_model: str = Field(default="google/gemini-2.5-flash-lite")
    openrouter_model_fallback: str = Field(default="mistralai/mistral-nemo")
    openrouter_max_tokens: int = Field(default=180, ge=16, le=1024)
    # Global per-process daily call ceiling. The hard stop that makes "cheap"
    # a guarantee, not a hope. ~0.017 cents/call → 600 calls ≈ a dime a day.
    game_llm_daily_call_cap: int = Field(default=600, ge=0)

    # --- Rate limiting (Phase 6) ---
    rate_limit_detail_per_day: int = Field(default=1, ge=0)
    rate_limit_basic_per_hour: int = Field(default=60, ge=0)

    # --- Monetization (Phase 6) ---
    kofi_url: str = Field(default="https://ko-fi.com/therealcatai")
    buttondown_api_key: str = Field(default="")
    buttondown_newsletter: str = Field(default="trialcat")

    # --- Admin ---
    admin_secret: str = Field(default="")  # Set via fly secrets; protects admin endpoints

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
