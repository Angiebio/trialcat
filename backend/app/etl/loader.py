"""Load parsed trial data into the database, idempotently.

This is the "write" side of the ETL pipeline. Takes the output of parse_trial()
and upserts it into the database so that running the ETL multiple times
produces the same state, not duplicates.

Upsert strategy:
- Trial: primary key is NCT ID. If it exists, delete its dependent rows
  (locations, interventions, outcomes) and re-insert, then update the trial
  columns. This is simpler than diffing fields and handles trials that gain
  or lose sites over time.
- Condition: natural key is (mesh_id OR term). We look up existing conditions
  before inserting so the same MeSH term is shared across all trials that
  use it.
- TrialCondition: the join table is fully regenerated per trial.
"""

import logging
import time
from typing import Optional, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Condition, Intervention, Location, Outcome, Trial, TrialCondition
from app.services.geo import to_iso2, to_us_state_code
from app.services.parser import parse_trial

logger = logging.getLogger(__name__)


class LoadError(TypedDict):
    """One trial that failed to load, for the stats summary."""

    nct_id: Optional[str]
    error_type: str
    error_msg: str


class LoadStats(TypedDict):
    """Summary returned by load_trials.

    loaded: number of trials successfully written
    failed: number of trials that hit an error and were skipped
    errors: list of LoadError dicts (capped to first N for huge batches)
    duration_s: wall-clock time for the load phase in seconds
    """

    loaded: int
    failed: int
    errors: list[LoadError]
    duration_s: float


def _upsert_condition(session: Session, info: dict) -> Condition:
    """Find or create a Condition row for the given parsed info dict.

    Lookup order:
    1. Match by mesh_id if present
    2. Match by term (case-insensitive)
    3. Create new
    """
    mesh_id: Optional[str] = info.get("mesh_id")
    term: str = info.get("term") or ""
    broad: Optional[str] = info.get("broad")

    existing: Optional[Condition] = None
    if mesh_id:
        existing = session.scalar(select(Condition).where(Condition.mesh_id == mesh_id))
    if not existing and term:
        existing = session.scalar(
            select(Condition).where(Condition.term == term)
        )

    if existing:
        # Update broad_category if we have one and it was missing before
        if broad and not existing.broad_category:
            existing.broad_category = broad
        return existing

    condition = Condition(mesh_id=mesh_id, term=term, broad_category=broad)
    session.add(condition)
    session.flush()  # assign primary key
    return condition


def load_trial(session: Session, raw: dict) -> Trial:
    """Parse and upsert a single raw CT.gov trial dict.

    Returns the persisted Trial instance (already attached to the session).
    Handles deletion of old dependent rows on update so there are no orphans.
    """
    parsed_trial, locations, interventions, outcomes, condition_infos = parse_trial(raw)

    # Fill in ISO country codes + USPS state codes for locations.
    # Parser leaves this for the ETL layer because it depends on our geo
    # service (application concern, not part of the pure parse function).
    for loc in locations:
        loc.country_code = to_iso2(loc.country)
        # Only populate state_code for US locations — for international
        # locations the `state` field holds provinces/regions that don't
        # follow a standard short-code scheme.
        if loc.country_code == "US":
            loc.state_code = to_us_state_code(loc.state)

    # --- Upsert the trial ---
    existing = session.scalar(select(Trial).where(Trial.nct_id == parsed_trial.nct_id))
    if existing:
        # Clear dependents, then copy field values onto existing row
        logger.debug("Updating existing trial %s", parsed_trial.nct_id)
        for loc in existing.locations:
            session.delete(loc)
        for iv in existing.interventions:
            session.delete(iv)
        for out in existing.outcomes:
            session.delete(out)
        session.query(TrialCondition).filter(
            TrialCondition.trial_nct_id == parsed_trial.nct_id
        ).delete()
        session.flush()

        # Copy scalar fields from parsed_trial onto existing.
        # Exclude the primary key and timestamp columns — those are managed
        # by SQLAlchemy (fetched_at on insert, updated_at on update).
        # Copying updated_at=None from the fresh in-memory trial would
        # violate NOT NULL before the onupdate default kicks in.
        SKIP_COLUMNS = {"nct_id", "fetched_at", "updated_at"}
        for col in Trial.__table__.columns:
            if col.name in SKIP_COLUMNS:
                continue
            setattr(existing, col.name, getattr(parsed_trial, col.name))
        trial = existing
    else:
        logger.debug("Inserting new trial %s", parsed_trial.nct_id)
        session.add(parsed_trial)
        trial = parsed_trial

    session.flush()  # make sure trial has a persisted pk before adding relations

    # --- Locations ---
    for loc in locations:
        loc.trial_nct_id = trial.nct_id
        session.add(loc)

    # --- Interventions ---
    for iv in interventions:
        iv.trial_nct_id = trial.nct_id
        session.add(iv)

    # --- Outcomes ---
    for out in outcomes:
        out.trial_nct_id = trial.nct_id
        session.add(out)

    # --- Conditions (dedup + join table) ---
    for info in condition_infos:
        condition = _upsert_condition(session, info)
        session.add(
            TrialCondition(
                trial_nct_id=trial.nct_id,
                condition_id=condition.id,
                is_primary=info.get("is_primary", True),
            )
        )

    session.flush()
    return trial


def load_trials(
    session: Session,
    raw_trials: list[dict],
    log_every: int = 100,
    max_errors_kept: int = 50,
) -> LoadStats:
    """Load many trials, tolerating per-trial failures.

    Philosophy: a batch of 10,000 trials should not be killed by one
    malformed row. We catch per-trial exceptions, log them, and continue.
    But we do NOT swallow them silently — every failure gets a log entry
    AND an entry in the returned stats dict so callers can decide what
    to do (alert, retry, ignore).

    Catastrophic errors (DB connection dropped, disk full, etc.) will
    bubble up because they don't originate from a per-trial `load_trial`
    call; they come from the session itself, and at that point there's
    nothing safe we can do.

    Args:
        session: SQLAlchemy session (caller manages commit/rollback)
        raw_trials: list of raw CT.gov trial dicts
        log_every: emit a progress log every N trials (default 100)
        max_errors_kept: cap the errors list at this many entries so huge
            failed batches don't eat memory (default 50)

    Returns:
        LoadStats dict with loaded/failed counts, errors list, duration.
    """
    started = time.monotonic()
    total = len(raw_trials)
    loaded = 0
    failed = 0
    errors: list[LoadError] = []

    for idx, raw in enumerate(raw_trials, start=1):
        # Try to extract NCT ID early for error reporting — if even this
        # fails, we use "unknown" and still count it as a failure.
        nct_id: Optional[str] = None
        try:
            nct_id = (
                raw.get("protocolSection", {})
                .get("identificationModule", {})
                .get("nctId")
            )
        except Exception:
            pass

        try:
            load_trial(session, raw)
            loaded += 1
        except Exception as e:
            failed += 1
            # Keep the first N errors in the returned list to prevent
            # unbounded memory use on huge failing batches.
            if len(errors) < max_errors_kept:
                errors.append(
                    LoadError(
                        nct_id=nct_id,
                        error_type=type(e).__name__,
                        error_msg=str(e)[:500],  # cap message length too
                    )
                )
            # Log every failure at warning level — production monitoring
            # should alert on non-zero failure counts anyway.
            logger.warning(
                "Failed to load trial %s: %s: %s",
                nct_id or "<unknown>",
                type(e).__name__,
                e,
            )

        # Progress heartbeat
        if log_every and idx % log_every == 0:
            logger.info(
                "ETL progress: %s/%s processed (%s loaded, %s failed)",
                idx,
                total,
                loaded,
                failed,
            )

    duration = time.monotonic() - started
    logger.info(
        "ETL complete: %s loaded, %s failed out of %s in %.1fs",
        loaded,
        failed,
        total,
        duration,
    )

    return LoadStats(
        loaded=loaded,
        failed=failed,
        errors=errors,
        duration_s=round(duration, 2),
    )
