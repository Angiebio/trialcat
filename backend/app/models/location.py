"""Location — a single study site for a trial.

A trial can have 1 to hundreds of sites (the VEGF Trap-Eye trial has 61).
We store each one denormalized with lat/lon because CT.gov v2 pre-computes
geopoints for us. This lets us skip the geocoding step entirely and
immediately answer "how many trials have sites in Germany?" or "how many
in California?" via SQL aggregation.

Indexing strategy:
- country_code is the most common filter (country-level choropleth)
- state is filtered at US drill-down time
- (trial_id, country_code) composite for the common aggregation query
"""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Location(Base):
    """One study site for a trial."""

    __tablename__ = "locations"
    __table_args__ = (
        # Most queries filter on trial + country; this composite index
        # accelerates the common "count sites per country" aggregation.
        Index("ix_locations_trial_country", "trial_nct_id", "country_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- Link to parent trial ---
    trial_nct_id: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("trials.nct_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # --- Site identity ---
    facility: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        doc="US state name or international province; free-text, not normalized",
    )
    country: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="Raw country name from CT.gov, e.g., 'United States'",
    )
    country_code: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
        index=True,
        doc="ISO 3166-1 alpha-2 code, e.g., 'US', 'DE', 'JP'. Computed at ETL.",
    )
    zip: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # --- Geo coordinates (from CT.gov's geoPoint field) ---
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- Status (some sites recruit, some don't) ---
    site_status: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        doc="RECRUITING, NOT_YET_RECRUITING, COMPLETED, etc.",
    )

    # --- Relationships ---
    trial: Mapped["Trial"] = relationship(back_populates="locations")

    def __repr__(self) -> str:
        return f"<Location {self.city}, {self.country_code} for {self.trial_nct_id}>"
