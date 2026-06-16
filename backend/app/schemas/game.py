# trialcat game schemas — v2.0 (16JUN2026)
"""Request/response models for the 'Race to Approval' game endpoints.

The game logic lives client-side; these are just the contracts for the three
things the server does: hand the player a real trial to fight for, record a
finished run, and serve the leaderboard. (The LLM FDA-reviewer contract lives
alongside but degrades to a scripted response when the model is off/over-budget.)
"""

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

# Loose email sanity check. We are NOT verifying deliverability — this is a
# leaderboard handle, not a credential — so a pragmatic "looks like an email"
# regex beats pulling in the email-validator dependency for a board game.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# =============================================================================
# Seed — "here is a real product, now get it approved"
# =============================================================================


class SeedTrial(BaseModel):
    """A real CT.gov trial, repackaged as a game scenario.

    pathway is the load-bearing field: 'drug' routes you through IND → phases →
    NDA/BLA; 'device' routes you through pre-sub → pivotal → 510(k)/PMA. The
    board literally forks on it.
    """

    nct_id: str
    title: str
    sponsor: Optional[str] = None
    pathway: Literal["drug", "device"]
    intervention_type: Optional[str] = None
    intervention_name: Optional[str] = None
    product_category: Optional[str] = None
    device_class: Optional[str] = None
    phase: Optional[str] = None
    therapeutic_area: Optional[str] = None
    overall_status: Optional[str] = None
    enrollment_count: Optional[int] = None
    # A 1-5 difficulty the engine derives from phase + enrollment + pathway,
    # so a 50,000-patient Phase 3 cardiovascular drug feels appropriately brutal.
    difficulty: int = Field(ge=1, le=5, default=3)


# =============================================================================
# Score submission + leaderboard
# =============================================================================


class ScoreSubmit(BaseModel):
    """Posted by the client when a run ends. No auth — name + email only."""

    first_name: str = Field(min_length=1, max_length=80)
    last_name: Optional[str] = Field(default=None, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    score: int = Field(ge=0)
    turns_taken: Optional[int] = Field(default=None, ge=0)
    outcome: Literal[
        "approved", "bankrupt", "failed_endpoint", "beaten_to_market", "clinical_hold"
    ]
    trial_nct_id: Optional[str] = Field(default=None, max_length=20)
    trial_title: Optional[str] = Field(default=None, max_length=512)
    pathway: Optional[Literal["drug", "device"]] = None
    difficulty: Optional[str] = Field(default=None, max_length=16)

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip(cls, v: Optional[str]) -> Optional[str]:
        return v.strip() if v else v

    @field_validator("email")
    @classmethod
    def _email_shape(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("that doesn't look like an email address")
        return v


class ScoreEntry(BaseModel):
    """One leaderboard row (player display name + their best run)."""

    rank: int
    display_name: str
    score: int
    outcome: str
    turns_taken: Optional[int] = None
    pathway: Optional[str] = None
    trial_nct_id: Optional[str] = None
    achieved_at: datetime


class ScoreSubmitResponse(BaseModel):
    """What the client gets back after posting a score."""

    recorded: bool = True
    your_score: int
    your_rank: int
    total_players: int
    is_personal_best: bool


class LeaderboardResponse(BaseModel):
    entries: list[ScoreEntry]
    total_scores: int
    generated_at: datetime


# =============================================================================
# LLM FDA reviewer (optional — scripted fallback when off/over-budget)
# =============================================================================


class ReviewRequest(BaseModel):
    """The player's marketing-application narrative, submitted to the reviewer.

    No PII here by design — only the game scenario + the player's free-text
    rationale. The route strips anything else before it reaches the model.
    """

    pathway: Literal["drug", "device"]
    therapeutic_area: Optional[str] = None
    phase: Optional[str] = None
    # The player's free-text "why should FDA approve this?" submission.
    submission_rationale: str = Field(min_length=1, max_length=1500)
    # Game state the reviewer reasons over. Data/evidence is the heavy weight
    # (data > narrative is the whole joke); the rest are flavor + nudges.
    evidence_score: int = Field(ge=0, le=100, default=50)
    reputation_score: int = Field(ge=0, le=100, default=50)
    integrity_flags: int = Field(ge=0, default=0)
    product_name: Optional[str] = Field(default=None, max_length=200)


# The standard FDA regulatory-action taxonomy. The reviewer returns exactly one.
ReviewVerdict = Literal[
    "APPROVED",
    "APPROVABLE_WITH_DEFICIENCIES",
    "COMPLETE_RESPONSE_LETTER",
    "REFUSE_TO_FILE",
]


class ReviewResponse(BaseModel):
    verdict: ReviewVerdict
    reviewer_name: str
    letter: str  # the in-character response text
    score_modifier: int  # +/- applied to the player's final score, clamped [-25, +20]
    source: Literal["llm", "scripted"]  # so the UI can badge it honestly
