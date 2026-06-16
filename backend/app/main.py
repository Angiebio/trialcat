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
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from starlette.responses import HTMLResponse

from app import __version__
from app.config import settings
from app.db import SessionLocal, create_all_tables
from app.routes import (
    aggregate_router,
    filters_router,
    game_router,
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
    # Ensure DB tables exist on startup — no more "no such table" crashes
    # on a fresh deploy with an empty volume.
    create_all_tables()
    logger.info("Database tables verified")
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
app.include_router(game_router)


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


@app.get("/about", response_class=HTMLResponse, tags=["pages"])
async def about(request: Request) -> HTMLResponse:
    """About, data provenance, and how-to-cite page (the scholarly front door)."""
    return templates.TemplateResponse(request=request, name="about.html")


@app.get("/game/rules", response_class=HTMLResponse, tags=["pages"])
async def game_rules(request: Request) -> HTMLResponse:
    """How to play + game terms / leaderboard data practice."""
    return templates.TemplateResponse(request=request, name="game_rules.html")


@app.get("/game", response_class=HTMLResponse, tags=["pages"])
async def game(request: Request) -> HTMLResponse:
    """'Race to Approval' — the satirical clinical-trials sim (v2).

    The map taught what trials look like in aggregate; the game lets you feel
    what it's like to push one through. Same data, two ways of knowing it.
    """
    return templates.TemplateResponse(
        request=request,
        name="game.html",
        context={
            "app_name": settings.app_name,
            "version": __version__,
            "env": settings.app_env,
        },
    )


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


# --- Admin endpoints ---
# Background ETL state — simple dict because we're single-process SQLite anyway.
# No need for Redis/Celery when your whole DB is a single file.
_etl_status: dict = {"running": False, "last_run": None}


def _verify_admin(secret: str) -> None:
    """Check admin secret, raise 403 if invalid."""
    if not settings.admin_secret or secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


@app.post("/admin/etl", tags=["admin"])
async def admin_etl(
    limit: int = Query(default=500, ge=1, le=5000),
    condition: Optional[str] = Query(default=None),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
) -> dict:
    """Trigger a small ETL run (synchronous, up to 5000 trials).

    For quick loads by therapeutic area. For bulk loading everything,
    use /admin/etl/bulk instead.
    """
    _verify_admin(x_admin_secret)

    import time
    from app.etl.loader import load_trials
    from app.services.ctgov_client import CTGovClient

    create_all_tables()
    client = CTGovClient()

    raw_trials: list[dict] = []
    fetch_start = time.monotonic()
    for trial in client.search_studies(condition=condition):
        raw_trials.append(trial)
        if len(raw_trials) >= limit:
            break
    fetch_duration = time.monotonic() - fetch_start

    if not raw_trials:
        return {"status": "empty", "message": "No trials matched the filter"}

    session = SessionLocal()
    try:
        stats = load_trials(session, raw_trials)
        session.commit()
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"ETL load failed: {e}")
    finally:
        session.close()

    return {
        "status": "ok",
        "fetched": len(raw_trials),
        "stats": stats if isinstance(stats, dict) else {"loaded": stats},
        "fetch_seconds": round(fetch_duration, 1),
    }


def _run_bulk_etl(updated_since: Optional[str] = None, batch_size: int = 1000) -> None:
    """Background worker for bulk ETL. Fetches ALL matching trials from CT.gov
    in batches, committing each batch so progress is never lost.

    This is the workhorse — it streams trials from CT.gov, loads them in
    chunks of `batch_size`, and commits after each chunk. If it crashes
    mid-run, you keep everything loaded so far.
    """
    import time
    from app.etl.loader import load_trials
    from app.services.ctgov_client import CTGovClient

    _etl_status["running"] = True
    _etl_status["started_at"] = datetime.now(timezone.utc).isoformat()
    _etl_status["error"] = None
    _etl_status["batches_loaded"] = 0
    _etl_status["total_loaded"] = 0
    _etl_status["total_failed"] = 0

    try:
        create_all_tables()
        client = CTGovClient()

        batch: list[dict] = []
        total_fetched = 0

        for trial in client.search_studies(updated_since=updated_since):
            batch.append(trial)
            total_fetched += 1

            if len(batch) >= batch_size:
                # Commit this batch — progress is never lost
                session = SessionLocal()
                try:
                    stats = load_trials(session, batch)
                    session.commit()
                    loaded = stats.get("loaded", 0) if isinstance(stats, dict) else stats
                    failed = stats.get("failed", 0) if isinstance(stats, dict) else 0
                    _etl_status["total_loaded"] += loaded
                    _etl_status["total_failed"] += failed
                    _etl_status["batches_loaded"] += 1
                    logger.info(
                        "ETL batch %s: loaded=%s failed=%s total_fetched=%s",
                        _etl_status["batches_loaded"], loaded, failed, total_fetched,
                    )
                except Exception as e:
                    session.rollback()
                    logger.exception("ETL batch failed: %s", e)
                    _etl_status["total_failed"] += len(batch)
                finally:
                    session.close()
                batch = []

        # Final partial batch
        if batch:
            session = SessionLocal()
            try:
                stats = load_trials(session, batch)
                session.commit()
                loaded = stats.get("loaded", 0) if isinstance(stats, dict) else stats
                failed = stats.get("failed", 0) if isinstance(stats, dict) else 0
                _etl_status["total_loaded"] += loaded
                _etl_status["total_failed"] += failed
                _etl_status["batches_loaded"] += 1
            except Exception as e:
                session.rollback()
                logger.exception("ETL final batch failed: %s", e)
                _etl_status["total_failed"] += len(batch)
            finally:
                session.close()

        _etl_status["total_fetched"] = total_fetched

    except Exception as e:
        logger.exception("ETL bulk run failed: %s", e)
        _etl_status["error"] = str(e)
    finally:
        _etl_status["running"] = False
        _etl_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        _etl_status["last_run"] = _etl_status["finished_at"]
        logger.info(
            "ETL bulk complete: loaded=%s failed=%s",
            _etl_status.get("total_loaded"), _etl_status.get("total_failed"),
        )


@app.post("/admin/etl/bulk", tags=["admin"])
async def admin_etl_bulk(
    updated_since: Optional[str] = Query(
        default=None,
        description="Only fetch trials updated since this date (MM/DD/YYYY). "
        "Omit to fetch everything.",
    ),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
) -> dict:
    """Kick off a bulk ETL run in a background thread.

    Streams ALL matching trials from CT.gov and loads them in batches of 1000,
    committing each batch. Check progress via GET /admin/etl/status.

    For nightly refresh, pass updated_since with yesterday's date.
    For full initial load, omit updated_since.
    """
    _verify_admin(x_admin_secret)

    if _etl_status.get("running"):
        return {
            "status": "already_running",
            "started_at": _etl_status.get("started_at"),
            "batches_loaded": _etl_status.get("batches_loaded", 0),
            "total_loaded": _etl_status.get("total_loaded", 0),
        }

    import threading
    thread = threading.Thread(
        target=_run_bulk_etl,
        kwargs={"updated_since": updated_since},
        daemon=True,
    )
    thread.start()

    return {
        "status": "started",
        "updated_since": updated_since or "all time",
        "message": "Bulk ETL running in background. Check /admin/etl/status for progress.",
    }


@app.get("/admin/etl/status", tags=["admin"])
async def admin_etl_status(
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
) -> dict:
    """Check the status of a running or completed bulk ETL job."""
    _verify_admin(x_admin_secret)
    return _etl_status


@app.post("/admin/etl/refresh", tags=["admin"])
async def admin_etl_refresh(
    days: int = Query(default=2, ge=1, le=30),
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
) -> dict:
    """Incremental refresh — fetch trials updated in the last N days.

    This is what the nightly cron job calls. Default is 2 days to
    catch anything that landed late in the previous day's window.
    """
    _verify_admin(x_admin_secret)

    if _etl_status.get("running"):
        return {"status": "already_running", "message": "Wait for current ETL to finish"}

    from datetime import timedelta
    since_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%m/%d/%Y")

    import threading
    thread = threading.Thread(
        target=_run_bulk_etl,
        kwargs={"updated_since": since_date},
        daemon=True,
    )
    thread.start()

    return {
        "status": "started",
        "updated_since": since_date,
        "message": f"Refreshing trials updated in the last {days} days.",
    }
