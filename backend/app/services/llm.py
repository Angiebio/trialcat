# trialcat game LLM client — v2.0 (16JUN2026)
"""A deliberately tiny, hard-capped OpenRouter client for the FDA reviewer NPC.

Design ethos: this is a side project's only LLM touch. It must be IMPOSSIBLE
for it to run up a bill. So:
  - empty key -> returns None (caller uses the scripted Dr. Vance fallback),
  - a global per-day call ceiling (in-memory; resets at UTC midnight),
  - a hard max_tokens cap sent on every request,
  - primary model -> cheaper fallback model -> None, never a crash.

The whole feature degrades to scripted text without ever failing the game. We
fail loud on OUR bugs; an unreachable model for a board game is not a bug, it's
a budget working as designed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)

# In-memory daily call ledger. Single-process SQLite app, so a module global is
# the right size of solution — no Redis to guard a few hundred calls a day.
_ledger = {"date": None, "count": 0}


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _budget_ok() -> bool:
    """True if we're under today's call ceiling. Rolls over at UTC midnight."""
    today = _today()
    if _ledger["date"] != today:
        _ledger["date"] = today
        _ledger["count"] = 0
    return _ledger["count"] < settings.game_llm_daily_call_cap


def calls_made_today() -> int:
    if _ledger["date"] != _today():
        return 0
    return _ledger["count"]


def chat(system_prompt: str, user_content: str, max_tokens: Optional[int] = None) -> Optional[str]:
    """One short chat completion via OpenRouter. Returns text, or None to fall back.

    None is returned (never raised) when: no API key, the daily budget is spent,
    or every model errored. Caller MUST handle None as "use scripted response".
    Send NO personally-identifying information in either argument.
    """
    if not settings.openrouter_api_key:
        return None
    if not _budget_ok():
        logger.info("Game LLM daily cap (%s) reached — using scripted fallback", settings.game_llm_daily_call_cap)
        return None

    cap = max_tokens or settings.openrouter_max_tokens
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        # OpenRouter likes attribution headers; harmless if ignored.
        "HTTP-Referer": "https://trialcat.ai",
        "X-Title": "trialcat — Race to Approval",
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content[:1500]},  # belt-and-suspenders truncation
    ]

    for model in (settings.openrouter_model, settings.openrouter_model_fallback):
        try:
            # Count the attempt BEFORE the call so a hammering bug can't bypass
            # the ceiling by erroring forever.
            _ledger["count"] += 1
            resp = requests.post(
                f"{settings.openrouter_base}/chat/completions",
                headers=headers,
                json={"model": model, "messages": messages, "max_tokens": cap, "temperature": 0.4},
                timeout=20.0,
            )
            if resp.status_code >= 400:
                logger.warning("OpenRouter %s returned %s: %s", model, resp.status_code, resp.text[:160])
                continue
            data = resp.json()
            text = (data.get("choices") or [{}])[0].get("message", {}).get("content")
            if text and text.strip():
                return text.strip()
        except requests.RequestException as e:
            logger.warning("OpenRouter %s call failed: %s", model, e)
            continue

    return None  # everything errored — the reviewer goes scripted
