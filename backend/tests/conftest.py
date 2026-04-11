"""Pytest shared fixtures.

Loads the saved CT.gov sample data once per session and exposes individual
trials by NCT ID for test use. Also provides the in-memory SQLite session
fixture that any test touching the DB can pull in.

This is the foundation of our "synthetic but real" testing approach — we
test against actual API data captured to disk.
"""

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ctgov_sample.json"


@pytest.fixture(scope="session")
def ctgov_samples() -> list[dict]:
    """All sample CT.gov trial dicts loaded from the fixture file."""
    if not FIXTURE_PATH.exists():
        pytest.fail(
            f"Missing fixture file at {FIXTURE_PATH}. "
            f"Run `python backend/tests/fixtures/_fetch_samples.py` to create it."
        )
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def samples_by_nct(ctgov_samples) -> dict[str, dict]:
    """Index of sample trials keyed by NCT ID for targeted tests."""
    return {
        s["protocolSection"]["identificationModule"]["nctId"]: s
        for s in ctgov_samples
    }


@pytest.fixture
def db_session():
    """Fresh in-memory SQLite database per test function.

    Enables foreign key enforcement. Each test gets a clean slate so they
    can't interfere with each other — the cost of creating an in-memory
    SQLite DB is negligible (<1ms) so we don't bother with transaction
    rollback tricks.
    """
    from app.models import Base

    engine = create_engine("sqlite:///:memory:", echo=False, future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
