"""Outcome — primary and secondary outcome measures for a trial.

Stored mainly for the Phase 7 NL features: endpoint clustering, comparison
across similar trials, "what primary endpoint do most cardiovascular Class III
device trials use?" — that kind of question.

We store the raw measure text (e.g., "Percentage of Participants Who Gained at
Least 15 Letters in BCVA at Week 24") alongside time frame and a boolean
primary/secondary flag. Phase 7 will add an `embedding` column once we know
what dimensionality we want.
"""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Outcome(Base):
    """A primary or secondary outcome measure for a trial."""

    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    trial_nct_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("trials.nct_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # The headline outcome description — usually 1-2 sentences
    measure: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Time frame (e.g., "Baseline through Week 24")
    time_frame: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Primary outcome or secondary?
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    # --- Relationships ---
    trial: Mapped["Trial"] = relationship(back_populates="outcomes")

    def __repr__(self) -> str:
        kind = "primary" if self.is_primary else "secondary"
        return f"<Outcome ({kind}) {self.measure[:60]}... for {self.trial_nct_id}>"
