"""Schemas for the /api/trials paginated list endpoint.

We return a summary view, not the full trial blob — the frontend only needs
enough to render a list item + link to ClinicalTrials.gov. Full detail is
a future feature (e.g., /api/trials/{nct_id}).
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TrialSummary(BaseModel):
    """Compact trial representation for list views."""

    nct_id: str
    brief_title: Optional[str] = None
    overall_status: Optional[str] = None
    phase: Optional[str] = None
    study_type: Optional[str] = None
    therapeutic_area: Optional[str] = None
    lead_sponsor_name: Optional[str] = None
    lead_sponsor_class: Optional[str] = None
    enrollment_count: Optional[int] = None
    start_date: Optional[date] = None
    primary_completion_date: Optional[date] = None
    approx_enrollment_rate_per_month: Optional[float] = Field(
        default=None,
        description="APPROXIMATE rate — UI must label as such",
    )
    location_count: int = Field(description="Total number of sites/locations for this trial")


class TrialListResponse(BaseModel):
    """Paginated list of trial summaries with pagination metadata."""

    trials: list[TrialSummary]
    page: int = Field(ge=1, description="1-indexed current page")
    page_size: int = Field(ge=1, le=100, description="Rows per page")
    total: int = Field(ge=0, description="Total matching trials across all pages")
    total_pages: int = Field(ge=0, description="Total number of pages for this filter")
    generated_at: datetime
