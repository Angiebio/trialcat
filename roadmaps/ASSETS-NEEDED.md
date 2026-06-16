# TrialCat / Race to Approval — Graphics & Assets Backlog

**Date:** 16 June 2026 · **Owner:** Angie (Illustrator exports) · **Status:** backlog — placeholders are live now, swap in real art later this week

> **How to swap any asset in:** drop the file into `frontend/static/img/` (or the noted subfolder) using the exact **filename** below. No code changes needed — the game already points at these paths. Where a placeholder is live, replacing the file is all it takes.

**Source `.ai` files** all live in:
`…/board game/Reg Board Game-20260616T015528Z-3-001/Reg Board Game/`
(`characters.ai`, `gamepaly.ai`, `logo.ai`, `icons.ai`, `dice-stickers.ai`, `cover-art.ai`)

**Visual style to match:** the "Sticker-Comic" system already shipped — flat cream + board-cyan, heavy `#1b1b1b` outlines, solid offset shadows (no blur), the retro-comic 2018 board look. Transparent backgrounds where noted so assets sit on the cream/cyan surfaces cleanly.

---

## Priority 1 — visible now, current placeholder is "good enough but improvable"

| ID | Asset | Source | Target path (exact) | Format | Size | Current placeholder | Notes |
|----|-------|--------|---------------------|--------|------|---------------------|-------|
| **A1** | **Founder portraits ×6** | `characters.ai` | `img/founders/{doctor,lawyer,gradstudent,scientist,professor,investor}.png` | PNG | ~600×900 (card) **or** ~600×600 (transparent cut-out) | ✅ Live — tight crops of the 6 cards (blue card bg + faint neighbor sliver) | Two options: (a) clean re-export of each **full card** (uniform, no neighbor bleed), or (b) **transparent character cut-outs** so I can frame them in our sticker style. Filenames must stay exactly as listed. |
| **A2** | **Game board (landscape, trimmed)** | `gamepaly.ai` | `img/board.png` | PNG (or `board.svg`) | ≥2000px wide | ✅ Live — full PyMuPDF render, includes a loose icon row + margins | A clean **landscape** export trimmed to just the board (drop the floating icon strip + white margins). Used as the intro hero **and** required for the race-page "Product Value Map" (token-on-board). SVG ideal for crispness. |

## Priority 2 — replaces a CSS-faked element / emoji

| ID | Asset | Source | Target path | Format | Size | Current placeholder | Notes |
|----|-------|--------|-------------|--------|------|---------------------|-------|
| **A3** | **REG logo + wordmark** | `logo.ai` | `img/reg-logo.svg` | **SVG**, transparent | vector | ⚠️ CSS-faked — header "REG" badge is a styled `::before` | The real REG mark + "The STRATEGY game (for regulatory affairs)" lockup. Powers the game header, the win seal, and the favicon. SVG so it scales to 16px and to a hero. |
| **A4** | **Icon set** | `icons.ai` | `img/icons/*.svg` (or one `icons-sprite.svg`) | SVG (or transparent PNG) | ~128px each | ⚠️ Emoji stand-ins (💰💵📊🤝⏳ in HUD; ⚑ etc.) | Organs / molecules / syringe / laptop / vial from the board. Lets us replace emoji-as-chrome with the real 2018 icon vocabulary in the HUD + action chips. |
| **A5** | **Favicon** | `logo.ai` (REG badge) | `img/favicon.png` (+ `favicon.ico`) | PNG / ICO | 32×32 & 16×16 | ✅ Live — generic trial-cat logo | Swap to the REG badge for game pages. Low effort once A3 exists. |

## Priority 3 — new art (your style), nice-to-have

| ID | Asset | Source | Target path | Format | Size | Current placeholder | Notes |
|----|-------|--------|-------------|--------|------|---------------------|-------|
| **A6** | **"APPROVED" / "CRL" stamps** | new (match style) | `img/stamp-approved.png`, `img/stamp-crl.png` | PNG transparent (or SVG) | ~500px | ⚠️ CSS text stamp on the end screen | Rubber-stamp seals that slam onto the board on win/loss. Big emotional payoff. Green APPROVED, orange COMPLETE RESPONSE. |
| **A7** | **Dice faces** | `dice-stickers.ai` | `img/dice/organ-{brain,lung,liver,pancreas,bone,heart}.png`, `img/dice/outcome-{check,x,bang,at}.png` | PNG/SVG transparent | ~128px | ❌ none (dice resolved invisibly in engine) | Only needed **if** we surface the organ + outcome dice visually (currently the engine rolls them silently for `diceOutcome` event cards). |
| **A8** | **Social / OG share card** | new (board + title) | `img/og-game.png` | PNG | 1200×630 | ⚠️ text-only `og:` tags | For link previews when the game gets shared. Board art + "Race to Approval" + the hook. |
| **A9** | **Cover / box art (front panel)** | `cover-art.ai` | `img/cover-front.png` | PNG | ~1000px | ❌ removed (the render was the full box dieline) | Optional alternate hero / "box on a shelf" composition. A clean **front panel only** export (the dieline has front+back+spine+barcode). |

---

## Status legend
✅ Live placeholder (working, improvable) · ⚠️ Faked/stand-in (CSS or emoji) · ❌ Not present yet

## Notes for whoever exports these
- Keep **filenames exact** — the templates/CSS reference these paths directly.
- **Transparent PNGs** for anything that sits on the cream or cyan surfaces (founders cut-outs, icons, stamps, REG mark). Solid-bg is fine for the board hero.
- Export PNGs at **2× the display size** (retina) where practical; SVG preferred for logo/icons/board.
- The locked palette (purple `#4a0873`, green `#5bb545`, cyan `#2bb8d8`, yellow `#e8e52a`, orange `#f5841f`, cream `#FAFAF5`, outline `#1b1b1b`) is in `TRCL-BRAND-STYLE-GUIDE` and `frontend/static/css/game.css`.

## Dependency note
- The race-page **"Product Value Map"** (cat token climbing the real board) wants **A2** (trimmed board) first, so the token can be positioned against a known image. Everything else is independent and swappable any time.
