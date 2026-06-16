I now have full ground truth. The backend is already built and it locks several things my design must honor exactly:

- **Outcomes are fixed:** `approved` (win) / `bankrupt` / `failed_endpoint` / `beaten_to_market` / `clinical_hold`.
- **State variables:** `evidence_score` (0-100) drives the FDA reviewer; `score`, `turns_taken`, `difficulty` (1-5) get persisted. The board-art report says the spine is **cash + product-value** — so the HUD needs cash, value, evidence, and turns.
- **Pathway forks the board:** `drug` (IND → phases → NDA/BLA) vs `device` (pre-sub → pivotal → 510(k)/PMA).
- **FDA reviewer is named** `Dr. Vivian Reyes, Division of Regulatory Reckoning`, returns `approvable` / `deficiencies` / `complete_response_letter`, and is badged `llm` vs `scripted`.
- **Create-user = first name, last name, email**, no auth; leaderboard shows first name + last initial.
- The header already has a working pure-SVG running cat in `.race-ribbon`. The teaser text already exists. My job is to elevate it into header nav and build everything downstream.

I have everything I need. Delivering the full implementable design spec.

---

# TrialCat v2 — "Race to Approval" Visual + UX Design Spec
### Regulatory War-Room edition — epic, credible, never the generic-AI look

**Audience for this doc:** the developer who will write `game.html`, `game.css`, and `game.js`. Everything here is keyed to the real backend (`/api/game/seed`, `/score`, `/leaderboard`, `/review`) and the existing brand CSS vars in `main.css`. Where a value is given, use it verbatim. No further design decisions required.

**Design north star:** A war room, not a toy box. Think the situation-room map wall meets a Bloomberg terminal meets a heist-movie countdown. The cat is the only soft thing in the room, and that contrast is the joke: a tiny green cat sprinting through the bureaucratic apocalypse. Dark purple field, data glowing on top, motion that means something (every animation maps to a real state change). The 2018 board art is the *spiritual* parent (pun characters, valuation ladder, "out of money!"), but the v2 render is sleek and dramatic, not retro-comic.

---

## 0. Foundational decisions (read first — they cascade)

1. **Two surfaces, one shell.** The map page (`index.html`) and the game page (`/game`) share `main.css` + the header. The game adds **one new stylesheet** `game.css` and **one** `game.js`. Do NOT fork `main.css`.
2. **The game page runs on a DARK theme** (war-room), the map stays light (cream). We achieve this with a `.theme-warroom` class on `<body>` of the game page that re-maps a handful of surface tokens — the *brand hues stay identical*, only backgrounds/surfaces flip. This keeps WCAG control in one place.
3. **The cat is the player token everywhere** — header runner, board token, win confetti. One SVG, reused. We promote the existing `.run-cat` SVG (already in `index.html`) into a shared partial.
4. **Motion is semantic.** Four canonical verbs — `advance / damage / approve / reject` — each gets ONE keyframe set, reused across the whole game. No bespoke animations per component.

### 0.1 Warroom token remap (add to `main.css` `:root`, then override under `.theme-warroom`)

```css
/* --- Warroom surface tokens (game page only). Brand HUES unchanged;
       only the stage they perform on goes dark. --- */
:root {
    /* existing brand vars stay as-is … then add: */
    --c-ink:        #1a0524;   /* near-black purple — the war-room void */
    --c-ink-2:      #25092f;   /* raised panel */
    --c-ink-3:      #310d3d;   /* hovered/active panel */
    --c-line:       rgba(199,227,177,0.14);  /* hairline on dark (green-tinted) */
    --c-line-hot:   rgba(91,181,69,0.55);    /* active hairline */
    --c-text-hi:    #FAFAF5;   /* primary text on dark (cream) */
    --c-text-mid:   rgba(250,250,245,0.72);
    --c-text-low:   rgba(250,250,245,0.45);
    --glow-green:   0 0 0 1px rgba(91,181,69,.5), 0 0 22px rgba(91,181,69,.45);
    --glow-yellow:  0 0 0 1px rgba(232,229,42,.5), 0 0 22px rgba(232,229,42,.5);
    --glow-orange:  0 0 0 1px rgba(245,132,31,.5), 0 0 26px rgba(245,132,31,.55);
    --ease-snap:    cubic-bezier(.2,.9,.2,1);    /* arrivals — overshoot-y */
    --ease-out-soft:cubic-bezier(.22,1,.36,1);   /* reveals */
    --ease-in-hard: cubic-bezier(.5,0,.9,.2);    /* impacts */
}

.theme-warroom {
    background:
        radial-gradient(1200px 600px at 70% -10%, rgba(91,181,69,.10), transparent 60%),
        radial-gradient(900px 500px at -10% 110%, rgba(74,8,115,.55), transparent 60%),
        var(--c-ink);
    color: var(--c-text-hi);
}
/* Subtle scanline/grid in the void — situation-room CRT energy, very low opacity */
.theme-warroom::before {
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image:
        linear-gradient(rgba(199,227,177,.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(199,227,177,.035) 1px, transparent 1px);
    background-size: 32px 32px;            /* on the 8px grid (4×) */
    mask-image: radial-gradient(closest-side at 50% 40%, #000 60%, transparent 100%);
}
```

---

## 1. LANDING-PAGE HEADER NAV — running cat + teaser

### 1.1 What already exists (do not rebuild)

`index.html` already ships a full `.race-ribbon` BELOW the header: a pure-SVG `.run-cat` galloping a track (IND→PH1→PH2→PH3→NDA→APPROVED) with the exact teaser **"Can you run your clinical trials fast enough?"** linking to `/game`. The keyframes (`gallop`, `scissorA/B`, `tailWag`, `groundScroll`, `goPulse`, `ribbonSweep`) and `prefers-reduced-motion` handling are done and good. **Keep the ribbon.**

### 1.2 What to ADD: a compact runner INSIDE the header nav

The brief asks for the running cat + teaser to live in the header nav specifically. The ribbon is the big doorway; the header gets a **small, always-visible nav entry** so the game is reachable from the chrome itself (and so it persists if the ribbon is ever collapsed). This is the most shippable path: **reuse the exact same SVG cat at a smaller scale**, drop it into `.header-right` as a single anchor, no new art, no sprite sheet.

**Why pure-SVG over a PNG sprite sheet:** the cat already exists as crisp inline SVG; scaling it to 22px costs nothing, recolors via brand vars, stays sharp on retina, and reuses the already-shipped `gallop`/`scissor`/`tailWag` keyframes. A sprite sheet would add a binary asset, an HTTP request, and a recolor problem for zero visual gain. **Decision: pure-SVG figure with animated legs/tail. Locked.**

#### Placement in the existing header

Insert as the FIRST child of `.header-right` (before `.tagline`), so reading order on desktop is: `[cat → "Play the game" teaser] · tagline · TRCL link · Donate`. It sits left of the existing items and never touches `.header-left` (the logo) or the map layout — the header is a flex row with `justify-content: space-between`, and this just adds one more flex item on the right cluster. Header height (`--header-height: 56px`) is unchanged; the 22px cat fits with room.

```html
<!-- Insert as first child of .header-right in index.html -->
<a class="nav-race" href="/game" aria-label="Play Race to Approval — can you run your clinical trials fast enough?">
    <span class="nav-race__stage" aria-hidden="true">
        <!-- SAME cat SVG as the ribbon, smaller. Copy the <svg class="run-cat"> block
             verbatim, change width/height to 30/19 and add class nav-race__cat. -->
        <svg class="run-cat nav-race__cat" viewBox="0 0 64 40" width="30" height="19" role="img" aria-label="running cat">
            <!-- …identical paths to the ribbon cat… -->
        </svg>
        <span class="nav-race__streak"></span>
    </span>
    <span class="nav-race__text">Can you run your trials fast enough?</span>
    <span class="nav-race__go">PLAY ▶</span>
</a>
```

#### CSS (add to `main.css`, header section)

```css
/* ==========================================================================
   HEADER NAV — Race entry (compact runner). Lives in .header-right.
   The cat is the same soul as the ribbon, shrunk to chrome scale: a tiny
   green sprinter who never stops, reminding you the clock is always running.
   ========================================================================== */
.nav-race {
    display: inline-flex; align-items: center; gap: 8px;
    height: 32px; padding: 0 6px 0 10px;
    border: 1px solid rgba(199,227,177,0.28);
    border-radius: 999px;
    background: rgba(91,181,69,0.08);
    text-decoration: none !important;
    white-space: nowrap;
    transition: border-color .15s, background .15s, transform .15s;
}
.nav-race:hover {
    border-color: var(--c-green);
    background: rgba(91,181,69,0.16);
    transform: translateY(-1px);
}
.nav-race__stage {
    position: relative; display: inline-flex; align-items: center;
    width: 34px; height: 20px; overflow: visible;
}
.nav-race__cat { animation: gallop .35s ease-in-out infinite; transform-origin: center; overflow: visible; }
/* reuse the ribbon's leg/tail rules by also matching .run-cat (they already exist) */
.nav-race__streak {
    position: absolute; right: 100%; top: 50%; transform: translateY(-50%);
    width: 14px; height: 2px; border-radius: 2px;
    background: linear-gradient(90deg, transparent, rgba(232,229,42,.85));
    transition: width .3s ease;
}
.nav-race:hover .nav-race__streak { width: 26px; }
.nav-race__text {
    color: var(--c-text-hi, #FAFAF5); /* on purple header */
    color: rgba(250,250,245,0.92);
    font-size: 12.5px; font-weight: 700; letter-spacing: .005em;
}
.nav-race__go {
    color: var(--c-purple); background: var(--c-yellow);
    font-size: 10.5px; font-weight: 900; letter-spacing: .05em;
    padding: 3px 8px; border-radius: 999px;
    box-shadow: 0 0 0 0 rgba(232,229,42,.7);
    animation: goPulse 1.6s ease-out infinite;
}
.nav-race:hover .nav-race__go { background: var(--c-green); color: var(--c-purple); }

/* Responsive: protect the map header on small screens.
   The big .race-ribbon below carries the message on mobile, so the header
   entry sheds text first, then the GO pill, leaving just the running cat. */
@media (max-width: 920px) { .nav-race__text { display: none; } }
@media (max-width: 600px) { .nav-race__go  { display: none; } .nav-race { padding: 0 8px; } }
```

This reuses the already-defined `@keyframes gallop` and `goPulse`, and the `.run-cat .legs-front/.legs-back/.cat-tail` rules already target `.run-cat`, so the legs and tail animate for free. The existing `@media (prefers-reduced-motion)` block already lists `.run-cat, .run-cat *` — it will quiet the nav cat too. One extra line: add `.nav-race__go` to that reduced-motion `animation: none` list.

**Coexistence guarantee:** `.nav-race` is a single inline-flex item appended to the existing `.header-right` flex row. It cannot reflow `.header-left` or the `.app-layout`/`#map` below (those are separate flex/block contexts). Worst case on a narrow viewport it collapses to a 32px circle — still a valid tap target.

---

## 2. THE GAME PAGE (`/game`) — full layout

A single-route SPA-ish page with **four screens** swapped via a `data-screen` attribute on `.game-root` (no router needed): `intro` → `enroll` → `play` → `gameover`. The leaderboard is a panel reachable from intro and gameover. State lives in `game.js`; screens are CSS-toggled (`[data-screen="play"] .screen--play { display:grid }`).

```html
<body class="theme-warroom">
  <header class="app-header"> … same header, with .nav-race … </header>

  <main class="game-root" data-screen="intro">
    <section class="screen screen--intro"> … </section>
    <section class="screen screen--enroll"> … </section>
    <section class="screen screen--play"> … </section>
    <section class="screen screen--gameover"> … </section>
    <aside class="lb-drawer" data-open="false"> … leaderboard … </aside>
  </main>

  <footer class="app-footer"> … same footer … </footer>
</body>
```

### 2.1 Screen: INTRO / HERO

A cinematic cold-open. Full-bleed dark war-room, the title slamming in, the cat already running across the bottom toward a glowing "APPROVED" gate.

**Grid:** single centered column, `max-width: 880px`, vertically centered (`min-height: calc(100vh - header - footer)`, `display:grid; place-items:center`).

Contents top→bottom:
- **Eyebrow:** `THE ONLY STRATEGY GAME FOR REGULATORY AFFAIRS™` — small, letter-spaced, green. (Honors the 2018 board mark verbatim.)
- **Title (H1):** `RACE TO APPROVAL` — massive, Inter 900, cream, with a yellow underscore swipe that draws in via `advance`.
- **Subtitle:** `Can you shepherd a real clinical trial to FDA approval before the money runs out?` Inter 400.
- **Credibility line (lands AFTER the hook, per brand voice):** `Built from real ClinicalTrials.gov data with a 25-year FDA regulatory strategist and the Northeastern University Regulatory Affairs program.`
- **Primary CTA:** `▶ START YOUR PROGRAM` (big yellow pill, `--glow-yellow`).
- **Secondary CTA:** `View the Leaderboard` (ghost button → opens `.lb-drawer`).
- **Ambient:** a horizontal mini-track at the very bottom with the running cat looping (reuse ribbon mechanics at large scale), and 3 floating "dossier" cards drifting up in the background at 6% opacity.

### 2.2 Screen: ENROLL (create user) — the "Form 1571" bit

The create-user screen is reframed as **filing your founding paperwork** — the satire makes a boring form funny and on-theme. Header reads `FILE YOUR PROGRAM — Form RC-1571` (a wink at FDA Form 1571, the IND cover form).

**Grid:** centered card, `max-width: 460px`, `.enroll-card` panel (`--c-ink-2`, 8px radius, `--glow-green` on focus-within).

Fields (maps exactly to `ScoreSubmit`/`Player`): 
- `first_name` (required) — label `Sponsor first name`
- `last_name` (optional) — label `Sponsor last name`
- `email` (required) — label `Contact email` with helper microcopy under it: `Your leaderboard handle. No password, no spam, never sent to the FDA reviewer AI. We show only your first name + last initial.` (This makes the no-auth/privacy posture from `models/game.py` visible to the user — required by the project's own ethic.)
- **Pathway pre-pick (optional):** two big toggle cards `DRUG (IND→NDA/BLA)` vs `DEVICE (510(k)/PMA)` vs `Surprise me` → feeds `?pathway=` on `/api/game/seed`.

CTA: `DEAL ME A TRIAL ▶` → calls `GET /api/game/seed`, then transitions to PLAY with a **card-deal animation** (the seed trial card flies in and flips — see §4 `approve`/flip).

Validation: inline, fail-loud-but-kind. Email uses the same shape the backend enforces (`[^@\s]+@[^@\s]+\.[^@\s]+`); show `that doesn't look like an email address` (matches the server's own message) on blur.

### 2.3 Screen: PLAY — the war room

The main event. A **3-zone grid** that feels like a mission console.

```css
.screen--play {
    display: grid;
    grid-template-columns: 280px 1fr 320px;
    grid-template-rows: auto 1fr auto;
    grid-template-areas:
        "hud      board    reviewer"
        "hud      board    reviewer"
        "actions  actions  reviewer";
    gap: 16px;
    padding: 16px;
    height: calc(100vh - var(--header-height) - var(--footer-height));
}
/* Mobile: stack — board first (the star), then HUD, reviewer, actions. */
@media (max-width: 900px) {
    .screen--play {
        grid-template-columns: 1fr;
        grid-template-areas: "board" "hud" "reviewer" "actions";
        height: auto;
    }
}
```

#### Zone A — RESOURCE HUD (`grid-area: hud`)

A vertical stack of "gauges." These are the state variables the engine and backend actually track. Four primary gauges + the scenario card.

1. **Seed-trial card** (top): the real CT.gov trial. Shows `trial_title`, `nct_id` (mono, links to clinicaltrials.gov in a new tab — ties game to map), `sponsor`, `phase`, `therapeutic_area`, and a **pathway badge** (purple `DRUG` / green `DEVICE`) and a **difficulty meter** (1–5 cat-paw pips, `difficulty` from seed).
2. **CASH** gauge — orange when low. The lose-condition resource (`bankrupt`). Big mono number, animated count via JS. Below ~15% it pulses with `damage` and the gauge bar goes `--c-orange`.
3. **PRODUCT VALUE** gauge — the board-art valuation ladder ($100k→$9B) mapped to a 0–100% bar in green. This is the "progress" feel.
4. **EVIDENCE** gauge (0–100) — the value sent to `/api/game/review` as `evidence_score`. Green→yellow→ gradient by level. Labeled `Evidence / Data Package`.
5. **TURNS** counter — `Turn 7` mono, small. Persisted as `turns_taken`.

```css
.hud { grid-area: hud; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }
.gauge { background: var(--c-ink-2); border: 1px solid var(--c-line); border-radius: 8px; padding: 12px; }
.gauge__label { font-size: 11px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--c-text-low); }
.gauge__value { font-family: var(--font-mono); font-size: 26px; font-weight: 700; color: var(--c-text-hi); line-height: 1.1; }
.gauge__bar { height: 6px; border-radius: 999px; background: rgba(255,255,255,.08); margin-top: 8px; overflow: hidden; }
.gauge__fill { height: 100%; border-radius: 999px; transition: width .6s var(--ease-out-soft); }
.gauge--cash  .gauge__fill { background: linear-gradient(90deg, var(--c-orange), var(--c-yellow)); }
.gauge--value .gauge__fill { background: linear-gradient(90deg, var(--c-green), var(--c-green-soft)); }
.gauge--evidence .gauge__fill { background: linear-gradient(90deg, var(--c-purple), var(--c-green)); }
.gauge.is-critical { animation: damage .5s var(--ease-in-hard); border-color: var(--c-line-hot); }
```

#### Zone B — BOARD + EVENT REVEAL (`grid-area: board`)

The hero. The winding regulatory pathway (full spec in §3) fills the center, the **cat token** sits on the current node, and event cards reveal here over the board.

- **TENSION METER** runs along the TOP of the board zone: a thin horizontal bar, green (calm) → yellow → orange → red as risk accrues (e.g., low cash, pending CRL, late phase). It is the mood ring of the run. When it crosses into red, the whole `.screen--play` gets a faint orange vignette (`box-shadow: inset 0 0 120px rgba(245,132,31,.18)`).
- **EVENT-CARD REVEAL:** when the player ends a turn, an event card (the REG deck) flips up center-board over a dimmed scrim. Big card, brand-cornered, with an icon (organ/molecule/syringe vocabulary from the 2018 icon sheet), a title, flavor text, and effect chips (`+12 EVIDENCE`, `−$4M`, `−1 TURN`). The card uses the **flip** animation. Examples that teach real reg literacy: *"FDA Type B Meeting granted — clarity on your endpoint. +Evidence, −Cash."* / *"Form 483 observation at your CRO. −Evidence until remediated."* / *"Competitor files first. Tension spikes — risk of `beaten_to_market`."*

#### Zone C — FDA REVIEWER DIALOG (`grid-area: reviewer`)

A persistent "comms channel" panel styled like a secure terminal — this is **Dr. Vivian Reyes, Division of Regulatory Reckoning** (the real `REVIEWER_NAME`). Idle, she shows a status line (`REVIEWER STANDING BY`). At the submission milestone (end of pathway), the player writes their **marketing-application narrative** in a textarea (`submission_rationale`, 1–1500 chars to match schema), and posts to `/api/game/review`.

The response renders as an **official letter** with the verdict stamped across it:
- `approvable` → green `APPROVABLE` stamp, `approve` animation, `+18` score chip.
- `deficiencies` → yellow `INFORMATION REQUEST` stamp, mild shake, `−4`.
- `complete_response_letter` → orange/red `COMPLETE RESPONSE LETTER` stamp, `reject` + `screen-shake`, `−22`.
- A small honest badge in the corner: `source: scripted` or `source: AI` (maps to `ReviewResponse.source` — the model honesty the schema demands). When `scripted`, badge reads `Reviewer (offline mode)`.

```css
.reviewer { grid-area: reviewer; display: flex; flex-direction: column; background: var(--c-ink-2); border: 1px solid var(--c-line); border-radius: 8px; overflow: hidden; }
.reviewer__hdr { padding: 12px; border-bottom: 1px solid var(--c-line); display: flex; gap: 8px; align-items: center; }
.reviewer__name { font-weight: 800; font-size: 13px; color: var(--c-green-soft); }
.reviewer__pulse { width: 8px; height: 8px; border-radius: 50%; background: var(--c-green); box-shadow: var(--glow-green); animation: tensionPulse 2s ease-in-out infinite; }
.reviewer__letter { padding: 14px; font-size: 13px; line-height: 1.6; color: var(--c-text-mid); flex: 1; overflow-y: auto; }
.stamp { display: inline-block; transform: rotate(-8deg); border: 3px solid currentColor; border-radius: 6px; padding: 4px 12px; font-weight: 900; letter-spacing: .08em; font-size: 18px; }
.stamp--approvable { color: var(--c-green); }
.stamp--deficiencies { color: var(--c-yellow); }
.stamp--crl { color: var(--c-orange); }
.reviewer__src { font-size: 10px; color: var(--c-text-low); font-family: var(--font-mono); }
```

#### Zone D — ACTION BAR (`grid-area: actions`)

Horizontal row of primary verbs, each a big tactile button. These ARE the board's decision forks from the 2018 art, modernized:

- `🎲 RUN A TRIAL TURN` (primary, yellow) — rolls the two dice (organ die + outcome die ✓/✗/!/@), advances the cat, draws an event.
- `💼 FUNDRAISE` — trade turns/value for cash (the "Get the grant funding!" / "Corporate venture" spaces).
- `🤝 HIRE CRO` — boosts trial throughput, costs cash (the "Hire CRO?" fork).
- `🔥 FIRE THE CEO` — risky reset of a stat (the "Fire the CEO?" fork) — confirm modal.
- `🏁 SUBMIT TO FDA` — enabled only at pathway end; opens the reviewer textarea.
- `💰 TAKE THE BUYOUT` — the "Sell! / No thanks!" fork — end early for a value-based score instead of pushing for approval. (Teaches that exit ≠ failure.)

Buttons are disabled with a reason tooltip when not affordable (fail-loud-but-kind: `Not enough cash — fundraise first`).

### 2.4 Screen: GAME OVER

Outcome-driven. The `outcome` decides the entire mood:
- **`approved`** — full **win sequence**: cat leaps through the APPROVED gate, green confetti burst, `approve` glow on everything, the title `APPROVED.` slams in, a one-line congratulations from Dr. Reyes, the final **score** big and mono, and a `🏆 SUBMIT TO LEADERBOARD` CTA (posts `ScoreSubmit`).
- **`bankrupt`** — orange, the 2018 board's `"You are out of money!"` callback verbatim as the headline. Cat slumps.
- **`failed_endpoint`** — yellow/orange, `"Your primary endpoint did not reach significance."`
- **`beaten_to_market`** — purple, `"A competitor crossed the finish line first."`
- **`clinical_hold`** — red, `screen-shake` on entry, `"CLINICAL HOLD."` stamped.

The score-submit confirmation shows `your_rank / total_players` and an `is_personal_best` ribbon (all three come straight from `ScoreSubmitResponse`). Then `VIEW LEADERBOARD` + `PLAY AGAIN` (re-seeds).

### 2.5 Leaderboard drawer

Slides in from the right (`.lb-drawer[data-open="true"]`). A ranked table from `GET /api/game/leaderboard`: `rank · display_name · score · outcome (as a colored chip) · pathway (drug/device icon) · turns · NCT (links out)`. The current player's row, if present, gets `--glow-green`. Header: `LEADERBOARD — fastest to approval`.

```css
.lb-drawer { position: fixed; top: var(--header-height); right: 0; bottom: 0; width: min(440px, 92vw);
    background: var(--c-ink-2); border-left: 1px solid var(--c-line-hot);
    transform: translateX(100%); transition: transform .35s var(--ease-snap); z-index: 1200; overflow-y: auto; }
.lb-drawer[data-open="true"] { transform: translateX(0); }
.lb-row { display: grid; grid-template-columns: 28px 1fr auto; gap: 8px; padding: 10px 14px; border-bottom: 1px solid var(--c-line); }
.lb-row.is-you { box-shadow: var(--glow-green); border-radius: 6px; }
.lb-outcome { font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 999px; }
.lb-outcome--approved { background: var(--c-green); color: var(--c-purple); }
.lb-outcome--bankrupt { background: var(--c-orange); color: #fff; }
/* …one chip color per outcome… */
```

---

## 3. BOARD VISUALIZATION — the winding regulatory pathway

**Recommendation: SVG path + positioned node circles + an absolutely-positioned HTML cat token that tweens between node coordinates.** This is the most shippable approach that still looks epic: the path is one `<path>` you can draw-on with `stroke-dasharray`, nodes are data-driven `<circle>`s, and the cat is the existing SVG dropped on top and moved with a CSS `transform: translate()` transition. No game-engine, no canvas, retina-crisp, recolorable.

### 3.1 Structure

```html
<div class="board" data-pathway="drug">
  <svg class="board__svg" viewBox="0 0 1000 520" preserveAspectRatio="xMidYMid meet">
    <!-- the laid track (faint) -->
    <path class="board__track" d="M60,460 C 220,460 220,300 380,300 S 560,140 740,140 S 940,300 940,300" fill="none"/>
    <!-- the traveled track (bright, grows via dasharray) -->
    <path class="board__progress" d="…same d…" fill="none"/>
    <!-- nodes injected by JS at sampled points along the path -->
    <g class="board__nodes"></g>
  </svg>
  <!-- the cat token, HTML so it can hold a glow + bob independent of the SVG -->
  <div class="board__cat" style="--x:60px; --y:460px;">
     <svg class="run-cat">…shared cat…</svg>
  </div>
  <div class="board__gate">APPROVED</div>
</div>
```

### 3.2 The two pathways (data, not hand-drawn)

Define each pathway as an ordered node list in `game.js`; JS places nodes by sampling the SVG path with `path.getPointAtLength()` so nodes always sit ON the line. Honor the schema's fork:

- **`drug`:** `Pre-IND → IND → Phase 1 → Phase 2 → Phase 3 → Pre-NDA Meeting → NDA/BLA Filed → FDA Review → APPROVED`
- **`device`:** `Q-Sub (Pre-Sub) → Bench/Biocompat → Pivotal Study → 510(k) or PMA Decision → FDA Review → APPROVED`

Node visual states: `upcoming` (hollow, `--c-line`), `current` (filled green, `--glow-green`, gentle `tensionPulse`), `cleared` (filled purple with a green check), `hazard` (orange ring — a node carrying a known REG-deck risk). Each node shows a tiny label above/below (alternating to avoid overlap on the snake).

```css
.board { grid-area: board; position: relative; background: var(--c-ink-2);
    border: 1px solid var(--c-line); border-radius: 8px; overflow: hidden; }
.board__svg { width: 100%; height: 100%; display: block; }
.board__track    { stroke: var(--c-line); stroke-width: 10; stroke-linecap: round; }
.board__progress { stroke: var(--c-green); stroke-width: 6; stroke-linecap: round;
    filter: drop-shadow(0 0 6px rgba(91,181,69,.7));
    stroke-dasharray: var(--len); stroke-dashoffset: var(--remaining);
    transition: stroke-dashoffset .8s var(--ease-out-soft); }
.node            { fill: var(--c-ink-3); stroke: var(--c-line); stroke-width: 2; transition: all .3s; }
.node--cleared   { fill: var(--c-purple); stroke: var(--c-green); }
.node--current   { fill: var(--c-green); stroke: var(--c-green-soft); filter: drop-shadow(0 0 10px rgba(91,181,69,.8)); }
.node--hazard    { stroke: var(--c-orange); }
.board__cat {
    position: absolute; left: 0; top: 0; width: 52px; height: 33px;
    transform: translate(var(--x), var(--y)) translate(-50%, -60%);
    transition: transform .7s var(--ease-snap);   /* the advance glide */
    filter: drop-shadow(0 4px 10px rgba(0,0,0,.5));
}
.board__cat.is-advancing .run-cat { animation: gallop .3s ease-in-out infinite; }
.board__gate {
    position: absolute; right: 18px; top: 18px;
    font-weight: 900; letter-spacing: .1em; color: var(--c-purple);
    background: var(--c-green); padding: 6px 12px; border-radius: 6px;
    box-shadow: var(--glow-green); animation: finishPulse 1.8s ease-in-out infinite;
}
```

**Advancing the cat:** on a successful turn, JS sets `--x`/`--y` on `.board__cat` to the next node's sampled coords and adds `.is-advancing`; the CSS `transform` transition glides it along (the `--ease-snap` overshoot gives a satisfying "pounce" into the node). Simultaneously update `.board__progress`'s `stroke-dashoffset` so the bright trail chases the cat. On reaching APPROVED, fire the win sequence (§4 `approve`).

---

## 4. MOTION SYSTEM — four canonical verbs

One small, reusable set. Everything else composes from these. Add to `game.css`.

```css
/* ADVANCE — forward progress: a confident pounce + settle. Used for cat moves,
   progress bars filling, the title underscore swipe, screen entrances. */
@keyframes advance {
    0%   { transform: translateY(6px) scale(.98); opacity: 0; }
    60%  { transform: translateY(-3px) scale(1.01); opacity: 1; }
    100% { transform: translateY(0) scale(1); opacity: 1; }
}
/* DAMAGE — something hurt you (cash drop, evidence loss, Form 483).
   A sharp lateral shake; pairs with an orange flash on the target. */
@keyframes damage {
    0%,100% { transform: translateX(0); }
    15% { transform: translateX(-6px); } 30% { transform: translateX(5px); }
    45% { transform: translateX(-4px); } 60% { transform: translateX(3px); }
    75% { transform: translateX(-2px); }
}
/* APPROVE — the win/positive verdict: green bloom + lift. */
@keyframes approve {
    0%   { box-shadow: 0 0 0 0 rgba(91,181,69,0); transform: scale(1); }
    50%  { box-shadow: 0 0 0 10px rgba(91,181,69,.0), var(--glow-green); transform: scale(1.03); }
    100% { box-shadow: var(--glow-green); transform: scale(1); }
}
/* REJECT — CRL / clinical hold: red recoil + desaturate flash. */
@keyframes reject {
    0%   { transform: scale(1); filter: none; }
    20%  { transform: scale(.97) rotate(-1deg); filter: saturate(.4) brightness(1.2); box-shadow: var(--glow-orange); }
    100% { transform: scale(1); filter: none; }
}
/* SCREEN-SHAKE — reserved for Clinical Hold only (the big one). On .game-root. */
@keyframes screenShake {
    0%,100% { transform: translate(0,0); }
    10% { transform: translate(-8px, 4px); } 20% { transform: translate(7px, -5px); }
    30% { transform: translate(-6px, 6px); } 40% { transform: translate(6px, -3px); }
    50% { transform: translate(-4px, 4px); } 60% { transform: translate(4px, -2px); }
    70% { transform: translate(-2px, 2px); }
}
/* CARD-FLIP — event reveal + seed-trial deal. 3D flip on the Y axis. */
@keyframes cardFlipIn {
    0%   { transform: perspective(900px) rotateY(90deg) translateY(8px); opacity: 0; }
    60%  { transform: perspective(900px) rotateY(-8deg); opacity: 1; }
    100% { transform: perspective(900px) rotateY(0); opacity: 1; }
}
/* TENSION-PULSE — the heartbeat for current node, reviewer status, tension dot. */
@keyframes tensionPulse { 0%,100% { opacity: .6; transform: scale(1); } 50% { opacity: 1; transform: scale(1.15); } }

/* --- Utility application classes (JS toggles these) --- */
.fx-advance { animation: advance .5s var(--ease-snap) both; }
.fx-damage  { animation: damage .5s var(--ease-in-hard); }
.fx-approve { animation: approve .7s var(--ease-out-soft); }
.fx-reject  { animation: reject .6s var(--ease-in-hard); }
.fx-flip    { animation: cardFlipIn .55s var(--ease-out-soft) both; transform-origin: center; backface-visibility: hidden; }
.is-shaking { animation: screenShake .6s var(--ease-in-hard); }
```

**Timing table (the whole motion budget):**

| Verb | Duration | Easing | Trigger |
|---|---|---|---|
| advance | 500ms (cat glide 700ms) | `--ease-snap` | turn success, cat move, bar fill, screen enter |
| damage | 500ms | `--ease-in-hard` | cash/evidence loss, 483, deficiency |
| approve | 700ms | `--ease-out-soft` | approvable verdict, win, node cleared |
| reject | 600ms | `--ease-in-hard` | CRL, failed endpoint |
| screenShake | 600ms | `--ease-in-hard` | **clinical_hold only** |
| cardFlipIn | 550ms | `--ease-out-soft` | event reveal, seed deal |
| tensionPulse | 2s loop | ease-in-out | current node, reviewer idle, tension dot |

**Reduced motion:** add a `game.css` block mirroring the existing one — under `@media (prefers-reduced-motion: reduce)`, set all `.fx-*`, `.is-shaking`, `.board__cat`, `.run-cat *`, `tensionPulse` users to `animation: none !important; transition: none !important;`. Cat still *teleports* to the next node (state stays correct), just without the glide. Confetti is skipped.

---

## 5. TYPE & COLOR USAGE

### 5.1 Loading Inter (the brand web font — replaces the system stack on the game page)

`main.css` currently uses a system stack by a "no typography until Phase 2" rule. V2 IS Phase 2 for the game. Load Inter via `@font-face` with `font-display: swap`, self-hosted in `/static/fonts/` (no third-party request, no CLS surprise, GDPR-clean — matters for a 501(c)(3)). Add a `--font-display` var so the rest of the system can stay system-font if desired.

```css
/* Put woff2 files in frontend/static/fonts/. Variable font = one file, all weights. */
@font-face {
    font-family: "Inter";
    font-style: normal;
    font-weight: 100 900;            /* variable */
    font-display: swap;
    src: url("/static/fonts/Inter-roman.var.woff2") format("woff2");
}
:root {
    --font-display: "Inter", var(--font-body);  /* headings/game UI */
}
.theme-warroom { font-family: var(--font-display); }
```

### 5.2 Inter weights per element

| Element | Inter weight | Size | Notes |
|---|---|---|---|
| Hero H1 `RACE TO APPROVAL` | 900 | clamp(40px, 7vw, 84px) | letter-spacing −0.02em (tighten at display size) |
| Screen titles / GAME OVER headline | 800 | clamp(28px, 4vw, 48px) | |
| Eyebrow / section kickers | 700 | 11–12px | letter-spacing .08em, UPPERCASE |
| Gauge labels, action buttons, chips | 700–800 | 11–13px | UPPERCASE for labels |
| Body / reviewer letter / flavor text | 400 | 13–15px | line-height 1.6 |
| Microcopy / disclaimers / source badge | 400 | 10–11px | `--c-text-low` |
| **Numbers** (cash, value, score, turns, NCT) | 700 | varies | **`--font-mono`**, not Inter — terminal feel + tabular alignment |

Use `font-variant-numeric: tabular-nums` on all live-counting numbers so they don't jitter as digits change.

### 5.3 Color usage map (and the rule behind it)

The palette has meaning; assign it consistently so color *teaches*:

| Color | Var | Means | Used for |
|---|---|---|---|
| Deep purple | `--c-purple` | the institution / authority | DRUG pathway, cleared nodes, FDA letterhead, primary on light |
| Bright green | `--c-green` | progress / go / win | DEVICE pathway, progress trail, current node, APPROVABLE, CTAs, win |
| Soft green | `--c-green-soft` | calm / completed | hairlines, secondary accents, reviewer name |
| Yellow | `--c-yellow` | urgency / action / money-good | primary CTA pills, PLAY, evidence-high, GO |
| Orange | `--c-orange` | danger / cost / warning | low cash, damage flash, CRL stamp, hazard nodes, bankrupt |
| Cream | `--c-cream` / `--c-text-hi` | the human voice | all body text on dark, light-surface bg |
| Ink purples | `--c-ink/2/3` | the war-room void | game backgrounds, panels |

**Semantic locks (don't deviate):** green = good/progress, orange = cost/danger, yellow = act now, purple = authority/the system. The verdict colors mirror the stamps exactly (approvable=green, deficiencies=yellow, CRL=orange-red).

### 5.4 WCAG AA compliance (verified targets)

- Body text uses `--c-text-hi` (#FAFAF5) on `--c-ink` (#1a0524): contrast ≈ **16:1** — passes AAA. `--c-text-mid` (72% cream) on ink ≈ **11:1** — passes AA easily.
- **Watch-outs (must follow):** yellow `--c-yellow` (#e8e52a) and bright green `--c-green` (#5bb545) are LOW-contrast on cream and as text on dark. **Rule: never use yellow or bright green as body text.** Use them only as fills behind dark (purple) text — e.g. the yellow CTA pill uses `color: var(--c-purple)` (contrast ≈ 9:1, passes AA). Green chips/stamps use purple or cream text. Orange `--c-orange` on dark ink as text ≈ 4.7:1 — passes AA for large/bold only, so keep orange text ≥18px bold (which it always is: stamps, warnings).
- Every gauge/chip pairs color with a **text label or icon**, so meaning never relies on color alone (colorblind-safe).
- Focus rings: reuse the map's green focus ring (`box-shadow: 0 0 0 2px rgba(91,181,69,.2)`) but on dark bump to `.45` alpha for visibility. All interactive elements get a visible focus state.
- Disabled buttons: `opacity:.45` + `cursor:not-allowed` + a `title`/`aria-disabled` reason (not color-only).

---

## 6. COMPONENT / CSS-CLASS LIST (BEM-ish, matches existing convention)

Existing convention is flat-ish hyphenated blocks (`.app-header`, `.filter-group`, `.race-ribbon`, `.race-cta`) with a few `__`/`--` (`.nav-race__go`). Follow that. New files: `frontend/static/css/game.css`, `frontend/static/js/game.js`, `frontend/templates/game.html`. The FastAPI route for `GET /game` renders `game.html`.

**Shell / theme**
- `.theme-warroom` — dark game theme on `<body>`
- `.game-root` — SPA container, holds `data-screen`
- `.screen`, `.screen--intro`, `.screen--enroll`, `.screen--play`, `.screen--gameover`

**Header nav (in `main.css`, used on both pages)**
- `.nav-race`, `.nav-race__stage`, `.nav-race__cat`, `.nav-race__streak`, `.nav-race__text`, `.nav-race__go`

**Intro**
- `.intro-hero`, `.intro-eyebrow`, `.intro-title`, `.intro-sub`, `.intro-cred`, `.intro-cta`, `.intro-cta--primary`, `.intro-cta--ghost`, `.intro-bgcards`

**Enroll**
- `.enroll-card`, `.enroll-title`, `.field`, `.field__label`, `.field__input`, `.field__help`, `.field--error`
- `.pathway-pick`, `.pathway-opt`, `.pathway-opt--drug`, `.pathway-opt--device`, `.pathway-opt.is-selected`
- `.enroll-submit`

**Play — HUD**
- `.hud`, `.gauge`, `.gauge__label`, `.gauge__value`, `.gauge__bar`, `.gauge__fill`
- `.gauge--cash`, `.gauge--value`, `.gauge--evidence`, `.gauge--turns`, `.gauge.is-critical`
- `.seed-card`, `.seed-card__title`, `.seed-card__nct`, `.seed-card__meta`, `.pathway-badge`, `.pathway-badge--drug`, `.pathway-badge--device`, `.difficulty`, `.difficulty__pip`

**Play — board** (§3)
- `.board`, `.board[data-pathway]`, `.board__svg`, `.board__track`, `.board__progress`, `.board__nodes`, `.node`, `.node--upcoming`, `.node--current`, `.node--cleared`, `.node--hazard`, `.node__label`, `.board__cat`, `.board__cat.is-advancing`, `.board__gate`
- `.tension`, `.tension__bar`, `.tension__fill`, `.tension.is-high` (+ `.screen--play.is-tense` vignette)

**Play — event card**
- `.event-scrim`, `.event-card`, `.event-card__icon`, `.event-card__title`, `.event-card__body`, `.event-card__effects`, `.effect-chip`, `.effect-chip--gain`, `.effect-chip--cost`

**Play — reviewer** (§2.3)
- `.reviewer`, `.reviewer__hdr`, `.reviewer__pulse`, `.reviewer__name`, `.reviewer__letter`, `.reviewer__form`, `.reviewer__textarea`, `.reviewer__submit`, `.reviewer__src`
- `.stamp`, `.stamp--approvable`, `.stamp--deficiencies`, `.stamp--crl`

**Play — actions**
- `.actionbar`, `.action-btn`, `.action-btn--primary` (run turn), `.action-btn--fund`, `.action-btn--cro`, `.action-btn--fire`, `.action-btn--submit`, `.action-btn--buyout`, `.action-btn:disabled`

**Game over**
- `.gameover`, `.gameover--approved`, `.gameover--bankrupt`, `.gameover--failed_endpoint`, `.gameover--beaten_to_market`, `.gameover--clinical_hold`
- `.gameover__headline`, `.gameover__score`, `.gameover__reviewer-line`, `.gameover__pb-ribbon`, `.gameover__cta-row`, `.confetti`

**Leaderboard**
- `.lb-drawer`, `.lb-drawer[data-open]`, `.lb-hdr`, `.lb-row`, `.lb-row.is-you`, `.lb-rank`, `.lb-name`, `.lb-score`, `.lb-outcome`, `.lb-outcome--approved` (+ one per outcome), `.lb-pathway`, `.lb-close`

**Motion utilities** (§4)
- `.fx-advance`, `.fx-damage`, `.fx-approve`, `.fx-reject`, `.fx-flip`, `.is-shaking`

---

## 7. Implementation notes the dev will thank me for

- **Reuse the cat once.** Extract the `<svg class="run-cat">…</svg>` into a Jinja include (`_runcat.html`) and `{% include %}` it in the header nav, the board token, and the intro mini-track. One source of truth, three placements.
- **Backend is done; wire to it, don't reinvent.** The four endpoints exist and are typed. The game engine (cash/value/evidence math, dice, decks) is the `game.js` work — backend only seeds, scores, leaderboards, reviews. `evidence_score` is the ONLY game-state field the reviewer sees; keep PII out of `/review` (the schema already forbids it, don't fight it).
- **Outcome strings are a contract.** Use exactly `approved / bankrupt / failed_endpoint / beaten_to_market / clinical_hold` everywhere (gameover classes, leaderboard chips, score POST) — they're validated server-side (`Literal[...]`).
- **Difficulty is server-derived** (`_derive_difficulty`); display it, don't recompute it. The cat-paw pips read `seed.difficulty` (1–5).
- **Honesty badge is mandatory**, not decorative: render `source` from `/review` (`AI` vs `offline mode`) — the schema author put it there on purpose (model honesty is a brand value).
- **The two dice are the randomness engine** (organ die: brain/lung/liver/pancreas/bone/heart; outcome die: ✓/✗/!/@). Surface them as a small dice-roll animation in/near the action bar when `RUN A TRIAL TURN` fires; the outcome face drives whether the cat advances (✓), takes damage (✗), reveals an event (!), or redraws (@).
- **Don't break the map.** All game CSS is namespaced under `.theme-warroom` / game blocks; the only `main.css` additions are the `.nav-race*` block and the warroom token vars (inert until `.theme-warroom` is on `<body>`). The map page never gets `.theme-warroom`, so it's untouched.

---

### Files to create / edit (paths)
- **Edit** `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\frontend\templates\index.html` — add `.nav-race` anchor as first child of `.header-right`.
- **Edit** `c:\Users\Zapper\OneDrive\Desktop\Enterprise\jsu_repo\projects\trialcat-website\trialcat\frontend\static\css\main.css` — add warroom token vars to `:root` + `.theme-warroom` block + `.nav-race*` block; add `.nav-race__go` to the existing reduced-motion list.
- **Create** `…\frontend\templates\game.html` (+ `_runcat.html` include).
- **Create** `…\frontend\static\css\game.css` (everything in §2–§6).
- **Create** `…\frontend\static\js\game.js` (engine + endpoint wiring).
- **Create** `…\frontend\static\fonts\Inter-roman.var.woff2` (self-hosted Inter).
- **Add route** in the backend serving `GET /game` → `game.html` (alongside the existing page route).

**Key reuse wins already in the repo:** the running-cat SVG and its `gallop/scissorA/scissorB/tailWag/groundScroll/goPulse/finishPulse` keyframes (in `main.css`) are production-ready and become the token + nav cat for free; the backend game models/schemas/routes/review service are complete and dictate the exact state variables, outcomes, and FDA-reviewer contract this UI is built around.