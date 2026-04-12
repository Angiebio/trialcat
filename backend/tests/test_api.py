"""End-to-end API tests using FastAPI's TestClient.

These tests spin up the full app with an in-memory SQLite DB loaded from
the fixture data, then exercise every endpoint via real HTTP calls. If
FastAPI routing, dependency injection, Pydantic validation, or the service
layer is broken, these fail.

This is the tightest integration we can test without deploying.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.etl.loader import load_trials
from app.main import app
from app.models import Base


@pytest.fixture
def api_client(ctgov_samples):
    """Create a TestClient with a fresh in-memory DB loaded with fixture trials.

    Overrides the `get_db` dependency so the app hits our test DB instead of
    the configured SQLite file. Uses StaticPool because SQLite `:memory:`
    databases are per-connection by default — without StaticPool, every
    sessionmaker() call gets a fresh empty DB and our fixture load is lost.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    # Load all fixture trials into the test DB
    with TestingSessionLocal() as session:
        load_trials(session, ctgov_samples)
        session.commit()

    # Override the get_db dependency in the FastAPI app
    def _override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# =============================================================================
# Health / version (smoke tests, Phase 1 coverage)
# =============================================================================


def test_health(api_client):
    resp = api_client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "trialcat"


def test_version(api_client):
    resp = api_client.get("/api/version")
    assert resp.status_code == 200
    body = resp.json()
    assert body["app"] == "trialcat"
    assert "version" in body


# =============================================================================
# /api/filters
# =============================================================================


class TestFiltersEndpoint:
    def test_returns_all_categories(self, api_client):
        resp = api_client.get("/api/filters")
        assert resp.status_code == 200
        body = resp.json()
        assert "therapeutic_areas" in body
        assert "phases" in body
        assert "statuses" in body
        assert "study_types" in body
        assert "intervention_types" in body
        assert "countries" in body

    def test_populated_from_fixtures(self, api_client):
        resp = api_client.get("/api/filters")
        body = resp.json()
        # Our fixtures include at least these therapeutic areas
        assert any("Ophthalmology" in a for a in body["therapeutic_areas"])
        # PHASE3 is heavily represented in fixtures
        assert "PHASE3" in body["phases"]
        # All fixtures have US sites
        assert "US" in body["countries"]


# =============================================================================
# /api/aggregate
# =============================================================================


class TestAggregateEndpoint:
    def test_by_country_default(self, api_client):
        resp = api_client.get("/api/aggregate?by=country")
        assert resp.status_code == 200
        body = resp.json()
        assert body["group_by"] == "country"
        assert len(body["rows"]) > 0
        # US should be present in our fixtures
        us_row = next((r for r in body["rows"] if r["group_key"] == "US"), None)
        assert us_row is not None
        assert us_row["trial_count"] >= 1

    def test_by_us_state(self, api_client):
        resp = api_client.get("/api/aggregate?by=us_state")
        assert resp.status_code == 200
        body = resp.json()
        assert body["group_by"] == "us_state"
        # At least one state should be represented
        assert len(body["rows"]) > 0
        # Every row should have a 2-letter state code
        for row in body["rows"]:
            assert len(row["group_key"]) == 2

    def test_aggregate_with_therapeutic_area_filter(self, api_client):
        resp = api_client.get("/api/aggregate?by=country&therapeutic_area=Ophthalmology")
        assert resp.status_code == 200
        body = resp.json()
        # With the filter we should have fewer trials than without
        resp_all = api_client.get("/api/aggregate?by=country")
        assert body["total_trials"] <= resp_all.json()["total_trials"]

    def test_aggregate_with_phase_filter(self, api_client):
        resp = api_client.get("/api/aggregate?by=country&phase=PHASE3")
        assert resp.status_code == 200
        assert resp.json()["total_trials"] > 0


# =============================================================================
# /api/stats
# =============================================================================


class TestStatsEndpoint:
    def test_no_filter_returns_all(self, api_client):
        resp = api_client.get("/api/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trial_count"] > 0
        assert body["total_enrollment"] is not None
        assert "approx_rate_sample_size" in body

    def test_filter_by_country(self, api_client):
        resp = api_client.get("/api/stats?country_code=US")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trial_count"] > 0
        assert body["filter_applied"]["country_code"] == "US"

    def test_filter_by_therapeutic_area(self, api_client):
        resp = api_client.get("/api/stats?therapeutic_area=Ophthalmology")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trial_count"] >= 1

    def test_impossible_filter_returns_zero(self, api_client):
        resp = api_client.get("/api/stats?country_code=XX")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trial_count"] == 0
        assert body["approx_rate_sample_size"] == 0

    def test_rate_distribution_present_when_trials_match(self, api_client):
        resp = api_client.get("/api/stats")
        body = resp.json()
        # With all fixture trials, we should have at least a few rates
        if body["approx_rate_sample_size"] > 0:
            assert body["approx_rate_min"] is not None
            assert body["approx_rate_median"] is not None
            assert body["approx_rate_max"] is not None
            assert body["approx_rate_min"] <= body["approx_rate_median"] <= body["approx_rate_max"]


# =============================================================================
# /api/trials
# =============================================================================


class TestTrialsEndpoint:
    def test_list_default_pagination(self, api_client):
        resp = api_client.get("/api/trials")
        assert resp.status_code == 200
        body = resp.json()
        assert "trials" in body
        assert body["page"] == 1
        assert body["page_size"] == 20
        assert body["total"] > 0

    def test_list_returns_summary_fields(self, api_client):
        resp = api_client.get("/api/trials")
        body = resp.json()
        assert len(body["trials"]) > 0
        t = body["trials"][0]
        assert t["nct_id"].startswith("NCT")
        assert "brief_title" in t
        assert "location_count" in t
        assert t["location_count"] >= 0

    def test_list_with_phase_filter(self, api_client):
        resp = api_client.get("/api/trials?phase=PHASE3")
        assert resp.status_code == 200
        body = resp.json()
        # Every returned trial should be phase 3
        for t in body["trials"]:
            assert t["phase"] == "PHASE3"

    def test_list_page_size_cap(self, api_client):
        resp = api_client.get("/api/trials?page_size=500")
        # Validator should reject, returning 422
        assert resp.status_code == 422

    def test_list_pagination_metadata(self, api_client):
        resp = api_client.get("/api/trials?page=1&page_size=2")
        body = resp.json()
        assert body["page_size"] == 2
        assert len(body["trials"]) <= 2
        if body["total"] > 2:
            assert body["total_pages"] >= 2

    def test_list_empty_filter_ok(self, api_client):
        """Filter that matches nothing should return empty list, not error."""
        resp = api_client.get("/api/trials?country_code=XX")
        assert resp.status_code == 200
        body = resp.json()
        assert body["trials"] == []
        assert body["total"] == 0
