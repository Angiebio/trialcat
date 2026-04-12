"""API route handlers.

Each module registers an APIRouter with a logical group of endpoints:
- api_filters: GET /api/filters
- api_aggregate: GET /api/aggregate
- api_stats: GET /api/stats
- api_trials: GET /api/trials

Routers get mounted into the main FastAPI app in main.py. Keeping them
modular means we can test each endpoint family in isolation and add
middleware (auth, rate limiting) selectively later.
"""

from app.routes.api_aggregate import router as aggregate_router
from app.routes.api_filters import router as filters_router
from app.routes.api_stats import router as stats_router
from app.routes.api_trials import router as trials_router

__all__ = [
    "aggregate_router",
    "filters_router",
    "stats_router",
    "trials_router",
]
