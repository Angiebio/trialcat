I have everything I need: the exact `Trial`/`Intervention` fields, the intervention-type enum (DRUG/BIOLOGICAL/DEVICE/...), device class/product-category heuristics, the therapeutic-area buckets, enrollment fields, the `openai_*` config (model `gpt-4o-mini`, optional key) and the `runpod`/local-LLM fallback story. The spec below is built to seed directly from this data and plug into this stack. The board-art canon (6 characters, REG/Staff decks, organ+outcome dice, valuation race, decision forks) is honored as flavor while the mechanics are rebuilt into a deterministic resource-management sim.

---

# TrialCat v2 — "REG: The Strategy Game" — Full Web Sim Mechanics Spec

**Version 1.0 (16JUN2026) · For developer implementation · Deterministic JS engine + FastAPI seed/score/LLM endpoints**

> Design north star: a single-player, ~8–15 minute, *Plague-Inc-for-regulatory-affairs* resource sim. Every game is seeded by a **real ClinicalTrials.gov trial** pulled from the existing `trials` table. The pathway, difficulty, and flavor all derive from that real trial's actual fields. The board game's shoots-and-ladders valuation track becomes a **two-axis survival sim**: keep cash alive while you convert money + time into *evidence* and *regulatory goodwill*, racing a competitor to approval. It must make a real reg-affairs professional both *learn something* and *laugh*.

---

## 0. Engine Architecture & Where It Lives

- **Deterministic JS engine** (`frontend/static/game/engine.js`): pure functions `applyAction(state, action) -> {state, log[]}` and `seededRandom`. All randomness flows through a **single seeded PRNG** (mulberry32 seeded from `state.seed`) so a game is fully replayable and **server-verifiable** (anti-cheat for the leaderboard). No `Math.random()` anywhere in the engine.
- **FastAPI** adds three thin endpoints (new router `app/routes/api_game.py`), reusing existing `get_db`, models, and `settings`:
  - `GET /api/game/seed` — picks a real trial, returns the **GameSeed** (Section 9).
  - `POST /api/game/review` — the optional LLM "FDA Reviewer" (Section 7). Pure scripted fallback if `settings.openai_api_key` is empty or the call fails.
  - `POST /api/game/score` — re-runs the action log through a server copy of the engine, validates the final score, writes to a `game_scores` leaderboard table (email + display name, no auth).
- **Wiring discipline (per CLAUDE.md):** the engine is the single source of truth; the UI only dispatches actions and renders `state`. The score endpoint *replays* the log rather than trusting a client-sent number — fail loud if replay ≠ claimed score.

---

## 1. Theme & Goal

You are the **regulatory strategist** for a startup shepherding **one real candidate product** (drug, biologic, or device — taken verbatim from the seeded trial's lead intervention) from its current stage through to **FDA market authorization**, before:

- your **Capital** hits $0 ("You are out of money!" — the original board's lose screen), **or**
- the **Competitor** reaches approval first ("Scooped — they got the label claim you wanted"), **or**
- you run out of the **Quarters** allotted (patent cliff / investor patience expires).

**Win** = receive FDA **Approval/Clearance** with resources to spare. Score rewards *speed + efficiency + evidence quality*; it punishes wasted capital, sloppy submissions, and goodwill burned on shortcuts.

The 6 original characters become **selectable "advisor" personas** (a light strategic modifier + the comedy), see Section 4.6.

---

## 2. Resources (the state variables)

Four resources. Two are *survival* (lose at zero), two are *quality* (gate outcomes and score).

| Resource | Field | Meaning (reg-affairs truth) | Start (baseline, before difficulty) | Hard fail |
|---|---|---|---|---|
| **Capital ($M)** | `capital` | Cash runway. Everything costs money; you raise it at funding forks. | `$50M` | `<= 0` → LOSE (out of money) |
| **Quarters** | `quartersLeft` | Time. Each turn = 1 fiscal quarter. The patent/investor clock. | `28` quarters (7 yr) | `<= 0` → LOSE (clock expired) |
| **Evidence (0–100)** | `evidence` | Strength of the clinical/nonclinical data package for the *current* stage. Resets-with-carryover at each stage gate. | `10` | n/a (low evidence → gate failures) |
| **Goodwill (0–100)** | `goodwill` | Regulatory relationship capital: pre-sub meetings attended, no shortcuts taken, clean conduct. FDA "knows you and trusts your data." | `50` | `< 0` clamps to 0; very low → harsher review |

Plus tracked scalars that aren't "spent" but drive logic & score:
- `competitorProgress` (0–100, advances each turn; reaching 100 = scooped).
- `integrityFlags` (count of shortcuts taken — clinical holds, cut-corner CMC; each one taxes the final score and goodwill).
- `dataQuality` (0–100, a running weighted average of how well you've enrolled/powered each study — feeds the LLM reviewer and score).

**Why these four (philosophical comment for the code):** *Drug development is the alchemy of turning money + time into belief. Capital and Quarters are what you spend; Evidence and Goodwill are what you must accumulate to buy the regulator's "yes." The game is honest because, like real life, you can be cash-rich and still fail for lack of evidence — or data-perfect and still die because the runway ran out first.*

---

## 3. The Board — Regulatory Pathway as Stages

The board is a **linear stage track** (not the original valuation snake; that money-ladder is repurposed into the score/funding system). The track **diverges by intervention type** of the seeded trial. Each stage is a node with an entry effect, an action menu, and a **stage gate** (a checkpoint you must pass to advance). Crossing a gate consumes accumulated evidence and emits a per-stage score.

### 3.1 DRUG / BIOLOGICAL pathway (`pathway: "DRUG"`)
Triggered when lead intervention `type ∈ {DRUG, BIOLOGICAL, GENETIC, DIETARY_SUPPLEMENT}` (BIOLOGICAL routes to a BLA at the end instead of NDA).

| # | Stage `id` | Name | Entry / theme | Gate requirement |
|---|---|---|---|---|
| 0 | `PRE_IND` | Pre-IND | Nonclinical + CMC; optional Pre-IND meeting with FDA | evidence ≥ 25 |
| 1 | `PHASE1` | Phase 1 (Safety) | Dose-finding, small N, MTD | evidence ≥ 35 |
| 2 | `PHASE2` | Phase 2 (Proof of concept) | Efficacy signal, dose selection; optional End-of-Phase-2 meeting (big goodwill lever) | evidence ≥ 50 |
| 3 | `PHASE3` | Phase 3 (Pivotal) | Large, powered, the expensive one | evidence ≥ 70 |
| 4 | `NDA_BLA` | NDA / BLA submission | The marketing application — **LLM Reviewer milestone** (Section 7) | review pass |
| 5 | `APPROVED` | Approval | Win state | — |

### 3.2 DEVICE pathway (`pathway: "DEVICE"`)
Triggered when lead intervention `type ∈ {DEVICE, DIAGNOSTIC_TEST}`. **Sub-route by `device_class_hint` / `product_category`:** Class III or PMA-signal products take the **PMA** branch (pivotal required); everything else takes the **510(k)** branch (predicate + pilot, no full pivotal).

| # | Stage `id` | Name | Entry / theme | Gate requirement |
|---|---|---|---|---|
| 0 | `PRE_SUB` | Pre-Submission (Q-Sub) | Bench + design; Pre-Sub meeting is the device-world goodwill superweapon | evidence ≥ 25 |
| 1 | `PILOT` | Pilot / Feasibility study | Small first-in-human | evidence ≥ 40 |
| 2 | `PIVOTAL` | Pivotal study | **PMA branch only:** required, expensive. **510(k) branch:** auto-skipped (advance with evidence ≥ 50 via predicate equivalence) | PMA: evidence ≥ 70 · 510(k): evidence ≥ 50 |
| 3 | `SUBMISSION` | 510(k) or PMA submission | Marketing application — **LLM Reviewer milestone** | review pass |
| 4 | `CLEARED` | Clearance / Approval | Win state | — |

> **Divergence rule (must implement):** the seed endpoint computes `pathway` and `submissionType` (`NDA` | `BLA` | `510k` | `PMA`) from the lead intervention and class hint. The two pathways differ in stage count, gate thresholds, and per-stage costs (device pilot/pivotal are cheaper per-quarter than drug Phase 3 but 510(k) has a much weaker evidence ceiling — teaching the real "least burdensome" device contrast).

### 3.3 COMBINATION / OBSERVATIONAL / ambiguous
- `COMBINATION_PRODUCT` → DRUG pathway + a flavor flag `combo: true` that adds one extra "assign the lead center (CDER vs CDRH)" event (teaches the combination-product jurisdiction joke).
- If the seeded trial is `OBSERVATIONAL` or has no clean intervention type, the seed endpoint **re-rolls** to a different interventional trial (the game needs a regulated product to shepherd). Fail loud server-side if no interventional trial is found after N tries.

---

## 4. Turn Loop & Action Set

A turn = **one fiscal quarter**. The loop is strictly ordered so the engine is deterministic:

```
START TURN
 1. UPKEEP   — quartersLeft -= 1; pay stage burn-rate (capital -= stageBurn);
               competitorProgress += competitorSpeed (modified by your tempo);
               if capital<=0 or quartersLeft<=0 or competitorProgress>=100 -> resolve LOSE.
 2. ACTIONS  — player chooses 1..N actions until ALL action points (AP) spent.
               Default AP per turn = 2. Actions cost AP + resources (table 4.1).
 3. EVENT    — draw 1 event card from the active deck (Section 5), apply effects,
               show log. (Some actions modify the draw, e.g. buy "regulatory intel".)
 4. ROLL     — for each action this turn flagged `rolls:true` (mainly RUN_STUDY),
               resolve its dice outcome now (Section 6) and apply evidence/quality deltas.
 5. GATE?    — if player chose ADVANCE_STAGE and gate requirement met, cross gate:
               emit stageScore, carry over (evidence *= 0.6), enter next stage.
 6. END TURN — recompute dataQuality; autosave state; render.
```

### 4.1 Action set (the strategic verbs)

Each action is `{type, payload}` (full contract in Section 10). `AP` = action-point cost.

| Action `type` | AP | Cost | Effect | Reg-affairs lesson |
|---|---|---|---|---|
| `RUN_STUDY` | 2 | `$` scaled by stage + chosen rigor | Rolls dice (Sec 6); converts capital→evidence & dataQuality. Player picks **rigor**: `lean` (cheap, low N, high variance) / `standard` / `gold` (expensive, high N, low variance, +goodwill). | Powering studies: you pay for certainty. |
| `PRESUB_MEETING` | 1 | `$3M` + 1 quarter | +12 goodwill, reveals the next gate's true threshold, reduces next review's deficiency odds. Once per stage. | Talk to FDA *early*; meetings de-risk. |
| `HIRE_CRO` | 1 | `$8M` upfront | +0.5 AP/turn for 4 turns (parallelize), small dataQuality boost. (The board's "Hire CRO?" fork.) | Outsourcing buys speed at cash cost. |
| `RAISE_CAPITAL` | 1 | costs goodwill if done too often | +Capital (amount scaled by current evidence & valuation; high evidence = better terms). Dilution penalty to final score. | Fundraising on data strength; dilution is real. |
| `STRENGTHEN_CMC` | 1 | `$4M` | +evidence (manufacturing/quality), reduces a class of review deficiencies. | CMC kills more NDAs than efficacy does. |
| `BUY_INTEL` | 1 | `$2M` | Peek next 2 events; slow competitor +nothing (just info). | Competitive/regulatory intelligence. |
| `TAKE_SHORTCUT` | 1 | `$0` | Big immediate evidence/time gain BUT +1 integrityFlag, −15 goodwill, raises clinical-hold event odds. | The tempting, score-taxing path. |
| `ADVANCE_STAGE` | 1 | free | Attempt the stage gate this turn (resolved in step 5). | Knowing when you have "enough." |
| `SUBMIT_APPLICATION` | 2 | filing fee `$3M` | Only at `NDA_BLA`/`SUBMISSION` stage. Triggers the **LLM Reviewer** (Sec 7). | The big swing. |

**Skill vs. luck:** the *choices* (when to advance vs. gather more evidence, rigor level, when to meet FDA, whether to shortcut, when to raise) are pure skill. Dice add variance *within* a chosen rigor band — higher rigor narrows the variance, so skilled play converts luck into near-certainty at a cash cost. This is the core teachable tension.

### 4.6 Advisor personas (the 6 original characters → strategic modifiers)
Pick one at game start. Pure flavor + a small asymmetry (keeps the IP & comedy, adds replay value):

| Persona | Modifier | Joke |
|---|---|---|
| **Dr. Curzitall** (Doctor) | +10 starting evidence, −10% study cost | "cures it all" |
| **D. Lay, JD** (Lawyer) | Review deficiencies cost 1 fewer quarter to fix; +goodwill resilience | "Delay, JD" |
| **Brian** (Grad Student) | +1 starting AP but −$10M capital (cheap labor, broke) | the everyman |
| **O. Vrsink, PhD** (Scientist) | `gold` rigor costs 15% less; +dataQuality | "kitchen-sink" |
| **Prof. Goetta Grant** (Professor) | `RAISE_CAPITAL` returns more, no dilution penalty once | "gotta get a grant" |
| **Ms. N. Vested, MBA** (Investor) | Start +$25M but competitor moves 10% faster | "Invested, MBA" |

---

## 5. Event System

At step 3 each turn, draw one event from the **active deck** chosen by weighted-random (seeded PRNG). Two decks mirror the board art:

- **REG deck** — regulatory friction/fortune (drawn ~70% of turns).
- **STAFF deck** — team/operational (drawn ~30%; the board's "Draw new staff").

Each event: `{id, deck, title, flavor, category, weight, condition?, effects[]}`. `effects` are typed deltas applied through the engine (`{target: "capital"|"evidence"|"goodwill"|"quartersLeft"|"competitorProgress"|"dataQuality", op:"add"|"mul"|"set", value}`), optionally a `choice` (player picks A/B — a mini decision fork like the board's "Get acquired? Sell!/No thanks!").

**Categories (REG):**
1. `CLINICAL` — enrollment slow (−evidence gain), site found, AE cluster (−goodwill or clinical hold if integrityFlags high).
2. `REGULATORY` — Refuse-to-File risk, advisory-committee scheduled, breakthrough/fast-track designation granted (skip-ahead bonus if evidence high), guidance changes mid-stream.
3. `CMC_QUALITY` — manufacturing deviation, supplier issue (−evidence unless STRENGTHEN_CMC done).
4. `MARKET` — competitor stumbles (−competitorProgress), payer skepticism, **acquisition offer** (a choice fork: take buyout = instant cash-out + a "partial win" score, or decline and keep climbing — the board's "Sell!/No thanks!").
5. `FORTUNE` — grant funding (+capital, the board's "You got the grant funding!"), corporate venture round (the board's "Corporate venture funds awarded!").

**Categories (STAFF):** key hire (+AP or +dataQuality), key departure (−AP next turn), whistleblower (if integrityFlags > 0: big goodwill/score hit — *honesty enforced by the engine*), burnout (−AP unless capital spent).

**Determinism rule:** event selection uses `seededRandom`; weights are static data in `events.json`. Conditions (`integrityFlags > 0`, current stage, etc.) gate which events are eligible, then weighted-pick among eligible. ~40–60 cards at MVP, expandable as static JSON (the legacy "32 cards" is the comedic floor, not a cap).

---

## 6. Randomness & Dice (the two original dice, reimagined)

The board's two custom dice become the **RUN_STUDY resolver**, preserving the canon faces:

- **Organ die** (BRAIN, LUNG, LIVER, PANCREAS, BONE, HEART) → seeds a **therapeutic-area flavor event** for the study and a tiny modifier if it matches the seeded trial's `therapeutic_area` (your team "knows this organ"): a matching roll gives a small evidence bonus. Mostly flavor + teaching that indication matters.
- **Outcome die** (✓ ✗ ! @, weighted) → the **study result**:
  - ✓ **Hit** → full evidence gain for the chosen rigor.
  - @ **Mixed/Redo** → partial evidence, optional pay-to-rerun.
  - ! **Complication** → small evidence + a CLINICAL event injected (AE, protocol deviation).
  - ✗ **Miss** → minimal evidence, dataQuality drop.

**Rigor reshapes the die** (skill > luck): `lean` weights ✗/@ heavier (cheap gamble); `gold` weights ✓ heavily (you bought your certainty); `standard` is balanced. Implementation: each rigor is a probability vector over the 4 outcome faces, fed to `seededRandom`. Evidence delta = `baseGain[stage] * rigorMultiplier * outcomeMultiplier`, then nudged by goodwill and the organ-match bonus.

All dice resolve through one function `rollStudy(state, rigor) -> {organ, outcome, evidenceDelta, qualityDelta, injectedEvent?}` using the seeded PRNG. **Same seed + same actions = same game**, which is what makes server-side score verification possible.

---

## 7. The LLM "FDA Reviewer" (optional, with scripted fallback)

Triggered by `SUBMIT_APPLICATION` at the submission stage. The player **composes or selects a short submission rationale** — a 1–3 sentence "cover letter / benefit-risk statement," either free-typed or chosen from 3–4 canned options (canned options guarantee playability and seed the comedy).

### 7.1 Endpoint: `POST /api/game/review`
**Request (engine sends a compact, PII-free packet):**
```json
{
  "submissionType": "NDA",                 // NDA|BLA|510k|PMA
  "indication": "Type 2 Diabetes",         // from seeded trial therapeutic_area/condition
  "interventionType": "DRUG",
  "rationaleText": "Our Phase 3 met its primary endpoint with a clean safety profile; benefit-risk is favorable.",
  "metrics": {                             // derived from final state, normalized 0-100
    "evidence": 78, "dataQuality": 71, "goodwill": 64,
    "integrityFlags": 1, "presubMeetingsHeld": 2,
    "enrollmentAdequacy": 0.82             // (achieved vs needed N), see Sec 8
  }
}
```

**Response (strict, typed — the engine never trusts free text back):**
```json
{
  "decision": "APPROVABLE_WITH_DEFICIENCIES", // APPROVED | APPROVABLE_WITH_DEFICIENCIES | COMPLETE_RESPONSE_LETTER | REFUSE_TO_FILE
  "scoreModifier": -8,                         // integer, clamped [-25, +20]
  "deficiencies": [
    {"code": "CMC", "severity": "minor", "text": "Stability data insufficient for 24-month shelf life."},
    {"code": "EFFICACY", "severity": "major", "text": "Single pivotal trial; consider confirmatory evidence."}
  ],
  "reviewerQuip": "Reviewer note: We appreciate enthusiasm. We appreciate data more.", // the funny line
  "fixCostQuarters": 2,                         // if not APPROVED, quarters to address & resubmit
  "fixCostCapital": 6                           // $M to address
}
```

- **Model:** uses `settings.openai_model` (`gpt-4o-mini`) via `settings.openai_api_key`; or the DGX local Qwen / `runpod_endpoint_url` if configured. **System prompt** casts it as a deadpan, fair-but-exacting FDA reviewer who scores against the metrics, *must* return the strict JSON schema (use JSON mode / function-calling), and whose `reviewerQuip` is the satirical payload. Temperature low for fairness.
- **Mapping rationale → outcome:** the LLM weighs `rationaleText` quality *lightly* and `metrics` *heavily* (so a slick sentence can't rescue a thin package — teaching that **data > narrative**, the whole joke of D. Lay, JD). Rubric handed to the model: evidence/dataQuality drive `decision`; `integrityFlags` and low goodwill push toward CRL/RTF; honest gaps acknowledged in the rationale earn small goodwill credit.

### 7.2 Scripted fallback (game fully playable with no LLM)
`POST /api/game/review` with `useLLM=false`, or any LLM error/empty key → deterministic rubric in code:
```
score = 0.45*evidence + 0.30*dataQuality + 0.15*goodwill
        + 12*(enrollmentAdequacy-0.5) - 10*integrityFlags + 4*presubMeetingsHeld
decision: score>=80 APPROVED · 60-79 APPROVABLE_WITH_DEFICIENCIES
          · 40-59 COMPLETE_RESPONSE_LETTER · <40 REFUSE_TO_FILE
deficiencies: pick from a static library keyed by which metric is weakest.
reviewerQuip: pick from a static deadpan-quip array (seeded).
```
The fallback emits the **same response schema**, so the engine is identical either way. **Fail-loud rule:** the engine calls review through one adapter; if the network call throws, log loud and transparently fall back — never silently swallow, never block the game.

### 7.3 Resolving the review in the engine
- `APPROVED` → cross to `APPROVED/CLEARED`, **WIN**, apply `scoreModifier`.
- Otherwise → spend `fixCostQuarters` + `fixCostCapital`, address deficiencies (a guided mini-loop: each deficiency is a small action to clear), then `SUBMIT_APPLICATION` again. RTF/CRL repeated without enough evidence is how a cash-rich-but-data-poor player still loses.

---

## 8. Win / Lose & Scoring

### 8.1 Outcomes
- **WIN** — reached `APPROVED`/`CLEARED`.
- **PARTIAL WIN** — accepted an acquisition buyout mid-game (capped score, flavored "exit before approval").
- **LOSE** — capital ≤ 0, quartersLeft ≤ 0, or competitor reached 100.

### 8.2 Leaderboard score (single integer, higher = better)
A real reg pro should read this formula and nod. Computed **server-side** by replaying the log:

```
BASE              = 1000  (win) | 400 (partial win) | 0 (loss, but still scored for the board)

SPEED_BONUS       = 25 * quartersLeft            // finishing early = patent life + investor joy
CAPITAL_EFFICIENCY= 6  * capitalRemaining($M)     // didn't torch the runway
EVIDENCE_QUALITY  = 5  * dataQuality              // strong, well-powered package
GOODWILL_BONUS    = 3  * goodwill                 // good regulatory citizenship
REVIEW_MODIFIER   = scoreModifier (from Sec 7)    // the reviewer's verdict, [-25..+20]

INTEGRITY_PENALTY = -150 * integrityFlags         // shortcuts cost you, hard
DILUTION_PENALTY  = -10  * capitalRaisedRounds     // over-fundraising taxes the exit
WASTE_PENALTY     = -2   * wastedEvidenceOverGate  // evidence hoarded far past the gate = dithering

DIFFICULTY_MULT   = seed.difficultyMultiplier (Sec 9, ~0.8–1.6)

FINAL = round( (BASE + SPEED_BONUS + CAPITAL_EFFICIENCY + EVIDENCE_QUALITY
               + GOODWILL_BONUS + REVIEW_MODIFIER + INTEGRITY_PENALTY
               + DILUTION_PENALTY + WASTE_PENALTY) * DIFFICULTY_MULT )
clamp FINAL >= 0
```

**Reads as:** *win fast, with cash left, on strong honest data, having been a good regulatory citizen.* Speed + efficiency + evidence quality rewarded; wasted resources and shortcuts punished — exactly the brief. Difficulty multiplier means clearing a hard real trial (PMA Class III oncology) outscores an easy one.

### 8.3 Leaderboard table (`game_scores`, SQLite, reuses `app.db`)
`id PK · display_name TEXT · email TEXT · score INT · seed_nct_id TEXT · pathway TEXT · outcome TEXT · advisor TEXT · created_at TIMESTAMP · action_log_hash TEXT`. No auth (per brief); email used only to dedupe a player's best and for the existing Buttondown opt-in. Validate/escape inputs; the score is the *replayed* value, never the client's claim.

---

## 9. Difficulty From Real Data

The seed endpoint reads the chosen trial's real fields and derives starting parameters. This is what makes every game *factual* and re-teaches the data each round.

| Real field | Drives | Rule |
|---|---|---|
| `intervention.type` (+`device_class_hint`, `product_category`) | **pathway / submissionType** | DRUG vs DEVICE branch; Class III/PMA-signal → PMA (hard); else 510(k) (easier). Section 3. |
| `phase` | **starting stage + remaining distance** | Seeded trial already at `PHASE2` → you start at `PHASE2` with carried evidence; less track left = lower base difficulty but you inherit its baggage. `NA`/early → start `PRE_IND`. |
| `therapeutic_area` | **organ-die match + indication flavor + difficulty** | Oncology/Neurology = higher `difficultyMultiplier` (hard endpoints, big trials); Dermatology/Other = lower. Also sets the organ-match bonus target. |
| `enrollment_count` | **evidence cost & `enrollmentAdequacy`** | Bigger N target → each evidence point costs more capital/quarters (powering a 3000-pt trial is brutal); `enrollmentAdequacy` (Sec 7) = achieved vs this target. |
| `overall_status` | **flavor + competitor speed** | `TERMINATED` seed → competitor starts ahead ("this molecule has a graveyard"); `RECRUITING` → neutral; `COMPLETED` → slight goodwill ("known quantity"). |
| `lead_sponsor_class` | **starting capital** | `INDUSTRY` → +capital (deep pockets); `NIH`/`ACADEMIC`/`OTHER` → −capital +goodwill (grant-funded underdog). Pairs with Prof. Goetta Grant. |
| `approx_enrollment_rate_per_month` | **clinical-event odds** | Low rate → higher "enrollment slow" event weight (teaching enrollment is the silent trial-killer; nods to TrialCat's whole reason for existing). |

```
difficultyMultiplier = clamp(
   1.0
   + areaWeight[therapeutic_area]          //  -0.2 .. +0.4
   + (submissionType=="PMA" ? 0.3 : submissionType=="510k" ? -0.2 : 0)
   + log10(max(enrollment_count,10))/20    //  bigger trials harder
   - (phaseAlreadyAdvanced * 0.05),        //  starting later = a touch easier
   0.8, 1.6)
```

Starting resources = baselines (Sec 2) adjusted by `lead_sponsor_class` and advisor (Sec 4.6). The seed endpoint **labels enrollment rate "approximate"** in any UI copy (the model's docstring is emphatic that reg pros spot sloppy math instantly).

### 9.1 GameSeed object (returned by `GET /api/game/seed`)
```json
{
  "seed": 1734300000,                 // int → PRNG seed; also lets you share/replay a game
  "trial": {                          // straight from the trials table, PII-free, public CT.gov data
    "nctId": "NCT04280705",
    "briefTitle": "...",
    "phase": "PHASE2",
    "studyType": "INTERVENTIONAL",
    "therapeuticArea": "Oncology",
    "leadSponsorClass": "INDUSTRY",
    "enrollmentCount": 420,
    "approxEnrollmentRatePerMonth": 12.3,
    "leadIntervention": {"type": "DRUG", "name": "...", "deviceClassHint": null, "productCategory": null}
  },
  "pathway": "DRUG",
  "submissionType": "NDA",
  "startStage": "PHASE2",
  "difficultyMultiplier": 1.25,
  "startResources": {"capital": 60, "quartersLeft": 28, "evidence": 22, "goodwill": 45},
  "competitorSpeed": 4.0,             // competitorProgress per turn
  "organMatchTarget": "PANCREAS",     // organ-die face that grants the bonus this game
  "ctgovUrl": "https://clinicaltrials.gov/study/NCT04280705"
}
```
Seed selection: weighted-random over `trials WHERE study_type='INTERVENTIONAL' AND phase IS NOT NULL AND interventions exist`, using the same PRNG family; re-roll on OBSERVATIONAL/no-intervention. Optionally accept `?nct_id=` to play a specific real trial (shareable challenges).

---

## 10. State Shape & Action Contract (the engine/UI/​server contract)

### 10.1 `GameState` (the full serializable object)
```ts
type Pathway = "DRUG" | "DEVICE";
type SubmissionType = "NDA" | "BLA" | "510k" | "PMA";
type StageId = "PRE_IND"|"PHASE1"|"PHASE2"|"PHASE3"|"NDA_BLA"|"APPROVED"
             | "PRE_SUB"|"PILOT"|"PIVOTAL"|"SUBMISSION"|"CLEARED";
type Outcome  = "IN_PROGRESS"|"WIN"|"PARTIAL_WIN"|"LOSE_CAPITAL"|"LOSE_TIME"|"LOSE_SCOOPED";

interface GameState {
  // --- identity / determinism ---
  version: 1;                     // schema version (CLAUDE.md file-versioning ethos)
  seed: number;                   // PRNG seed (from GameSeed)
  rngCursor: number;              // # of PRNG draws consumed (advances each draw; part of save)
  seedNctId: string;              // which real trial seeded this game
  pathway: Pathway;
  submissionType: SubmissionType;
  advisor: string;                // persona id, Sec 4.6

  // --- progress ---
  stage: StageId;
  stageIndex: number;             // 0-based position on the active track
  turn: number;                   // quarter number, 1-based
  outcome: Outcome;

  // --- resources (Sec 2) ---
  capital: number;                // $M, float
  quartersLeft: number;           // int
  evidence: number;               // 0-100 float, current stage
  goodwill: number;               // 0-100 float
  dataQuality: number;            // 0-100 float (running)

  // --- trackers ---
  competitorProgress: number;     // 0-100
  competitorSpeed: number;        // per-turn increment
  integrityFlags: number;         // shortcuts taken
  capitalRaisedRounds: number;    // for dilution penalty
  enrollmentTarget: number;       // from seed enrollment_count
  enrollmentAchieved: number;     // accumulates via RUN_STUDY
  presubMeetingsHeld: number;
  apThisTurn: number;             // remaining action points this turn
  apPerTurn: number;              // base AP (advisor/CRO modify)
  croTurnsLeft: number;           // HIRE_CRO buff countdown

  // --- review (Sec 7) ---
  lastReview: ReviewResponse | null;
  pendingDeficiencies: Deficiency[];

  // --- bookkeeping for verification & UI ---
  difficultyMultiplier: number;
  actionLog: GameAction[];        // append-only; server replays this to verify score
  eventLog: { turn:number; text:string }[];
  organMatchTarget: string;       // organ-die face granting the bonus
  finalScore: number | null;      // set only at terminal state
}
```

### 10.2 Action types (the `action` union dispatched to `applyAction`)
```ts
type GameAction =
  | { type:"START_GAME";   seed:GameSeed; advisor:string }
  | { type:"RUN_STUDY";    rigor:"lean"|"standard"|"gold" }     // rolls
  | { type:"PRESUB_MEETING" }
  | { type:"HIRE_CRO" }
  | { type:"RAISE_CAPITAL" }
  | { type:"STRENGTHEN_CMC" }
  | { type:"BUY_INTEL" }
  | { type:"TAKE_SHORTCUT" }
  | { type:"ADVANCE_STAGE" }
  | { type:"SUBMIT_APPLICATION"; rationaleText:string; rationaleChoiceId?:string }
  | { type:"RESOLVE_EVENT_CHOICE"; eventId:string; choice:"A"|"B" }  // for fork events (acquisition etc.)
  | { type:"END_TURN" };                                          // triggers UPKEEP of next turn
```
Each returns `{ state: GameState, log: string[] }`. `END_TURN` runs Section 4's UPKEEP→EVENT pipeline for the *next* quarter. Terminal states freeze further actions except a read-only `SUBMIT_SCORE` to the leaderboard.

### 10.3 Supporting types
```ts
interface Deficiency { code:"CMC"|"EFFICACY"|"SAFETY"|"CLINICAL"|"LABELING"; severity:"minor"|"major"; text:string }
interface ReviewResponse {
  decision:"APPROVED"|"APPROVABLE_WITH_DEFICIENCIES"|"COMPLETE_RESPONSE_LETTER"|"REFUSE_TO_FILE";
  scoreModifier:number; deficiencies:Deficiency[]; reviewerQuip:string;
  fixCostQuarters:number; fixCostCapital:number;
}
```

---

## 11. MVP Build Order (smallest playable → full)

1. **Seed endpoint + GameState + engine core** (`START_GAME`, `RUN_STUDY`, `ADVANCE_STAGE`, `END_TURN`, gates, lose/win) — playable loop with scripted reviewer fallback only. *This is a complete game.*
2. **Events + dice flavor + remaining actions** (PRESUB, CRO, RAISE, CMC, SHORTCUT, INTEL, fork events).
3. **LLM reviewer** wired behind the adapter (fallback already proves the seam).
4. **Leaderboard** table + score replay/verify endpoint + simple email/name form.
5. **Polish:** advisor asymmetries, board-art SVGs (the canon assets render losslessly), reviewer quips, shareable `?nct_id=` challenge links.

**Definition of done per CLAUDE.md:** the loop is wired end-to-end (seed → play → submit → review → score → leaderboard), it fails loud on bad input or LLM error (never silent), the server *replays* the action log rather than trusting the client, and a regulatory professional who plays it both learns the real drug-vs-device divergence and laughs at the reviewer's deadpan.

---

### Key files to create (all absolute paths)
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\routes\api_game.py` — seed / review / score endpoints (mount in `app/main.py` alongside existing routers).
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\services\game_engine.py` — server-side mirror of the JS engine for score replay/verification.
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\services\fda_reviewer.py` — LLM adapter + scripted fallback (reads `settings.openai_*` / `runpod_*`).
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\backend\app\models\game_score.py` — `game_scores` SQLAlchemy model.
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\frontend\static\game\engine.js` — deterministic engine (single PRNG, `applyAction`).
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\frontend\static\game\events.json` — REG + STAFF card data (static, expandable).
- `C:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\frontend\static\game\` — board-art SVGs exported from the legacy `.ai` files (board, 6 character cards, dice faces, REG badge).

**Data-contract notes for the implementer (verified against the live codebase):**
- Intervention type enum is exactly `DRUG, BIOLOGICAL, DEVICE, PROCEDURE, BEHAVIORAL, RADIATION, GENETIC, DIAGNOSTIC_TEST, DIETARY_SUPPLEMENT, COMBINATION_PRODUCT, OTHER` (`app/models/intervention.py`). Pathway routing in Section 3 uses these literal values.
- Phase enum is exactly `EARLY_PHASE1, PHASE1, PHASE2, PHASE3, PHASE4, NA` (`app/models/trial.py`); `startStage` mapping uses these.
- `therapeutic_area` values are the buckets in `parser.py`'s `MESH_TO_THERAPEUTIC_AREA` (Oncology, Ophthalmology, Neurology, Cardiovascular, …) — `areaWeight[]` keys must match these strings.
- `device_class_hint` is `'I'|'II'|'III'|None` and `product_category` is the heuristic family (Software/Digital Health, Cardiovascular, …) — both already populated for DEVICE rows; PMA routing keys off `device_class_hint=='III'` OR `product_category` in a high-risk set.
- LLM config already exists: `settings.openai_api_key`, `settings.openai_model` (`gpt-4o-mini`), plus `runpod_endpoint_url`/`runpod_api_key` for the local-LLM path — the reviewer adapter reads these; empty key → scripted fallback. No new config required for MVP.