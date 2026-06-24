# Board Mode — UX / Animation Patterns (Sticker-Comic)

**Date:** 22JUN2026 · **For:** TrialCat "Race to Approval" Board Mode
**Constraints:** vanilla JS, vanilla CSS, WebAudio. NO frameworks. NO asset files.
Every token pulled from `game.css` (`--c-cyan #2bb8d8`, `--ink #1b1b1b`,
`--c-purple #4a0873`, `--c-yellow #e8e52a`, `--c-green #5bb545`,
`--c-orange #f5841f`, `--c-cream #FAFAF5`, `--font-display` Bricolage,
`--font` Inter). Hard outlines, SOLID offset shadows (no blur), no gradients.

These five patterns are the turn loop made physical:
**SPIN (1) → flip a deck card (2) + whoosh sound (3) → token climbs the snake (4)**,
all wired into the existing `renderAll()` loop (5).

Board geometry note: `board.svg` viewBox is `810.16 × 320.98`; avatars animate
along a hand-authored waypoint polyline in those coords (Pattern 4 is the
tween primitive; the waypoint table lives in game.js).

---

## 1. Comic Spinner (vanilla JS + CSS/SVG)

A 4-wedge cyan/yellow/green/orange wheel with a hard ink rim and a fixed pointer.
Spins with ease-out cubic-bezier, lands on a random wedge 1–4, fires a callback.
The wheel is one inline SVG (no asset). Ticking sound = Pattern 3 `tick()`.

### CSS
```css
/* ===== COMIC SPINNER — a die-cut wheel, hard rim, solid shadow ===== */
.spinner-wrap { display:flex; flex-direction:column; align-items:center; gap:10px; margin:6px 0 14px; }
.spinner-stage {
  position:relative; width:148px; height:148px;
  filter: drop-shadow(6px 6px 0 var(--ink)); /* the only "shadow" — flat, offset, no blur */
}
.spinner-wheel { width:100%; height:100%; transform:rotate(0deg);
  transition: transform 2.7s cubic-bezier(.13,.86,.27,1); transform-origin:50% 50%; will-change:transform; }
.spinner-wheel.no-anim { transition:none; }
/* the fixed pointer — a yellow comic tab stamped over 12 o'clock */
.spinner-pointer {
  position:absolute; top:-13px; left:50%; transform:translateX(-50%);
  width:0; height:0; border-left:13px solid transparent; border-right:13px solid transparent;
  border-top:22px solid var(--c-yellow); z-index:3;
  filter: drop-shadow(0 2px 0 var(--ink)); }
.spinner-pointer::after { /* ink outline on the pointer */
  content:""; position:absolute; left:-13px; top:-22px; width:0; height:0;
  border-left:13px solid transparent; border-right:13px solid transparent; border-top:22px solid transparent;
  border-image: none; }
.spinner-hub { /* REG-stamp center cap */
  position:absolute; top:50%; left:50%; transform:translate(-50%,-50%) rotate(-6deg);
  width:38px; height:38px; display:grid; place-items:center; z-index:2;
  background:var(--c-yellow); color:var(--c-purple); font-family:var(--font-display);
  font-weight:800; font-size:13px; border:3px solid var(--ink); border-radius:7px; box-shadow:2px 2px 0 0 var(--ink); }
.spinner-btn { /* the chunky SPIN button (reuses .btn-comic visual language) */
  font-family:var(--font-display); font-weight:800; font-size:16px; letter-spacing:.02em;
  color:var(--c-purple); background:var(--c-green); border:3px solid var(--ink); border-radius:6px;
  padding:10px 26px; cursor:pointer; box-shadow:4px 4px 0 0 var(--ink);
  transition:transform .08s, box-shadow .08s, background .12s; }
.spinner-btn:hover:not(:disabled){ background:var(--c-yellow); }
.spinner-btn:active:not(:disabled){ transform:translate(4px,4px); box-shadow:0 0 0 0 var(--ink); }
.spinner-btn:disabled{ background:#e6e2d6; color:#9a93a6; box-shadow:4px 4px 0 0 #bdb6a6; cursor:not-allowed; }
.spinner-result { font-family:var(--font-display); font-weight:800; font-size:13px; color:var(--c-purple);
  min-height:18px; text-transform:uppercase; letter-spacing:.04em; }
@media (prefers-reduced-motion: reduce){ .spinner-wheel{ transition:transform .25s linear !important; } }
```

### JS
```js
/* makeSpinner — a 4-up comic wheel that lands on 1..4 and burns capital per step.
 * Practical: deterministic landing math so the pointer truly points at the wedge.
 * Philosophical: chance with an honest face. The wheel must STOP where it SAYS,
 * or the player stops trusting the board — and trust is the only currency a game
 * actually runs on. */
const SPIN_WEDGES = [
  { n:1, fill:'#2bb8d8' }, // cyan
  { n:2, fill:'#e8e52a' }, // yellow
  { n:3, fill:'#5bb545' }, // green
  { n:4, fill:'#f5841f' }, // orange
];
function spinnerSVG(){
  // four 90° wedges as <path>; numbers placed at wedge midpoints.
  const cx=74, cy=74, r=70;
  const pt=(deg)=>[cx+r*Math.cos(deg*Math.PI/180), cy+r*Math.sin(deg*Math.PI/180)];
  let paths='';
  SPIN_WEDGES.forEach((w,i)=>{
    const a0=i*90-90, a1=a0+90;               // start wedge 1 at top (12 o'clock)
    const [x0,y0]=pt(a0), [x1,y1]=pt(a1);
    paths += `<path d="M${cx},${cy} L${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z"
                fill="${w.fill}" stroke="#1b1b1b" stroke-width="3"/>`;
    const [tx,ty]=pt(a0+45); const mx=cx+(tx-cx)*0.62, my=cy+(ty-cy)*0.62;
    paths += `<text x="${mx.toFixed(1)}" y="${(my+6).toFixed(1)}" text-anchor="middle"
                font-family="Bricolage Grotesque, sans-serif" font-weight="800" font-size="28"
                fill="#1b1b1b">${w.n}</text>`;
  });
  return `<svg viewBox="0 0 148 148" class="spinner-wheel" id="spin-wheel">
    <circle cx="74" cy="74" r="71" fill="none" stroke="#1b1b1b" stroke-width="5"/>${paths}</svg>`;
}
/** Mount the spinner into a container; onResult(steps:1..4) fires when it stops. */
function makeSpinner(containerEl, onResult){
  containerEl.classList.add('spinner-wrap');
  containerEl.innerHTML = `
    <div class="spinner-stage">
      <div class="spinner-pointer"></div>
      ${spinnerSVG()}
      <div class="spinner-hub">REG</div>
    </div>
    <button class="spinner-btn" id="spin-go">SPIN ▶</button>
    <div class="spinner-result" id="spin-out"></div>`;
  const wheel = containerEl.querySelector('#spin-wheel');
  const btn   = containerEl.querySelector('#spin-go');
  const out   = containerEl.querySelector('#spin-out');
  let turns = 0; // accumulate so it always spins forward (never snaps backward)

  btn.addEventListener('click', ()=>{
    btn.disabled = true; out.textContent = '';
    const steps = 1 + Math.floor(Math.random()*4);        // the real outcome: 1..4
    // wedge i occupies [i*90 .. i*90+90); its CENTER sits at i*90+45 from 12 o'clock.
    // pointer is fixed at top, so rotate the wheel so that wedge-center meets top.
    const wedgeIdx = steps - 1;
    const targetCenter = wedgeIdx*90 + 45;                // degrees clockwise of top
    const jitter = (Math.random()*36 - 18);               // land off-center, comic imperfect
    turns += 4 + Math.floor(Math.random()*2);             // 4–5 full revolutions of drama
    const finalDeg = turns*360 - targetCenter + jitter;   // negative target = rotate so center hits top
    wheel.style.transform = `rotate(${finalDeg}deg)`;

    // ticking sound that decelerates with the wheel (Pattern 3)
    if (window.SFX) window.SFX.spinnerTicks(2700);

    const done = ()=>{
      wheel.removeEventListener('transitionend', done);
      out.textContent = `Move ${steps} ${steps===1?'square':'squares'} →`;
      if (window.SFX) window.SFX.flip(); // soft confirm
      onResult(steps); // caller re-enables when its move animation finishes
    };
    wheel.addEventListener('transitionend', done, { once:true });
    // safety: if transitionend never fires (reduced-motion / bg tab), resolve anyway
    setTimeout(()=>{ if (btn.disabled) done(); }, 3100);
  });
  return { enable(){ btn.disabled=false; }, disable(){ btn.disabled=true; }, el:btn };
}
```

---

## 2. CSS 3D Card-Flip on Deck Draw

Player clicks a deck → a card flips from face-down (REG-stamped back) to its
face (the drawn card). Pure CSS `rotateY` with `preserve-3d`. The face is built
from the existing `.card-modal` look so it reads as the same sticker family.

### CSS
```css
/* ===== DECK DRAW — a card that flips face-up in 3D ===== */
.flip-scene { perspective:1200px; width:300px; max-width:88vw; margin:0 auto; }
.flip-card { position:relative; width:100%; aspect-ratio:3/4; transform-style:preserve-3d;
  transition:transform .62s cubic-bezier(.2,.9,.2,1); transform:rotateY(180deg); /* starts showing BACK */ }
.flip-card.is-flipped { transform:rotateY(0deg); }                  /* lands showing FACE */
.flip-face, .flip-back {
  position:absolute; inset:0; backface-visibility:hidden; -webkit-backface-visibility:hidden;
  border:4px solid var(--ink); border-radius:8px; box-shadow:7px 7px 0 0 var(--ink);
  display:flex; flex-direction:column; overflow:hidden; }
/* the BACK — REG-stamped kraft, the 2018 spine mark, halftone dots */
.flip-back { transform:rotateY(0deg); background:var(--c-purple);
  background-image:radial-gradient(circle at 1px 1px, rgba(255,255,255,.10) 1px, transparent 0);
  background-size:14px 14px; align-items:center; justify-content:center; }
.flip-back .reg-stamp { font-family:var(--font-display); font-weight:800; font-size:46px; color:var(--c-yellow);
  border:5px solid var(--c-yellow); border-radius:12px; padding:10px 18px; transform:rotate(-6deg);
  text-shadow:3px 3px 0 var(--ink); letter-spacing:-.04em; }
.flip-back .deck-name { position:absolute; bottom:14px; font-family:var(--font-display); font-weight:700;
  font-size:13px; color:var(--c-cream); letter-spacing:.16em; text-transform:uppercase; }
/* the FACE — colored by card kind, matches .card-modal palette */
.flip-face { transform:rotateY(180deg); background:var(--c-cream); padding:18px 16px; text-align:left; }
.flip-face.good { background:var(--c-green-soft); } .flip-face.bad { background:#ffe0c2; } .flip-face.swing { background:#fdf6a8; }
.flip-face .fc-kind { font-family:var(--font-display); font-weight:800; font-size:11px; letter-spacing:.12em; text-transform:uppercase; color:var(--c-purple); }
.flip-face .fc-suit { position:absolute; top:12px; right:14px; font-size:22px; }
.flip-face h3 { margin:8px 0 8px; font-family:var(--font-display); font-weight:800; font-size:20px; line-height:1.08; color:var(--c-purple); }
.flip-face .fc-flavor { font-size:13px; line-height:1.5; color:var(--c-purple-80); flex:1; overflow:auto; }
.flip-face .fc-effect { font-family:var(--font-display); font-weight:700; font-size:14px; margin-top:8px; }
.flip-face .fc-effect .up{ color:#2f8a1c; } .flip-face .fc-effect .down{ color:var(--c-orange); }
@media (prefers-reduced-motion: reduce){ .flip-card{ transition:none; } }
```

### JS
```js
/* drawAndFlip — picks a random card from a deck, flips it face-up.
 * Practical: build DOM face-down, force reflow, then add .is-flipped next frame
 * so the browser actually animates the transition (a classic gotcha).
 * Philosophical: the flip is the player's ONE moment of pure agency in a turn
 * otherwise ruled by dice and regulators. Give it weight: a real beat, a sound,
 * a reveal. The hand that turns the card is the hand that still believes. */
const DECK_SUIT = { '🔬 R&D':'♣', '🧪 Enroll':'♥', '🏛️ FDA':'♠', '💵 Funding':'♦' };

function drawAndFlip(overlayEl, deckName, card, onSettled){
  // card = a RAW_DECK-shaped object {t,k,f,e,...} OR an ACTIONS entry; normalize:
  const kind   = card.k || 'swing';
  const title  = card.t || card.name;
  const flavor = card.f || card.desc || '';
  const suit   = DECK_SUIT[deckName] || '★';
  const effect = card._effectHTML || ''; // caller may precompute effectSummary HTML

  overlayEl.innerHTML = `
    <div class="flip-scene">
      <div class="flip-card" id="flip-card">
        <div class="flip-back"><div class="reg-stamp">REG</div><div class="deck-name">${deckName}</div></div>
        <div class="flip-face ${kind}">
          <span class="fc-suit">${suit}</span>
          <div class="fc-kind">${kind==='good'?'✦ Good news':kind==='bad'?'⚠ Bad news':'⚖ It could go either way'}</div>
          <h3>${escapeHtml(title)}</h3>
          <div class="fc-flavor">${linkJargon(flavor)}</div>
          ${effect?`<div class="fc-effect">${effect}</div>`:''}
        </div>
      </div>
    </div>`;
  overlayEl.classList.add('active');

  const cardEl = overlayEl.querySelector('#flip-card');
  void cardEl.offsetWidth;             // force reflow so the .is-flipped transition fires
  if (window.SFX) window.SFX.flip();   // whoosh at the moment of the turn
  requestAnimationFrame(()=> requestAnimationFrame(()=> cardEl.classList.add('is-flipped')));

  const settle = ()=>{ cardEl.removeEventListener('transitionend', settle); onSettled && onSettled(card); };
  cardEl.addEventListener('transitionend', settle, { once:true });
  setTimeout(()=>{ if (cardEl.classList.contains('is-flipped')) settle(); }, 800); // reduced-motion safety
}

/** Pull a random card from one of the four named decks. Decks map to RAW_DECK
 *  by tone; Funding favors money cards. Tune freely. */
function drawFromDeck(deckName){
  // simple split: Funding pulls capital-positive cards, others pull broadly.
  const pool = deckName === '💵 Funding'
    ? RAW_DECK.filter(c => (c.e && c.e.c > 0) || (c.sp && c.sp.type==='choose'))
    : RAW_DECK;
  return pool[Math.floor(Math.random()*pool.length)];
}
```

---

## 3. WebAudio Flip / Whoosh / Spinner-Tick (no asset files)

One tiny synth module on the page. Lazily creates one `AudioContext` on first
user gesture (browser autoplay policy). All sounds are generated — zero files.
Includes a mute toggle pattern with `localStorage` persistence and a header chip.

### JS
```js
/* SFX — a pocket synth. Practical: lazy AudioContext (autoplay policy needs a
 * user gesture), oscillators + noise buffers, no files shipped. Philosophical:
 * sound is the cheapest dopamine in game design and the easiest to get wrong.
 * Short, dry, comic. A whoosh, a tick, a coin — never a drone. And ALWAYS a
 * mute, because consent includes the right to silence. */
window.SFX = (function(){
  let ctx = null, muted = (localStorage.getItem('tc_muted') === '1');
  const ensure = ()=>{ if(!ctx){ const AC = window.AudioContext||window.webkitAudioContext; if(AC) ctx=new AC(); }
                       if (ctx && ctx.state==='suspended') ctx.resume(); return ctx; };

  // a master gain so mute is instant and global
  let master=null;
  const bus = ()=>{ const c=ensure(); if(!c) return null; if(!master){ master=c.createGain(); master.gain.value=muted?0:1; master.connect(c.destination);} return master; };

  function tone(freq, t0, dur, type='sine', gain=0.18, slideTo=null){
    const c=ensure(); const out=bus(); if(!c||!out) return;
    const o=c.createOscillator(), g=c.createGain();
    o.type=type; o.frequency.setValueAtTime(freq, t0);
    if(slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, t0+dur);
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(gain, t0+0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t0+dur);
    o.connect(g); g.connect(out); o.start(t0); o.stop(t0+dur+0.02);
  }
  function noiseBurst(t0, dur, gain=0.12, hp=600){
    const c=ensure(); const out=bus(); if(!c||!out) return;
    const len=Math.floor(c.sampleRate*dur), buf=c.createBuffer(1,len,c.sampleRate), d=buf.getChannelData(0);
    for(let i=0;i<len;i++) d[i]=(Math.random()*2-1)*(1-i/len); // decaying white noise
    const src=c.createBufferSource(); src.buffer=buf;
    const f=c.createBiquadFilter(); f.type='highpass'; f.frequency.value=hp;
    const g=c.createGain(); g.gain.setValueAtTime(gain,t0); g.gain.exponentialRampToValueAtTime(0.0001,t0+dur);
    src.connect(f); f.connect(g); g.connect(out); src.start(t0); src.stop(t0+dur);
  }

  return {
    // card flip: a short filtered whoosh + a tiny pitched "snap"
    flip(){ const c=ensure(); if(!c) return; const t=c.currentTime;
      noiseBurst(t, 0.16, 0.14, 900); tone(520, t+0.05, 0.10, 'triangle', 0.10, 240); },
    // whoosh: longer airy sweep for a token launching off a square
    whoosh(){ const c=ensure(); if(!c) return; const t=c.currentTime;
      noiseBurst(t, 0.26, 0.10, 500); tone(300, t, 0.26, 'sine', 0.07, 760); },
    // a single mechanical tick (one square climbed)
    tick(){ const c=ensure(); if(!c) return; const t=c.currentTime;
      tone(1400, t, 0.035, 'square', 0.06, 1100); },
    // decelerating tick train that matches the spinner's ease-out over `ms`
    spinnerTicks(ms){ const c=ensure(); if(!c) return; const t0=c.currentTime; const total=ms/1000;
      let t=0, gap=0.045;                          // start fast
      while(t < total){ tone(1500, t0+t, 0.03, 'square', 0.05, 1150); t+=gap; gap*=1.14; } }, // slow down
    // coin/up sting for funding & good cards
    coin(){ const c=ensure(); if(!c) return; const t=c.currentTime;
      tone(880,t,0.08,'square',0.10); tone(1320,t+0.07,0.12,'square',0.10); },
    // dull thud for bad cards / bankrupt
    thud(){ const c=ensure(); if(!c) return; const t=c.currentTime;
      tone(150,t,0.22,'sine',0.18,60); noiseBurst(t,0.10,0.06,200); },

    // ---- mute toggle pattern ----
    isMuted(){ return muted; },
    toggleMute(){ muted=!muted; localStorage.setItem('tc_muted', muted?'1':'0');
      if(master) master.gain.setTargetAtTime(muted?0:1, ensure().currentTime, 0.01); return muted; },
  };
})();

/* Header mute chip — drop next to the leaderboard button. Reuses .ghost-btn.
 * <button class="ghost-btn" id="sfx-toggle">🔊</button>  */
function wireMuteToggle(){
  const b = document.getElementById('sfx-toggle'); if(!b) return;
  const paint = ()=>{ b.textContent = SFX.isMuted() ? '🔇' : '🔊';
                      b.setAttribute('aria-label', SFX.isMuted()?'Unmute':'Mute'); };
  paint();
  b.addEventListener('click', ()=>{ SFX.toggleMute(); paint(); if(!SFX.isMuted()) SFX.tick(); });
}
document.addEventListener('DOMContentLoaded', wireMuteToggle);
```

---

## 4. Avatar Tween Between Two Points (comic bounce/squash)

`requestAnimationFrame` tween of a token from `(x0,y0)` to `(x1,y1)` in viewBox
coords, with an arc hop, an anticipation squash on launch, and a stretch→squash
landing. Drives one square-to-square hop; chain it across the spun number of
squares so the cat visibly climbs the snake, ticking per square.

### JS
```js
/* tweenToken — one comic hop between two waypoints, RAF-driven.
 * Practical: position the avatar in viewBox space; CSS `left/top` in % keeps it
 * glued to the responsive board image. We animate a normalized 0..1 `p`, apply
 * an ease, add a sine ARC for the hop, and a squash/stretch envelope so it reads
 * like a sticker getting flicked up the board.
 * Philosophical: weight sells life. A token that teleports is a number; a token
 * that crouches, leaps, and lands with a wobble is a CHARACTER climbing toward
 * a $9B exit it has no business reaching. We animate the hope. */
const VB_W = 810.16, VB_H = 320.98; // board.svg viewBox

/** el: the avatar span (position:absolute inside .value-board).
 *  from/to: {x,y} in viewBox coords. hop: arc height px. dur: ms. */
function tweenToken(el, from, to, { hop=26, dur=380, onTick, onDone } = {}){
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce){ placeToken(el, to.x, to.y, 1, 1); onTick&&onTick(); onDone&&onDone(); return; }
  const t0 = performance.now();
  const easeOutBack = t => { const c1=1.70158, c3=c1+1; return 1 + c3*Math.pow(t-1,3) + c1*Math.pow(t-1,2); };
  (function frame(now){
    let p = Math.min(1, (now - t0) / dur);
    const e = easeOutBack(p);                          // overshoot landing = comic snap
    const x = from.x + (to.x - from.x) * e;
    const y = from.y + (to.y - from.y) * e;
    const arc = Math.sin(Math.PI * p) * hop;           // up-and-over hop (px, screen space)
    // squash/stretch: crouch at launch, stretch mid-air, squash on land
    let sx=1, sy=1;
    if (p < 0.15){ const k=p/0.15; sx=1+0.18*(1-k); sy=1-0.22*(1-k); }      // anticipation crouch
    else if (p < 0.7){ sy=1.14; sx=0.9; }                                   // airborne stretch
    else { const k=(p-0.7)/0.3; sy=1-0.16*Math.sin(Math.PI*k); sx=1+0.16*Math.sin(Math.PI*k); } // land squash
    placeToken(el, x, y, sx, sy, arc);
    if (p < 1){ requestAnimationFrame(frame); }
    else { placeToken(el, to.x, to.y, 1, 1, 0); onTick&&onTick(); onDone&&onDone(); }
  })(t0);
}

/** Convert viewBox coords → % offsets and apply transform. The `-arc` lifts the
 *  token in SCREEN space without disturbing its board anchor. */
function placeToken(el, vx, vy, sx=1, sy=1, arc=0){
  el.style.left = (vx / VB_W * 100) + '%';
  el.style.top  = (vy / VB_H * 100) + '%';
  el.style.transform = `translate(-50%,-50%) translateY(${-arc}px) scale(${sx.toFixed(3)},${sy.toFixed(3)})`;
}

/* climbPath — chain hops across N squares of the snake, ticking each landing.
 * waypoints: ordered [{x,y,trigger?}] in viewBox coords (the snake polyline).
 * Burns capital per square via the caller's onSquare(idx) hook. */
function climbPath(el, waypoints, fromIdx, steps, { onSquare, onArrive } = {}){
  const target = Math.min(waypoints.length - 1, fromIdx + steps);
  let i = fromIdx;
  const step = ()=>{
    if (i >= target){ onArrive && onArrive(target); return; }
    const a = waypoints[i], b = waypoints[i+1];
    tweenToken(el, a, b, {
      hop: 24, dur: 360,
      onDone: ()=>{ i++; if (window.SFX) SFX.tick(); onSquare && onSquare(i); 
                    requestAnimationFrame(step); }   // next hop after this lands
    });
  };
  if (window.SFX) SFX.whoosh();   // launch the whole climb
  step();
}
```

Usage in the turn loop:
```js
// after the spinner resolves with `steps`:
climbPath(catEl, BOARD_WAYPOINTS, S.pathIdx, steps, {
  onSquare:(idx)=>{ S.res.capital -= CAPITAL_PER_SQUARE; renderHUD();   // burn fuel per square
                    if (S.res.capital < 0) return; },
  onArrive:(idx)=>{ S.pathIdx = idx; const wp = BOARD_WAYPOINTS[idx];
                    if (wp.trigger) fireSquareTrigger(wp.trigger);       // land → trigger
                    if (!checkEnd()) { renderHUD(); renderValueBoard(); spinner.enable(); } }
});
```

---

## 5. Integration Notes — wiring into the existing `render` loop without a fight

**The existing loop (don't replace, extend).** `renderAll()` calls
`renderScenario / renderHUD / renderTension / renderValueBoard / renderBoard /
renderReadiness / renderActions / renderLog`. Board Mode adds movement and a
spinner step but keeps all of these as the single source of truth for the HUD.

1. **Avatars already exist and already use % positioning.** `#board-cat` /
   `#board-rival` in `game.html` are `position:absolute` inside `.value-board`,
   animated today by `renderValueBoard()` setting `style.left` by value%. Board
   Mode swaps that ONE function's body to drive position from a **waypoint index**
   instead of value%. Pattern 4's `placeToken()` writes both `left` and `top`,
   so the cat can finally turn the corners of the snake. Keep `renderValueBoard()`
   as the idempotent "snap to truth" (used on load and reduced-motion);
   `climbPath()` is the animated path between truths. **Never** let both run at
   once — animate, then on `onArrive` set `S.pathIdx` and let `renderValueBoard()`
   confirm the final cell.

2. **The spinner is a new turn phase, not a new screen.** Mount it once into a
   container in the play screen (e.g. a `<div id="spinner-mount">` added near
   `.actions`), `makeSpinner(mountEl, steps => climbPath(...))`. Gate it: the
   SPIN button is `disabled` until the player has drawn a card this turn
   (`S.drewThisTurn`), and re-`enable()`d in `climbPath`'s `onArrive`. This
   encodes the locked turn loop: **draw (agency) → spin (fate) → climb (cost) →
   trigger (consequence).**

3. **Deck draw replaces the four `.action` buttons' handler, not their markup.**
   `renderActions()` already renders the four decks as `.card-play` stacks with
   the right suits/headers. Board Mode rebinds their click: instead of
   `onAction(id)` applying a fixed delta, the handler calls
   `drawFromDeck(deckName)` → `drawAndFlip(overlayEl, deckName, card, settled=>{
   applyDelta(rawToDelta(card.e)); S.drewThisTurn=true; spinner.enable();
   renderAll(); })`. The flip overlay reuses `#overlay-event` (add a
   `flip-scene` child) or a new `#overlay-flip` with the same `.overlay/.active`
   pattern — the dimmed-board backdrop and z-index are already styled.

4. **Square triggers reuse the deck machinery you already have.** The 36
   `RAW_DECK` cards become `wp.trigger` payloads. A trigger node calls the
   EXISTING `showEvent()` / `showChoice()` / `resolveChoice()` path — choice forks
   (Get Acquired / Fire CEO / Hire CRO) already route through `showChoice()` and
   `opt.cashOut` already ends the game as `acquired`. So "land on Get Acquired?"
   = `showChoice(RAW_DECK.find(c=>c.id==='EVT-030'))`. Zero new modal code; you're
   spatializing handlers that already exist.

5. **Capital burn slots into `applyDelta`/`clamp`/`checkEnd` untouched.** Per-square
   burn is just `S.res.capital -= CAPITAL_PER_SQUARE` inside `climbPath`'s
   `onSquare`, then `renderHUD()`. Bankruptcy already triggers in `checkEnd()`
   (`if (S.res.capital < 0) return lose('bankrupt')`) → "You are out of money"
   square is the same loss with a board location. Call `checkEnd()` after the
   climb settles (in `onArrive`), not mid-hop, so the death animation doesn't
   fight the movement tween.

6. **Sound respects the existing motion contract.** `game.css` already has a
   `@media (prefers-reduced-motion: reduce)` block killing token bob and modal
   wobble; Patterns 1, 2, 4 each honor it (instant snap, no flip, `placeToken`
   direct). SFX is independent of motion and gated behind a user gesture + the
   `localStorage` mute. Initialize the AudioContext on the FIRST real click
   (the SPIN or a deck draw) — never on load — so autoplay policy never warns.

7. **One reduced-motion + one mobile caveat.** On `prefers-reduced-motion`, the
   spinner still resolves (short linear spin), the flip is skipped (face shown
   immediately), and `climbPath` snaps via `placeToken(... ,1,1)` then fires
   triggers — the game stays fully playable. On mobile (`max-width:680px` already
   in `game.css`), the spinner stage shrinks to ~110px (add a width override in
   the media query) and the `.flip-scene` is `max-width:88vw` so it never clips.

**State additions (minimal):** `S.pathIdx` (waypoint index, replaces nothing —
new), `S.drewThisTurn` (bool, gates the spinner), `BOARD_WAYPOINTS` (const data,
the snake polyline in viewBox coords), `CAPITAL_PER_SQUARE` (const, the fuel
burn). Everything else — resources, scoring, Vance, glossary, leaderboard —
runs exactly as it does today.
```
