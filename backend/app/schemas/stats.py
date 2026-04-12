"""Request and response schemas for the stats + aggregate endpoints.

Two families:

- **Aggregate**: returns per-group counts (for the map choropleth). One row
  per country (or per US state). Fast, indexed queries.

- **Stats**: returns distribution summaries (for the popup when a user clicks
  a country). Answers: how many trials, total enrolled, low/median/high
  enrollment rate, average time-to-enroll.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.filters import FilterQuery


# =============================================================================
# Aggregate (choropleth) endpoint
# =============================================================================


class AggregateRow(BaseModel):
    """One row of the choropleth aggregation.

    The `group_key` field holds whatever we're aggregating by:
    - `by=country` → ISO alpha-2 code: "US", "DE", "JP"
    - `by=us_state` → USPS 2-letter code: "CA", "NY", "TX"
    """

    group_key: str = Field(description="Country code or state code")
    trial_count: int = Field(description="Number of distinct trials with at least one site")
    total_enrollment: Optional[int] = Field(
        default=None,
        description="Sum of enrollment_count across matching trials",
    )


class AggregateResponse(BaseModel):
    """Full choropleth response — rows + metadata about what was aggregated."""

    group_by: str = Field(description="What the rows are grouped by: 'country' or 'us_state'")
    rows: list[AggregateRow]
    total_trials: int = Field(description="Total distinct trials across all groups")
    generated_at: datetime = Field(description="Server timestamp when this response was computed")


# =============================================================================
# Stats (popup) endpoint
# =============================================================================


class StatsResponse(BaseModel):
    """Summary stats for a filter cohort — the data behind a country click popup.

    All "rate" fields use approx_enrollment_rate_per_month, which is an
    APPROXIMATION (see Trial.approx_enrollment_rate_per_month docstring).
    The UI should label these clearly as approximate.
    """

    # --- Echoes of the filter so the frontend knows what it's looking at ---
    filter_applied: FilterQuery

    # --- Counts ---
    trial_count: int = Field(description="Distinct trials matching the filter")
    total_enrollment: Optional[int] = Field(
        default=None,
        description="Sum of enrollment_count across matching trials",
    )

    # --- Distribution of approximate monthly enrollment rate ---
    # Only trials with a non-null rate are included in these numbers. If
    # fewer than N trials have rates, the stats are flagged as unreliable
    # via `sample_size`.
    approx_rate_min: Optional[float] = Field(
        default=None,
        description="Minimum approximate patients/month across matching trials",
    )
    approx_rate_median: Optional[float] = Field(
        default=None,
        description="Median approximate patients/month",
    )
    approx_rate_max: Optional[float] = Field(
        default=None,
        description="Maximum approximate patients/month",
    )
    approx_rate_sample_size: int = Field(
        default=0,
        description="Number of trials contributing to the rate distribution. <5 means don't trust it.",
    )

    # --- Duration stats ---
    avg_months_enrolling: Optional[float] = Field(
        default=None,
        description="Average months_enrolling (APPROXIMATE — see column docstring)",
    )

    generated_at: datetime
