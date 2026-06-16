"""GET /api/stats — summary statistics for a filter cohort.

Returns trial count, total enrollment, and the approximate enrollment rate
distribution (min/median/max + sample size) for the given filter. This is
the data behind the popup that appears when a user clicks a country on
the map.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import FilterQuery, StatsResponse
from app.services.stats import compute_stats

router = APIRouter(prefix="/api", tags=["stats"])


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Summary stats for a filter cohort",
    description=(
        "Returns trial count, total enrollment, and the distribution of "
        "approximate enrollment rates (min/median/max) for the trials "
        "matching the filter. Note: rates are APPROXIMATE and should be "
        "labeled as such in any UI that displays them."
    ),
)
def read_stats(
    db: Session = Depends(get_db),
    country_code: Optional[str] = Query(default=None, min_length=2, max_length=3),
    state_code: Optional[str] = Query(default=None, min_length=2, max_length=2),
    therapeutic_area: Optional[str] = Query(default=None),
    phase: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    study_type: Optional[str] = Query(default=None),
    intervention_type: Optional[str] = Query(default=None),
    device_class: Optional[str] = Query(default=None),
    product_category: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
) -> StatsResponse:
    """Return summary stats for the filter cohort."""
    filters = FilterQuery(
        country_code=country_code,
        state_code=state_code,
        therapeutic_area=therapeutic_area,
        phase=phase,
        status=status,
        study_type=study_type,
        intervention_type=intervention_type,
        device_class=device_class,
        product_category=product_category,
        start_date=start_date,
        end_date=end_date,
    )
    return compute_stats(db, filters)
