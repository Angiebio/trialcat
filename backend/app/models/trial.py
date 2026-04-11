"""Trial — the core unit of aggregation in trialcat.

One row per NCT ID. Everything else (locations, interventions, etc.) hangs
off this table via foreign keys. The Trial row itself holds the denormalized
"hot path" fields that filters touch most often: phase, status, study type,
enrollment count, start/completion dates.

Why denormalize some fields into Trial instead of a separate Phase table?
Because Phase is a small enum (Phase 1-4, Early, NA), and every filter query
will touch it. Joining a lookup table for an enum is slower and uglier than
just storing the string directly. We only normalize when cardinality is high
and the join provides real value (locations, conditions).
"""

from datetime import date
from typing import List, Optional

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Trial(Base):
    """A single clinical trial as identified by NCT ID."""

    __tablename__ = "trials"

    # --- Primary identity ---
    nct_id: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
        doc="ClinicalTrials.gov unique identifier (e.g., 'NCT04280705')",
    )

    # --- Descriptive ---
    brief_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    official_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brief_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Sponsor ---
    # Stored flat because each trial has exactly one lead sponsor.
    # Collaborators could be a separate table later if we need them.
    lead_sponsor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lead_sponsor_class: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        doc="INDUSTRY, NIH, OTHER_GOV, ACADEMIC, etc.",
    )

    # --- Status & lifecycle ---
    overall_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="RECRUITING, COMPLETED, TERMINATED, etc.",
    )
    study_type: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="INTERVENTIONAL, OBSERVATIONAL, EXPANDED_ACCESS",
    )

    # Phase is stored as a string — most trials have one phase, a few have
    # ["PHASE1", "PHASE2"] so we pick the highest. Filter queries are easier
    # against a single column than a join.
    phase: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        index=True,
        doc="EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4, NA",
    )

    # --- Dates ---
    # Dates in CT.gov can be year-only (2019) or year-month (2019-07) or full.
    # We parse to a Date by filling in missing parts with 01 (see etl layer).
    # The actual/anticipated distinction is stored too — it matters for the
    # enrollment metrics we compute later.
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    start_date_type: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, doc="ACTUAL or ANTICIPATED"
    )
    primary_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    primary_completion_date_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    completion_date_type: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # --- Enrollment ---
    enrollment_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    enrollment_type: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        doc="ACTUAL (trial completed enrollment) or ESTIMATED (target)",
    )

    # --- Enrollment rate (computed in ETL, not by CT.gov) ---
    # These are the MONEY columns — what everything else in trialcat serves.
    # Computed as: enrollment_count / months_enrolling
    # where months_enrolling = (primary_completion - start) in months.
    enrollment_rate_per_month: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        doc="Average patients enrolled per month over the enrollment period",
    )
    months_enrolling: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        doc="Duration of active enrollment in months",
    )

    # --- Therapeutic area (computed from MeSH hierarchy) ---
    # The broad bucket (e.g., "Cardiovascular Diseases", "Neoplasms").
    # Stored on Trial directly because every filter query touches it.
    # A trial can theoretically span multiple areas but in practice 95% have one.
    therapeutic_area: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        doc="Broad MeSH category, e.g., 'Cardiovascular Diseases'",
    )

    # --- Relationships ---
    locations: Mapped[List["Location"]] = relationship(
        back_populates="trial",
        cascade="all, delete-orphan",
    )
    interventions: Mapped[List["Intervention"]] = relationship(
        back_populates="trial",
        cascade="all, delete-orphan",
    )
    conditions: Mapped[List["Condition"]] = relationship(
        secondary="trial_conditions",
        back_populates="trials",
    )
    outcomes: Mapped[List["Outcome"]] = relationship(
        back_populates="trial",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Trial {self.nct_id} phase={self.phase} status={self.overall_status}>"
