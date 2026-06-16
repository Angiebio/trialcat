# TrialCat — Session State & What's Next (16 June 2026)

**Purpose:** carry state across context. Where we are, what's live, and the big
pending piece (the board-game overhaul). Read this first next session.

---

## ✅ LIVE ON PROD (trialcat.ai / trialcat.fly.dev)

Shipped this session, v1.0 → **v2.4** (tags in the trialcat repo; pushed to
github.com/Angiebio/trialcat). Deploy = `flyctl deploy --remote-only` from
`…/trialcat` (flyctl at `~/.fly/bin/flyctl.exe`, not on PATH; auth token cached
in `~/.fly/config.yml` — set `FLY_API_TOKEN` from it inline if `whoami` is empty).

- **The map** (`/`): device/drug **drill-down** (intervention type → FDA device
  class + product category, drug pharm class), **Study Type filter** (Interventional
  / Observational / Expanded Access — surfaced 616 hidden observational trials),
  device auto-sets Phase=NA, **hover-erases-choropleth bug fixed** (base style is
  now the data choropleth so resetStyle restores color). Galloping-cat **race
  ribbon** with BOTH pathways (device IDE/EFS/Feas./Pivotal/510k + drug
  IND/PH1/PH2/PH3/NDA).
- **The game** (`/game`): "Race to Approval" — 6 founder characters (real 2018
  art), Dr. Eleanor Vance LLM reviewer, **self-building glossary** (seeded + LLM
  generates+caches unseen terms, judge-loop on regenerate), sticker-comic look,
  the real board as hero + a value-board with cat+rival tokens, leaderboard with
  funny rank titles. Pages: `/game/rules`, `/about` (citations), `/terms` (MA law).
- **LLM**: OpenRouter (`google/gemini-2.5-flash-lite` + mistral fallback). Key set
  as Fly secret `OPENROUTER_API_KEY` (from Flamekeeper `.env` `SYSTEM_OPENROUTER_API_KEY`).
  **Graceful fallback triple-locked**: circuit breaker on 401/402 (out of
  credits → scripted for the day, no wasted calls), catch-all (any error →
  scripted, never 500), hard caps (max_tokens 180, ~3 calls/game, 600/day).
- **openFDA**: key set as Fly secret `OPENFDA_API_KEY` (innovate@therealcat.ai).
  **Enrichment running in background on prod** → check `/data/enrich.log` via
  `flyctl ssh console -a trialcat -C "cat /data/enrich.log"`; verify prod
  `product_categories_by_type` fills in afterward.
- **Migration**: `ensure_columns()` in `db.py` adds `interventions.product_category`
  to the existing prod volume on startup (idempotent).

---

## 🎲 BIG NEXT PIECE — Board-game mode overhaul (Angie's vision, NOT yet built)

Reconceive the game from a card-resource sim into a **Game-of-Life-style board
game**: avatars MOVE along the real board, a **spinner** drives movement, each
step **burns runway (capital)**, board squares are **event triggers**, and
**reaching the end of the board = game over** (final score = product value).

**Requirements (verbatim intent):**
1. **Remove the $$M labels from the board** (capital is tracked in the HUD now).
   Avatars (🐈 you, 🐕 competitor) move along the board synced to runway/progress.
2. **Board squares = event triggers** mapped to real mechanics: grant funding
   (+capital), corporate venture funds (+capital), boot-strap, **You are out of
   money** (lose), Fire the CEO?, Hire CRO?, **Get acquired / Sell! / No thanks!**
   (buyout fork — mandatory sell on some), Draw +N cards, draw-only-from-deck-X, etc.
3. **Spinner** (she prefers a spinner over dice) → move N squares forward.
4. **Nonlinear path**: avatars follow the snake path square-by-square. TECH
   CHALLENGE: take the board SVG (`static/img/board.svg`, viewBox 810.16×320.98)
   and move avatars along it correctly through the squares, landing on triggers.
   Approach: author a **waypoint polyline** (ordered list of square-center x,y in
   viewBox coords, ~40 nodes tracing the snake) as data; avatars animate node→node;
   tag certain nodes with triggers. (Extracting exact rect centers from the SVG is
   possible but fiddly; hand-authoring waypoints over the image is the pragmatic path.)
5. **Rewrite the event triggers** and ensure each maps to a real mechanic.
6. **End condition**: reaching board end ends the game at whatever product value
   (out of funds/data also ends it). Like Game of Life's finish.

**The 4 action boxes → DECKS:** the 3 study actions + funding should read as
**general decks you draw from** (R&D, Enroll, FDA, Funding). Style them as
**vertical card-deck stacks** (partly done: `.card-play` now has stacked card-back
::before/::after). TODO: a **card-flip draw animation** (+ optional subtle
Web-Audio "flip" sound), and the instruction "draw a card from one of the four
decks" (done). Possibly make drawing pull a RANDOM card from that category's deck
(bigger mechanic — fits the board model).

**Open design decisions to confirm with Angie before/while building:**
- The turn loop: each turn = spin+move (burn capital) AND draw a deck card? Or
  one or the other? (Recommend: draw a deck card = your action; a spin moves you
  along the runway and burns capital; landing triggers fire. Movement could be
  tied to the action or a separate spin step.)
- Where product VALUE comes from now (cards/events build it; board position is
  runway/time, not value). End score = final product value.
- Capital burn per step + spinner range (e.g., spin 1–4; each square ~ -$Xm).

**Done already this session (Part 1 of her feedback):** card terminology made
general (Do R&D / Start enrolling patients / Meet with the FDA / Raise funds — no
"Type B meeting"), instruction updated, decks given a stacked-card look.

---

## 🗂️ Smaller pending / backlog
- Card-flip animation + optional sound on deck draw.
- Board avatars currently move on the *value-board* (a separate strip) by value%,
  NOT along the real board path — the overhaul replaces this with true path movement.
- Observational design fields (time perspective retrospective/prospective,
  observational model) — not parsed from CT.gov yet; parser + column + reload.
- Feasibility/Pivotal are NOT structured CT.gov fields (free-text/title only).
- Graphics backlog: `roadmaps/ASSETS-NEEDED.md` (founder cut-outs, REG SVG, icons,
  stamps). The board header lost the script "Your" when duplicate text was stripped.
- "Green only on hover" alt for the map if she prefers it over the density choropleth.

## 🔑 Key facts for next session
- Repo: `…/projects/trialcat-website/trialcat` (own git, remote Angiebio/trialcat).
  jsu_repo tracks it as a gitlink; bump after inner commits.
- Stack: FastAPI + SQLite + static Leaflet/vanilla-JS. Game engine = client-side
  `frontend/static/js/game.js`. Map = `frontend/static/js/map.js`.
- Commit signature: `Flame (Claude Opus 4.8) at therealcat.ai 501(c)(3). Building
  Structurally Unprofitable AI since 2023.`
