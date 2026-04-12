"""Filter query parameters shared by all endpoints that aggregate over trials.

FilterQuery is a Pydantic model that every stats/aggregate/trials endpoint
accepts, so the same filter syntax applies everywhere: `country=US`,
`therapeutic_area=Cardiovascular`, `phase=PHASE3`, `start_date=2025-01-01`,
etc.

Validation lives here (not in the handlers) so route code stays focused on
orchestration.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class FilterQuery(BaseModel):
    """Shared filter parameters for trial aggregation queries.

    All fields are optional; leaving them None means "no filter on this field".
    An empty FilterQuery matches every trial in the database.
    """

    # --- Geographic ---
    country_code: Optional[str] = Field(
        default=None,
        description="ISO 3166-1 alpha-2 country code, e.g., 'US', 'DE', 'JP'",
        min_length=2,
        max_length=3,
    )
    state_code: Optional[str] = Field(
        default=None,
        description="USPS 2-letter US state code (only meaningful when country_code='US')",
        min_length=2,
        max_length=2,
    )

    # --- Trial characteristics ---
    therapeutic_area: Optional[str] = Field(
        default=None,
        description="Broad therapeutic area, e.g., 'Cardiovascular', 'Oncology'",
    )
    phase: Optional[str] = Field(
        default=None,
        description="Highest trial phase: PHASE1, PHASE2, PHASE3, PHASE4, NA",
    )
    status: Optional[str] = Field(
        default=None,
        description="Overall status: COMPLETED, RECRUITING, TERMINATED, etc.",
    )
    study_type: Optional[str] = Field(
        default=None,
        description="Study type: INTERVENTIONAL, OBSERVATIONAL, EXPANDED_ACCESS",
    )
    intervention_type: Optional[str] = Field(
        default=None,
        description="Intervention type: DRUG, DEVICE, BIOLOGICAL, BEHAVIORAL, etc.",
    )

    # --- Time range ---
    # Filters apply against Trial.start_date. A trial counts if its start_date
    # falls within [start_date, end_date] inclusive. Missing start_dates are
    # excluded from time-filtered queries (safer than guessing).
    start_date: Optional[date] = Field(
        default=None,
        description="Inclusive lower bound for trial start_date",
    )
    end_date: Optional[date] = Field(
        default=None,
        description="Inclusive upper bound for trial start_date",
    )

    # --- Normalize uppercase enum-like fields so callers don't have to ---
    @field_validator("country_code", "state_code", "phase", "status", "study_type", "intervention_type")
    @classmethod
    def _upper(cls, v: Optional[str]) -> Optional[str]:
        return v.upper() if v else v


class FilterOptions(BaseModel):
    """Response model for GET /api/filters — the dropdown choices.

    Returned sorted alphabetically by default so the UI doesn't have to.
    """

    therapeutic_areas: list[str] = Field(
        description="Distinct therapeutic_area values present in the database"
    )
    phases: list[str] = Field(description="Distinct phase values")
    statuses: list[str] = Field(description="Distinct overall_status values")
    study_types: list[str] = Field(description="Distinct study_type values")
    intervention_types: list[str] = Field(description="Distinct intervention type values")
    countries: list[str] = Field(description="Distinct country_code values (from location rows)")
