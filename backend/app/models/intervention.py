"""Intervention — a drug, device, procedure, or behavioral element tested by a trial.

CT.gov's intervention types are a fixed enum: DRUG, BIOLOGICAL, DEVICE,
PROCEDURE, BEHAVIORAL, RADIATION, GENETIC, DIAGNOSTIC_TEST, DIETARY_SUPPLEMENT,
COMBINATION_PRODUCT, OTHER. We store the type directly on this table so
filter queries can just say `WHERE type = 'DEVICE'`.

Device class (I, II, III) is NOT in CT.gov data — it comes from FDA's
510(k)/PMA database. For MVP we heuristically parse it from the intervention
description text (regex) and store it as `device_class_hint`. Phase 8 v2
work will cross-reference with the actual FDA classification database.
"""

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Intervention(Base):
    """One intervention (treatment arm) for a trial."""

    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    trial_nct_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("trials.nct_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # --- What the intervention is ---
    type: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="DRUG, BIOLOGICAL, DEVICE, PROCEDURE, BEHAVIORAL, etc.",
    )
    name: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Heuristic device class extracted from description text (MVP) ---
    # Will be replaced with FDA DB cross-ref in v2. Stored as a hint, not authoritative.
    device_class_hint: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        index=True,
        doc="Heuristic: 'I', 'II', 'III' parsed from description. None if not a device or not detected.",
    )

    # --- Relationships ---
    trial: Mapped["Trial"] = relationship(back_populates="interventions")

    def __repr__(self) -> str:
        return f"<Intervention {self.type}:{self.name[:30] if self.name else '?'} for {self.trial_nct_id}>"
