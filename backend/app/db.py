"""Database connection and session management.

Uses SQLAlchemy 2.0 with the synchronous engine — we don't need async DB
access because SQLite doesn't really have async support anyway, and our
FastAPI handlers can hand off short sync DB work without blocking.

If we ever move to Postgres + real concurrency, swap this out for the async
engine. Every handler that uses `get_db` is already structured to accept
a session dependency so the switch is mechanical.
"""

from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base


def _make_engine():
    """Create the SQLAlchemy engine from settings.

    For SQLite we enable foreign key enforcement (it's off by default in SQLite
    for backwards-compatibility reasons, which is silly for new projects).
    """
    # Ensure the parent directory of the SQLite file exists
    if settings.database_url.startswith("sqlite:///"):
        db_path_str = settings.database_url.replace("sqlite:///", "")
        db_path = Path(db_path_str)
        db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        settings.database_url,
        echo=False,  # set True for SQL debugging
        future=True,
    )

    # Enable foreign key enforcement for SQLite
    if engine.url.drivername.startswith("sqlite"):
        from sqlalchemy import event

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def create_all_tables() -> None:
    """Create all tables defined on Base metadata.

    Called from ETL bootstrap, tests, and first-run code. Idempotent —
    if tables already exist, SQLAlchemy skips them.
    """
    Base.metadata.create_all(bind=engine)


def ensure_columns() -> None:
    """Hand-rolled, idempotent column migrations for a long-lived prod volume.

    create_all() makes new TABLES but never ALTERs an existing one — so a v1
    database (already on the Fly volume with 23k trials) won't grow v2's new
    columns on its own. The map would then 500 on a missing column. This adds
    them by hand: a cheap PRAGMA check, safe to run on every startup.

    The discipline here is 'fail loud, but migrate quietly': a missing column on
    a shipped table is a known, expected gap on upgrade, not a bug — so we close
    it without drama, and log that we did.
    """
    import logging

    from sqlalchemy import text

    log = logging.getLogger("trialcat")
    # (table, column, sqlite_type) added after that table first shipped.
    additions = [
        ("interventions", "product_category", "VARCHAR(48)"),  # v2.1 drill-down
    ]
    with engine.begin() as conn:
        for table, column, coltype in additions:
            rows = list(conn.execute(text(f"PRAGMA table_info({table})")))
            if not rows:
                continue  # table doesn't exist yet — create_all will build it correctly
            existing = {r[1] for r in rows}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"))
                log.info("migration: added %s.%s", table, column)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and ensures cleanup.

    Usage in a route:
        @app.get("/api/stats")
        def stats(db: Session = Depends(get_db)):
            ...
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
