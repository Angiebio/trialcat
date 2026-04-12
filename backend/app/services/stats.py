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
    return bool(filters.intervention_type)


def _apply_join_filters(stmt: Select, filters: FilterQuery) -> Select:
    """Add joins and location/intervention filters. Use alongside apply_filters."""
    if _needs_location_join(filters):
        stmt = stmt.join(Location, Location.trial_nct_id == Trial.nct_id)
        if filters.country_code:
            stmt = stmt.where(Location.country_code == filters.country_code)
        if filters.state_code:
            stmt = stmt.where(Location.state_code == filters.state_code)

    if _needs_intervention_join(filters):
        stmt = stmt.join(Intervention, Intervention.trial_nct_id == Trial.nct_id)
        stmt = stmt.where(Intervention.type == filters.intervention_type)

    return stmt


# =============================================================================
# Aggregate endpoint (choropleth)
# =============================================================================


def aggregate_by_country(session: Session, filters: FilterQuery) -> AggregateResponse:
    """Group matching trials by ISO country code.

    Each trial contributes once per country it has sites in — so a
    multinational trial appears in multiple groups. The overall
    `total_trials` count is DISTINCT so it reflects the filter cohort size.
    """
    # Per-country counts: distinct trials with at least one site in each country
    row_stmt = (
        select(
            Location.country_code,
            func.count(distinct(Trial.nct_id)).label("trial_count"),
            func.sum(Trial.enrollment_count).label("total_enrollment"),
        )
        .join(Location, Location.trial_nct_id == Trial.nct_id)
        .where(Location.country_code.isnot(None))
        .group_by(Location.country_code)
        .order_by(func.count(distinct(Trial.nct_id)).desc())
    )
    row_stmt = apply_filters(row_stmt, filters)
    # Don't double-join Location if intervention filter also needs joins
    if _needs_intervention_join(filters):
        row_stmt = row_stmt.join(Intervention, Intervention.trial_nct_id == Trial.nct_id)
        row_stmt = row_stmt.where(Intervention.type == filters.intervention_type)

    rows = [
        AggregateRow(
            group_key=cc,
            trial_count=int(count),
            total_enrollment=int(total) if total is not None else None,
        )
        for cc, count, total in session.execute(row_stmt).all()
    ]

    # Distinct trial count (independent of how many countries each trial hits)
    total = _count_distinct_trials(session, filters)

    return AggregateResponse(
        group_by="country",
        rows=rows,
        total_trials=total,
        generated_at=datetime.now(timezone.utc),
    )


def aggregate_by_us_state(session: Session, filters: FilterQuery) -> AggregateResponse:
    """Group matching trials by USPS state code. Only considers US locations."""
    # Force US country code; respect any other filter the caller sent
    us_filters = filters.model_copy(update={"country_code": "US"})

    row_stmt = (
        select(
            Location.state_code,
            func.count(distinct(Trial.nct_id)).label("trial_count"),
            func.sum(Trial.enrollment_count).label("total_enrollment"),
        )
        .join(Location, Location.trial_nct_id == Trial.nct_id)
        .where(Location.country_code == "US")
        .where(Location.state_code.isnot(None))
        .group_by(Location.state_code)
        .order_by(func.count(distinct(Trial.nct_id)).desc())
    )
    row_stmt = apply_filters(row_stmt, us_filters)
    if _needs_intervention_join(us_filters):
        row_stmt = row_stmt.join(Intervention, Intervention.trial_nct_id == Trial.nct_id)
        row_stmt = row_stmt.where(Intervention.type == us_filters.intervention_type)

    rows = [
        AggregateRow(
            group_key=sc,
            trial_count=int(count),
            total_enrollment=int(total) if total is not None else None,
        )
        for sc, count, total in session.execute(row_stmt).all()
    ]

    total = _count_distinct_trials(session, us_filters)

    return AggregateResponse(
        group_by="us_state",
        rows=rows,
        total_trials=total,
        generated_at=datetime.now(timezone.utc),
    )


# =============================================================================
# Stats (popup) endpoint
# =============================================================================


def compute_stats(session: Session, filters: FilterQuery) -> StatsResponse:
    """Compute the summary stats for a filter cohort.

    Returns counts, total enrollment, and the distribution of approximate
    enrollment rates (min/median/max + sample size so the UI can decide
    whether to show them). Also returns average months_enrolling.
    """
    trial_count = _count_distinct_trials(session, filters)

    # Total enrollment
    total_enr_stmt = select(func.sum(Trial.enrollment_count)).select_from(Trial)
    total_enr_stmt = _apply_join_filters(total_enr_stmt, filters)
    total_enr_stmt = apply_filters(total_enr_stmt, filters)
    total_enrollment = session.execute(total_enr_stmt).scalar()

    # Pull rate values into Python for median. SQLite has no PERCENTILE_CONT.
    rate_stmt = select(Trial.approx_enrollment_rate_per_month).select_from(Trial)
    rate_stmt = _apply_join_filters(rate_stmt, filters)
    rate_stmt = apply_filters(rate_stmt, filters)
    rate_stmt = rate_stmt.where(Trial.approx_enrollment_rate_per_month.isnot(None))
    # Distinct on nct_id to avoid double-counting trials with multiple sites
    rate_stmt = rate_stmt.distinct()

    rates = [r[0] for r in session.execute(rate_stmt).all()]
    rate_min = min(rates) if rates else None
    rate_max = max(rates) if rates else None
    rate_median = statistics.median(rates) if rates else None

    # Average months enrolling
    months_stmt = select(func.avg(Trial.months_enrolling)).select_from(Trial)
    months_stmt = _apply_join_filters(months_stmt, filters)
    months_stmt = apply_filters(months_stmt, filters)
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

    return FilterOptions(
        therapeutic_areas=_distinct_strs(Trial.therapeutic_area),
        phases=_distinct_strs(Trial.phase),
        statuses=_distinct_strs(Trial.overall_status),
        study_types=_distinct_strs(Trial.study_type),
        intervention_types=_distinct_strs(Intervention.type),
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
