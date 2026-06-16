UPC confirmed: `6 02573 64078 4` (= 602573640784). I now have complete coverage. Here is the report.

---

# Game Archaeology Report: "The Strategy Game (for Regulatory Affairs)" / "REG"

**Source folder:** `.../board game/Reg Board Game-20260616T015528Z-3-001/Reg Board Game/`
**Dating:** All art/print files stamped **23FEB2018**. Publisher: **Doctor Incubator, LLC** — "an Angela N. Johnson business" (`www.thedoctorincubator.com`). This is Angie's own pre-TRCL venture.

**Method note:** The two PDFs the prompt pointed me at (`temp-print.pdf`, `UPC/Printable-23FEB2018.pdf`) are NOT the game — `temp-print.pdf` is a medical-icon/sticker sheet and `Printable-23FEB2018.pdf` is a **"Polymer Salon — Artisan Key Caps by Sean Murphy"** zombie-skull logo (Sean's keycap side-business; the folder has mixed assets). The plan's `.../Printable/` path holds `Character cards.ai`, not a PDF. `cube_outline.pdf` is a generic atozteacherstuff.com papercraft cube template (a die-folding aid). The real game art is in the `.ai` files — which I rendered via their embedded PDF-compatibility stream in PyMuPDF, and whose live (un-outlined) text I extracted directly. Everything below is read from the actual art, not inferred. Renders saved under `/tmp/boardgame_render/` (`AI_gameplay_board.png`, `AI_characters.png`, `AI_cover-art.png`, `AI_logo.png`, `AI_dice-stickers.png`, `board270_left.png`, `board270_right.png`, `upc.png`).

---

## 1. Title / Branding

- **Primary title:** *"The **STRATEGY** **game**"* with the strapline **"for regulatory affairs."** A handwritten "only" sits above STRATEGY (a wink — "The *only* Strategy game for regulatory affairs").
- **Short brand mark:** **"REG"** — bold outlined 3-letter logotype, also used as a blue square icon-badge. This is the spine/token brand.
- **Logo file** holds 5 lockups: full title (black, and a blue STRATEGY variant), the standalone "REG" wordmark, and a combined REG-badge + title lockup. All carry a ™.
- Tone is deliberately cartoonish/retro-comic — a serious regulatory topic dressed as a light family-style board game.

---

## 2. Board Layout

A single long, snaking track titled **"Your PRODUCT'S VALUE"** (the path label running the length of the board) — the spine of the game is **driving your drug's valuation up while not running out of cash**. It is NOT a literal IND→NDA pathway map; it's a **fundraising/valuation gauntlet**, which is the more honest satire of how reg-affairs actually plays out.

**The spaces are dollar valuations**, snaking in a boustrophedon (back-and-forth) layout. Reading the value ladder from the cheap end up:

- **Low rung (cash/early):** `$100k → $1M → $5M → $10M → $15M → $25M → $50M → $60M → $70M → $80M → $90M`
- **Mid rung:** `$100M → $200M → $250M → $300M → $400M → $500M → $600M → $700M → $800M → $900M`
- **High rung (valuation/exit):** `$1B → $1.25B → $1.5B → $2.0B → $2.5B → $3B → $3.5B → $4B → $5B → $6B → $9B`

So the track climbs from **$100k to $9B** — the journey from garage to blockbuster.

**Special / event spaces (exact label text):**
- **"You got the grant funding!"**
- **"Corporate venture funds awarded!"**
- **"Boot-strap it!"** (two helper characters drawn beside it)
- **"You are out of money!"** (the lose condition, drawn with a distressed character)
- **"Fire the CEO?"**
- **"Hire CRO?"**
- **"Get acquired?"** / **"Sell!"** / **"No thanks!"** (decision forks — appears twice: e.g. *"Sell! $750M / No thanks!"* and *"$500M Sell! / No thanks!"* — i.e. you may take a buyout at a value or decline and keep climbing)
- **"Draw new staff"**
- **"Draw +1 staff card & +1 REG card"**
- Repeated motivational refrains printed on the board rails: **"Develop your drug before funding runs out!"** (printed twice).

**Component count (from cover):** *"1 game board with 4 tiles"* — so the physical board is a 4-panel fold-out; the long track I read spans those tiles.

---

## 3. Characters (6 player cards — satirical reg-affairs personas)

Cartoon character cards, each with a name, archetype label, and a colored token disc (matching player pawns). Names are puns. The clarity render is `AI_characters.png`:

| Token color | Name | Archetype | Pun / read |
|---|---|---|---|
| White/silver | **Dr. Curzitall** | **Doctor** | "Doctor cures it all" — lab-coat physician holding a chart |
| Gold/yellow | **D. Lay, JD** | **Lawyer** | "Delay, JD" — arms-crossed suited regulatory attorney |
| Blue | **Brian** | **Grad Student** | the everyman grad student, lanyard + "Science" tee, hands up |
| Green | **O. Vrsink, PhD** | **Scientist** | "Oversink / kitchen-sink PhD" — bench scientist with flasks |
| Pink | **Prof. Goetta Grant** | **Professor** | "Gotta get a grant" — older prof with a pointer/cane |
| Red | **Ms. N. Vested, MBA** | **Investor** | "Invested, MBA" — businesswoman on a phone with a money cup |

Six characters → up to **6 players** (matches cover: *"6 player cards & tokens"*).

---

## 4. Resource Tokens / Dice / Cards (intended mechanics)

**Two custom fold-up dice** (from `dice-stickers.ai`, sticker sheets to wrap blank cubes — "Cut on solid lines / Fold on dotted lines," © Doctor Incubator, LLC):
- **Organ die** — six faces: **BRAIN, LUNG, LIVER, PANCREAS, BONE, HEART.** → You're developing a drug for a body system / therapeutic area; the die likely picks your indication or a trial-event organ.
- **Outcome die** — six faces of result-markers: **✓ (green check), ✗ (red X), ! (exclamation), @ (the "circle-arrow/recycle" mark)**, mixed. → A pass/fail/complication/redo result die — your trial/submission verdict each turn.

**Cards (cover: "32 playing cards"):**
- **REG cards** — the regulatory-event/hazard deck (the "REG" brand). Board space *"Draw +1 staff card & +1 REG card"* ties draws to progress.
- **Staff cards** — *"Draw new staff,"* *"+1 staff card"* — you assemble a team; the 6 characters are roles you recruit.
- Decision cards tie to the **Hire CRO? / Fire the CEO? / Get acquired? / Sell?** forks.

**Tokens / icons (`icons.ai` + the icon sheet):** anatomical organs (brain, lung, liver, pancreas, bone, heart — mirroring the die), molecule/compound glyphs, **syringes, blood-vial, laptop**, plus **"combo!"** call-outs and the ✓/✗/! result markers. These read as **money/data/asset cubes and event icons** — the plan's guess of "resource cubes = money/time/data" is well-supported (the entire board is a money ladder, and the icons supply data/clinical assets).

**Implied loop:** Recruit staff → roll dice (pick organ/indication + get an outcome) → draw REG events → move along the valuation track → hit decision forks (hire CRO, fire CEO, take a buyout or push on) → **win = drive product value to the top without "You are out of money!"** It is a press-your-luck **fundraising-survival race**, not a linear checklist — which is exactly the satirical truth of drug development.

---

## 5. Visual Style, Color, Motifs, Humor

- **Style:** Flat retro-comic cartooning, heavy black outlines (the "VectorHero" Illustrator brush pack in the folder is the linework engine), exaggerated big-head caricatures.
- **Palette:** Dominant **cyan/sky-blue** board with white rounded-square spaces; characters in primary token colors (white/gold/blue/green/pink/red); REG badge is a saturated blue.
- **Motifs:** Crumpled-paper texture background (`paper source.psd`), organ illustrations, molecules/compounds, lab glassware, money figures ($), the recurring **REG** badge.
- **Humor/tone:** Insider reg-affairs satire. The joke is that "regulatory strategy" is really a cash-survival scramble — *"Develop your drug before funding runs out!"*, *"Fire the CEO?"*, *"You are out of money!"* The pun names (Dr. Curzitall, D. Lay JD, Prof. Goetta Grant, Ms. N. Vested) are the comedic core. Cover pitch leans on it: **"What a difference a game makes! Did you know research shows gaming is more effective than conventional continuing education? Learn the basics of U.S. regulatory strategy or sharpen your skills by playing the game of regulation with your friends and coworkers."** — pedagogy-as-product, explicitly citing research (`thedoctorincubator.com/reg-citations`).

---

## 6. Legal / UPC / Productization Context

This was a **genuinely productized retail item**, not a sketch:

- **UPC/GTIN:** `6 02573 64078 4` → **602573640784** (barcode confirmed visually; `.eps/.pdf/.tif` provided). Purchased from **EZ UPC** with a **Certificate of Authenticity** (`Certificate-Doctor-23335.pdf`) — number is owned, not product-locked until assigned.
- **SKU:** **ITEM NO. 201.**
- **Box copy is print-ready:** age **12+**, ~**0 min**(?)/play-time field, **manufacturing line:** *"Parts made in the U.S.A. or China or H.K. / Assembled and packaged in the U.S.A."*
- **Toy-safety compliance done:** **Choking Hazard / WARNING — small parts not suitable for children under 3** (icon + the `0x52_not_suitable_for_children_with_age_0-3.svg` CE-style mark), plus reference PDFs (`InternationalToyPamphlet`, "Legal Blurb on a Board Game Box — 13 steps / Pixy Games UK") — Angie literally researched board-game box legal compliance.
- **Address of record:** 1710 Cherokee Dr., Fort Wright, KY 41011.
- **QR code** asset present (`qrcode.eps`) pointing to the website.
- **Box contents (canonical):** *"instructions, 1 game board with 4 tiles, 6 player cards & tokens, 32 playing cards."*

---

## 7. Constraints & Inspiration for the Web (v2) Adaptation

**Constraints / fixed canon to honor:**
- **The game is a valuation race, not a pathway map.** Win = climb `$100k → $9B`; lose = "You are out of money!" The v2 rules engine should model **cash + product-value as the two core state variables**, not a linear IND→approval track. (This refines the plan file's Phase-0 guess — the board is fundraising-survival, with reg events as friction.)
- **6 fixed characters** with set names/colors/archetypes — reuse verbatim; they're the IP and the comedy. Token colors map to player identity.
- **Two dice = two state inputs:** organ/indication die (6 body systems) + outcome die (✓/✗/!/@). Keep both — they're the randomness engine.
- **Three card decks** to model: **REG** (events/regulatory friction), **Staff** (team-building), and decision/acquisition cards. 32 cards total is the legacy count.
- **Branding is locked and good:** "The (only) STRATEGY game for regulatory affairs" + the **REG** badge. The plan suggests embedding under trialcat.ai; the existing brand is strong enough to keep as the game's sub-brand. Note the publisher byline is **Doctor Incubator, LLC / Angela N. Johnson** — a 2018 entity; v2 should decide whether to re-badge under TRCL.
- **Decision forks (Hire CRO? / Fire the CEO? / Get acquired?–Sell!/No thanks!)** are the interactive moments — perfect hooks for the planned **LLM "FDA reviewer" NPC** and for branching web UI.

**Inspiration / assets ready to pipeline:**
- Art is **clean vector** and renders losslessly from the `.ai` PDF-compat stream — board, 6 character cards, logo lockups, dice-sticker faces, and the icon set can all be exported to SVG/PNG today (I already rasterized them at 4× with crisp legibility). No art needs to be recommissioned.
- The cover already contains the **elevator pitch and the pedagogy claim** ("gaming is more effective than conventional CE") and a citations URL — that copy seeds the trialcat.ai `/learn` landing page and the pedagogy-paper framing directly.
- The icon sheet (organs, molecules, syringes, vials, laptop, ✓/✗/!, "combo!") gives a ready token/badge vocabulary for the web UI and for a "combo" bonus mechanic the original art hints at.

**Watch-outs:** The "Polymer Salon" keycap logo and the loose medical-icon sticker sheet in this folder are **not part of this game** — don't pull them into the v2 asset set. The real per-component sources are: `gamepaly.ai` (board), `characters.ai` (6 cards), `cover-art.ai` (box/contents/legal copy), `logo.ai` (branding), `dice-stickers.ai` (2 dice), `icons.ai` (tokens), `Printable/Character cards.ai` (print cards — its PDF-compat preview was empty, so it needs Illustrator to export). The `.psd` (`paper source.psd`) is the background texture.