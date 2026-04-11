"""ETL loader tests — verify parse → upsert → query roundtrip against fixtures.

Uses an in-memory SQLite DB so each test gets a clean slate. This is the
integration point between the parser and the database: if tables join
correctly, if foreign keys enforce, if the upsert path works.
"""

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.etl.loader import load_trial, load_trials
from app.models import Base, Condition, Intervention, Location, Outcome, Trial


@pytest.fixture
def db_session():
    """Fresh in-memory SQLite database for each test function."""
    engine = create_engine("sqlite:///:memory:", echo=False, future=True)
    # Enable FK enforcement
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class TestLoadSingleTrial:
    def test_load_vegf_trap_eye(self, db_session, samples_by_nct):
        raw = samples_by_nct["NCT00943072"]
        trial = load_trial(db_session, raw)
        db_session.commit()

        # Trial row
        assert trial.nct_id == "NCT00943072"
        assert trial.enrollment_count == 189
        assert trial.therapeutic_area == "Ophthalmology"

        # Locations came through with ISO codes
        locs = db_session.scalars(
            select(Location).where(Location.trial_nct_id == trial.nct_id)
        ).all()
        assert len(locs) == 61
        us_locs = [l for l in locs if l.country_code == "US"]
        assert len(us_locs) > 0

        # At least one location has geo coordinates
        with_geo = [l for l in locs if l.lat is not None]
        assert len(with_geo) > 0

        # Interventions
        ivs = db_session.scalars(
            select(Intervention).where(Intervention.trial_nct_id == trial.nct_id)
        ).all()
        assert len(ivs) >= 1

        # At least one primary outcome
        primary_outs = db_session.scalars(
            select(Outcome).where(
                Outcome.trial_nct_id == trial.nct_id,
                Outcome.is_primary == True,
            )
        ).all()
        assert len(primary_outs) >= 1


class TestLoadManyTrials:
    def test_load_all_samples(self, db_session, ctgov_samples):
        count = load_trials(db_session, ctgov_samples)
        db_session.commit()

        assert count == len(ctgov_samples)

        # Verify DB contains everything
        trial_count = db_session.scalar(select(func.count(Trial.nct_id)))
        assert trial_count == len(ctgov_samples)

        # Every trial should have at least one condition linked
        for raw in ctgov_samples:
            nct = raw["protocolSection"]["identificationModule"]["nctId"]
            t = db_session.scalar(select(Trial).where(Trial.nct_id == nct))
            assert t is not None
            assert len(t.conditions) > 0, f"Trial {nct} has no conditions"


class TestLoadIsIdempotent:
    def test_loading_twice_does_not_duplicate(self, db_session, samples_by_nct):
        raw = samples_by_nct["NCT00943072"]

        # First load
        load_trial(db_session, raw)
        db_session.commit()

        # Count dependent rows
        loc_count_1 = db_session.scalar(
            select(func.count(Location.id)).where(Location.trial_nct_id == "NCT00943072")
        )
        int_count_1 = db_session.scalar(
            select(func.count(Intervention.id)).where(
                Intervention.trial_nct_id == "NCT00943072"
            )
        )

        # Second load of the same raw trial
        load_trial(db_session, raw)
        db_session.commit()

        # Counts should be identical (not doubled)
        loc_count_2 = db_session.scalar(
            select(func.count(Location.id)).where(Location.trial_nct_id == "NCT00943072")
        )
        int_count_2 = db_session.scalar(
            select(func.count(Intervention.id)).where(
                Intervention.trial_nct_id == "NCT00943072"
            )
        )

        assert loc_count_1 == loc_count_2
        assert int_count_1 == int_count_2

        # Still exactly one trial
        trial_count = db_session.scalar(select(func.count(Trial.nct_id)))
        assert trial_count == 1


class TestConditionDedup:
    def test_shared_conditions_are_deduped(self, db_session, ctgov_samples):
        load_trials(db_session, ctgov_samples)
        db_session.commit()

        # Total Conditions should be <= sum of raw condition counts,
        # because common ones (e.g., "Cardiovascular Diseases") are shared
        total_raw_conditions = 0
        for raw in ctgov_samples:
            proto = raw["protocolSection"]
            total_raw_conditions += len(
                (proto.get("conditionsModule") or {}).get("conditions") or []
            )
            total_raw_conditions += len(
                (raw.get("derivedSection", {}).get("conditionBrowseModule") or {}).get("meshes") or []
            )

        cond_count = db_session.scalar(select(func.count(Condition.id)))
        assert cond_count <= total_raw_conditions
        assert cond_count > 0
