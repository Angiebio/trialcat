"""GET /api/filters — the dropdown options for the UI.

Returns distinct values present in the database for each filter field.
This endpoint powers the frontend's filter controls so they stay in sync
with whatever data has actually been loaded.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import FilterOptions
from app.services.stats import get_filter_options

router = APIRouter(prefix="/api", tags=["filters"])


@router.get(
    "/filters",
    response_model=FilterOptions,
    summary="Get available filter values",
    description=(
        "Returns the distinct values present in the current database for "
        "each filter field. Used to populate dropdown menus in the frontend."
    ),
)
def read_filters(db: Session = Depends(get_db)) -> FilterOptions:
    """Return distinct values for each filterable field."""
    return get_filter_options(db)
