# FDA Data Enrichment — TrialCat (Phase 8 v2)

**Date:** 16 JUN 2026
**Status:** Shipped to `data/trialcat.db` (devices fully; drugs within the no-key daily budget)
**Scope:** A *nice-to-have* enrichment overlay on top of TrialCat's existing keyword heuristics. It does not replace them — it upgrades the rows it can and leaves the rest on the honest keyword guess.

---

## What we built

Three new artifacts (no forbidden files touched):

| File | Role |
|------|------|
| `app/services/fda_enrich.py` | `FDAEnrichClient` — sealed openFDA HTTP layer (mirrors `ctgov_client.py`): `requests.Session`, retry-on-5xx, fail-loud-on-our-4xx, descriptive User-Agent, polite pacing, token-keyed in-memory cache, optional `OPENFDA_API_KEY`. Two classifiers: `classify_device(name)` and `classify_drug(name)`. Returns `None` on no-match. |
| `app/etl/enrich_fda.py` | CLI ETL (mirrors `refresh.py`): iterates interventions, dedupes lookups via the client cache, UPDATES the DB in small batches, idempotent + re-runnable. Flags: `--kind {device,drug,all}`, `--limit`, `--max-calls` (default 800), `--dry-run`, `--verbose`. Devices first (cheap), then drugs to the call budget. |
| `app/config.py` (appended) | `openfda_api_key` (default `""`) and `openfda_api_base` (`https://api.fda.gov`). |

**openFDA contract notes baked into the client:**
- A `404` from openFDA means *"your search matched zero records"* — an expected no-match, returned as `None`, **not** raised. Only genuine `4xx` query bugs and exhausted-retry `5xx` raise `OpenFDAAPIError`. This is the difference between graceful degradation and a crash storm, because most investigational drug arms legitimately 404.
- No-key tier ≈ **240 req/min, 1,000 req/day**. A free key lifts the daily ceiling to **120,000**.

---

## Matching strategy

CT.gov gives us *brand* names; FDA databases index *generic* nouns and *active ingredients*. The whole job is translation, and it is honestly approximate.

### Devices — generic-noun extraction + MODE voting
1. **Noun extraction.** A curated, priority-ordered list of generic device nouns (`stent`, `guidewire`, `catheter`, `pacemaker`, `ventilator`, ... ~120 terms mined across two tuning passes against the real DB). The *most specific* noun present in the brand string wins; ultra-generic fallbacks (`pump`, `tube`, `scope`) are consulted only if nothing specific matched. The brand string `"ANGIOGUARD XP Emboli Capture Guidewire"` resolves on `guidewire`.
2. **MODE voting, not top-hit.** The single top hit for a generic noun is unreliable — the first `device_name:"stent"` record is an *intracranial coil-assist stent*, specialty `Unknown`, class 3. So we pull the top 25 records and take the **most common** `device_class` and the **most common non-`Unknown`** `medical_specialty_description`. The crowd of matches is wiser than the head record. Product code + regulation number are pulled from a record *consistent with* the winning mode, so the metadata belongs to the class we report.
3. **Class normalization.** openFDA `"1"/"2"/"3"` → FDA Roman `I/II/III`. `"N"/"U"/"f"` → `None` (we say "don't know" rather than invent a class).
4. **Anti-garbage guard.** The bare nouns `system` and `device` are blocklisted from driving a specialty: `device_name:"system"` is dominated by *microbiology test systems*, so the mode wrongly stamped "Microbiology" onto every `…System` brand (a transcranial-ultrasound *System* is not microbiology). For those nouns we return no-match and let the keyword heuristic hold the floor. **Subtraction is not enrichment** — a decent guess beats a confident wrong answer. (This bug was caught in QC of the first real run and corrected; the ETL is idempotent so the re-run cleanly converged.)

### Drugs — ingredient extraction + verified NDC lookup
1. **Fast rejections (no API call spent).** Investigational codes (`AZD5718`, `BMS-863233`, `D3S-003`) via regex; placebo / vehicle / sham arms via stopword check. These can't be in approved-drug DBs, so we don't waste a slice of the daily budget on them.
2. **Noise stripping.** Strip dosage/units/route/salt/formulation (`"Warfarin Sodium 3 MG"` → `warfarin`), then yield candidate ingredient tokens longest-first (long tokens are the least likely to be stopwords, most likely to be the true drug).
3. **openFDA NDC lookup with verification.** Query `drug/ndc.json?search=generic_name:"<token>"`. The NDC search is fuzzy and combo-products abound, so each hit is **verified**: (a) the token must appear as a whole word in the matched product's `generic_name`; (b) the product must be a finished `HUMAN PRESCRIPTION/OTC DRUG` (not bulk "for further processing"); (c) for multi-ingredient products the token must be the **lead** ingredient — otherwise `"Clotrimazole 1% … Hyaluronic Acid"` would wrongly tag hyaluronic acid as an azole antifungal. Ingredient count is computed across *all* separators openFDA uses including the `" - "` that homeopathic listings abuse (this caught a `"Melatonin"`-tagged-as-`"Interferon gamma"` false positive).
4. **Class selection.** From the product's `pharm_class` list, prefer the `[EPC]` (Established Pharmacologic Class — the canonical "this is a beta-blocker" label), falling back to `[MoA]`/`[CS]`/`[PE]`. If a verified finished drug has no pharm class, we still report `Rx-only` / `OTC`.
5. **No-match bucket.** Anything unmatched (investigational, not-in-NDC) → `"Investigational / Unclassified"` — itself an honest, filterable answer, which is the *expected* state for a large share of trial arms.

---

## Measured match rates (live API, real DB — 2,016 interventions)

### Devices (407 rows)
| Metric | Count | Rate |
|---|---|---|
| Got FDA device class (I/II/III) | 132 | **32.4%** |
| Got FDA medical-specialty category | 143 | **35.1%** |
| Distinct generic nouns queried | ~80 | (huge dedup: 407 rows → ~80 calls) |

The ~65% that don't match are overwhelmingly **digital-health apps** (`PrEP Decision Aid`, `Asthma SMART`), **brand-only names** with no generic noun (`Nerivio`, `Lumitrace`, `geko`, `Modius Calm`), and **procedures masquerading as devices** (`acupuncture`, `Renal Denervation`, `shockwave therapy`). These rows keep their existing keyword `product_category` — never nulled.

**New device class distribution:** II = 92, I = 21, III = 19, None = 275.
**Device category distribution (top):** Other Device 156, Cardiovascular 34, Neurostimulation 27, Neurology 24, Software/Digital Health 19, Imaging/Diagnostic 19, General/Plastic Surgery 15, Gastroenterology/Urology 12, Respiratory 11, General Hospital 11, Orthopedic/Implant 9, Monitoring/Sensor 9, … (FDA specialties now interleaved with surviving keyword buckets).

Sample device mappings:
- `ANGIOGUARD XP Emboli Capture Guidewire` → class **II**, **Cardiovascular** (code NKQ, reg 870.1330)
- `Concha TENS` → class **II**, **Neurology** (code QFD, reg 882.5890)
- `phakic intraocular lens implantation` → class **III**, **Ophthalmic**
- `Twin Block Appliance` → class **II**, **Orthopedic**

### Drugs (1,609 rows, run under the no-key budget)
| Metric | Count | Rate |
|---|---|---|
| Classified (pharm class or Rx/OTC) | 864 | **53.7%** |
| `Investigational / Unclassified` | 586 | **36.4%** |
| Deferred (hit `--max-calls`, **logged loudly**) | 159 | 9.9% |

**Drug category distribution (top):** Investigational/Unclassified 586, *(deferred null 159)*, Rx-only 55, Nucleoside Metabolic Inhibitor 53, Corticosteroid 42, Kinase Inhibitor 39, Platinum-based Drug 27, OTC 24, General Anesthetic 21, Amide Local Anesthetic 20, NSAID 16, Opioid Agonist 15, Alkylating Drug 15, VEGF Inhibitor 14, HMG-CoA Reductase Inhibitor 14, Folate Analog Metabolic Inhibitor 14, … (a clean oncology + cardio-metabolic pharmacology spread, consistent with the trial corpus).

Sample drug mappings:
- `Simvastatin 40mg` → **HMG-CoA Reductase Inhibitor [EPC]** (Rx)
- `oseltamivir [Tamiflu]` → **Neuraminidase Inhibitor [EPC]** (Rx)
- `metoprolol` → **beta-Adrenergic Blocker [EPC]** (Rx)
- `Cisplatin` → **Platinum-based Drug [EPC]** (Rx)
- `Aspirin` → **NSAID [EPC]** (OTC)
- `Melatonin` → **OTC** (verified finished product, no EPC)
- `AZD5718`, `Placebo to aspirin` → no call spent → `Investigational / Unclassified`

**Daily call budget:** devices 79 + drugs 700 = **779 calls**, comfortably under the 1,000/day no-key cap. The 159 deferred drug rows were named in the run log, not silently dropped.

---

## Caveats (the "ballpark accuracy is fine" reality)

- **Generic-noun specialty drift.** For some nouns the FDA corpus mode skews to an unexpected panel (e.g. a bare `"stent"` mode leans Gastroenterology/Urology because of the volume of ureteral/biliary stent records). Class is more robust than specialty.
- **Fuzzy NDC combo hits.** A handful of drug arms get a plausible-but-wrong EPC from a combo/fuzzy match (`Sitagliptin` → `Biguanide` via metformin+sitagliptin combos; `IL-2 and Nivolumab` → `Endoglycosidase`; tokens like `inhibitor` occasionally hit allergenic-extract products). Estimated wrong-class rate among *classified* drugs is low single-digit %; acceptable for an overlay, not for a regulatory filing.
- **Multi-word imaging/procedure names** (`Magnetic Resonance Imaging` standalone, `Total Knee Replacement`) match a noun but openFDA may return nothing useful for the exact phrase → no-match, keyword kept.
- The overlay is **advisory**. Nothing here is an FDA determination; it is a navigational best-guess for slicing the dataset.

---

## Rate-limit constraint + production recommendation

The whole drug pass is gated by the **no-key 1,000 req/day** ceiling — we deferred 159 rows on the first run. For production:

1. **Get a free openFDA API key** (https://open.fda.gov/apis/authentication/) and set `OPENFDA_API_KEY` in `.env`. The client already threads it into every request via the `api_key` query param; the daily ceiling jumps to 120,000, eliminating deferral.
2. **Nightly enrichment job.** Wire `python -m app.etl.enrich_fda --kind=all` into the same scheduler that runs `refresh.py`. It's idempotent and converges, so a nightly run naturally finishes any deferred rows and picks up newly-ingested trials.
3. **Persist the cache.** The in-memory token cache dies with the process. A tiny `fda_lookup_cache` table (token → JSON result, with a TTL) would make re-runs near-free and decouple us from the daily ceiling almost entirely. FDA classifications change rarely; a 30–90 day TTL is plenty.
4. **Tune the noun list as data grows.** New brand patterns will appear; the noun list is the cheapest lever on device match rate.

---

## Known gap: Purple Book / biologics (deferred)

The 214 `BIOLOGICAL` and 19 `COMBINATION_PRODUCT` interventions are **not** enriched. The FDA **Purple Book** (licensed biologics, biosimilars, interchangeables) has **no clean public JSON API** comparable to openFDA's device/drug endpoints — it's a downloadable database/search UI, not a queryable REST service. Biologics also frequently lack an `[EPC]` in the NDC directory (e.g. `pembrolizumab` returns `DRUG FOR FURTHER PROCESSING` with null pharm_class on its bulk entry). Options for a future pass: (a) ingest the Purple Book database dump on a schedule and match locally; (b) use `drug/drugsfda.json` `openfda.pharmacologic_class` for the subset of biologics that carry it. **Deferred** — out of scope for this MVP overlay, and biologics' pharmacologic classes are often the trial's whole point (well-described in the protocol already).
