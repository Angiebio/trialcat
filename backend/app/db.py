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
