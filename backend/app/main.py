"""trialcat FastAPI entry point.

This is the hello-world skeleton for Phase 1. It does three things:
1. Serves the static frontend (index.html, JS, CSS)
2. Exposes a /health endpoint so Fly.io (and us) can tell if the app is alive
3. Includes a /api/version endpoint so we always know what's deployed

Future phases layer on: /api/stats, /api/aggregate, /api/trials, /api/nl/*.
Each endpoint is small, typed, and fail-loud — the Cairn principle that
structure is more valuable than cleverness applies here too.
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse

from app import __version__
from app.config import settings
from app.routes import (
    aggregate_router,
    filters_router,
    stats_router,
    trials_router,
)

# --- Logging setup ---
# Configure at module import so even startup errors get formatted correctly.
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S%z",
)
logger = logging.getLogger("trialcat")


# --- Lifespan handler ---
# Runs once at startup and once at shutdown. Great place for DB warmup,
# cache preload, or verifying we can reach upstream services. For now it
# just announces we're alive so the logs have a clear start-of-run marker.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Structured startup/shutdown — every journey needs a clear beginning and end."""
    logger.info(
        "trialcat starting: env=%s version=%s",
        settings.app_env,
        __version__,
    )
    yield
    logger.info("trialcat shutting down")


# --- App instance ---
app = FastAPI(
    title="trialcat",
    description="Clinical trial enrollment intelligence, visualized.",
    version=__version__,
    lifespan=lifespan,
    # OpenAPI docs stay available in dev, hidden in prod (toggle via env later)
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
)


# --- Static files + templates ---
# We mount the whole frontend/static directory at /static so CSS, JS, GeoJSON,
# and images are all accessible without custom routes per asset type.
# Paths are resolved from the repo root so they work whether we run from
# /app (inside Docker) or from the project root (local dev).
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = REPO_ROOT / "frontend" / "static"
TEMPLATES_DIR = REPO_ROOT / "frontend" / "templates"

# Create dirs if missing so first-run doesn't crash on a fresh clone
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# --- API routers ---
# Each group of endpoints lives in its own module under app.routes.
# Mounting them here keeps main.py as a readable "what's in this app" index.
app.include_router(filters_router)
app.include_router(aggregate_router)
app.include_router(stats_router)
app.include_router(trials_router)


# --- Routes ---


@app.get("/", response_class=HTMLResponse, tags=["pages"])
async def index(request: Request) -> HTMLResponse:
    """Serve the main map page (Phase 4 will populate this with Leaflet)."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.app_name,
            "version": __version__,
            "env": settings.app_env,
        },
    )


@app.get("/terms", response_class=HTMLResponse, tags=["pages"])
async def terms(request: Request) -> HTMLResponse:
    """Terms of use and disclaimer page."""
    return templates.TemplateResponse(request=request, name="terms.html")


@app.get("/health", tags=["system"])
async def health() -> JSONResponse:
    """Liveness probe. Fly.io (and UptimeRobot) will hit this to confirm the app is alive.

    Kept deliberately simple: no DB check, no upstream check. If this endpoint
    responds, the Python process is up and routing works. Readiness probes
    (DB ready, etc.) will be a separate /ready endpoint in a later phase.
    """
    return JSONResponse(
        {
            "status": "ok",
            "app": settings.app_name,
            "version": __version__,
            "env": settings.app_env,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


@app.get("/api/version", tags=["system"])
async def version() -> dict:
    """Machine-readable version endpoint for deployment verification.

    Having this separate from /health means we can query 'what's deployed'
    without triggering whatever health check logic exists.
    """
    return {
        "app": settings.app_name,
        "version": __version__,
        "env": settings.app_env,
    }
