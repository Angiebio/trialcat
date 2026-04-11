"""Condition — MeSH-normalized disease / condition labels.

We use a many-to-many relationship between Trial and Condition because:
1. A single trial often targets multiple conditions (e.g., "Type 2 Diabetes,
   Obesity, Hypertension")
2. The same condition appears in thousands of trials, so deduplication saves space
3. Filter queries like "all Cardiovascular trials" become a clean join instead
   of a text LIKE '%Cardiovascular%' hack

We key Conditions by MeSH ID when we have one, falling back to a slugified
version of the term when we don't. MeSH provides the ancestor hierarchy
we need to walk for therapeutic area classification.
"""

from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Condition(Base):
    """A disease or medical condition, ideally with a MeSH ID."""

    __tablename__ = "conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # MeSH ID (e.g., 'D003920' for Diabetes Mellitus). Nullable because not
    # every condition term has a MeSH mapping — CT.gov sometimes has free-text
    # conditions that CT.gov's MeSH mapper doesn't recognize.
    mesh_id: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        unique=True,
        index=True,
    )

    # Human-readable term. Always populated.
    term: Mapped[str] = mapped_column(String(256), nullable=False, index=True)

    # Broad MeSH ancestor (e.g., "Cardiovascular Diseases") for therapeutic
    # area aggregation. Computed from mesh_id by walking the MeSH tree.
    # Cached here so we don't walk the tree at query time.
    broad_category: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        doc="Top-level MeSH category, e.g., 'Cardiovascular Diseases', 'Neoplasms'",
    )

    # --- Relationships ---
    trials: Mapped[List["Trial"]] = relationship(
        secondary="trial_conditions",
        back_populates="conditions",
    )

    def __repr__(self) -> str:
        return f"<Condition {self.term} [{self.mesh_id or 'no-mesh'}]>"


class TrialCondition(Base):
    """Association table for the many-to-many between Trial and Condition.

    We use an explicit association table (not a plain secondary Table) so we
    can attach metadata per link if we ever need to — for example, "was this
    condition the primary focus of the trial vs. a secondary condition".
    """

    __tablename__ = "trial_conditions"

    trial_nct_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("trials.nct_id", ondelete="CASCADE"),
        primary_key=True,
    )
    condition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conditions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # Whether this condition came from the trial's primary conditions list
    # (True) or from a secondary/ancestor MeSH term (False). Helps us
    # weight relevance in searches.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
