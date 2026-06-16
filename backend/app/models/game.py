# trialcat game models — v2.0 (16JUN2026)
"""Player + GameScore: the leaderboard spine for 'Race to Approval'.

The game itself runs client-side (a deterministic JS engine — see
frontend/static/js/game.js). The backend only persists two things: who played
and how they did. Deliberately tiny.

Privacy posture (MVP, and labeled as such everywhere a human can see it):
we capture first name, last name, and email for the leaderboard. There is NO
authentication, NO verification, NO password — the email is a contact handle
and a soft de-dup key, nothing more. We never send it to the LLM. A grown-up
version (consent, verification, deletion endpoint) is a Phase-2 concern; today
this is a leaderboard for a satirical regulatory-affairs game, not a registry.

Philosophical note: the whole tool teaches that regulatory rigor is about
proportionality — Class I devices don't need PMAs. So the data we collect for
a board game shouldn't pretend to be a clinical system. Right-sized is the
ethic, here too.
"""

from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Player(Base):
    """One human who entered their name + email to appear on the leaderboard.

    De-duplicated on lowercased email so the same person replaying doesn't
    spawn a crowd of near-identical rows. (Base gives us fetched_at — which
    here reads as "first played" — and updated_at = "last seen".)
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    # Unique, lowercased contact handle. Not verified, not a credential.
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)

    scores: Mapped[list["GameScore"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Player {self.first_name} {self.last_name or ''} ({self.email})>"


class GameScore(Base):
    """One completed playthrough. The unit the leaderboard ranks.

    We denormalize the seeded trial's title + pathway onto the score row so the
    leaderboard can show 'shepherded NCT01234567 (a Phase 3 device) to approval
    in 9 turns' without a join back to the trials table — and so the record
    survives even if that trial later ages out of the local DB.
    """

    __tablename__ = "game_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    player_id: Mapped[int] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # The single number the leaderboard sorts on. Higher = faster + more
    # efficient route to FDA approval (see scoring in game.js / the engine spec).
    score: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    turns_taken: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 'approved' is the only win; the rest are the flavors of defeat
    # ('bankrupt', 'failed_endpoint', 'beaten_to_market', 'clinical_hold').
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # What real CT.gov trial seeded this run (the data tie-in that makes the
    # game and the map one thing instead of two).
    trial_nct_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    trial_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # 'drug' (NDA/BLA pathway) or 'device' (510(k)/PMA pathway) — divergent boards.
    pathway: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    difficulty: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    player: Mapped["Player"] = relationship(back_populates="scores")

    def __repr__(self) -> str:
        return f"<GameScore {self.score} ({self.outcome}) by player {self.player_id}>"


# Composite index for the leaderboard's hot query: top scores, newest first.
Index("ix_game_scores_leaderboard", GameScore.score.desc(), GameScore.fetched_at.desc())


class GlossaryTerm(Base):
    """One entry in the self-building glossary — the labor of teaching, persisted.

    Seeded with hand-written definitions; grown by the LLM as players tap terms
    the dictionary hasn't seen. Each curiosity leaves the next player a richer
    glossary. `source` tells the UI whether to offer a regenerate (only 'llm'
    entries can be improved); `quality_score` rises each time the judge keeps the
    stored definition over a fresh candidate (a soft 'this one has earned trust').
    """

    __tablename__ = "glossary_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Normalized dedup key (lowercased, punctuation-stripped). The lookup handle.
    term_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    term: Mapped[str] = mapped_column(String(120), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    # 'seed' (hand-written), 'llm' (generated, regenerable), 'pending' (no LLM yet).
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="seed")
    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<GlossaryTerm {self.term_key} ({self.source})>"
