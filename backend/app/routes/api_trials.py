"""GET /api/trials — paginated list of trial summaries.

The "show me the trials" drill-down. Takes the standard filter params
plus pagination (page, page_size). Returns compact summaries — full trial
detail is a potential future endpoint at /api/trials/{nct_id}.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import FilterQuery, TrialListResponse
from app.services.stats import list_trials

router = APIRouter(prefix="/api", tags=["trials"])


@router.get(
    "/trials",
    response_model=TrialListResponse,
    summary="Paginated list of trials matching a filter",
    description=(
        "Returns compact trial summaries for the given filter cohort. "
        "Pagination is 1-indexed; `page_size` is capped at 100 to prevent "
        "accidental bulk downloads. Results are sorted newest-first by "
        "start_date."
    ),
)
def read_trials(
    db: Session = Depends(get_db),
    country_code: Optional[str] = Query(default=None, min_length=2, max_length=3),
    state_code: Optional[str] = Query(default=None, min_length=2, max_length=2),
    therapeutic_area: Optional[str] = Query(default=None),
    phase: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    study_type: Optional[str] = Query(default=None),
    intervention_type: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    page: int = Query(default=1, ge=1, description="1-indexed page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Rows per page (max 100)"),
) -> TrialListResponse:
    """Return a paginated list of trial summaries."""
    filters = FilterQuery(
        country_code=country_code,
        state_code=state_code,
        therapeutic_area=therapeutic_area,
        phase=phase,
        status=status,
        study_type=study_type,
        intervention_type=intervention_type,
        start_date=start_date,
        end_date=end_date,
    )
    return list_trials(db, filters, page=page, page_size=page_size)
