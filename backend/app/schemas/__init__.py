"""Pydantic request/response schemas for the API layer.

Every endpoint takes a typed request model and returns a typed response
model. Schemas live here (not in routes/) so they can be reused across
handlers, documented via FastAPI's auto OpenAPI, and imported by tests
without pulling in the whole route module.

Rule of thumb: if it flows over the wire, it has a schema here.
"""

from app.schemas.filters import FilterOptions, FilterQuery
from app.schemas.stats import AggregateResponse, AggregateRow, StatsResponse
from app.schemas.trials import TrialListResponse, TrialSummary

__all__ = [
    "FilterQuery",
    "FilterOptions",
    "AggregateRow",
    "AggregateResponse",
    "StatsResponse",
    "TrialSummary",
    "TrialListResponse",
]
