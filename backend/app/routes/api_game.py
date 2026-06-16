# trialcat game API — v2.0 (16JUN2026)
"""'Race to Approval' backend: seed a real trial, record a run, serve the board.

The game engine is client-side (frontend/static/js/game.js). The server's whole
job here is three verbs:
  - SEED:  hand the player a real CT.gov trial to shepherd to approval, with a
           pathway (drug vs device) that forks the whole board. This is the data
           tie-in that makes the game and the map one artifact, not two.
  - SCORE: persist a finished run + the (unverified, MVP) player handle.
  - BOARD: the leaderboard.
Plus REVIEW: the LLM "FDA reviewer" NPC, which degrades to a scripted letter
when the model is disabled or over its daily budget — the game is fully
playable with zero LLM spend.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import GameScore, Intervention, Player, Trial
from app.schemas.game import (
    LeaderboardResponse,
    ReviewRequest,
    ReviewResponse,
    ScoreEntry,
    ScoreSubmit,
    ScoreSubmitResponse,
    SeedTrial,
)
from app.services.game_review import generate_review

router = APIRouter(prefix="/api/game", tags=["game"])


# =============================================================================
# Difficulty — the seeded trial's real attributes set the challenge curve
# =============================================================================


def _derive_difficulty(phase: Optional[str], enrollment: Optional[int], pathway: str) -> int:
    """Map a real trial onto a 1-5 difficulty.

    The reasoning mirrors real life: late-phase, large-enrollment drug programs
    are the brutal ones (years, fortunes, attrition); early or small device
    studies are gentler. Not a model of truth — a model of *vibe* that's true
    enough to teach the shape of the work.
    """
    score = 2
    phase_weight = {
        "EARLY_PHASE1": 0, "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 2,
    }
    score += phase_weight.get((phase or "").upper(), 1)
    if enrollment:
        if enrollment >= 5000:
            score += 2
        elif enrollment >= 500:
            score += 1
    # Drugs carry the heavier regulatory burden (NDA/BLA vs many 510(k)s).
    if pathway == "drug":
        score += 1
    return max(1, min(5, score))


# =============================================================================
# SEED
# =============================================================================


@router.get(
    "/seed",
    response_model=SeedTrial,
    summary="Deal a real CT.gov trial as a game scenario",
)
def seed_game(
    db: Session = Depends(get_db),
    pathway: Optional[str] = Query(
        default=None, description="Bias the draw: 'drug' or 'device'. Omit for either."
    ),
    therapeutic_area: Optional[str] = Query(default=None),
) -> SeedTrial:
    """Pick a real trial (with a drug or device intervention) at random.

    The drawn intervention's type decides the pathway, which decides the board.
    We bias toward trials that make a satisfying scenario (named, with a real
    intervention) and let the caller nudge by pathway/area so the map's current
    filters can flow into the game.
    """
    wanted_types = (
        ["DEVICE"] if pathway == "device"
        else ["DRUG"] if pathway == "drug"
        else ["DRUG", "DEVICE"]
    )

    stmt = (
        select(Trial, Intervention)
        .join(Intervention, Intervention.trial_nct_id == Trial.nct_id)
        .where(Intervention.type.in_(wanted_types))
        .where(Trial.brief_title.isnot(None))
    )
    if therapeutic_area:
        stmt = stmt.where(Trial.therapeutic_area == therapeutic_area)
    stmt = stmt.order_by(func.random()).limit(1)

    row = db.execute(stmt).first()
    if not row:
        # Fail loud: an empty DB means the ETL never ran. Better a clear 503
        # than a game that silently deals nothing.
        raise HTTPException(
            status_code=503,
            detail="No seedable trials in the database yet — run the ETL first.",
        )

    trial, iv = row
    drawn_pathway = "device" if iv.type == "DEVICE" else "drug"

    return SeedTrial(
        nct_id=trial.nct_id,
        title=trial.brief_title,
        sponsor=trial.lead_sponsor_name,
        pathway=drawn_pathway,
        intervention_type=iv.type,
        intervention_name=iv.name,
        product_category=iv.product_category,
        device_class=iv.device_class_hint,
        phase=trial.phase,
        therapeutic_area=trial.therapeutic_area,
        overall_status=trial.overall_status,
        enrollment_count=trial.enrollment_count,
        difficulty=_derive_difficulty(trial.phase, trial.enrollment_count, drawn_pathway),
    )


# =============================================================================
# SCORE
# =============================================================================


def _display_name(first: str, last: Optional[str]) -> str:
    """First name + last initial. A small privacy courtesy on a public board."""
    if last:
        return f"{first} {last[0].upper()}."
    return first


@router.post(
    "/score",
    response_model=ScoreSubmitResponse,
    summary="Record a finished run",
)
def submit_score(payload: ScoreSubmit, db: Session = Depends(get_db)) -> ScoreSubmitResponse:
    """Upsert the player (by email) and append their score.

    No auth, no verification — the email is a soft de-dup key. We never expose
    the raw email on the leaderboard (only first name + last initial).
    """
    # Upsert player by lowercased email (the schema already lowercased it).
    player = db.scalar(select(Player).where(Player.email == payload.email))
    if player:
        # Keep the latest name they entered — people fix typos.
        player.first_name = payload.first_name
        player.last_name = payload.last_name
    else:
        player = Player(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
        )
        db.add(player)
    db.flush()  # assign player.id

    # Was this their personal best (before inserting the new row)?
    prev_best = db.scalar(
        select(func.max(GameScore.score)).where(GameScore.player_id == player.id)
    )
    is_pb = prev_best is None or payload.score > prev_best

    score_row = GameScore(
        player_id=player.id,
        score=payload.score,
        turns_taken=payload.turns_taken,
        outcome=payload.outcome,
        trial_nct_id=payload.trial_nct_id,
        trial_title=payload.trial_title,
        pathway=payload.pathway,
        difficulty=payload.difficulty,
    )
    db.add(score_row)
    db.commit()

    # Rank = how many runs scored strictly higher, +1. (Run-level, not player-level.)
    higher = db.scalar(
        select(func.count(GameScore.id)).where(GameScore.score > payload.score)
    ) or 0
    total_players = db.scalar(select(func.count(Player.id))) or 0

    return ScoreSubmitResponse(
        your_score=payload.score,
        your_rank=int(higher) + 1,
        total_players=int(total_players),
        is_personal_best=is_pb,
    )


@router.get(
    "/leaderboard",
    response_model=LeaderboardResponse,
    summary="Top runs",
)
def leaderboard(
    db: Session = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
) -> LeaderboardResponse:
    """Top scores, highest first, newest as the tiebreak."""
    total = db.scalar(select(func.count(GameScore.id))) or 0

    rows = db.execute(
        select(GameScore, Player)
        .join(Player, Player.id == GameScore.player_id)
        .order_by(GameScore.score.desc(), GameScore.fetched_at.desc())
        .limit(limit)
    ).all()

    entries = [
        ScoreEntry(
            rank=i + 1,
            display_name=_display_name(p.first_name, p.last_name),
            score=gs.score,
            outcome=gs.outcome,
            turns_taken=gs.turns_taken,
            pathway=gs.pathway,
            trial_nct_id=gs.trial_nct_id,
            achieved_at=gs.fetched_at,
        )
        for i, (gs, p) in enumerate(rows)
    ]

    return LeaderboardResponse(
        entries=entries,
        total_scores=int(total),
        generated_at=datetime.now(timezone.utc),
    )


# =============================================================================
# REVIEW — the LLM FDA reviewer NPC (scripted fallback when off/over-budget)
# =============================================================================


@router.post(
    "/review",
    response_model=ReviewResponse,
    summary="Submit your marketing application to the FDA reviewer",
)
def review_submission(payload: ReviewRequest) -> ReviewResponse:
    """Run the player's submission narrative past the reviewer NPC.

    Delegates to the review service, which tries the (capped, cheap) LLM and
    falls back to a scripted letter so this endpoint never fails the game just
    because the model is off. No DB, no PII.
    """
    return generate_review(payload)
