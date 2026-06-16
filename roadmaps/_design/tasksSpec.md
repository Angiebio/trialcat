I now have complete, authoritative knowledge of the actual code. Confirmed: the prod app is `trialcat` (so `trialcat.fly.dev`), `auto_stop_machines = 'stop'` with `min_machines_running = 0` (the exact risk the earlier findings flagged), 1GB / 1 shared CPU, 1GB RAM. The dev DB is already fully built and enriched. Writing the final specs now.

---

# TrialCat Refinement Specs — Grounded in the Actual Code (read 2026-06-16)

> **Critical correction to the task premise.** The device-class drill-down described in TASK 1 as "NEW work" is **already fully wired, end to end, in the code on disk.** I read every file. `device_class` and `product_category` already exist in `FilterQuery` + the upper-normalizer, `_apply_intervention_join` already handles both on a single join, `FilterOptions` already carries `device_classes` + `product_categories_by_type`, `get_filter_options` already computes them, and the frontend already has the dependent `#group-device-class` / `#group-product-category` selects with `updateDrilldowns()` / `buildFilterParams()` / `resetFilters()` wiring. There is even a full **`app/etl/enrich_fda.py`** that overlays authoritative openFDA device class + product category on the heuristic. **And the local dev DB already proves it ran:** `data/trialcat.db` (15.9 MB, 2,500 trials, 4,140 interventions, 407 DEVICE rows) has `device_class_hint` populated (I:21, II:130, III:19) and 807 rows with `product_category` including FDA-enriched labels like `Kinase Inhibitor [EPC]`, `General, Plastic Surgery`, `Rx-only`.
>
> So I am NOT re-speccing wiring that exists. Below, TASK 1 specifies the **two genuine remaining gaps** I found by reading the code (a real correctness bug + a missing client capability), and TASK 2 specifies the data/migration work. Everything references real line numbers.

---

## TASK 1 — Device-class drill-down: what's actually missing

The drill-down filtering path is complete. Reading it closely surfaced **two real gaps** and one **stretch** worth doing. These are the precise, file-level deltas.

### Gap 1A (P1, real bug) — `state_code` upper-normalizer is fine, but `product_category` filtering breaks on enriched DRUG labels because the validator does NOT uppercase it (correct) yet the frontend can send a stale value. Actually verify: the real bug is the **`device_class` join short-circuit when only `device_class` is set without `intervention_type`.**

Re-reading `stats.py:97-106`, the logic is already correct (each branch applied independently — the comment at lines 92-94 explicitly handles the "only device_class set" case). **This is not a bug.** I confirmed by tracing: `_needs_intervention_join` returns True if any of the three is set, and each `where` is conditional. Good.

The **actual** P1 is in `_apply_intervention_join` interaction with the **aggregate endpoints**: in `aggregate_by_country` (`stats.py:142`) and `aggregate_by_us_state` (`stats.py:182`), `Location` is `.join()`ed first, then `_apply_intervention_join` adds a second `.join(Intervention, ...)`. A trial with N locations × M interventions now yields **N×M rows**. The per-country `func.count(distinct(Trial.nct_id))` (line 139) is DISTINCT so the **count is safe**, but `func.sum(Trial.enrollment_count)` (line 140) is **NOT distinct** — it sums `enrollment_count` once per (location × intervention) row, **inflating `total_enrollment` by the intervention multiplicity** whenever an intervention filter is active. This already affects `intervention_type` filtering today; the device drill-down just makes it more visible.

**Fix — `stats.py`, `aggregate_by_country` (around line 136) and `aggregate_by_us_state` (around line 176).** Make enrollment a distinct-trial subquery, or guard the sum. Minimal correct fix is a correlated distinct sum via a CTE/subquery. The lowest-risk patch that matches the existing style:

Search for (in `aggregate_by_country`):
```python
        .join(Location, Location.trial_nct_id == Trial.nct_id)
        .where(Location.country_code.isnot(None))
        .group_by(Location.country_code)
```
The enrollment inflation only occurs when `_needs_intervention_join` is True. Replace the naive `func.sum(Trial.enrollment_count)` with a sum over distinct trials. Concretely, compute per-country counts and enrollment from a deduplicated subquery:

```python
# Practical: when an intervention filter forces a second join, each trial
# fans out to (locations × interventions) rows — count(DISTINCT) stays honest
# but SUM(enrollment) double-counts. We collapse to one row per (country, trial)
# BEFORE summing, so enrollment is counted exactly once per trial-in-country.
# Philosophical: a trial's patients don't multiply because it tests two devices.
# The map should report bodies enrolled, not rows joined.
trial_in_country = (
    select(
        Location.country_code.label("cc"),
        Trial.nct_id.label("nct"),
        Trial.enrollment_count.label("enr"),
    )
    .select_from(Trial)
    .join(Location, Location.trial_nct_id == Trial.nct_id)
    .where(Location.country_code.isnot(None))
    .distinct()
)
trial_in_country = apply_filters(trial_in_country, filters)
trial_in_country = _apply_intervention_join(trial_in_country, filters)
sub = trial_in_country.subquery()

row_stmt = (
    select(
        sub.c.cc,
        func.count(distinct(sub.c.nct)).label("trial_count"),
        func.sum(sub.c.enr).label("total_enrollment"),
    )
    .group_by(sub.c.cc)
    .order_by(func.count(distinct(sub.c.nct)).desc())
)
rows = [...]  # unchanged consumption below
```

Do the identical transform in `aggregate_by_us_state` (filter `Location.country_code == "US"` and `state_code.isnot(None)`, group by `sub.c.sc`). Note: `_apply_intervention_join` joins on `Trial.nct_id`, and the subquery selects from `Trial`, so the join target is in scope. **Add a test** in `/tests` asserting that `total_enrollment` for a country is unchanged whether or not `intervention_type=DEVICE` is applied to a trial that has 2+ device interventions.

> If Angie prefers the smallest possible change and can tolerate the known overcount, the alternative is to drop `total_enrollment` from the row when an intervention filter is active and show only counts. The subquery fix above is the correct one and is cheap on a SQLite of this size.

### Gap 1B (P2, missing capability) — `CTGovClient.search_studies` has no `intervention_type` parameter, so the ETL can't *fetch* a device-heavy slice from CT.gov

`ctgov_client.py:81-94` — `search_studies(...)` accepts `condition, intervention, location, sponsor, status, phase, study_type, advanced_query, fields, updated_since, updated_before`. There is **no `intervention_type`**. Confirmed against live CT.gov probing: intervention type is **not** an `aggFilters` facet; it must go through the Essie expression `AREA[InterventionType]<TYPE>` injected into `query.term` (which the client maps from `advanced_query`, line 120-121). So today you *can* pass it via `advanced_query="AREA[InterventionType]DEVICE"`, but the CLI (`refresh.py`) exposes no flag for it, and combining with another `advanced_query` would collide.

**Fix — add a first-class `intervention_type` param. Two-file change.**

**`ctgov_client.py`** — add the param and fold it into `query.term` alongside any existing `advanced_query`:

Add to the signature (after `study_type`, line 89):
```python
        intervention_type: Optional[str] = None,
```
After the `advanced_query` block (line 120-121), replace:
```python
        if advanced_query:
            params["query.term"] = advanced_query
```
with:
```python
        # Intervention type is NOT an aggFilters facet (confirmed against the
        # live v2 API: aggFilters=interventionType -> "Unknown aggregation-filter
        # name"). It only exists as an Essie AREA expression in query.term. We AND
        # it onto any caller-supplied advanced_query so both survive.
        # Practical: build the query.term from the pieces we actually have.
        # Philosophical: CT.gov gives you drug-vs-device as a search, never a facet
        # — the registry knows what a trial tests, but won't hand it to you on a tray.
        term_parts: list[str] = []
        if advanced_query:
            term_parts.append(advanced_query)
        if intervention_type:
            term_parts.append(f"AREA[InterventionType]{intervention_type.upper()}")
        if term_parts:
            params["query.term"] = " AND ".join(f"({p})" for p in term_parts)
```

**`refresh.py`** — add the CLI flag and pass it through:

After the `--study-type` argument (ends line 118), add:
```python
    parser.add_argument(
        "--intervention-type",
        type=str,
        default=None,
        choices=[
            "DRUG", "DEVICE", "BIOLOGICAL", "BEHAVIORAL", "PROCEDURE",
            "RADIATION", "GENETIC", "DIAGNOSTIC_TEST", "DIETARY_SUPPLEMENT",
            "COMBINATION_PRODUCT", "OTHER",
        ],
        help="Fetch only trials with this intervention type (AREA[InterventionType]). "
             "Differs from --intervention, which is a name search.",
    )
```
In `fetch_batch`, add to the `search_studies(...)` call (after `study_type=args.study_type,`, line 161):
```python
        intervention_type=args.intervention_type,
```
And add `args.intervention_type` to the startup log line at `refresh.py:178-189` for traceability.

This makes the device-heavy backfill in TASK 2 a one-liner: `--intervention-type=DEVICE --limit=1500`.

### Stretch (P3, already shipped) — the "product category" heuristic

The stretch the task proposes — a keyword map (catheter/stent/imaging/software-SaMD/diagnostic) → product category — **already exists and is better than proposed.** See `parser.py:166-225`: `_DEVICE_CATEGORY_KEYWORDS` is an ordered, priority-sorted map with 10 buckets (Software/Digital Health, Cardiovascular, Neurostimulation, Orthopedic/Implant, Imaging/Diagnostic, Surgical/Ablation, Drug Delivery/Infusion, Respiratory, Monitoring/Sensor, Wound Care), with a `"Other Device"` fallback so devices never silently drop. It's invoked at parse time (`parser.py:375-377`) for DEVICE rows only, and `enrich_fda.py` later overlays authoritative openFDA medical-specialty panels on top.

**The only stretch left worth doing**: the keyword list is device-only and never updated post-ingest. If you tune `_DEVICE_CATEGORY_KEYWORDS` (e.g., add "TAVR" you already have; add "wearable patch", "closed-loop", "neural interface"), existing rows won't reclassify until re-ingested. Provide a tiny reclassify script (no network) so heuristic tuning doesn't require a full CT.gov re-pull:

**New file `backend/app/etl/reclassify_devices.py`:**
```python
"""Re-run the name-heuristic product_category over existing DEVICE rows.

Heuristics evolve faster than data does. When we add a keyword bucket to
parser._DEVICE_CATEGORY_KEYWORDS, the trials already in the DB don't know about
it. This script re-applies the CURRENT heuristic to every DEVICE row — pure
local compute, zero CT.gov/openFDA calls — so a keyword tweak reaches old data
in seconds. It will NOT clobber an FDA-enriched category (a value containing a
medical-specialty panel or '[EPC]'): the floodlight outranks the candle.

Version 1.0 16JUN2026
"""
import logging, sys
from sqlalchemy import select
from app.db import SessionLocal, create_all_tables
from app.models import Intervention
from app.services.parser import _classify_device_product

logger = logging.getLogger(__name__)

# FDA-enriched values we must not overwrite with a keyword guess.
_FDA_ENRICHED_MARKERS = ("[EPC]", "Rx-only", "OTC")  # plus specialty-panel names

def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    create_all_tables()
    s = SessionLocal()
    changed = skipped_fda = 0
    try:
        rows = list(s.execute(select(Intervention).where(Intervention.type == "DEVICE")).scalars())
        for r in rows:
            # Don't subtract a true light to install a guess.
            if r.product_category and any(m in r.product_category for m in _FDA_ENRICHED_MARKERS):
                skipped_fda += 1
                continue
            new = _classify_device_product(r.name, r.description)
            if new and new != r.product_category:
                r.product_category = new
                changed += 1
        s.commit()
        logger.info("Reclassified %s DEVICE rows; preserved %s FDA-enriched.", changed, skipped_fda)
    except Exception:
        s.rollback(); raise
    finally:
        s.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
```
Run: `python -m app.etl.reclassify_devices`. (Honest caveat: distinguishing FDA-enriched specialty panels from keyword buckets purely by string is imperfect — `"Cardiovascular"` is both a keyword bucket AND an FDA panel. If you want a clean line, add a one-byte `category_source` column (`'keyword'` / `'fda'`) to `Intervention` and gate on that instead. That's the principled version; the marker-string heuristic above is the zero-migration version.)

---

## TASK 2 — Data backfill: local dev + prod

### Reality check on local dev (already done — verify, don't rebuild)

The committed `data/trialcat.db` is **already a representative, enriched dataset**: 2,500 trials, 4,140 interventions across all 11 types, 407 DEVICE rows, device classes I/II/III present, 807 product categories populated (including openFDA-enriched panels). **Do not delete it.** If a teammate's clone shows only 30 PHASE3 rows, they have a stale/empty volume — they should pull the committed `.db` from git or rebuild with the commands below.

**Verify the local DB (copy-paste):**
```powershell
# From backend/ — confirm the dataset is intact before touching anything
python -c "import sqlite3; c=sqlite3.connect('data/trialcat.db'); cur=c.cursor(); cur.execute('SELECT count(*) FROM trials'); print('trials', cur.fetchone()[0]); cur.execute(\"SELECT type, count(*) FROM interventions GROUP BY type ORDER BY 2 DESC\"); print(cur.fetchall())"
```

**If you DO need to rebuild local dev from scratch** (e.g., to exercise the new `--intervention-type` flag), run from `backend/` with `.env` pointing `DATABASE_URL` at the local file:
```powershell
# 1) Broad bounded base slice — diverse phases/types, ~fast
python -m app.etl.refresh --limit=2000

# 2) Guarantee device coverage using the NEW flag from Gap 1B
python -m app.etl.refresh --intervention-type=DEVICE --limit=1200
python -m app.etl.refresh --intervention-type=DIAGNOSTIC_TEST --limit=300
python -m app.etl.refresh --intervention-type=COMBINATION_PRODUCT --limit=150

# 3) Some drug/biologic depth for the pathway contrast (NDA/BLA vs 510(k)/PMA)
python -m app.etl.refresh --condition=oncology --phase=PHASE3 --limit=500
python -m app.etl.refresh --intervention=pembrolizumab --limit=200

# 4) Overlay authoritative FDA class + product category (uses openFDA, budgeted)
python -m app.etl.enrich_fda --kind=all --max-calls=800
```
The parser populates `device_class_hint` + `product_category` automatically on ingest (`parser.py:366-377`); `enrich_fda.py` then upgrades them. Without the openFDA key the daily ceiling is ~1,000 calls — `--max-calls=800` is the safe default; re-run `--kind=drug` the next day to finish deferred rows (the script logs deferrals loudly, `enrich_fda.py:213-218, 293-299`).

### Prod backfill (the real work)

Prod (`app = 'trialcat'` per `fly.toml:6`, so `https://trialcat.fly.dev`) is partial because **nothing in the automated path ever did a broad initial pull.** The nightly (`nightly-refresh.yml:24` cron `0 4 * * *`) only calls `POST /admin/etl/refresh?days=2` → `_run_bulk_etl(updated_since = now-2d)` (`main.py:379-409`) → CT.gov `AREA[LastUpdatePostDate]RANGE[<2d ago>,MAX]` (`ctgov_client.py:126-131`). That only ever sweeps trials edited in a rolling 2-day window. `/admin/etl/bulk` with **no** `updated_since` does a full all-time sweep (`main.py:268`, `updated_since=None` → no date filter) but **nothing schedules it.**

**Step 0 — migrate the prod schema FIRST (this is the schema-drift bug; it bit prod even though local is fine).** `create_all_tables()` uses `Base.metadata.create_all` (`db.py:57-63`), which **never ALTERs an existing table**. Prod's volume predates the `product_category` column, so it likely lacks it — and any device drill-down query throws `OperationalError: no such column: interventions.product_category`. Add the column before any backfill:

```bash
# SSH/console into the Fly machine, then:
fly ssh console -a trialcat
# inside the machine:
python - <<'PY'
import sqlite3
c = sqlite3.connect("/data/trialcat.db")
cols = [r[1] for r in c.execute("PRAGMA table_info(interventions)")]
if "product_category" not in cols:
    c.execute("ALTER TABLE interventions ADD COLUMN product_category VARCHAR(48)")
    print("added product_category")
if "device_class_hint" not in cols:
    c.execute("ALTER TABLE interventions ADD COLUMN device_class_hint VARCHAR(16)")
    print("added device_class_hint")
c.commit(); c.close()
PY
```
(SQLite `ADD COLUMN` is O(1), safe, non-locking for a single-writer file. Indexes on these columns aren't auto-created by `ADD COLUMN`; the model declares them `index=True` but `create_all` won't add an index to a pre-existing table either — add them explicitly if `/api/filters` DISTINCT scans feel slow: `CREATE INDEX IF NOT EXISTS ix_interventions_product_category ON interventions(product_category);` and same for `device_class_hint`.)

**Step 1 — trigger the full backfill** (omit `updated_since` = all-time). Re-ingest re-runs the parser, so it backfills `device_class_hint`/`product_category` for every DEVICE row touched (`loader.py:113-119` deletes old interventions and re-inserts fresh, parser-populated ones):
```bash
# Keep the machine awake for the duration FIRST (see Risk 1), then:
curl -X POST "https://trialcat.fly.dev/admin/etl/bulk" \
  -H "X-Admin-Secret: $TRIALCAT_ADMIN_SECRET"

# Poll (in-memory dict; resets if the machine restarts):
curl "https://trialcat.fly.dev/admin/etl/status" -H "X-Admin-Secret: $TRIALCAT_ADMIN_SECRET"
```
The worker streams all ~590k, batches of 1000, commits per batch (`main.py:268-311`) — resumable; a crash loses at most the in-flight ≤1000.

**Step 2 — enrich prod after bulk.** There's no admin endpoint for `enrich_fda.py`; run it on the machine:
```bash
fly ssh console -a trialcat -C "python -m app.etl.enrich_fda --kind=all --max-calls=800"
# Re-run --kind=drug daily until 'deferred' hits 0, or set OPENFDA_API_KEY (lifts cap to 120k/day).
```

**Step 3 — supplement the nightly with a periodic full sweep (recommended).** The 2-day incremental is correct for *freshness* but can never *complete* coverage, and there's no high-water-mark checkpoint (`admin_etl_refresh` recomputes `now − days` every run, `main.py:394-395`), so missed nights leave silent gaps. Add a separate monthly workflow that calls `/admin/etl/bulk` with no `updated_since`:

**New file `.github/workflows/monthly-full-sweep.yml`:**
```yaml
# Monthly FULL sweep — closes coverage gaps the 2-day incremental can never reach.
# The nightly keeps data FRESH; this keeps it COMPLETE. They're different jobs.
# Cost: $0 (GitHub Actions free tier). Requires TRIALCAT_ADMIN_SECRET secret.
name: Monthly Full Sweep
on:
  schedule:
    - cron: '0 5 1 * *'   # 05:00 UTC on the 1st of each month (after nightly)
  workflow_dispatch: {}
jobs:
  full-sweep:
    runs-on: ubuntu-latest
    timeout-minutes: 240          # full registry can take 1-3+ hours
    steps:
      - name: Wake the Fly.io machine
        run: |
          for a in 1 2 3; do
            code=$(curl -s -o /dev/null -w "%{http_code}" "https://trialcat.fly.dev/health" --max-time 15 || echo 000)
            [ "$code" = "200" ] && break || sleep 10
          done
      - name: Trigger full bulk (no updated_since = all time)
        run: |
          resp=$(curl -s -X POST "https://trialcat.fly.dev/admin/etl/bulk" \
            -H "X-Admin-Secret: ${{ secrets.TRIALCAT_ADMIN_SECRET }}" --max-time 30 || echo '{"status":"curl_error"}')
          echo "$resp"
          echo "$resp" | grep -qE '"status":"(started|already_running)"' || { echo "::error::bulk not started"; exit 1; }
      - name: Poll to completion
        run: |
          for i in $(seq 1 240); do            # up to ~2h of polling at 30s
            sleep 30
            st=$(curl -s "https://trialcat.fly.dev/admin/etl/status" -H "X-Admin-Secret: ${{ secrets.TRIALCAT_ADMIN_SECRET }}" --max-time 10 || echo '{"running":true}')
            running=$(echo "$st" | python3 -c "import sys,json;print(json.load(sys.stdin).get('running',True))" 2>/dev/null || echo True)
            if [ "$running" = "False" ]; then
              echo "$st" | python3 -m json.tool || echo "$st"
              err=$(echo "$st" | python3 -c "import sys,json;print(json.load(sys.stdin).get('error') or '')" 2>/dev/null || echo "")
              [ -n "$err" ] && [ "$err" != "None" ] && { echo "::error::$err"; exit 1; }
              exit 0
            fi
          done
          echo "::warning::full sweep still running after poll window — likely finishing on its own"
```
(A lighter alternative is a *weekly* sweep with `updated_since` = ~90 days back, which self-heals recent gaps far faster than a full registry pull — change the cron to `0 5 * * 0` and append `?updated_since=$(date -d '90 days ago' +%m/%d/%Y)` to the bulk URL. Recommend BOTH: weekly 90-day self-heal + monthly true-full.)

### Risks (prod backfill)

1. **`auto_stop_machines = 'stop'` + `min_machines_running = 0` (`fly.toml:25,27`) is the headline risk.** The bulk runs in a **daemon thread** (`main.py:355-361`) with no inbound traffic during the long background job, so Fly can sleep the machine mid-run → thread dies, `_etl_status` (in-memory dict, `main.py:184`) resets. Per-batch commit means you keep loaded data, but the run won't finish. **Mitigation:** before Step 1, either set `fly scale count 1 --region ewr` and temporarily flip `auto_stop_machines = 'off'` (redeploy), or keep it awake by curling `/health` every ~60s for the duration. Restore the stop policy after.

2. **SQLite size on a 1GB volume / 1 shared CPU (`fly.toml:42-46`).** Local is ~6.3 KB/trial (15.9 MB / 2,500). 590k trials ≈ **3.7 GB** plus indexes/WAL → budget ~5 GB. **Verify the `trialcat_data` volume is ≥5 GB** (`fly volumes list -a trialcat`); the default mount may be 1–3 GB. A bulk into a too-small volume fails loud mid-run with `disk I/O error`. Also: a multi-GB single-file SQLite on 1 shared CPU will slow `/api/aggregate` and `/api/stats`; ensure indexes exist on `interventions.type`, `interventions.product_category`, `interventions.device_class_hint`, `trials.phase`, `trials.overall_status`, `locations.country_code` (the model declares them, but `create_all` won't add them to the pre-existing prod table — see Step 0 note).

3. **No high-water checkpoint** (`main.py:394-395` recomputes `now − days` each nightly). A few missed nights silently leave gaps only a full/periodic sweep closes — the Step 3 workflow is the structural fix, not a nicety.

4. **openFDA budget** (`enrich_fda.py`): no-key tier ~1,000/day. A full-prod enrichment of ~74k device + ~209k drug rows will defer heavily on the first pass. Set `OPENFDA_API_KEY` (`config.py:56`, lifts to 120k/day) before enriching prod, or accept multi-day convergence (the candle stays lit on deferred rows — heuristic `product_category` is already populated by the parser, so the map is never blank while FDA enrichment catches up).

---

## File-level summary of recommended changes

| File | Change | Priority |
|---|---|---|
| `backend/app/services/stats.py` (`aggregate_by_country` ~136, `aggregate_by_us_state` ~176) | Dedup-before-sum subquery so `total_enrollment` isn't inflated by the intervention join | **P1 bug** |
| `backend/app/services/ctgov_client.py` (sig ~89, query.term ~120) | Add `intervention_type` param → `AREA[InterventionType]<TYPE>` ANDed into `query.term` | P2 |
| `backend/app/etl/refresh.py` (args ~118, `fetch_batch` ~161, log ~178) | Add `--intervention-type` flag, pass through | P2 |
| `backend/app/etl/reclassify_devices.py` (new) | Local-only re-apply of name heuristic to existing DEVICE rows after keyword tuning | P3 stretch |
| Prod `/data/trialcat.db` via `fly ssh console` | `ALTER TABLE interventions ADD COLUMN product_category` (+ `device_class_hint`, + indexes) — schema drift fix | **P1 (prod)** |
| `.github/workflows/monthly-full-sweep.yml` (new) | Periodic full `/admin/etl/bulk` to close coverage gaps the incremental can't | P2 |

**No changes needed** to `filters.py`, `intervention.py`, `index.html`, or `map.js` for the device-class drill-down — that wiring is already complete and correct on disk (verified line by line). The dev DB at `data/trialcat.db` is already representative and FDA-enriched; preserve it.

Key files (absolute):
- `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\services\stats.py`
- `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\services\ctgov_client.py`
- `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\etl\refresh.py`
- `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\etl\enrich_fda.py`
- `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\services\parser.py`
- `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\main.py`
- `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\fly.toml`
- `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\.github\workflows\nightly-refresh.yml`