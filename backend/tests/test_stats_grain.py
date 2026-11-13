"""Trial-grain regressions for the stats and choropleth aggregates.

Entirely synthetic, in-memory fixtures. No ClinicalTrials.gov data.

Why this file exists: until November 2026, stats.py summed enrollment after
joining sites (a trial with 61 US sites counted 61 times toward the US) and
deduplicated rate VALUES while a comment said it deduplicated trial IDs. Both
bugs passed the existing suite, because no fixture had a trial with two
matching sites or two trials with the same rate. These fixtures have both.

The minimum fixture (A, B, C): enrollment 100, 100, 300 and rate 10, 10, 30.
A has two US/MA sites, one DE site and two DEVICE interventions. Correct
answers: 3 trials, 500 enrolled, rate median 10 from 3 observations. The old
code gave 600 and a median of 20 from 2.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models import Base, Intervention, Location, Trial
from app.schemas.filters import FilterQuery
from app.services.stats import aggregate_by_country, aggregate_by_us_state, compute_stats


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for ident, enrollment, rate, months in [("A", 100, 10, 10),
                                                ("B", 100, 10, 20),
                                                ("C", 300, 30, 30)]:
            session.add(Trial(nct_id=ident, enrollment_count=enrollment,
                              approx_enrollment_rate_per_month=rate, months_enrolling=months))
        session.flush()
        for ident, country, state in [("A", "US", "MA"), ("A", "US", "MA"),
                                      ("A", "DE", None), ("B", "US", "MA"),
                                      ("C", "US", "CA")]:
            session.add(Location(trial_nct_id=ident, country_code=country, state_code=state))
        for ident in ["A", "A", "B", "C"]:
            session.add(Intervention(trial_nct_id=ident, type="DEVICE"))
        session.flush()
        yield session
    engine.dispose()


def _snapshot(db, filters):
    """Every number the map and popup show for one filter, as plain tuples."""
    stats = compute_stats(db, filters)
    countries = aggregate_by_country(db, filters)
    states = aggregate_by_us_state(db, filters)
    return (
        (stats.trial_count, stats.total_enrollment, stats.approx_rate_sample_size,
         stats.approx_rate_median, stats.avg_months_enrolling),
        [(r.group_key, r.trial_count, r.total_enrollment) for r in countries.rows],
        countries.total_trials,
        [(r.group_key, r.trial_count, r.total_enrollment) for r in states.rows],
        states.total_trials,
    )


def test_stats_keep_trial_identity(db):
    # The popup for "US, DEVICE". A's second US site and second DEVICE
    # intervention must not count A twice; A and B sharing rate 10 must stay
    # two observations, so the median is 10, not the 20 the old code returned.
    stats = compute_stats(db, FilterQuery(country_code="US", intervention_type="DEVICE"))
    assert stats.trial_count == 3
    assert stats.total_enrollment == 500
    assert stats.approx_rate_sample_size == 3
    assert stats.approx_rate_median == 10
    assert stats.avg_months_enrolling == 20


def test_country_pairs_are_unique_and_multinational_totals_nonadditive(db):
    # A runs in the US and DE, so its whole-trial 100 appears in both rows.
    # That is correct for "enrollment of trials with a site here", and it is
    # why the rows must never be summed into a world total.
    result = aggregate_by_country(db, FilterQuery(intervention_type="DEVICE"))
    rows = {r.group_key: r for r in result.rows}
    assert rows["US"].trial_count == 3
    assert rows["US"].total_enrollment == 500
    assert rows["DE"].trial_count == 1
    assert rows["DE"].total_enrollment == 100
    assert result.total_trials == 3


def test_geographic_filters_match_groups(db):
    filters = FilterQuery(country_code="US", state_code="MA", intervention_type="DEVICE")
    countries = aggregate_by_country(db, filters)
    states = aggregate_by_us_state(db, filters)
    assert [(r.group_key, r.trial_count, r.total_enrollment) for r in countries.rows] == [("US", 2, 200)]
    assert [(r.group_key, r.trial_count, r.total_enrollment) for r in states.rows] == [("MA", 2, 200)]
    assert countries.total_trials == states.total_trials == 2


def test_extra_matching_site_or_intervention_changes_nothing(db):
    # The invariant stated in the stats.py docstrings, tested directly: a third
    # US/MA site and a third DEVICE intervention for A leave every number the
    # map and popup show exactly as it was.
    for filters in (FilterQuery(), FilterQuery(country_code="US"),
                    FilterQuery(country_code="US", state_code="MA", intervention_type="DEVICE")):
        before = _snapshot(db, filters)
        db.add(Location(trial_nct_id="A", country_code="US", state_code="MA"))
        db.add(Intervention(trial_nct_id="A", type="DEVICE"))
        db.flush()
        assert _snapshot(db, filters) == before


def test_missing_and_equal_values_remain_distinct_trials(db):
    db.add(Trial(nct_id="D", enrollment_count=None, approx_enrollment_rate_per_month=None))
    db.flush()
    stats = compute_stats(db, FilterQuery())
    assert stats.trial_count == 4
    assert stats.total_enrollment == 500
    assert stats.approx_rate_sample_size == 3
    assert stats.approx_rate_median == 10
    assert stats.avg_months_enrolling == 20


def test_total_trials_is_the_cohort(db):
    # D matches the (empty) filter but has no site. The sidebar headline has
    # always counted the cohort, so D is counted, while no country row holds it.
    db.add(Trial(nct_id="D", enrollment_count=50))
    db.flush()
    result = aggregate_by_country(db, FilterQuery())
    assert result.total_trials == 4
    assert sum(1 for r in result.rows if r.group_key == "US") == 1
    assert {r.group_key for r in result.rows} == {"US", "DE"}
    # The US state view's cohort is trials with a US site: A, B and C.
    assert aggregate_by_us_state(db, FilterQuery()).total_trials == 3


def test_empty_cohort_keeps_unknown_distinct_from_zero(db):
    stats = compute_stats(db, FilterQuery(country_code="JP"))
    assert stats.trial_count == stats.approx_rate_sample_size == 0
    assert stats.total_enrollment is None
    assert stats.approx_rate_median is None
    assert stats.avg_months_enrolling is None
