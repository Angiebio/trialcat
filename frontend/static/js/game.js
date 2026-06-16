/**
 * The Strategy Game (for Regulatory Affairs) — "Race to Approval"  v2.1 (16JUN2026)
 *
 * The web rebirth of Angie's 2018 board game (TRCL 501(c)(3), with support from
 * Biotech Mentor LLC). Drive a real CT.gov product up the valuation track —
 * $100k to a $9B exit — without running out of money, blowing the endpoint, or
 * getting scooped. Pick your founder. Survive the REG deck. Face Dr. Vance.
 *
 * Deterministic-ish JS engine; the server only seeds a real trial, judges your
 * FDA submission, and keeps the leaderboard. Content (cards, board, copy) is
 * the satirical payload, lifted from the design pass and kept faithful to the
 * original art's jokes (Ms. N. Vested still leads your down round).
 *
 * Data > narrative. That's the game, and the industry.
 */

// ============================================================================
// CONTENT — characters, board, the REG deck, copy
// ============================================================================

// The six personas from the board. Each bends the opening, true to the pun.
const CHARACTERS = [
  { id: 'doctor',   name: 'Dr. Curzitall',        role: 'The Doctor',      emoji: '🩺', blurb: 'Cures it all. Starts with real clinical credibility — and data to match.', start: { data: 12 }, studyCostMult: 0.9 },
  { id: 'lawyer',   name: 'D. Lay, JD',           role: 'The Lawyer',      emoji: '⚖️', blurb: 'Delay, JD. Bad regulatory news lands softer when you read the CFR for fun.', start: { reputation: 8 }, badNewsShield: 0.5 },
  { id: 'gradstudent', name: 'Brian',             role: 'The Grad Student',emoji: '🎓', blurb: 'Broke, brilliant, doing payroll at 2am. One extra turn of runway, ten fewer million in the bank.', start: { capital: -12 }, extraTurns: 1 },
  { id: 'scientist',name: 'O. Vrsink, PhD',       role: 'The Scientist',   emoji: '🔬', blurb: 'Kitchen-sink rigor. Clean studies pay you back harder in data.', start: { data: 14 }, cleanBonus: 5 },
  { id: 'professor',name: 'Prof. Goetta Grant',   role: 'The Professor',   emoji: '📚', blurb: 'Gotta get a grant. Non-dilutive money flows; your raises sting less.', start: { capital: 8 }, raiseBonus: 1.6, raiseNoRepHit: true },
  { id: 'investor', name: 'Ms. N. Vested, MBA',   role: 'The Investor',    emoji: '💼', blurb: 'Invested, MBA. Deep pockets up front — but the competition smells blood and moves faster.', start: { capital: 30 }, competitorMult: 1.25 },
];

// Condensed pathways (board valueBands → product value climbs as you advance).
// need = readiness to clear the gate. The seeded trial's type picks the board.
const PATHWAYS = {
  drug: {
    label: 'Drug — NDA/BLA pathway',
    stages: [
      { key: 'preind', name: 'Pre-IND',         need: 12, blurb: 'You ask FDA if your plan is insane before spending the money. They answer in writing. You will reread that letter like a breakup text.' },
      { key: 'ph1',    name: 'Phase 1',         need: 16, blurb: 'First in humans. Not looking for it to work yet, just to not hurt anyone — a low bar your drug will still try to limbo under.' },
      { key: 'ph2',    name: 'Phase 2',         need: 22, blurb: 'Does it actually do anything? ~70% of programs die here. The valley of death has excellent parking.' },
      { key: 'ph3',    name: 'Phase 3',         need: 28, blurb: 'The big, expensive, registrational trial. Hundreds of millions riding on a p-value you do not control.' },
      { key: 'sub',    name: 'NDA/BLA',         need: 20, submission: true, blurb: 'You file. The application is 100,000+ pages. The reviewer reads all of it. This is the closest thing to love between a sponsor and the federal government.' },
      { key: 'approved', name: 'Approval',      need: 0,  terminal: true, blurb: 'Approved. Now do it again for the pediatric study, the REMS, and the post-marketing commitments.' },
    ],
  },
  device: {
    label: 'Device — 510(k)/PMA pathway',
    stages: [
      { key: 'concept', name: 'Concept',        need: 10, blurb: 'Define what the device must do, then spend three years discovering what "must" means to a regulator. Documentation all the way down.' },
      { key: 'presub',  name: 'Pre-Sub (Q-Sub)',need: 14, blurb: 'Ask CDRH for feedback before you commit. Remarkably helpful, right up until they mention the testing you hadn’t budgeted for.' },
      { key: 'bench',   name: 'Bench & Biocompat',need: 16, blurb: 'ISO 10993: confirm your device won’t dissolve, ignite, or befriend the immune system. It takes longer than you think. It always does.' },
      { key: 'pivotal', name: 'Pivotal / 510(k) vs PMA', need: 24, blurb: 'The fork. 510(k) is fast and crowded; PMA is slow, lonely, and wants real clinical evidence. De Novo is for the brave.' },
      { key: 'sub',     name: 'Submission',     need: 18, submission: true, blurb: 'You file and wait for the AI (Additional Information) request, which is not optional — it’s a stage of grief.' },
      { key: 'cleared', name: 'Clearance',      need: 0,  terminal: true, blurb: 'Cleared. Now stand up your QMS, complaint handling, UDI, and post-market surveillance. The device is born; it needs a pediatrician forever.' },
    ],
  },
};

// Actions. delta in RAW content units (scaled in applyDelta). ready = readiness.
const ACTIONS = [
  { id: 'clean', name: 'Run it clean', tag: 'study',
    desc: 'By the protocol, by the book. Slow, costly, and the kind of data that survives review.',
    delta: { capital: -3, data: 2, reputation: 0 }, ready: 14 },
  { id: 'fast', name: 'Enroll fast & dirty', tag: 'study',
    desc: 'Pack the sites, ask questions later. Quick readiness, ugly data, an integrity flag Dr. Vance will find.',
    delta: { capital: -2, data: 1, reputation: -1 }, ready: 20, integrity: 1 },
  { id: 'fda', name: 'Engage the FDA early',
    desc: 'Book a Type B meeting. Costs money and pride, buys goodwill and a clearer path.',
    delta: { capital: -1, data: 1, reputation: 2, value: 0, competitor: -1 }, ready: 8 },
  { id: 'raise', name: 'Raise capital',
    desc: 'Dilute the cap table, smile at the board, promise the moon. Refills the war chest.',
    delta: { capital: 5, reputation: -1 }, ready: 0, isRaise: true },
];

// The REG deck — 36 cards, faithful to the design content. Raw deltas {c,d,r,v}
// (capital/data/reputation/value); sp = normalized special handler.
const RAW_DECK = [
  // ---- GOOD ----
  { id:'EVT-001', t:'Breakthrough Therapy Designation', k:'good', f:'FDA agrees your drug is promising enough to skip ahead in line. You now get to email the same reviewer four times a week, and they have to answer. Bliss.', e:{d:1,r:3,v:2} },
  { id:'EVT-002', t:'Fast Track Granted', k:'good', f:'Rolling review unlocked. You may now submit your application in pieces, like a hostage negotiation where the hostage is your NDA and you are also the kidnapper.', e:{r:2,v:2} },
  { id:'EVT-003', t:'RMAT Designation', k:'good', f:'Your cell therapy is a Regenerative Medicine Advanced Therapy. Investors who cannot define "potency assay" wire you money anyway. The answer was always yes.', e:{c:4,r:2,v:3} },
  { id:'EVT-004', t:'Patient Advocacy Group Rallies', k:'good', f:'Real patients show up to your AdComm in matching t-shirts and break the panel’s heart. The biostatistician’s p-value of 0.061 suddenly feels rude to mention.', e:{c:1,r:4,v:1} },
  { id:'EVT-005', t:'Positive Type B Meeting', k:'good', f:'FDA agrees with your pivotal design in writing. You frame the minutes. You will cite them in three years when they pretend it never happened.', e:{d:2,r:2,v:1} },
  { id:'EVT-006', t:'Priority Review Voucher', k:'good', f:'You earned a PRV for your rare pediatric disease drug. Use it, or sell it for ~$100M to a company that wants to rush a wrinkle cream. Capitalism!', e:{c:5,v:2} },
  { id:'EVT-007', t:'Enrollment Ahead of Schedule', k:'good', f:'Sites are enrolling faster than projected, which has never once happened in recorded history. Savor this. It is not real.', e:{c:-1,d:3,r:1,v:1} },
  { id:'EVT-008', t:'Clean CMC Inspection', k:'good', f:'Investigators leave your fill-finish site with zero observations. Your VP of Manufacturing weeps openly in the parking lot. A unicorn.', e:{d:1,r:3,v:1} },
  { id:'EVT-009', t:'Strong Phase 2 Readout', k:'good', f:'Your stock pops 40% on a press release with "statistically significant" and "well-tolerated." Nobody read the secondary endpoints. Don’t tell them.', e:{c:6,d:2,r:1,v:3} },
  { id:'EVT-010', t:'KOL Endorsement at Congress', k:'good', f:'The field’s most cited investigator calls your mechanism "genuinely interesting" from the podium. You hear angels. Your competitor hears their valuation deflating.', e:{c:2,r:3,v:1} },
  { id:'EVT-011', t:'Orphan Drug Designation', k:'good', f:'Seven years of exclusivity and a tax credit, because your disease is rare and your accountant is thrilled. Free money with a clear rationale — the rarest creature in biotech.', e:{c:3,r:1,v:2} },
  { id:'EVT-012', t:'Real-World Evidence Accepted', k:'good', f:'FDA accepts your external control arm built from registry data. The 1990s called and could not believe it. Frame this card.', e:{c:1,d:3,r:1,v:1} },
  // ---- BAD ----
  { id:'EVT-013', t:'Clinical Hold', k:'bad', f:'FDA has "questions" about a safety signal. All dosing stops. You will spend four months proving one elevated liver enzyme was the assay’s fault and not yours.', e:{c:-2,d:-1,r:-2,v:-2}, sp:{type:'skip'} },
  { id:'EVT-014', t:'Form 483 Issued', k:'bad', f:'An inspector found "objectionable conditions" at your site. You have 15 business days to write a response longer than the inspection itself, and to mean it.', e:{c:-2,r:-2,v:-1} },
  { id:'EVT-015', t:'Refuse-to-File Letter', k:'bad', f:'FDA won’t even REVIEW your application. The 74-day letter lands like a slap with a federal seal. Your filing fee is non-refundable. So is your dignity.', e:{c:-3,d:-1,r:-3,v:-3}, sp:{type:'skip'} },
  { id:'EVT-016', t:'Complete Response Letter', k:'bad', f:'Not an approval. Not a denial. A CRL — the regulatory equivalent of "we need to talk." The deficiencies are "CMC and clinical." That is the whole drug.', e:{c:-3,d:-2,r:-2,v:-3}, sp:{type:'skip'} },
  { id:'EVT-017', t:'Pivotal Enrollment Shortfall', k:'bad', f:'Your sites enrolled 11% of target in 60% of the timeline. The CRO has "learnings." You have a burn rate and a board meeting Thursday.', e:{c:-2,d:-2,r:-1,v:-2} },
  { id:'EVT-018', t:'Government Shutdown', k:'bad', f:'FDA’s user-fee work continues but new meetings freeze. Your PDUFA clock is fine; your sanity is not. Congress will fix this in 34 days, plus a fiscal cliff.', e:{c:-1,v:-1}, sp:{type:'skip'} },
  { id:'EVT-019', t:'Site Data Integrity Finding', k:'bad', f:'One investigator may have invented some subjects. You exclude the site, FDA notices you noticed, and your statistical power evaporates like ethanol off a swab.', e:{c:-2,d:-3,r:-2,v:-2} },
  { id:'EVT-020', t:'CMC / Manufacturing Failure', k:'bad', f:'Three consecutive batches fail dissolution spec. Your process is "not yet validated," a kind phrase for "a science experiment with a PDUFA date."', e:{c:-3,d:-1,r:-1,v:-2} },
  { id:'EVT-021', t:'Reviewer Turnover', k:'bad', f:'Your primary reviewer left for industry. The new one hasn’t read the file, disagrees about your endpoint, and emails "just to align" Friday at 5:47pm.', e:{r:-2,v:-1}, sp:{type:'skip'} },
  { id:'EVT-022', t:'Post-Market Safety Signal', k:'bad', f:'A FAERS cluster triggers a Drug Safety Communication. Your label grows a boxed warning the size of a billboard. Sales call it "a positioning challenge."', e:{c:-2,d:-1,r:-3,v:-2} },
  { id:'EVT-023', t:'Investor Down Round', k:'bad', f:'Ms. N. Vested, MBA, leads a financing at half your last valuation "to be supportive." Your option pool is now a rounding error. She still wants a board seat.', e:{c:3,r:-2,v:-3} },
  { id:'EVT-024', t:'Warning Letter Goes Public', k:'bad', f:'Your unanswered 483 escalated to a Warning Letter, and FDA posts it with your name in bold. Short-sellers find it before your CEO finishes coffee.', e:{c:-2,r:-4,v:-3} },
  // ---- SWINGY ----
  { id:'EVT-025', t:'Advisory Committee Meeting', k:'swing', f:'The AdComm convenes. The panel votes on your benefit-risk, live, in public, while you sit in the front row not allowed to talk.', e:{c:-1}, sp:{type:'coin', heads:{r:4,v:3}, tails:{r:-3,v:-3}} },
  { id:'EVT-026', t:'Type A Meeting Requested', k:'swing', f:'FDA would "like to schedule a Type A meeting." Either to resolve a dispute in your favor or to explain, gently, why your program is on fire. Roll to find out.', sp:{type:'dice', check:{d:2,v:2}, x:{v:-2,skip:true}, bang:{r:-1}, at:{c:-1,d:1}} },
  { id:'EVT-027', t:'Surprise Competitor Filing', k:'swing', f:'A rival you forgot existed just filed in your indication. If they read out first, you are second-to-market with a press release nobody reprints. Unless you sprint.', e:{r:-1}, sp:{type:'race', ahead:{v:2}, behind:{v:-3}} },
  { id:'EVT-028', t:'KOL Feud', k:'swing', f:'Two giants of the field publicly disagree about your mechanism in dueling editorials. Drama is engagement. Whoever your data supports just got very, very loud.', sp:{type:'coin', heads:{r:3}, tails:{r:-2,v:-1}} },
  { id:'EVT-029', t:'Accelerated Approval Offered', k:'swing', f:'FDA offers approval on a surrogate endpoint, with a confirmatory trial due later. Take the shortcut and owe the future a Phase 4, or hold out for the hard outcome.', sp:{type:'choose', a:{label:'Take accelerated approval', v:4, r:-1}, b:{label:'Wait for full approval', v:1, d:-1, skip:true}} },
  { id:'EVT-030', t:'Get Acquired?', k:'swing', f:'A strategic offers to buy you at a premium to your current value. Cash out and end the game a winner, or decline and gamble that the top of the track is real. (Board canon.)', sp:{type:'choose', a:{label:'SELL! 💰', cashOut:true}, b:{label:'No thanks!', v:1}} },
  { id:'EVT-031', t:'Fire the CEO?', k:'swing', f:'The board has thoughts about leadership "after the CRL." Bring in a turnaround CEO (cash, fresh credibility) or keep the founder (vision, baggage).', sp:{type:'choose', a:{label:'Bring in new CEO', c:3, r:2, v:-1}, b:{label:'Keep the founder', r:-1, v:2}} },
  { id:'EVT-032', t:'Hire a CRO?', k:'swing', f:'Outsource the trial to professionals who run 40 studies at once and will remember your name 60% of the time. Faster enrollment, faster burn. (Board canon.)', sp:{type:'choose', a:{label:'Hire the CRO', c:-3, d:3}, b:{label:'Run it in-house', d:1, r:1}} },
  { id:'EVT-033', t:'Expansion Cohort Surprise', k:'swing', f:'Your dose-escalation cohort shows an unexpected signal in a tumor type you weren’t studying. A new indication or a multiplicity problem. The statistician is sweating.', sp:{type:'dice', check:{d:2,v:3}, x:{d:-1}, bang:{v:1,r:-1}, at:{d:1}} },
  { id:'EVT-034', t:'FDA Wants a New Endpoint', k:'swing', f:'Mid-program, the Division "encourages" a clinically meaningful endpoint over your surrogate. Comply and re-power the trial, or push back with a Type C meeting and your nerve.', sp:{type:'choose', a:{label:'Adopt the endpoint', c:-2, d:2, r:2}, b:{label:'Defend your surrogate', r:-1}} },
  { id:'EVT-035', t:'Pre-Sub (Q-Sub) Feedback', k:'swing', f:'Device track: your Q-Sub meeting with CDRH either confirms your predicate is fine, or reveals you’ve been comparing yourself to a device recalled in 2019. Roll for it.', sp:{type:'dice', check:{d:2,v:2}, x:{d:-2,v:-1,skip:true}, bang:{r:-1}, at:{c:-1,d:1}} },
  { id:'EVT-036', t:'The Boot-Strap Gambit', k:'swing', f:'Out of runway, you boot-strap the next milestone on grant funding and sheer will. (Board canon: "Boot-strap it!") Heroic if it works, a Chapter 7 filing if it doesn’t.', e:{c:-1}, sp:{type:'coin', heads:{c:4,r:2}, tails:{c:-2,v:-2}} },
];

// Funny leaderboard rank titles — regulatory AND founder/startup jabs, by outcome+score.
function rankTitle(outcome, score) {
  if (outcome === 'approved') {
    if (score >= 2600) return '🦄 Regulatory Unicorn';
    if (score >= 2000) return '🏆 Regulatory Legend';
    if (score >= 1400) return '🚀 On Track to Exit';
    return '✅ Approvable Human';
  }
  if (outcome === 'acquired') {
    if (score >= 1200) return '💰 Exited Before Series B';
    return '🤝 Took the Money (Smart)';
  }
  if (outcome === 'bankrupt') return '💸 Never Raised Series B';
  if (outcome === 'beaten_to_market') return '🥈 Scooped at the Buzzer';
  if (outcome === 'clinical_hold') return '🛑 Permanent Hold Club';
  return '🔬 Still Enrolling (p=0.06 Forever)';  // failed_endpoint / time
}

const WIN_COPY = { title: 'APPROVED.', sub: 'Your application met the standard for substantial evidence of effectiveness. Somewhere, Dr. Vance allows herself a single, measured nod. You drove a molecule from $100k to the top of the track without going broke, blowing the endpoint, or getting scooped. That is not luck. That is regulatory strategy.' };
const ACQUIRED_COPY = { title: 'ACQUIRED.', sub: 'You took the buyout at the top of your valuation and handed the post-marketing commitments to someone with a bigger legal department. A partial win, and the smartest people in biotech would shake your hand. The molecule lives. So does your cap table.' };
const LOSE_COPY = {
  bankrupt:        { title: 'YOU ARE OUT OF MONEY.', sub: 'The science was sound — it almost always is. But the trial runs on capital, not hypotheses, and yours hit zero. The molecule goes back in the freezer. The mice are unmoved. Every great drug that never existed died exactly here. Excellent company.' },
  failed_endpoint: { title: 'THE PIVOTAL TRIAL MISSED.', sub: 'The primary endpoint did not reach significance. There is a promising subgroup — there is always a subgroup — but Dr. Vance has explained, in writing, why post hoc is not substantial evidence. The drug may even work. The data declined to prove it.' },
  beaten_to_market:{ title: 'YOU CAME IN SECOND.', sub: 'A competitor you half-forgot read out first, filed first, and got their letter while yours was still in the queue. Second-to-market is a real place, mostly populated by excellent drugs and modest revenue. Their CEO is doing a victory lap. You are doing a budget review.' },
  clinical_hold:   { title: 'CLINICAL HOLD — PERMANENT.', sub: 'The safety questions never got good answers, and your goodwill ran out before your luck did. The hold became the ending. First, do no harm; also, do no approval.' },
};

const VALUE_BANDS = [
  [0,'$100k'],[8,'$1M'],[16,'$5M'],[26,'$25M'],[38,'$90M'],[50,'$300M'],
  [64,'$900M'],[78,'$2.5B'],[90,'$5B'],[97,'$9B'],
];
function valueLabel(v) { let lab='$100k'; for (const [t,l] of VALUE_BANDS) if (v>=t) lab=l; return lab; }

// scaling of raw card/action deltas → engine units
const SCALE = { capital: 7, data: 6, reputation: 6, value: 5 };

// ============================================================================
// STATE
// ============================================================================
let player = null;       // {first,last,email}
let chosenChar = null;   // CHARACTERS entry
let S = null;            // game state
const $ = (id) => document.getElementById(id);

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  $(id).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================================================================
// INIT / NAV
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  $('btn-begin').addEventListener('click', () => showScreen('screen-register'));
  $('btn-register').addEventListener('click', register);
  $('reg-email').addEventListener('keydown', e => { if (e.key === 'Enter') register(); });
  $('nav-leaderboard').addEventListener('click', showLeaderboardStandalone);
  $('event-ok').addEventListener('click', closeEvent);
  $('btn-submit-review').addEventListener('click', submitReview);
  $('btn-review-continue').addEventListener('click', afterReview);
  $('btn-play-again').addEventListener('click', () => { $('overlay-end').classList.remove('active'); showScreen('screen-characters'); renderCharacters(); });
});

// ============================================================================
// REGISTER → CHARACTER SELECT → SEED → PLAY
// ============================================================================
function register() {
  const first = $('reg-first').value.trim();
  const last = $('reg-last').value.trim();
  const email = $('reg-email').value.trim();
  const err = $('reg-err');
  if (!first) { err.textContent = 'A first name, at least. Even a fake one.'; return; }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) { err.textContent = "That email doesn't look real. It doesn't have to be — just shaped like one."; return; }
  err.textContent = '';
  player = { first, last, email };
  showScreen('screen-characters');
  renderCharacters();
}

function renderCharacters() {
  // The real 2018 character cards (name, role, art, token disc are all baked
  // into the image); the blurb adds the gameplay bonus the cards don't show.
  $('characters-grid').innerHTML = CHARACTERS.map(c => `
    <button class="founder-card sticker-tilt" data-char="${c.id}">
      <img class="founder-card__art" src="/static/img/founders/${c.id}.png" alt="${escapeHtml(c.name)} — ${escapeHtml(c.role)}" loading="lazy">
      <span class="founder-card__blurb">${escapeHtml(c.blurb)}</span>
    </button>`).join('');
  $('characters-grid').querySelectorAll('.founder-card').forEach(b =>
    b.addEventListener('click', () => { chosenChar = CHARACTERS.find(c => c.id === b.dataset.char); startGame(); }));
}

async function startGame() {
  showScreen('screen-play');
  $('scenario-card').innerHTML = '<em>Dealing you a real product from the registry…</em>';
  let seed;
  try {
    const resp = await fetch('/api/game/seed');
    if (!resp.ok) throw new Error('seed ' + resp.status);
    seed = await resp.json();
  } catch (e) {
    $('scenario-card').innerHTML = '<em>Could not reach the registry. Is the server up? (' + e + ')</em>';
    return;
  }
  buildState(seed);
  renderAll();
}

function buildState(seed) {
  const pathway = PATHWAYS[seed.pathway] ? seed.pathway : 'drug';
  const d = seed.difficulty || 3;
  const ch = chosenChar;
  S = {
    seed, pathway, char: ch,
    stages: PATHWAYS[pathway].stages,
    pos: 0, readiness: 0, turn: 1,
    // Generous runway: the original board's real pressure is cash + competition,
    // not a hard clock. The clock exists so dithering has a cost, not to guillotine.
    maxTurns: 18 - d + (ch.extraTurns || 0),
    res: {
      capital: 100 + (ch.start.capital || 0),
      data: 0 + (ch.start.data || 0),
      reputation: 60 + (ch.start.reputation || 0),
      value: 4,
    },
    competitor: 0,
    // Tuned so a competent run reaches submission with room to spare; the rival
    // is a clock, not a guillotine. Engaging the FDA early buys you breathing room.
    competitorRise: Math.ceil(55 / (16 - d + 3)) * (ch.competitorMult || 1),
    integrity: 0,
    difficulty: d, status: 'playing', outcome: null, log: [], reviewModifier: 0,
    raiseUsedNoHit: false,
  };
  pushLog(`${ch.name} (${ch.role}) opens a ${PATHWAYS[pathway].label}. Difficulty ${d}/5. ${S.maxTurns} turns of runway.`, 'turn');
}

// ============================================================================
// RENDER
// ============================================================================
function renderAll() { renderScenario(); renderHUD(); renderTension(); renderBoard(); renderReadiness(); renderActions(); renderLog(); }

function renderScenario() {
  const s = S.seed;
  $('scenario-card').innerHTML = `
    <span class="tag path">${S.pathway.toUpperCase()} · ${S.pathway === 'device' ? '510(k)/PMA' : 'NDA/BLA'}</span>
    ${s.therapeutic_area ? `<span class="tag">${escapeHtml(s.therapeutic_area)}</span>` : ''}
    ${s.product_category ? `<span class="tag alt">${escapeHtml(s.product_category)}</span>` : ''}
    ${s.device_class ? `<span class="tag">Class ${escapeHtml(s.device_class)}</span>` : ''}
    ${s.phase && s.phase !== 'NA' ? `<span class="tag">${escapeHtml(s.phase)}</span>` : ''}
    <h2>${escapeHtml(s.title)}</h2>
    <div class="meta">Playing as <strong>${escapeHtml(S.char.name)}</strong> · product: <strong>${escapeHtml(s.intervention_name || s.intervention_type || 'an investigational product')}</strong>
      ${s.sponsor ? ` · orig. sponsor ${escapeHtml(s.sponsor)}` : ''}
      · <a class="nct" href="https://clinicaltrials.gov/study/${encodeURIComponent(s.nct_id)}" target="_blank" rel="noopener">${escapeHtml(s.nct_id)}</a></div>`;
}

function renderHUD() {
  const r = S.res;
  const tile = (cls, ico, lab, val, pct) => `<div class="res ${cls}" id="res-${cls}"><div class="ico">${ico}</div><div class="lab">${lab}</div><div class="val">${val}</div><div class="bar"><i style="width:${Math.max(0,Math.min(100,pct))}%"></i></div></div>`;
  $('hud').innerHTML =
    tile('value', '💰', 'Product value', valueLabel(r.value), r.value) +
    tile('capital', '💵', 'Capital', '$' + Math.round(r.capital) + 'M', r.capital) +
    tile('evidence', '📊', 'Data', Math.round(r.data), r.data) +
    tile('reputation', '🤝', 'Goodwill', Math.round(r.reputation), r.reputation) +
    tile('time', '⏳', 'Turns left', (S.maxTurns - S.turn + 1), (S.maxTurns - S.turn + 1) / S.maxTurns * 100);
}
function renderTension() { const p=Math.max(0,Math.min(100,S.competitor)); $('tension-bar').style.width=p+'%'; $('tension-pct').textContent=Math.round(p)+'%'; }

function renderBoard() {
  $('board').innerHTML = S.stages.map((st, i) => {
    let cls='node'; if(i<S.pos)cls+=' done'; if(i===S.pos)cls+=' current';
    const token = i===S.pos ? '<span class="token">🐈</span>' : '';
    return `<div class="${cls}" title="${escapeHtml(st.blurb||'')}">${token}<div class="n-num">${i<S.pos?'✓':i+1}</div><div class="n-name">${st.name}</div></div>`;
  }).join('');
}

function renderReadiness() {
  const st=S.stages[S.pos], need=st.need||0;
  $('readiness-label').textContent = st.submission ? 'Submission package' : `Readiness — ${st.name}`;
  $('readiness-now').textContent = Math.round(S.readiness);
  $('readiness-need').textContent = need;
  $('readiness-bar').style.width = (need ? Math.min(100, S.readiness/need*100) : 100) + '%';
}

function renderActions() {
  const st=S.stages[S.pos], canAdvance = S.readiness >= (st.need||0);
  const fmt=(k,v)=>{const sign=v>0?'up':'down';const label={capital:'$',data:'Data',reputation:'Goodwill',value:'Value',competitor:'Rival'}[k]||k;const raw=v*(SCALE[k]||1);const num=k==='capital'?`${v>0?'+':''}${Math.round(raw)}M`:`${v>0?'+':''}${Math.round(raw)}`;return `<span class="${sign}">${label} ${num}</span>`;};
  let html = ACTIONS.map(a=>{
    const costs=Object.entries(a.delta).map(([k,v])=>fmt(k,v));
    if(a.ready)costs.push(`<span class="up">Readiness +${a.ready}</span>`);
    if(a.integrity)costs.push(`<span class="down">⚑ integrity</span>`);
    return `<button class="action" data-act="${a.id}"><span class="a-name">${a.name}</span><span class="a-desc">${a.desc}</span><span class="a-cost">${costs.join(' · ')}</span></button>`;
  }).join('');
  const advLabel = st.submission ? 'FILE WITH FDA →' : `Advance to ${S.stages[S.pos+1]?S.stages[S.pos+1].name:'approval'} →`;
  html += `<button class="action advance" data-act="__advance" ${canAdvance?'':'disabled'}><span class="a-name">${advLabel}</span><span class="a-desc">${canAdvance?(st.submission?'Lock the package and face Dr. Vance.':'Bank value + evidence and move up the track.'):'Build more readiness first.'}</span></button>`;
  $('actions').innerHTML = html;
  $('actions').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>onAction(b.dataset.act)));
}

function renderLog(){ $('log-entries').innerHTML = S.log.slice().reverse().map(e=>`<div class="entry ${e.cls||''}">${e.text}</div>`).join(''); }
function pushLog(text,cls){ S.log.push({text,cls}); }

// ============================================================================
// TURN LOGIC
// ============================================================================
function onAction(actId) {
  if (S.status !== 'playing') return;
  if (actId === '__advance') return advance();
  const act = ACTIONS.find(a => a.id === actId);
  if (!act) return;

  let delta = Object.assign({}, act.delta);
  // Character passives
  if (act.tag === 'study' && S.char.studyCostMult) delta.capital = Math.round(delta.capital / SCALE.capital * S.char.studyCostMult * SCALE.capital) / SCALE.capital;
  if (act.id === 'clean' && S.char.cleanBonus) delta.data = (delta.data || 0) + S.char.cleanBonus / SCALE.data;
  if (act.isRaise) {
    if (S.char.raiseBonus) delta.capital *= S.char.raiseBonus;
    if (S.char.raiseNoRepHit && !S.raiseUsedNoHit) { delta.reputation = 0; S.raiseUsedNoHit = true; }
  }
  applyDelta(delta);
  if (act.ready) S.readiness += act.ready;
  if (act.integrity) { S.integrity += act.integrity; pushLog(`Turn ${S.turn}: ${act.name}. (integrity flag +1 — Dr. Vance keeps a ledger)`, 'bad'); }
  else pushLog(`Turn ${S.turn}: ${act.name}.`, 'turn');

  S.turn += 1;
  S.competitor += S.competitorRise + (act.integrity ? 3 : 0);
  drawEvent(act.integrity ? 0.6 : 0.45);
  clamp();
  if (!checkEnd()) renderAll();
}

function applyDelta(delta) {
  for (const [k, v] of Object.entries(delta || {})) {
    if (!v) continue;
    if (k === 'competitor') S.competitor += v * (SCALE.value); // raw rival units
    else if (k in S.res) S.res[k] += v * (SCALE[k] || 1);
  }
}

function advance() {
  const st = S.stages[S.pos];
  if (S.readiness < (st.need || 0)) return;
  if (st.submission) return openReview();
  const valBump = Math.round(100 / S.stages.length);
  const evBonus = Math.round(4 + S.res.reputation / 14);
  S.res.value += valBump; S.res.data += evBonus; S.readiness = 0; S.pos += 1;
  pushLog(`Cleared ${st.name}. Product value up to ${valueLabel(S.res.value)}; data +${evBonus}.`, 'good');
  clamp(); flashRes('value');
  if (!checkEnd()) renderAll();
}

// ============================================================================
// EVENTS (REG deck)
// ============================================================================
function rawToDelta(raw){ const m={c:'capital',d:'data',r:'reputation',v:'value'}; const out={}; for(const[k,val]of Object.entries(raw||{})){ if(m[k])out[m[k]]=val; } return out; }

function drawEvent(prob) {
  if (Math.random() > prob) return;
  const card = RAW_DECK[Math.floor(Math.random() * RAW_DECK.length)];
  // base effect
  let applied = rawToDelta(card.e);
  let extraNote = '';
  let skip = false;
  const sp = card.sp;
  if (sp) {
    if (sp.type === 'skip') { skip = true; }
    else if (sp.type === 'coin') { const heads = Math.random() < 0.5; const branch = heads ? sp.heads : sp.tails; Object.assign(applied, mergeRaw(applied, rawToDelta(branch))); extraNote = heads ? ' (the coin landed your way)' : ' (the coin did not)'; }
    else if (sp.type === 'dice') { const faces=['check','x','bang','at']; const face=faces[Math.floor(Math.random()*4)]; const br=sp[face]||{}; Object.assign(applied, mergeRaw(applied, rawToDelta(br))); if(br.skip)skip=true; extraNote = ` (rolled ${({check:'✓',x:'✗',bang:'!',at:'@'})[face]})`; }
    else if (sp.type === 'race') { const ahead = S.res.data >= 45; const br = ahead ? sp.ahead : sp.behind; Object.assign(applied, mergeRaw(applied, rawToDelta(br))); extraNote = ahead ? ' (you were ahead on data)' : ' (you were behind on data)'; }
    else if (sp.type === 'choose') { return showChoice(card); }  // choice modal handles application
  }
  applyDelta(applied);
  if (skip) { S.turn += 1; S.competitor += S.competitorRise; }
  showEvent(card, applied, extraNote, skip);
  pushLog(`Event: ${card.t}.${extraNote} ${effectSummary(applied, skip)}`, card.k === 'good' ? 'good' : card.k === 'bad' ? 'bad' : '');
}

function mergeRaw(a, b){ const out=Object.assign({},a); for(const[k,v]of Object.entries(b)) out[k]=(out[k]||0)+v; return out; }

function effectSummary(applied, skip) {
  const names={capital:'$',data:'Data',reputation:'Goodwill',value:'Value'};
  const parts=[]; for(const[k,v]of Object.entries(applied)){ if(!v)continue; const raw=Math.round(v); parts.push(`${names[k]||k} ${v>0?'+':''}${raw}${k==='capital'?'M':''}`); }
  if(skip)parts.push('lose a turn');
  return parts.length?'('+parts.join(', ')+')':'(no net effect)';
}

function showEvent(card, applied, note, skip) {
  const box=$('event-card'); box.className='card-modal '+card.k;
  $('event-kind').textContent = card.k==='good'?'✦ Good news':card.k==='bad'?'⚠ Bad news':'⚖ It could go either way';
  $('event-title').textContent = card.t;
  $('event-flavor').textContent = card.f + (note||'');
  $('event-effect').innerHTML = effectSummary(applied, skip).replace(/^\(|\)$/g,'').split(', ').map(p=>`<span class="${/[-]/.test(p)||/lose/.test(p)?'down':'up'}">${p}</span>`).join(' &nbsp; ');
  $('overlay-event').classList.add('active');
  if (card.k==='bad') document.body.classList.add('shake');
}
function closeEvent(){ $('overlay-event').classList.remove('active'); document.body.classList.remove('shake'); clamp(); if(!checkEnd())renderAll(); }

// ---- Choice (mustChoose) cards: buyout, CRO, fire CEO, endpoint, accelerated ----
let _choiceCard = null;
function showChoice(card) {
  _choiceCard = card;
  $('choice-title').textContent = card.t;
  $('choice-flavor').textContent = card.f;
  const optBtn = (key, o) => `<button class="btn-primary choice-opt" data-opt="${key}">${escapeHtml(o.label)}</button>`;
  $('choice-options').innerHTML = optBtn('a', card.sp.a) + optBtn('b', card.sp.b);
  $('choice-options').querySelectorAll('button').forEach(b => b.addEventListener('click', () => resolveChoice(b.dataset.opt)));
  $('overlay-choice').classList.add('active');
}
function resolveChoice(key) {
  const card=_choiceCard, opt=card.sp[key];
  $('overlay-choice').classList.remove('active');
  if (opt.cashOut) { S.status='won'; S.outcome='acquired'; pushLog(`Accepted the buyout at ${valueLabel(S.res.value)}. Exit before approval — a partial win.`, 'good'); return endGame(); }
  const applied = rawToDelta(opt);
  applyDelta(applied);
  let skip=false; if(opt.skip){skip=true; S.turn+=1; S.competitor+=S.competitorRise;}
  pushLog(`${card.t}: chose "${opt.label}". ${effectSummary(applied, skip)}`, '');
  clamp();
  if(!checkEnd())renderAll();
}

// ============================================================================
// FDA REVIEW (Dr. Eleanor Vance)
// ============================================================================
function openReview() {
  $('review-input-stage').style.display=''; $('review-result-stage').style.display='none';
  $('review-text').value='';
  $('review-reviewer').textContent='Dr. Eleanor Vance · Division of Regulatory Reckoning';
  $('overlay-review').classList.add('active'); $('review-text').focus();
}
async function submitReview() {
  const rationale = $('review-text').value.trim() || 'We respectfully submit our application for review.';
  $('btn-submit-review').disabled=true; $('btn-submit-review').textContent='Dr. Vance is reading…';
  let result;
  try {
    const resp = await fetch('/api/game/review', { method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ pathway:S.pathway, therapeutic_area:S.seed.therapeutic_area, phase:S.seed.phase,
        submission_rationale:rationale, evidence_score:clampN(S.res.data), reputation_score:clampN(S.res.reputation),
        integrity_flags:S.integrity, product_name:S.seed.intervention_name }) });
    result = await resp.json();
  } catch (e) { result = localReview(); }
  $('btn-submit-review').disabled=false; $('btn-submit-review').textContent='Submit to FDA →';
  showReviewResult(result);
}
function clampN(v){ return Math.max(0, Math.min(100, Math.round(v))); }
function localReview() {
  const e=S.res.data; const v = e>=72?'APPROVED':e>=52?'APPROVABLE_WITH_DEFICIENCIES':e>=34?'COMPLETE_RESPONSE_LETTER':'REFUSE_TO_FILE';
  const mod={APPROVED:18,APPROVABLE_WITH_DEFICIENCIES:6,COMPLETE_RESPONSE_LETTER:-12,REFUSE_TO_FILE:-22}[v];
  return { verdict:v, reviewer_name:'Dr. Eleanor Vance (offline)', letter:'The Division has reviewed your submission.', score_modifier:mod, source:'scripted' };
}
let _pendingVerdict=null;
function showReviewResult(result) {
  _pendingVerdict=result;
  $('review-input-stage').style.display='none'; $('review-result-stage').style.display='';
  const badge=$('review-badge'); badge.className='review-badge '+(result.source==='llm'?'llm':'scripted');
  badge.textContent = result.source==='llm'?'AI reviewer':'Reviewer';
  $('review-letter').textContent=result.letter;
  $('review-reviewer').textContent=result.reviewer_name||'Division of Regulatory Reckoning';
  $('review-verdict').textContent = 'VERDICT: ' + result.verdict.replace(/_/g,' ');
}
function afterReview() {
  const v=_pendingVerdict; $('overlay-review').classList.remove('active');
  S.reviewModifier = v.score_modifier || 0;
  if (v.verdict === 'APPROVED') {
    S.pos += 1; S.res.value = Math.max(S.res.value, 96); S.status='won'; S.outcome='approved';
    pushLog(`FDA: APPROVED. ${S.reviewModifier>=0?'+':''}${S.reviewModifier} to score.`, 'good'); return endGame();
  }
  // Any non-approval: pay the fix cost, refile. Cash/time-poor players lose here.
  const harsh = v.verdict === 'REFUSE_TO_FILE' || v.verdict === 'COMPLETE_RESPONSE_LETTER';
  applyDelta({ capital: harsh ? -3 : -2, reputation: harsh ? -1 : 0 });
  // Lawyer (D. Lay) softens the fix
  S.readiness = Math.max(0, (S.stages[S.pos].need||0) - (S.char.badNewsShield ? 12 : 8));
  S.turn += (S.char.badNewsShield ? 1 : 2);
  S.competitor += S.competitorRise;
  pushLog(`FDA: ${v.verdict.replace(/_/g,' ')}. Address the deficiencies and refile.`, 'bad');
  clamp();
  if (!checkEnd()) renderAll();
}

// ============================================================================
// WIN / LOSE / SCORE
// ============================================================================
function clamp() {
  S.res.reputation=Math.max(0,Math.min(100,S.res.reputation));
  S.res.data=Math.max(0,Math.min(100,S.res.data));
  S.res.value=Math.max(0,Math.min(100,S.res.value));
  S.competitor=Math.max(0,S.competitor);
}
function checkEnd() {
  if (S.status !== 'playing') return true;
  if (S.res.capital < 0) return lose('bankrupt');
  if (S.competitor >= 100) return lose('beaten_to_market');
  if (S.res.reputation <= 0 && S.stages[S.pos].submission) return lose('clinical_hold');
  if ((S.maxTurns - S.turn + 1) <= 0) return lose('failed_endpoint');
  return false;
}
function lose(outcome){ S.status='lost'; S.outcome=outcome; endGame(); return true; }

function computeScore() {
  if (S.outcome === 'approved') {
    const t=Math.max(0,S.maxTurns-S.turn+1);
    return Math.max(0, Math.round(1000 + t*40 + S.res.capital*2 + S.res.data*4 + S.res.value*7 + S.res.reputation*2 + S.reviewModifier*10 + S.difficulty*120 - S.integrity*30 - S.competitor));
  }
  if (S.outcome === 'acquired') {
    return Math.max(0, Math.round(400 + S.res.value*9 + S.res.capital*2 + S.res.data*2 + S.difficulty*80 - S.integrity*20));
  }
  return Math.max(0, Math.round(S.pos*60 + S.res.value*3 + S.res.data*1 + Math.max(0,S.res.capital)));
}

async function endGame() {
  const won = S.outcome==='approved', acquired = S.outcome==='acquired';
  const score = computeScore();
  const box=$('end-box'); box.className='end-modal '+(won||acquired?'won':'lost');
  const copy = won?WIN_COPY:acquired?ACQUIRED_COPY:(LOSE_COPY[S.outcome]||{title:'GAME OVER',sub:''});
  $('end-title').textContent=copy.title; $('end-sub').textContent=copy.sub;
  $('end-score').style.display=''; $('end-score').textContent=score.toLocaleString();
  $('end-title2').textContent = rankTitle(S.outcome, score);
  $('end-rank').textContent='Submitting your run…';
  $('overlay-end').classList.add('active');

  let rankInfo=null;
  try {
    const resp=await fetch('/api/game/score',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({first_name:player.first,last_name:player.last,email:player.email,score,turns_taken:S.turn,
        outcome:S.outcome==='acquired'?'approved':S.outcome,  // 'acquired' maps to a win-class row for the board
        trial_nct_id:S.seed.nct_id,trial_title:S.seed.title,pathway:S.pathway,difficulty:String(S.difficulty)})});
    if(resp.ok)rankInfo=await resp.json();
  } catch(e){}
  $('end-rank').textContent = rankInfo
    ? `Rank #${rankInfo.your_rank} of ${rankInfo.total_players} sponsors${rankInfo.is_personal_best?' · personal best! 🎉':''}`
    : '(could not reach the leaderboard)';
  loadLeaderboard($('end-leaderboard'));
}

// ============================================================================
// LEADERBOARD
// ============================================================================
async function loadLeaderboard(tableEl) {
  try {
    const resp=await fetch('/api/game/leaderboard?limit=12'); const data=await resp.json();
    if(!data.entries.length){ tableEl.innerHTML='<tr><td>No runs yet. Be the first sponsor on the board.</td></tr>'; return; }
    const medal=(r)=>r===1?'🥇':r===2?'🥈':r===3?'🥉':r;
    tableEl.innerHTML='<tr><th>#</th><th>Sponsor</th><th>Title</th><th>Score</th><th>Result</th></tr>' +
      data.entries.map(e=>`<tr class="${player && e.display_name.startsWith(player.first)?'you':''}">
        <td class="rank">${medal(e.rank)}</td>
        <td>${escapeHtml(e.display_name)}</td>
        <td class="rtitle">${escapeHtml(rankTitle(e.outcome, e.score))}</td>
        <td><strong>${e.score.toLocaleString()}</strong></td>
        <td>${e.outcome==='approved'?'✅':'❌'} ${e.pathway||''}</td>
      </tr>`).join('');
  } catch(e){ tableEl.innerHTML='<tr><td>Leaderboard unavailable.</td></tr>'; }
}
function showLeaderboardStandalone() {
  const box=$('end-box'); box.className='end-modal';
  $('end-title').textContent='🏆 Hall of Sponsors'; $('end-title2').textContent='';
  $('end-sub').textContent='The fastest to FDA approval, the smartest exits, and the bravest failures.';
  $('end-score').style.display='none'; $('end-rank').textContent='';
  $('overlay-end').classList.add('active'); loadLeaderboard($('end-leaderboard'));
  $('btn-play-again').textContent = player ? 'Play again' : 'Play';
}

// ============================================================================
// UTIL
// ============================================================================
function flashRes(cls){ const el=$('res-'+cls); if(!el)return; el.classList.add('flash'); setTimeout(()=>el.classList.remove('flash'),500); }
function escapeHtml(s){ return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
