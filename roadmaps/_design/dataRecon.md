The docs pages are JS-rendered so WebFetch can't read them. My live API probing already gave authoritative, definitive evidence — that's stronger than docs. I have everything needed for both tasks. Let me do one final confirmation: the bulk endpoint with no `updated_since` would fetch all ~590k (runtime/size risk), and confirm the local DB file size is ~16MB for 2529 trials to estimate prod scaling.

I have all evidence needed. Final report:

---

# (A) DATA STATE — Diagnosis & Fix

## What's actually true (corrected from the task premise)
- **Local dev DB is NOT 30 PHASE3 trials.** `backend/data/trialcat.db` (16.1 MB) holds **2,529 trials** with diverse phases (NA 973, null 627, PHASE2 328, PHASE3 218, PHASE1 207, PHASE4 150, EARLY_PHASE1 26), study types (INTERVENTIONAL 1902, OBSERVATIONAL 616, EXPANDED_ACCESS 6), and 11 intervention types (DRUG 1668, OTHER 751, BEHAVIORAL 428, DEVICE 410, PROCEDURE 362, BIOLOGICAL 215, DIETARY_SUPPLEMENT 164, DIAGNOSTIC_TEST 128, RADIATION 51, COMBINATION_PRODUCT 19, GENETIC 10). So the dev dataset is already representative across intervention types/phases. If a fresh clone shows 30/all-PHASE3, that's a stale/empty volume, not the committed `.db`.
- **CT.gov live total today: 589,884 studies** (apiVersion 2.0.5, dataTimestamp 2026-06-16). Prod's 23,698 is ~4% of the registry.

## WHY the prod dataset is partial (precise root cause)
There is **no broad initial backfill anywhere in the automated path**. Trace:
- `nightly-refresh.yml` (cron `0 4 * * *`) only calls `POST /admin/etl/refresh?days=2`.
- `admin_etl_refresh` (main.py:359) computes `since_date = now - 2 days` and calls `_run_bulk_etl(updated_since=since_date)`.
- `_run_bulk_etl` (main.py:222) passes `updated_since` into `client.search_studies`, which sets `filter.advanced=AREA[LastUpdatePostDate]RANGE[<since>,MAX]` (ctgov_client.py:126-131).
- So the registry is only ever swept for **trials whose LastUpdatePostDate falls in a rolling 2-day window**. Trials not edited recently are never fetched. The 23,698 figure is just the accumulation of ~2-day windows since whatever the last manual `/admin/etl/bulk` (no `updated_since`) run reached before it died/was interrupted. `/admin/etl/bulk` exists and CAN do a full sweep (omit `updated_since` → `search_studies(updated_since=None)` → no date filter → all 590k), but **nothing schedules or completed it**.
- **It is purely a scheduling/orchestration gap, not a code bug in the ETL itself.** The bulk worker batches at 1000 and commits per batch (`_run_bulk_etl`), so it's safe to resume.

## Secondary real bug found (schema drift — affects task-1 device drill-down)
`app/models/intervention.py` declares `product_category` (and `device_class_hint`), but the **live `interventions` table has NO `product_category` column** (PRAGMA: id, trial_nct_id, type, name, description, device_class_hint, fetched_at, updated_at). `create_all_tables()` uses SQLAlchemy `create_all`, which **never ALTERs an existing table** — so the column the model added later was never created on the existing volume. Any query against `product_category` (the DEVICE product-type drill-down task-1/the game needs) throws `OperationalError: no such column`. This must be migrated before the device-vs-drug drill-down works. Files: `backend/app/models/intervention.py:63`, `backend/app/db.py` (`create_all_tables`).

## EXACT FIX

**(1) Backfill a representative LOCAL dev dataset across diverse intervention types/phases.** The CLI `app/etl/refresh.py` cannot filter by intervention type directly (no `--intervention-type` flag; `--intervention` is a name query), so slice by therapeutic area + phase to get spread, or do one bounded broad pull. From `backend/`:
```
# Broad bounded slice (fast, diverse) — ~2.5k trials like current dev DB
python -m app.etl.refresh --limit=3000

# Or guarantee intervention-type coverage with targeted device + drug pulls:
python -m app.etl.refresh --condition=cardiovascular --limit=500
python -m app.etl.refresh --intervention=catheter --limit=300      # devices
python -m app.etl.refresh --intervention=stent --limit=300         # devices
python -m app.etl.refresh --intervention=pembrolizumab --limit=200 # biologics/drug
python -m app.etl.refresh --condition=diabetes --phase=PHASE3 --phase=PHASE4 --limit=500
```
First, fix the schema drift so the device drill-down works (no Alembic in repo):
```
python -c "import sqlite3; c=sqlite3.connect('data/trialcat.db'); c.execute('ALTER TABLE interventions ADD COLUMN product_category VARCHAR(48)'); c.commit()"
```
(or delete `data/trialcat.db` and let `create_all_tables()` rebuild fresh with the current model, then re-run refresh). Then backfill `product_category`/`device_class_hint` for DEVICE rows via the heuristic parser.

**(2) Trigger a full/broader PROD backfill via existing `/admin/etl/bulk`** (omit `updated_since` = all-time = full registry):
```
curl -X POST "https://trialcat.fly.dev/admin/etl/bulk" \
  -H "X-Admin-Secret: $TRIALCAT_ADMIN_SECRET"
# poll:
curl "https://trialcat.fly.dev/admin/etl/status" -H "X-Admin-Secret: $TRIALCAT_ADMIN_SECRET"
```
Worker streams all ~590k, batches of 1000, commits per batch — resumable if it dies.

**(3) Supplement the nightly?** Yes. The 2-day incremental is correct for *freshness* but can never *complete* coverage. Add either (a) a one-time full bulk now, then keep nightly incremental, or (b) a **monthly/weekly fuller sweep** workflow that calls `/admin/etl/bulk` with no `updated_since` (or a wide `updated_since`, e.g. 90 days) to self-heal gaps. Recommend a separate `monthly-full-sweep.yml` (`cron: '0 5 1 * *'`) hitting `/admin/etl/bulk`, with a longer poll timeout than the nightly's 20 min.

## RISKS
- **Fly.io runtime:** full bulk = ~5,900 pages × pageSize 100 at CT.gov's pace = roughly 1–3+ hours. The bulk runs in a **daemon thread** with no persistence of progress across machine restarts — if Fly's `auto_stop_machines` sleeps the machine mid-run (no inbound traffic during a long background job), the thread dies and `_etl_status` resets (in-memory dict). Mitigations: ensure `auto_stop_machines=false` or keep it awake during backfill; bump the GH Action `timeout-minutes` and poll loop; the per-batch commit means restarts only lose the in-flight ≤1000.
- **SQLite size:** 2,529 trials = 16.1 MB → ~6.4 KB/trial. 590k trials ≈ **3.5–4 GB** on the Fly volume (plus indexes/WAL → budget ~5 GB). Verify the Fly volume is large enough; a single-file SQLite of that size on a 1-CPU machine will also make `/api/aggregate` and `/api/stats` queries slower — confirm indexes exist on `interventions.type`, `trials.phase`, `trials.overall_status`.
- **No `updated_since` checkpoint table:** nightly always recomputes "now − 2 days"; it doesn't record the last successful high-water mark, so a few missed nights silently leave a gap only a full sweep closes — another reason for the periodic full sweep.

---

# (B) CT.GOV FACETS — Confirmed via live API (apiVersion 2.0.5, 2026-06-16)

## aggFilters facets (what's valid)
Probing the live `/api/v2/studies?aggFilters=` endpoint, **valid** facet names return results; invalid ones return `"Unknown aggregation-filter name: <name>"`. Confirmed valid: **`phase`, `status`, `studyType`, `sex`, `funderType`, `healthy`, `docs`, `results`**.

- **studyType** facet — confirmed valid. Value codes: `int` (INTERVENTIONAL, 450,120), `obs` (OBSERVATIONAL, 137,735), `exp` (EXPANDED_ACCESS, 1,055). (Matches the client's `study_type_map`.)
- **phase** facet — valid; codes `0/1/2/3/4/na` (matches client `phase_map`).
- **status** facet — valid; lowercase short codes `rec/not/enr/act/sus/ter/com/wit/unk` (matches client `status_map`).

## Intervention type — NO aggFilter exists (key finding for task-1)
Every plausible key (`interventionType`, `interventionTypes`, `intervention`, `intvType`, `intervType`) returns **`Unknown aggregation-filter name`**. There is **no aggFilter facet for intervention type**. To filter by it you must use the Essie/advanced query expression:
```
query.term=AREA[InterventionType]DRUG     -> 208,779 studies
query.term=AREA[InterventionType]DEVICE   ->  74,125 studies
query.term=AREA[InterventionType]BIOLOGICAL -> 29,563 studies
```
(URL-encoded: `AREA%5BInterventionType%5D...`). **Implication for the code:** the current `CTGovClient.search_studies` has no `intervention_type` param — to fetch by device-vs-drug you must add an `AREA[InterventionType]<TYPE>` expression into `query.term` (it already maps `advanced_query → query.term`, ctgov_client.py:120-121), so you can pass it through `advanced_query` today.

## Full CT.gov InterventionType enum — confirmed (11 values, exact)
From `/api/v2/stats/field/values?fields=InterventionType` (field path `protocolSection.armsInterventionsModule.interventions.type`, uniqueValuesCount 11, missingStudiesCount 59,657):
1. DRUG — 208,779
2. OTHER — 120,889
3. DEVICE — 74,125
4. BEHAVIORAL — 62,302
5. PROCEDURE — 58,809
6. BIOLOGICAL — 29,563
7. DIAGNOSTIC_TEST — 19,021
8. DIETARY_SUPPLEMENT — 17,710
9. RADIATION — 10,541
10. COMBINATION_PRODUCT — 3,354
11. GENETIC — 2,847

This exactly matches the 11-value enum in the prompt and in `app/models/intervention.py:3-6`.

## StudyType enum — confirmed (3 values)
Field `protocolSection.designModule.studyType`, 3 values: INTERVENTIONAL (450,120), OBSERVATIONAL (137,735), EXPANDED_ACCESS (1,055).

## Device class (I/II/III) — CONFIRMED ABSENT from CT.gov
`/api/v2/stats/field/values?fields=DeviceClass` → **`Unknown piece name of field path: DeviceClass`**. There is no DeviceClass field anywhere in the CT.gov schema. This confirms the design note in `intervention.py:8-11`: device class must come from FDA's 510(k)/PMA database, not CT.gov. The repo currently approximates it with `device_class_hint` (regex from description) and the intended `product_category` heuristic (the column that's missing from the live table — see the schema-drift bug above).

This grounds the game's pathway divergence: **drug/biologic = NDA/BLA**, **device = 510(k)/PMA** — and the data reality is that CT.gov gives you `InterventionType` (drug vs device split, queryable via `AREA[InterventionType]`) but NOT regulatory class, so the device Class I/II/III drill-down requires the FDA DB cross-reference, exactly as the model comments anticipate.

Relevant files:
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\main.py` (admin ETL endpoints; `_run_bulk_etl`)
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\services\ctgov_client.py` (aggFilters/query.term construction; no intervention_type param)
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\models\intervention.py` (declares `product_category` — missing from live table)
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\data\trialcat.db` (2,529 trials, 16.1 MB, no `product_category` column)
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\.github\workflows\nightly-refresh.yml` (incremental-only; no full sweep)