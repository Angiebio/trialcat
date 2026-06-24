# TrialCat Board Mode — Session State & What's Next (22 June 2026)

**Read this first next session.** Board Mode is BUILT and verified locally, NOT yet
committed or deployed. Prod (trialcat.fly.dev) still serves the old v2.5 resource-sim.

---

## ✅ DONE THIS SESSION (local, uncommitted)

The board-game overhaul from STATE-AND-NEXT-16JUN is built. The cat now physically
climbs a 39-square snake: **draw a deck card → spin the wheel (1–4) → climb, burning
capital each square → land on a square's trigger.** Milestone gates halt the climb
until readiness is met; the submission gate always routes through Dr. Vance.

### Files changed (the deliverable)
- `frontend/static/js/game.js` — **full rewrite to v3.0 Board Mode.** NODE_DATA[39]
  (the snake, each square RAW_DECK-shaped with `e`/`sp`), DECKS (4 draw decks),
  balance consts, `nodeCenter()` serpentine layout (8×5, viewBox 980×700),
  `buildBoardSVG()` (sticker-comic tiles + cyan road), token tween (`animateHopTo`),
  `makeSpinner()`, `drawAndFlip()`, WebAudio `SFX`, turn loop
  (`onDeckDraw`→`onSpin`→`climbSteps`→`land`→`endTurn`), `fireSquare`-style dispatch,
  `advanceCompetitor` (dog as clock), `renderGateStatus` ("Next gate" line),
  reused Vance/glossary/leaderboard/scoring.
- `frontend/templates/game.html` — board stage + tokens, spinner dock, flip overlay,
  one-line HUD, mute chip, "Next gate" element. Removed old value-board img / stage
  nodes / readiness bar.
- `frontend/static/css/game.css` — board/road/tile/token/spinner/flip/hop/highlight
  styles, `.gate-status` pill, **mobile header wrap fix** (was 114px overflow → 0).
- `frontend/templates/game_rules.html` — **rewritten for Board Mode** (draw/spin/climb,
  gates, drug-vs-device section). The old "Run it clean / Advance" copy is gone.

### Design provenance (Phase 1 + 3 workflows) → `roadmaps/_design/`
- `board-spec.json` (+ `board-sample.svg`, `board_live.png`), `mechanics-spec.json`,
  `squares.json`, `ux-patterns.md`. The 3-track parallel design workflow + the
  adversarial mechanics breaker (caught: Vance-skippable, costless stall, pass-through
  funding, dominant low-spin, broken dog formula — all fixed in the build).
- Reconciliation call: 3 tracks diverged on square count (24/39/40); **anchored on the
  39-square content topology**, applied the **mechanics balance model + 7 fixes**, dressed
  in the **board-spec visual system**.

### Drug / device / biologic terminology (Angie-reviewed)
- Gates swap by pathway (Pre-IND/Ph1/2/3/NDA-BLA ↔ Concept/Pre-Sub/Bench/Pivotal/Submission)
  via `MILESTONE_LABEL`/`MILESTONE_NEED`; Pivotal gate fires a device 510(k)/PMA fork.
- **Deck cards + event squares now carry `dev:{name?,label?,f?}` variants**, resolved by
  `pwField(o, field)` when `S.pathway==='device'`. Confirmed swaps:
  Type B→Pre-Sub, Breakthrough Therapy→Breakthrough Device, Fast Track→**STeP** (Angie),
  Clinical Hold→IDE Disapproval, Orphan Drug→Humanitarian Use Device,
  PRV→**Parallel Review (FDA+CMS)** (Angie), CMC→QMS/Design-Controls,
  Phase 2 readout→Feasibility (EFS), Refuse-to-File→Refuse to Accept,
  CRL→Not Substantially Equivalent, CMC/Mfg→Design V&V, AdComm→Advisory Panel,
  PDUFA→MDUFA. **RMAT left as-is** (Angie: device-eligible in theory, no precedent).
  Biologics fold into the drug/NDA-BLA track for v1.
- Device vocabulary added to the glossary term list (tappable, self-building).

### Other fixes
- **Loss-score inversion capped**: a loss now scores `min(900, …)` so a deep bankruptcy
  can never out-rank a real approval (base 1000). *(Phase 3 may refine the formula.)*
- **Mobile**: game header wraps (0 overflow), landing renders clean, "Next gate" line
  makes the gate objective readable where tiles are tiny.
- **DB-PATH FOOTGUN FIXED**: `.env` has `DATABASE_URL=sqlite:///data/trialcat.db` — a
  **relative** path, so the DB resolved per-launch-dir (empty from `trialcat/`, populated
  from `backend/`). The populated 2500-trial DB was at `backend/data/trialcat.db`; copied
  it to the canonical `data/trialcat.db`. A default-launched local server now seeds.

### Verification (local)
- `node --check` clean. Full e2e: **0 console errors** across smart drug + forced device
  games; both reach the submission gate; device gates render device labels. Earlier runs
  confirmed wins ("Approvable Human") and losses both resolve. Mobile 0 overflow verified.

---

## ✅ PHASE 3 APPLIED + LIVE-VALIDATED (23JUN)
`balance-v3.json` landed. It found the shipped game was **effectively unwinnable**
(smart d3 won ~16%) plus **two critical bugs my own tests missed**. All fixed + applied:
- **FDA verdict** (`game_review.py _classify`, THE central fix): `0.55*data+0.25*rep`,
  thresholds 78/58/38 → `0.80*data+0.15*rep`, thresholds **70/50/30**. Data-dominant;
  maxed data approves on its own. (Client `localReview` fallback aligned to match.)
- **BASE_MAX_TURNS 22→28**, **refile defang** (readiness reset need-2 not need-8; +1 turn
  not +2) — kills the refile death-spiral.
- **IDLE_BURN 4→7 + START_CAPITAL 112→118** — keeps never-fund fatal (~90% bust).
- **dogStep base 1.1→1.0** — d1/d2 ~0% scoop, scales to ~21% @ d5.
- **Loss score** `min(900, idx*20+…)` → `min(800, idx*14+…)` — win floor 1905 vs loss
  cap 800, gradient alive, inversion permanently shut.
- **BUG: double-climb** (`makeSpinner`): the 3100ms fallback fired `onResult` twice
  (button stayed disabled through the climb) → every spin could climb 2×. Fixed with a
  one-shot `settled` flag.
- **BUG: device freeze** (`climbSteps`): the 510(k)/PMA fork fired BEFORE stepping off the
  Pivotal gate → resume re-parked forever. Fixed: advance off the gate, then fork.
- **ACQUIRED revival** (optional): forced-sell at Get-Acquired when broke (was 0/360k games).

**Live re-validation (server reloaded for the verdict change):** smart d3 = **8/10 approved,
2 scooped** (~80%, was 16%); **4/4 device games approved past the Pivotal gate** (freeze
gone); **0 console/page errors**. Matches the balance agent's port (conservative ~86%).

## 🎯 NEXT (the ship sequence)
1. **Commit** (Flame/TRCL signature) → `flyctl deploy --remote-only` from `…/trialcat`
   (token in `~/.fly/config.yml`; set `FLY_API_TOKEN` inline if `whoami` empty) →
   smoke-test live → **tag v3** → bump jsu_repo gitlink. **(Gated on Angie's go.)**
2. **Angie's playtest** = the feel pass (spinner/flip/climb, difficulty, jokes).
3. Optional: re-run ~20 live d3 games post-deploy to confirm ≥88% (port floor was ~86%).

## 🔭 LATER / v2 (explicitly deferred, not blocking)
- Board swipe-zoom on mobile (bigger tiles) — tokens are %-positioned so this needs the
  SVG sized to a scroll container; non-trivial.
- Card-flip on the forced-deck squares (currently a plain event modal).
- The painted-parallax backdrop (board-spec Angle C).
- The "draw +1 staff AND a REG card" double-draw (`alsoReg`) — currently stubbed to one.
- True 3-way drug/biologic/device track (biologics get their own BLA/CBER terms).

## 🔑 Key facts
- Repo `…/projects/trialcat-website/trialcat` (own git, remote Angiebio/trialcat); jsu_repo
  tracks it as a gitlink. Stack: FastAPI + SQLite + static Leaflet/vanilla-JS.
- Local dev server: `…/.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1
  --port 8000 --app-dir backend` from `…/trialcat` (canonical DB now populated).
- Commit signature: `Flame (Claude Opus 4.8) at therealcat.ai 501(c)(3). Building
  Structurally Unprofitable AI since 2023.`
