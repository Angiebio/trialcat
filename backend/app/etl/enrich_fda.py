"""FDA enrichment ETL — overlay real openFDA facts onto our heuristic guesses.

This is the script you run to upgrade interventions from keyword-heuristic
classification to authoritative-ish FDA classification. It is the v2 promised in
intervention.py's docstring: cross-reference the FDA classification DB instead of
regex-guessing device class from free text.

What it writes:
- DEVICE rows: set `device_class_hint` (I/II/III) when openFDA returns a class;
  OVERWRITE `product_category` with the FDA medical-specialty review panel
  ("Cardiovascular", "Neurology", ...) when matched. On no-match we KEEP the
  existing keyword category — we never null out a working heuristic to replace
  it with nothing. Subtraction is not enrichment.
- DRUG rows: set `product_category` to the established pharmacologic class (or an
  Rx/OTC label); on no-match set it to "Investigational / Unclassified", which is
  itself an honest, filterable answer for the many investigational arms that
  rightly aren't in approved-drug databases.

Design (mirrors app/etl/refresh.py):
- Runs from any working dir via the `app.*` package path.
- Idempotent and re-runnable: re-running converges to the same DB state.
- Commits in small batches so a crash mid-run doesn't lose everything and a
  long run shows progress.
- DEDUPES lookups via the client's token cache — 40 "stent" trials, one call.
- BUDGET-AWARE: --max-calls caps real HTTP calls to stay under openFDA's no-key
  1,000/day ceiling. When we hit the cap we STOP and LOG LOUDLY what was
  deferred. No silent truncation — a deferred row is a promise we name out loud.

Usage examples:
    # Devices first (cheap — high dedup), then drugs within the call budget
    python -m app.etl.enrich_fda --kind=all

    # Just devices, dry run (no DB writes), see what WOULD change
    python -m app.etl.enrich_fda --kind=device --dry-run

    # Drugs only, small slice, tight budget for testing
    python -m app.etl.enrich_fda --kind=drug --limit=50 --max-calls=60

Philosophy: heuristics are a candle; FDA data is a floodlight. We light the
floodlight where we can reach the switch, and we leave the candle burning
everywhere we can't — because a dim true light beats a dark "None".
"""

import argparse
import logging
import sys
import time
from typing import Optional

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, create_all_tables
from app.models import Intervention
from app.services.fda_enrich import FDAEnrichClient

logger = logging.getLogger(__name__)


# Default budget. openFDA without a key allows ~1,000 requests/day; we leave
# headroom for retries and any other same-day usage. The ETL refuses to blow
# past this — see the budget guard in enrich_drugs().
DEFAULT_MAX_CALLS = 800

# Commit every N updated rows. Small enough to bound data loss on a crash,
# large enough not to thrash SQLite. The DB is the floor we stand on; we keep
# re-checking it's still there.
COMMIT_BATCH_SIZE = 50


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the enrichment run (matches refresh.py)."""
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
        prog="python -m app.etl.enrich_fda",
        description=(
            "Enrich trialcat interventions with openFDA device classification "
            "and drug pharmacologic class. Overlay on top of keyword heuristics."
        ),
        epilog=(
            "openFDA's no-key tier allows ~1,000 requests/day. --max-calls "
            "(default 800) keeps us under that. Set OPENFDA_API_KEY in .env to "
            "lift the ceiling to 120,000/day for production runs."
        ),
    )
    parser.add_argument(
        "--kind",
        choices=["device", "drug", "all"],
        default="all",
        help="Which interventions to enrich (default: all = devices then drugs).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max DB rows to consider PER KIND (0 = no limit, the default).",
    )
    parser.add_argument(
        "--max-calls",
        type=int,
        default=DEFAULT_MAX_CALLS,
        help=(
            f"Max real openFDA HTTP calls this run (default {DEFAULT_MAX_CALLS}). "
            "Cache hits are free and don't count. Deferred rows are LOGGED, "
            "never silently dropped."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Look up and report, but DO NOT write to the database.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args()


def _maybe_commit(session, dry_run: bool, updated: int, force: bool = False) -> None:
    """Commit in batches (no-op on dry run). Fail loud — rollback then re-raise."""
    if dry_run:
        return
    if force or (updated and updated % COMMIT_BATCH_SIZE == 0):
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            logger.exception("Commit failed, rolled back this batch: %s", e)
            raise


def enrich_devices(
    session,
    client: FDAEnrichClient,
    args: argparse.Namespace,
) -> dict:
    """Enrich DEVICE interventions. Returns a stats dict.

    Devices go first because they dedupe hard (407 device rows collapse to a few
    dozen distinct generic nouns), so they buy the most enrichment per call.
    """
    stmt = select(Intervention).where(Intervention.type == "DEVICE")
    if args.limit:
        stmt = stmt.limit(args.limit)
    rows = list(session.execute(stmt).scalars())

    logger.info("DEVICE: %s rows to consider", len(rows))

    considered = 0
    matched = 0
    class_set = 0
    category_overwritten = 0
    deferred = 0
    deferred_names: list[str] = []

    for row in rows:
        considered += 1
        if not row.name:
            continue

        # Budget guard. If looking up this row's noun would require a NEW HTTP
        # call and we're at the cap, defer it LOUDLY. Cache hits are exempt —
        # they're free, so a deferred row only happens for genuinely new tokens.
        noun = client.extract_device_noun(row.name)
        needs_new_call = noun is not None and noun not in client._device_cache
        if needs_new_call and client.api_calls_made >= args.max_calls:
            deferred += 1
            if len(deferred_names) < 20:
                deferred_names.append(row.name)
            continue

        result = client.classify_device(row.name)
        if result is None:
            # No-match: KEEP the existing keyword product_category. We do not
            # null a working heuristic — the candle stays lit.
            continue

        matched += 1

        new_class = result.get("device_class")
        new_category = result.get("product_category")

        if new_class and row.device_class_hint != new_class:
            row.device_class_hint = new_class
            class_set += 1
        if new_category and row.product_category != new_category:
            row.product_category = new_category  # FDA specialty wins over keyword
            category_overwritten += 1

        logger.debug(
            "DEVICE match: %r -> class=%s specialty=%s (term=%s, code=%s)",
            row.name, new_class, new_category,
            result.get("matched_term"), result.get("product_code"),
        )

        _maybe_commit(session, args.dry_run, matched)

    _maybe_commit(session, args.dry_run, matched, force=True)

    if deferred:
        logger.warning(
            "DEVICE: DEFERRED %s rows — hit --max-calls budget (%s). "
            "Re-run to finish. First deferred names: %s",
            deferred, args.max_calls, deferred_names,
        )

    return {
        "considered": considered,
        "matched": matched,
        "class_set": class_set,
        "category_overwritten": category_overwritten,
        "deferred": deferred,
    }


def enrich_drugs(
    session,
    client: FDAEnrichClient,
    args: argparse.Namespace,
) -> dict:
    """Enrich DRUG interventions. Returns a stats dict.

    Drugs dedupe less than devices (more distinct active ingredients) and many
    arms are investigational, so this is where the call budget actually bites.
    No-match arms are explicitly bucketed as "Investigational / Unclassified".
    """
    stmt = select(Intervention).where(Intervention.type == "DRUG")
    if args.limit:
        stmt = stmt.limit(args.limit)
    rows = list(session.execute(stmt).scalars())

    logger.info("DRUG: %s rows to consider", len(rows))

    considered = 0
    pharm_class_set = 0
    unclassified_set = 0
    deferred = 0
    deferred_names: list[str] = []

    for row in rows:
        considered += 1
        if not row.name:
            continue

        # Budget guard. A drug row might require several token lookups; if we're
        # already at the cap and this row hasn't been fully resolved by cache,
        # defer it loudly rather than start a new call we can't afford.
        cleaned = client.clean_drug_name(row.name)
        tokens = client._drug_candidate_tokens(cleaned)
        any_uncached_token = any(t not in client._drug_cache for t in tokens)
        if any_uncached_token and client.api_calls_made >= args.max_calls:
            deferred += 1
            if len(deferred_names) < 20:
                deferred_names.append(row.name)
            continue

        result = client.classify_drug(row.name)

        if result is not None:
            new_category = result["product_category"]
            if row.product_category != new_category:
                row.product_category = new_category
                pharm_class_set += 1
            logger.debug(
                "DRUG match: %r -> %s (%s)",
                row.name, new_category, result.get("source"),
            )
        else:
            # No-match is the EXPECTED state for investigational arms. Name it
            # honestly so the UI can filter on it, rather than leaving it blank.
            label = client.DRUG_NO_MATCH_LABEL
            if row.product_category != label:
                row.product_category = label
                unclassified_set += 1

        _maybe_commit(session, args.dry_run, considered)

    _maybe_commit(session, args.dry_run, considered, force=True)

    if deferred:
        logger.warning(
            "DRUG: DEFERRED %s rows — hit --max-calls budget (%s). "
            "Re-run (ideally with OPENFDA_API_KEY) to finish. "
            "First deferred names: %s",
            deferred, args.max_calls, deferred_names,
        )

    return {
        "considered": considered,
        "pharm_class_set": pharm_class_set,
        "unclassified_set": unclassified_set,
        "deferred": deferred,
    }


def main() -> int:
    """Enrichment entry point. Returns process exit code."""
    args = parse_args()
    setup_logging(args.verbose)

    logger.info("trialcat FDA enrichment starting")
    logger.info(
        "kind=%s limit=%s max_calls=%s dry_run=%s api_key=%s",
        args.kind, args.limit, args.max_calls, args.dry_run,
        "set" if settings.openfda_api_key else "NONE (no-key tier, 1000/day cap)",
    )

    if not args.dry_run:
        create_all_tables()  # idempotent
        logger.info("Database schema ready: %s", settings.database_url)

    client = FDAEnrichClient()
    session = SessionLocal()
    start = time.monotonic()
    device_stats: Optional[dict] = None
    drug_stats: Optional[dict] = None

    try:
        # Devices first — cheapest enrichment-per-call thanks to noun dedup.
        if args.kind in ("device", "all"):
            device_stats = enrich_devices(session, client, args)

        # Then drugs, spending whatever call budget devices left behind.
        if args.kind in ("drug", "all"):
            if client.api_calls_made >= args.max_calls and args.kind == "all":
                logger.warning(
                    "Skipping DRUG enrichment: device phase already consumed the "
                    "full --max-calls budget (%s). Re-run --kind=drug tomorrow "
                    "or set OPENFDA_API_KEY.",
                    args.max_calls,
                )
            else:
                drug_stats = enrich_drugs(session, client, args)
    except Exception as e:
        session.rollback()
        logger.exception("Enrichment failed, rolled back uncommitted work: %s", e)
        return 1
    finally:
        session.close()

    duration = time.monotonic() - start

    # --- Summary ---
    logger.info("=" * 60)
    logger.info("FDA enrichment summary%s", "  (DRY RUN — no writes)" if args.dry_run else "")
    logger.info("=" * 60)
    logger.info("  openFDA HTTP calls made: %s", client.api_calls_made)
    logger.info("  distinct device nouns cached: %s", len(client._device_cache))
    logger.info("  distinct drug tokens cached:  %s", len(client._drug_cache))
    if device_stats:
        logger.info("  DEVICE considered:          %s", device_stats["considered"])
        logger.info("  DEVICE matched in openFDA:  %s", device_stats["matched"])
        logger.info("  DEVICE class_hint set:      %s", device_stats["class_set"])
        logger.info("  DEVICE category overwritten:%s", device_stats["category_overwritten"])
        logger.info("  DEVICE deferred (budget):   %s", device_stats["deferred"])
    if drug_stats:
        logger.info("  DRUG considered:            %s", drug_stats["considered"])
        logger.info("  DRUG pharm/Rx-OTC set:      %s", drug_stats["pharm_class_set"])
        logger.info("  DRUG unclassified bucketed: %s", drug_stats["unclassified_set"])
        logger.info("  DRUG deferred (budget):     %s", drug_stats["deferred"])
    logger.info("  Elapsed: %.1fs", duration)

    return 0


if __name__ == "__main__":
    sys.exit(main())
