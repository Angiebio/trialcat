"""Aggregation and statistics service.

The business logic behind `/api/stats`, `/api/aggregate`, `/api/trials`,
and `/api/filters`. Takes a FilterQuery, builds the appropriate SQLAlchemy
expression, runs it, and returns primitives or model instances.

Design rule: every function here takes a `Session` explicitly. The route
handlers grab the session via FastAPI's `Depends(get_db)` and pass it
through. This keeps the service testable without FastAPI in scope.

Why not put SQL directly in the route handlers? Because:
1. Aggregation logic is reused across endpoints (e.g., the same filter
   resolver powers stats, aggregate, and trials list)
2. Tests don't need HTTP — they can call service functions directly
3. When we migrate to Postgres + proper window functions, only this module
   changes

SQLite limitation note: we compute medians in Python because SQLite lacks
PERCENTILE_CONT. For a dataset of ~500K trials with typical filter cohorts
of <10K, pulling a rate column into memory and calling statistics.median()
is entirely acceptable. If we grow past that, swap to Postgres.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Select, and_, distinct, func, select
from sqlalchemy.orm import Session

from app.models import Intervention, Location, Trial
from app.schemas.filters import FilterOptions, FilterQuery
from app.schemas.stats import AggregateResponse, AggregateRow, StatsResponse
from app.schemas.trials import TrialListResponse, TrialSummary


# =============================================================================
# Filter resolution — shared by every endpoint
# =============================================================================


def apply_filters(stmt: Select, filters: FilterQuery) -> Select:
    """Attach WHERE conditions from a FilterQuery to an existing select().

    The select() MUST already select from Trial (and optionally join Location
    or Intervention if the filter needs them). This helper handles the
    conditions but not the joins — joining early keeps the call sites honest
    about what tables are in play.
    """
    conditions = []

    if filters.therapeutic_area:
        conditions.append(Trial.therapeutic_area == filters.therapeutic_area)
    if filters.phase:
        conditions.append(Trial.phase == filters.phase)
    if filters.status:
        conditions.append(Trial.overall_status == filters.status)
    if filters.study_type:
        conditions.append(Trial.study_type == filters.study_type)
    if filters.start_date:
        conditions.append(Trial.start_date >= filters.start_date)
    if filters.end_date:
        conditions.append(Trial.start_date <= filters.end_date)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    return stmt


def _needs_location_join(filters: FilterQuery) -> bool:
    """Return True if any filter field requires a Location join."""
    return bool(filters.country_code or filters.state_code)


def _needs_intervention_join(filters: FilterQuery) -> bool:
    # Any of these facets pulls in the Interventions table: the broad type
    # (DRUG/DEVICE) or either device drill-down beneath DEVICE (class, category).
    return bool(
        filters.intervention_type or filters.device_class or filters.product_category
    )


def _apply_intervention_join(stmt: Select, filters: FilterQuery) -> Select:
    """Join Interventions once and apply the type + device-class conditions.

    The single source of truth for the intervention drill-down, shared by
    stats/trials/count and both choropleth aggregates. Two reasons it lives
    here instead of being inlined per call site:
      1. The DEVICE → class drill-down must behave identically everywhere.
      2. When ONLY device_class is set we must NOT emit `type == None` — that
         would silently match nothing. Each branch is applied independently.
    Caller owns the no-double-join contract (this helper joins at most once).
    """
    if not _needs_intervention_join(filters):
        return stmt
    stmt = stmt.join(Intervention, Intervention.trial_nct_id == Trial.nct_id)
    if filters.intervention_type:
        stmt = stmt.where(Intervention.type == filters.intervention_type)
    if filters.device_class:
        stmt = stmt.where(Intervention.device_class_hint == filters.device_class)
    if filters.product_category:
        stmt = stmt.where(Intervention.product_category == filters.product_category)
    return stmt


def _apply_join_filters(stmt: Select, filters: FilterQuery) -> Select:
    """Add joins and location/intervention filters. Use alongside apply_filters."""
    if _needs_location_join(filters):
        stmt = stmt.join(Location, Location.trial_nct_id == Trial.nct_id)
        if filters.country_code:
            stmt = stmt.where(Location.country_code == filters.country_code)
        if filters.state_code:
            stmt = stmt.where(Location.state_code == filters.state_code)

    stmt = _apply_intervention_join(stmt, filters)

    return stmt


# =============================================================================
# Aggregate endpoint (choropleth)
# =============================================================================


def _aggregate_geography(session: Session, filters: FilterQuery,
                         group_by: str) -> AggregateResponse:
    """Aggregate unique (trial identity, geography) pairs, never joined site rows.

    Purpose: the choropleth rows. One contribution per trial per group.
    Contract: rows hold (group_key, distinct trials, summed whole-trial
    enrollment). `total_trials` is the filter cohort, counted once per trial,
    exactly as before this fix, so the sidebar headline keeps its meaning.
    Invariant: adding a second matching site or intervention to a trial changes
    no number here. Two different trials with equal enrollment stay two trials.
    Rationale: enrollment belongs to a trial, not to a site row. The version
    this replaces joined Location and then summed, so a trial with 61 US sites
    added its enrollment to the US 61 times, while its docstring promised "each
    trial contributes once per country". SUM(DISTINCT enrollment) is not a fix
    either: it merges different trials that happen to share a value.
    Failure: unknown geography (NULL key) is excluded from rows, never coerced
    into a bucket. A NULL enrollment stays NULL, never 0.
    Evidence: tests/test_stats_grain.py (pair uniqueness, filter parity,
    extra-site invariance, cohort total).

    These are enrollments of trials with a site in the geography, not patients
    enrolled in that geography. Multinational group totals are not additive.
    """
    key = Location.country_code if group_by == "country" else Location.state_code
    pairs = (select(Trial.nct_id.label("trial_id"), key.label("group_key"))
             .join(Location, Location.trial_nct_id == Trial.nct_id)
             .where(key.isnot(None)))
    # The Location join already exists: apply its filters here exactly once.
    if filters.country_code:
        pairs = pairs.where(Location.country_code == filters.country_code)
    if filters.state_code:
        pairs = pairs.where(Location.state_code == filters.state_code)
    pairs = _apply_intervention_join(pairs, filters)
    pairs = apply_filters(pairs, filters).distinct().subquery()
    statement = (select(pairs.c.group_key, func.count(pairs.c.trial_id),
                        func.sum(Trial.enrollment_count))
                 .join(Trial, Trial.nct_id == pairs.c.trial_id)
                 .group_by(pairs.c.group_key)
                 .order_by(func.count(pairs.c.trial_id).desc(), pairs.c.group_key))
    rows = [AggregateRow(group_key=key, trial_count=int(count),
                         total_enrollment=int(total) if total is not None else None)
            for key, count, total in session.execute(statement).all()]
    # The headline is the cohort, not the union of groups. A trial with no
    # mapped site still matched the user's filters, and the sidebar has always
    # counted it. Changing that meaning would be an API contract change riding
    # along with an arithmetic fix, so it stays as it was (the schema
    # description now says so). Evidence: test_total_trials_is_the_cohort.
    total = _count_distinct_trials(session, filters)
    return AggregateResponse(group_by=group_by, rows=rows, total_trials=total,
                             generated_at=datetime.now(timezone.utc))


def aggregate_by_country(session: Session, filters: FilterQuery) -> AggregateResponse:
    """Count each matching trial once per country containing a matching site."""
    return _aggregate_geography(session, filters, "country")


def aggregate_by_us_state(session: Session, filters: FilterQuery) -> AggregateResponse:
    """Count each matching trial once per US state containing a matching site."""
    us_filters = filters.model_copy(update={"country_code": "US"})
    return _aggregate_geography(session, us_filters, "us_state")


# =============================================================================
# Stats (popup) endpoint
# =============================================================================


def compute_stats(session: Session, filters: FilterQuery) -> StatsResponse:
    """Compute the summary stats for a filter cohort.

    Returns counts, total enrollment, and the distribution of approximate
    enrollment rates (min/median/max + sample size so the UI can decide
    whether to show them). Also returns average months_enrolling.
    """
    # Resolve membership at trial grain before any arithmetic. Location and
    # intervention joins decide WHO is in the cohort; they must never decide
    # HOW MANY TIMES a trial is counted. This is the number in the country
    # popup, so the old join-then-sum inflated exactly the figure people read.
    # Evidence: tests/test_stats_grain.py::test_stats_keep_trial_identity.
    ids = _apply_join_filters(select(Trial.nct_id), filters)
    ids = apply_filters(ids, filters).distinct().subquery()
    eligible = Trial.nct_id.in_(select(ids.c.nct_id))
    trial_count = int(session.scalar(select(func.count()).select_from(ids)) or 0)

    # Total enrollment
    total_enr_stmt = select(func.sum(Trial.enrollment_count)).select_from(Trial)
    total_enr_stmt = total_enr_stmt.where(eligible)
    total_enrollment = session.execute(total_enr_stmt).scalar()

    # Pull rate values into Python for median. SQLite has no PERCENTILE_CONT.
    rate_stmt = select(Trial.approx_enrollment_rate_per_month).select_from(Trial)
    rate_stmt = rate_stmt.where(eligible)
    rate_stmt = rate_stmt.where(Trial.approx_enrollment_rate_per_month.isnot(None))
    # Preserve equal rate values from different trials: each is one observation.
    # The old line here was `.distinct()` under a comment saying "distinct on
    # nct_id", but the query selected only the rate column, so it deduplicated
    # VALUES: two trials at 10 pts/mo became one, and the median moved. The
    # `eligible` filter above already gives one row per trial, so nothing is
    # deduplicated here at all. Evidence: test_stats_keep_trial_identity.

    rates = [r[0] for r in session.execute(rate_stmt).all()]
    rate_min = min(rates) if rates else None
    rate_max = max(rates) if rates else None
    rate_median = statistics.median(rates) if rates else None

    # Average months enrolling
    months_stmt = select(func.avg(Trial.months_enrolling)).select_from(Trial)
    months_stmt = months_stmt.where(eligible)
    months_stmt = months_stmt.where(Trial.months_enrolling.isnot(None))
    avg_months = session.execute(months_stmt).scalar()

    return StatsResponse(
        filter_applied=filters,
        trial_count=trial_count,
        total_enrollment=int(total_enrollment) if total_enrollment is not None else None,
        approx_rate_min=round(rate_min, 2) if rate_min is not None else None,
        approx_rate_median=round(rate_median, 2) if rate_median is not None else None,
        approx_rate_max=round(rate_max, 2) if rate_max is not None else None,
        approx_rate_sample_size=len(rates),
        avg_months_enrolling=round(avg_months, 2) if avg_months is not None else None,
        generated_at=datetime.now(timezone.utc),
    )


# =============================================================================
# Trials list endpoint
# =============================================================================


def list_trials(
    session: Session,
    filters: FilterQuery,
    page: int = 1,
    page_size: int = 20,
) -> TrialListResponse:
    """Return a paginated list of trial summaries.

    Pagination is 1-indexed for user-friendliness. page_size is capped at 100
    to prevent accidental "download my whole database" requests.
    """
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    total = _count_distinct_trials(session, filters)

    base_stmt = select(Trial).distinct()
    base_stmt = _apply_join_filters(base_stmt, filters)
    base_stmt = apply_filters(base_stmt, filters)
    base_stmt = base_stmt.order_by(Trial.start_date.desc().nulls_last(), Trial.nct_id)
    base_stmt = base_stmt.offset(offset).limit(page_size)

    trials = session.scalars(base_stmt).all()

    # One extra query to get location counts per trial in the page
    summaries: list[TrialSummary] = []
    for t in trials:
        loc_count = session.scalar(
            select(func.count(Location.id)).where(Location.trial_nct_id == t.nct_id)
        )
        summaries.append(
            TrialSummary(
                nct_id=t.nct_id,
                brief_title=t.brief_title,
                overall_status=t.overall_status,
                phase=t.phase,
                study_type=t.study_type,
                therapeutic_area=t.therapeutic_area,
                lead_sponsor_name=t.lead_sponsor_name,
                lead_sponsor_class=t.lead_sponsor_class,
                enrollment_count=t.enrollment_count,
                start_date=t.start_date,
                primary_completion_date=t.primary_completion_date,
                approx_enrollment_rate_per_month=t.approx_enrollment_rate_per_month,
                location_count=int(loc_count or 0),
            )
        )

    total_pages = (total + page_size - 1) // page_size if total else 0

    return TrialListResponse(
        trials=summaries,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        generated_at=datetime.now(timezone.utc),
    )


# =============================================================================
# Filter options endpoint
# =============================================================================


def get_filter_options(session: Session) -> FilterOptions:
    """Return the unique values for each filterable field.

    This powers dropdowns in the frontend. We run 6 small DISTINCT queries
    — tiny even on a 500K trial DB because each grouping is small.
    """

    def _distinct_strs(col) -> list[str]:
        rows = session.execute(
            select(col).where(col.isnot(None)).distinct().order_by(col)
        ).all()
        return [r[0] for r in rows if r[0]]

    # Group product categories by intervention type so the UI can show only the
    # relevant drill-down values for the selected type (device families when
    # DEVICE is picked, drug/pharm classes when DRUG is picked). One small query.
    pc_rows = session.execute(
        select(Intervention.type, Intervention.product_category)
        .where(Intervention.product_category.isnot(None))
        .where(Intervention.type.isnot(None))
        .distinct()
        .order_by(Intervention.type, Intervention.product_category)
    ).all()
    by_type: dict[str, list[str]] = {}
    for itype, pcat in pc_rows:
        by_type.setdefault(itype, []).append(pcat)

    return FilterOptions(
        therapeutic_areas=_distinct_strs(Trial.therapeutic_area),
        phases=_distinct_strs(Trial.phase),
        statuses=_distinct_strs(Trial.overall_status),
        study_types=_distinct_strs(Trial.study_type),
        intervention_types=_distinct_strs(Intervention.type),
        device_classes=_distinct_strs(Intervention.device_class_hint),
        product_categories=_distinct_strs(Intervention.product_category),
        product_categories_by_type=by_type,
        countries=_distinct_strs(Location.country_code),
    )


# =============================================================================
# Internal helpers
# =============================================================================


def _count_distinct_trials(session: Session, filters: FilterQuery) -> int:
    """Return count(DISTINCT Trial.nct_id) respecting the current filters.

    Must use DISTINCT because a Trial with 61 US sites would otherwise be
    counted 61 times when we join Location for a country_code filter.
    """
    stmt = select(func.count(distinct(Trial.nct_id))).select_from(Trial)
    stmt = _apply_join_filters(stmt, filters)
    stmt = apply_filters(stmt, filters)
    return int(session.execute(stmt).scalar() or 0)
