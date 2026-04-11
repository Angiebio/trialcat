"""ETL loader tests — verify parse → upsert → query roundtrip against fixtures.

Uses an in-memory SQLite DB (from conftest.db_session) so each test gets
a clean slate. This is the integration point between the parser and the
database: if tables join correctly, if foreign keys enforce, if the upsert
path works.
"""

from sqlalchemy import func, select

from app.etl.loader import load_trial, load_trials
from app.models import Condition, Intervention, Location, Outcome, Trial


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
        stats = load_trials(db_session, ctgov_samples)
        db_session.commit()

        # New LoadStats contract (Phase 2.5)
        assert stats["loaded"] == len(ctgov_samples)
        assert stats["failed"] == 0
        assert stats["errors"] == []
        assert stats["duration_s"] >= 0

        # Verify DB contains everything
        trial_count = db_session.scalar(select(func.count(Trial.nct_id)))
        assert trial_count == len(ctgov_samples)

        # Every trial should have at least one condition linked
        for raw in ctgov_samples:
            nct = raw["protocolSection"]["identificationModule"]["nctId"]
            t = db_session.scalar(select(Trial).where(Trial.nct_id == nct))
            assert t is not None
            assert len(t.conditions) > 0, f"Trial {nct} has no conditions"


class TestLoadFaultTolerance:
    """load_trials must log-and-continue on per-trial failure, not crash the batch."""

    def test_malformed_trial_is_recorded_not_raised(self, db_session, ctgov_samples):
        # Inject a deliberately malformed "trial" between two good ones
        malformed = {"protocolSection": {"identificationModule": {}}}  # missing nctId
        batch = [ctgov_samples[0], malformed, ctgov_samples[1]]

        stats = load_trials(db_session, batch)
        db_session.commit()

        # 2 good trials loaded, 1 bad trial skipped but recorded
        assert stats["loaded"] == 2
        assert stats["failed"] == 1
        assert len(stats["errors"]) == 1
        assert stats["errors"][0]["error_type"] in ("ValueError", "KeyError", "AttributeError")

    def test_error_list_caps_at_max_errors_kept(self, db_session):
        # Build a batch of N malformed trials with max_errors_kept=3
        bad = [{"protocolSection": {"identificationModule": {}}} for _ in range(10)]
        stats = load_trials(db_session, bad, max_errors_kept=3)

        assert stats["loaded"] == 0
        assert stats["failed"] == 10
        # Only the first 3 errors were kept in the list
        assert len(stats["errors"]) == 3


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
