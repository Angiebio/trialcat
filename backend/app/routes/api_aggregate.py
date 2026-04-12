"""GET /api/aggregate — choropleth data for the map.

Returns per-country (or per-US-state) trial counts and enrollment totals
filtered by the standard FilterQuery. Called on initial map render and
whenever filters change.
"""

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import AggregateResponse, FilterQuery
from app.services.stats import aggregate_by_country, aggregate_by_us_state

router = APIRouter(prefix="/api", tags=["aggregate"])


@router.get(
    "/aggregate",
    response_model=AggregateResponse,
    summary="Aggregate trials by country or US state",
    description=(
        "Returns per-group trial counts and total enrollment. Use "
        "`by=country` for the world map choropleth and `by=us_state` "
        "for the US drill-down view. All filter params are optional."
    ),
)
def read_aggregate(
    db: Session = Depends(get_db),
    by: Literal["country", "us_state"] = Query(
        default="country",
        description="Grouping dimension",
    ),
    therapeutic_area: Optional[str] = Query(default=None),
    phase: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    study_type: Optional[str] = Query(default=None),
    intervention_type: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
) -> AggregateResponse:
    """Return per-group trial aggregates for the map."""
    filters = FilterQuery(
        therapeutic_area=therapeutic_area,
        phase=phase,
        status=status,
        study_type=study_type,
        intervention_type=intervention_type,
        start_date=start_date,
        end_date=end_date,
    )

    if by == "us_state":
        return aggregate_by_us_state(db, filters)
    return aggregate_by_country(db, filters)
