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

    # --- Heuristic product category for the DEVICE drill-down ---
    # CT.gov gives us no sub-classification of devices, and the FDA class hint
    # above is too sparse to be useful (most descriptions never say "Class II").
    # So we classify by the only signal we reliably have: the intervention name.
    # A "catheter" is a catheter whether or not anyone wrote down its class.
    # This is the populated, human-meaningful "product type" granularity below
    # DEVICE — the thing a regulatory professional actually wants to slice by.
    # Heuristic, not authoritative; None for non-devices or unrecognized names.
    product_category: Mapped[Optional[str]] = mapped_column(
        String(48),
        nullable=True,
        index=True,
        doc="Heuristic device product category (Cardiovascular, Imaging, Software/Digital Health, etc.). None if not a device or unrecognized.",
    )

    # --- Relationships ---
    trial: Mapped["Trial"] = relationship(back_populates="interventions")

    def __repr__(self) -> str:
        return f"<Intervention {self.type}:{self.name[:30] if self.name else '?'} for {self.trial_nct_id}>"
