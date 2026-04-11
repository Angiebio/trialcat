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
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Condition, Intervention, Location, Outcome, Trial, TrialCondition
from app.services.geo import to_iso2
from app.services.parser import parse_trial

logger = logging.getLogger(__name__)


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

    # Fill in ISO country codes for locations (parser leaves this for the ETL layer
    # because it depends on our geo service, which is an application concern)
    for loc in locations:
        loc.country_code = to_iso2(loc.country)

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


def load_trials(session: Session, raw_trials: list[dict]) -> int:
    """Load many trials in one transaction. Returns the count loaded."""
    count = 0
    for raw in raw_trials:
        try:
            load_trial(session, raw)
            count += 1
        except Exception as e:
            logger.exception("Failed to load trial: %s", e)
            raise
    return count
