"""ETL command-line entry point — fetch CT.gov data and load it into SQLite.

This is the script you run to get real data into the database. It wraps the
CTGovClient (fetch), parser (transform), and loader (upsert) into a single
command with flags for common filters.

Usage examples:
    # Small load: 50 cardiovascular Phase 3 trials
    python -m app.etl.refresh --condition=cardiovascular --phase=PHASE3 --limit=50

    # By sponsor
    python -m app.etl.refresh --sponsor="Pfizer" --limit=200

    # Bulk load with no filter (careful — this is hundreds of thousands of trials)
    python -m app.etl.refresh --limit=500

    # Dry run: fetch but don't write to DB (useful for testing the client)
    python -m app.etl.refresh --condition=diabetes --limit=10 --dry-run

Design notes:
- Runs from any working directory because it imports via `app.*` package path
- Creates tables on first run (idempotent via SQLAlchemy's create_all)
- Prints a summary at the end even if some trials failed to load
- Logs at INFO level so you can see progress without DEBUG noise
"""

import argparse
import logging
import sys
import time
from typing import Optional

from app.config import settings
from app.db import SessionLocal, create_all_tables
from app.etl.loader import load_trials
from app.services.ctgov_client import CTGovClient

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the ETL run.

    INFO by default, DEBUG when --verbose is set. Single handler writing to
    stderr so it doesn't pollute any stdout-based piping a caller might do.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )


def parse_args() -> argparse.Namespace:
    """Define the CLI surface."""
    parser = argparse.ArgumentParser(
        prog="python -m app.etl.refresh",
        description="Fetch and load ClinicalTrials.gov data into trialcat's SQLite DB.",
        epilog=(
            "If no filters are provided, ALL trials in CT.gov will be fetched "
            "(hundreds of thousands). Always use --limit for safety during dev."
        ),
    )

    # Filter flags — passed through to CTGovClient.search_studies
    parser.add_argument(
        "--condition",
        type=str,
        default=None,
        help="Disease/condition filter, e.g., 'cardiovascular', 'diabetes'. Supports Boolean.",
    )
    parser.add_argument(
        "--intervention",
        type=str,
        default=None,
        help="Drug/intervention name filter, e.g., 'pembrolizumab'.",
    )
    parser.add_argument(
        "--sponsor",
        type=str,
        default=None,
        help="Sponsor name filter, e.g., 'Pfizer', 'NIH'.",
    )
    parser.add_argument(
        "--location",
        type=str,
        default=None,
        help="Geographic filter, e.g., 'United States', 'Germany'.",
    )
    parser.add_argument(
        "--phase",
        type=str,
        action="append",
        default=None,
        help=(
            "Phase filter (can specify multiple). "
            "Options: EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4, NA."
        ),
    )
    parser.add_argument(
        "--status",
        type=str,
        action="append",
        default=None,
        help=(
            "Recruitment status filter (can specify multiple). "
            "Common: RECRUITING, COMPLETED, TERMINATED."
        ),
    )
    parser.add_argument(
        "--study-type",
        type=str,
        default=None,
        choices=["INTERVENTIONAL", "OBSERVATIONAL", "EXPANDED_ACCESS"],
        help="Study type filter.",
    )

    # Safety and behavior flags
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max trials to fetch (default: 100). Use 0 for no limit (careful).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch from CT.gov but DO NOT write to database.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )

    return parser.parse_args()


def fetch_batch(
    client: CTGovClient,
    args: argparse.Namespace,
) -> list[dict]:
    """Fetch trials from CT.gov, respecting the CLI's --limit flag.

    We use the streaming search_studies iterator and break early once we've
    collected `limit` trials. This keeps memory bounded even if the caller
    asks for a filter that matches millions of trials.
    """
    raw_trials: list[dict] = []
    count = 0
    for trial in client.search_studies(
        condition=args.condition,
        intervention=args.intervention,
        location=args.location,
        sponsor=args.sponsor,
        status=args.status,
        phase=args.phase,
        study_type=args.study_type,
    ):
        raw_trials.append(trial)
        count += 1
        if args.limit and count >= args.limit:
            logger.info("Reached --limit of %s trials, stopping fetch", args.limit)
            break

    return raw_trials


def main() -> int:
    """ETL entry point. Returns process exit code."""
    args = parse_args()
    setup_logging(args.verbose)

    logger.info("trialcat ETL starting")
    logger.info(
        "Filters: condition=%s intervention=%s sponsor=%s location=%s phase=%s status=%s study_type=%s limit=%s dry_run=%s",
        args.condition,
        args.intervention,
        args.sponsor,
        args.location,
        args.phase,
        args.status,
        args.study_type,
        args.limit,
        args.dry_run,
    )

    # Ensure the DB schema exists (idempotent — safe to call every run)
    if not args.dry_run:
        create_all_tables()
        logger.info("Database schema ready: %s", settings.database_url)

    # --- Fetch phase ---
    client = CTGovClient()
    fetch_start = time.monotonic()
    try:
        raw_trials = fetch_batch(client, args)
    except Exception as e:
        logger.exception("Fetch failed: %s", e)
        return 1

    fetch_duration = time.monotonic() - fetch_start
    logger.info(
        "Fetched %s trials from CT.gov in %.1fs",
        len(raw_trials),
        fetch_duration,
    )

    if not raw_trials:
        logger.warning("No trials matched the filter — nothing to load")
        return 0

    if args.dry_run:
        # Just show what we would have loaded
        logger.info("DRY RUN: would load %s trials. First 3 NCT IDs:", len(raw_trials))
        for t in raw_trials[:3]:
            nct = t.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
            logger.info("  - %s", nct)
        return 0

    # --- Load phase ---
    load_start = time.monotonic()
    session = SessionLocal()
    try:
        stats = load_trials(session, raw_trials)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception("Load failed catastrophically, rolled back: %s", e)
        return 1
    finally:
        session.close()

    load_duration = time.monotonic() - load_start
    total_duration = time.monotonic() - fetch_start

    # --- Summary ---
    logger.info("=" * 60)
    logger.info("ETL summary")
    logger.info("=" * 60)
    if isinstance(stats, dict):
        logger.info("  Loaded:   %s", stats.get("loaded", "?"))
        logger.info("  Failed:   %s", stats.get("failed", "?"))
        logger.info("  Fetch:    %.1fs", fetch_duration)
        logger.info("  Load:     %.1fs", load_duration)
        logger.info("  Total:    %.1fs", total_duration)
        errors = stats.get("errors", [])
        if errors:
            logger.warning("  %s trials failed to load. First 5:", len(errors))
            for err in errors[:5]:
                logger.warning(
                    "    %s: %s", err.get("nct_id"), err.get("error_msg", "?")
                )
    else:
        # Pre-Task-4 fallback: loader returns an int
        logger.info("  Loaded:   %s", stats)
        logger.info("  Fetch:    %.1fs", fetch_duration)
        logger.info("  Load:     %.1fs", load_duration)
        logger.info("  Total:    %.1fs", total_duration)

    return 0


if __name__ == "__main__":
    sys.exit(main())
