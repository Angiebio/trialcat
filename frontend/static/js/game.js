/**
 * The Strategy Game (for Regulatory Affairs) — "Race to Approval"  v3.0 BOARD MODE (22JUN2026)
 *
 * The web rebirth of Angie's 2018 board game (TRCL 501(c)(3), with support from
 * Biotech Mentor LLC), reborn as a Game-of-Life-style climb. You no longer click
 * abstract actions — you DRAW a card (your agency), SPIN a wheel (fate), and your
 * cat physically CLIMBS the snake from $100k to a $9B exit, burning runway-capital
 * every square, while a rival dog races the same track and Dr. Vance waits at the top.
 *
 * Design lineage (reconciled from the 22JUN design workflow, roadmaps/_design/):
 *   - 39-square board + spatialized triggers + decks + jokes ... squares.json
 *   - balance model + 7 adversarial fixes (idle burn, land-only funding,
 *     gates-halt-climb, submission-always-stops, dog-as-clock, scoring) ... mechanics-spec.json
 *   - sticker-comic SVG board + tokens + spinner ............... board-spec.json
 *   - spinner / card-flip / WebAudio / avatar-tween code ....... ux-patterns.md
 *
 * Practical: deterministic-ish client engine; the server only seeds a real trial,
 * judges the FDA submission, and keeps the leaderboard.
 * Philosophical: the molecule rises on capital, not hypotheses. The board never
 * lies about that. Neither do we. Data > narrative. That's the game, and the industry.
 */

// ============================================================================
// CHARACTERS — the six personas from the 2018 board. Each bends the climb.
// (start deltas are RAW engine units; capital is raw $M, data/reputation scaled.)
// ============================================================================
const CHARACTERS = [
  { id:'doctor',     name:'Dr. Curzitall',      role:'The Doctor',       emoji:'🩺', blurb:'Cures it all. Starts with real clinical credibility — and data to match. Every study burns a little less.', start:{ data:12 }, studyCostMult:0.9 },
  { id:'lawyer',     name:'D. Lay, JD',         role:'The Lawyer',       emoji:'⚖️', blurb:'Delay, JD. Bad regulatory news lands softer when you read the CFR for fun. Refiling stings less.', start:{ reputation:8 }, badNewsShield:0.5 },
  { id:'gradstudent',name:'Brian',              role:'The Grad Student', emoji:'🎓', blurb:'Broke, brilliant, doing payroll at 2am. Two extra turns of runway, twelve fewer million in the bank.', start:{ capital:-12 }, extraTurns:2 },
  { id:'scientist',  name:'O. Vrsink, PhD',     role:'The Scientist',    emoji:'🔬', blurb:'Kitchen-sink rigor. Every R&D draw pays back harder in data.', start:{ data:14 }, cleanBonus:5 },
  { id:'professor',  name:'Prof. Goetta Grant', role:'The Professor',    emoji:'📚', blurb:'Gotta get a grant. Non-dilutive money flows; your raises hit 1.6× and the first one costs no goodwill.', start:{ capital:8 }, raiseBonus:1.6, raiseNoRepHit:true },
  { id:'investor',   name:'Ms. N. Vested, MBA', role:'The Investor',     emoji:'💼', blurb:'Invested, MBA. Deep pockets up front. The competition smells blood and moves faster — but botches its first sprint.', start:{ capital:30 }, competitorMult:1.10, investorScoopSave:true },
];

// Condensed regulatory pathways (label + the 6 milestone stage names/needs swap by pathway).
const PATHWAYS = {
  drug:   { label:'Drug — NDA/BLA pathway' },
  device: { label:'Device — 510(k)/PMA pathway' },
};

// VALUE_BANDS: board position → product-value label. The HUD headline number.
const VALUE_BANDS = [
  [0,'$100k'],[8,'$1M'],[16,'$5M'],[26,'$25M'],[38,'$90M'],[50,'$300M'],
  [64,'$900M'],[78,'$2.5B'],[90,'$5B'],[97,'$9B'],
];
function valueLabel(v){ let lab='$100k'; for(const [t,l] of VALUE_BANDS) if(v>=t) lab=l; return lab; }

// ============================================================================
// BALANCE CONSTANTS (mechanics-spec.json v3.0, validated by Monte-Carlo; the
// numbers are re-checked against the live 39-square loop in Phase 3).
// CAPITAL is raw $M — no scale (legibility). data/reputation keep SCALE 6.
// ============================================================================
const START_CAPITAL   = 118;   // $M; char.start.capital stacks on top (P3-tuned 112->118: survive the heavier idle burn)
const CAPITAL_BAR_MAX  = 160;   // HUD bar display ceiling
const IDLE_BURN        = 7;     // $M burned every turn before the climb — stalling is never free (P3-tuned 4->7: never-fund must starve)
const START_GOODWILL   = 60;
const BASE_MAX_TURNS   = 28;    // runway (P3-tuned 22->28: room for ONE refile; the dog, not the clock, is the top-end threat)
const FIRST_TO_FILE    = 37;    // dog reaches this snake-node before you file => scooped (FIX-5)
const BANKRUPT_FLOOR   = 8;     // land on the "out of money" square under this => forced bust
const SCALE = { data:6, reputation:6 }; // capital & value are RAW

function burn(idx){ return Math.round((2.8 + 0.05*idx) * 10) / 10; }  // climbing cost gradient (FIX gradient)
function dogStep(){ return (1.0 + 0.18*S.difficulty) * (S.char.competitorMult || 1); }  // P3-tuned base 1.1->1.0: d1/d2 ~0% scoop, slope keeps scoop scaling to ~21% @ d5

// Milestone readiness needs + labels, by pathway+slot (slot 5 = Dr. Vance, need 0).
const MILESTONE_NEED  = { drug:[12,16,22,28,20,0], device:[10,14,16,24,18,0] };
const MILESTONE_LABEL = {
  drug:  ['Pre-IND','Phase 1','Phase 2','Phase 3','NDA/BLA','Dr. Vance'],
  device:['Concept','Pre-Sub','Bench','Pivotal','Submission','Dr. Vance'],
};
// The device player's one defining regulatory decision (fires at slot-3 gate, device only).
const DEVICE_FORK = {
  t:'Pivotal — 510(k) vs PMA?', k:'swing',
  f:'The fork. 510(k) is fast and crowded; PMA is slow, lonely, and wants real clinical evidence. De Novo is for the brave.',
  sp:{ type:'choose', a:{label:'510(k) — fast, crowded', c:2, d:-1, v:1}, b:{label:'PMA — slow, real evidence', c:-3, d:3, r:1, v:1} },
};

// ============================================================================
// THE BOARD — 39 snake squares (squares.json), each RAW_DECK-shaped:
//   { type, label, band, pct, slot?, k(kind), f(flavor), e(raw deltas {c,d,r,v}), sp(special) }
// The label's finer $ is decorative tile text; only `band`+`pct` touch the engine.
// ============================================================================
const NODE_DATA = [
  { type:'start',    label:'START',        band:'$100k', pct:0,  k:'',      f:"A slide deck, a dream, and a bank balance that rounds to zero. Dr. Vance has seen ten thousand of you. Climb the snake. Don't run out of money." },
  { type:'value',    label:'$1M',          band:'$1M',   pct:8,  k:'good',  f:"You incorporated in Delaware and bought a freezer. The freezer is already 40% of your runway.", e:{d:1} },
  { type:'milestone',label:'Pre-IND',      band:'$5M',   pct:16, slot:0,    f:"You ask FDA if your plan is insane before spending the money. They answer in writing. You will reread that letter like a breakup text.", sp:{type:'gate', slot:0} },
  { type:'funding',  label:'Grant Funding!',band:'$5M',  pct:18, k:'good',  f:"Non-dilutive money, the rarest creature in biotech. Nobody took equity, nobody gets a board seat, and you keep your soul one more quarter.", e:{c:28}, sp:{type:'funding'} },
  { type:'value',    label:'$10M',         band:'$5M',   pct:22, k:'good',  f:"A KOL returned your email. You read it nine times looking for hidden enthusiasm. There is none, but there is also no 'no.'", e:{d:1,r:1} },
  { type:'deck',     label:'Draw New Staff',band:'$25M', pct:26, k:'good',  f:"You hired a regulatory lead who has actually received a CRL and lived. Worth more than the Series A.", e:{r:2,d:1}, sp:{type:'deck', deck:'rnd'} },
  { type:'funding',  label:'Corp. Venture Funds!',band:'$25M',pct:27, k:'good', f:"A strategic wrote a check and asked for 'just a small information right.' It is never small. The war chest is fat today.", e:{c:36}, sp:{type:'funding'} },
  { type:'milestone',label:'Phase 1',      band:'$25M',  pct:30, slot:1,    f:"First in humans. Not looking for it to work yet, just to not hurt anyone — a low bar your drug will still try to limbo under.", sp:{type:'gate', slot:1} },
  { type:'deck',     label:'Draw +1 Staff & +1 REG',band:'$25M',pct:33, k:'good', f:"Pull two off the board: a hire and a regulatory card. The painted square always made you draw twice. The deck remembers.", e:{r:1,d:1}, sp:{type:'deck', deck:'rnd', alsoReg:true} },
  { type:'deck',     label:'Draw: R&D 🔬',  band:'$90M',  pct:38, k:'',     f:"Lab work by the book. The board makes you pull from the R&D deck — data that survives review is built, not bought.", sp:{type:'deck', deck:'rnd'} },
  { type:'fork',     label:'Hire CRO?',    band:'$90M',  pct:39, k:'swing', f:"Outsource the trial to professionals who run 40 studies at once and will remember your name 60% of the time. Faster enrollment, faster burn.", sp:{type:'choose', a:{label:'Hire the CRO', c:-3, d:3}, b:{label:'Run it in-house', d:1, r:1}} },
  { type:'hazard',   label:'Enrollment Shortfall',band:'$90M',pct:41, k:'bad', f:"Your sites enrolled 11% of target in 60% of the timeline. The CRO has 'learnings.' You have a burn rate and a board meeting Thursday.", e:{c:-2,d:-2,r:-1,v:-2}, sp:{type:'hazard'} },
  { type:'value',    label:'$70M',         band:'$90M',  pct:43, k:'good',  f:"Enrollment ahead of schedule, which has never once happened in recorded history. It is not real.", e:{c:-1,d:2,v:1} },
  { type:'deck',     label:'Draw: Enroll 🧪',band:'$90M', pct:45, k:'',     f:"Open the sites, bring patients in. The board makes you pull from the Enroll deck — faster progress, messier data. Dr. Vance keeps a ledger.", sp:{type:'deck', deck:'enroll'} },
  { type:'milestone',label:'Phase 2',      band:'$90M',  pct:48, slot:2,    f:"Does it actually do anything? ~70% of programs die here. The valley of death has excellent parking.", sp:{type:'gate', slot:2} },
  { type:'value',    label:'$100M',        band:'$300M', pct:50, k:'good',  f:"Your stock pops 40% on a press release with 'statistically significant' and 'well-tolerated.' Nobody read the secondary endpoints. Don't tell them.", e:{c:3,d:1,v:2} },
  { type:'hazard',   label:"You're Out of Money!",band:'$300M',pct:52, k:'bad', f:"The science was sound — it almost always is. But the trial runs on capital, not hypotheses. Land here flat broke and the molecule goes back in the freezer. The mice are unmoved.", e:{c:-4}, sp:{type:'hazard', bankruptIfBroke:true} },
  { type:'deck',     label:'Draw: FDA 🏛️', band:'$300M', pct:54, k:'',     f:"Request a meeting with the agency to align on your plan. The board makes you pull from the FDA deck — costs money and time, buys goodwill and a clearer path.", sp:{type:'deck', deck:'fda'} },
  { type:'hazard',   label:'Form 483 Issued',band:'$300M',pct:56, k:'bad', f:"An inspector found 'objectionable conditions' at your site. You have 15 business days to write a response longer than the inspection itself, and to mean it.", e:{c:-2,r:-2,v:-1}, sp:{type:'hazard'} },
  { type:'dice',     label:'Advisory Committee',band:'$300M',pct:58, k:'swing', f:"The AdComm convenes. The panel votes on your benefit-risk, live, in public, while you sit in the front row not allowed to talk. Roll the room.", dev:{label:'Advisory Panel', f:"The Medical Devices Advisory Panel convenes. They vote on your benefit-risk, live, in public, while you sit in the front row not allowed to talk. Roll the room."}, e:{c:-1}, sp:{type:'dice', check:{r:4,v:3}, x:{r:-3,v:-3,skip:true}, bang:{r:-1}, at:{d:1,v:1}} },
  { type:'value',    label:'$400M',        band:'$300M', pct:60, k:'good',  f:"FDA accepts your external control arm built from registry data. The 1990s called and could not believe it. Frame this square.", e:{c:1,d:2,r:1,v:1} },
  { type:'fork',     label:'Fire the CRO?',band:'$300M', pct:62, k:'swing', f:"The board has thoughts about leadership 'after the CRL,' and somewhere in the minutes 'CRO' became 'CEO.' Bring in a turnaround chief (cash, fresh credibility) or keep the founder (vision, baggage). The board cannot keep its C-suite straight either.", sp:{type:'choose', a:{label:'Bring in new chief', c:3, r:2, v:-1}, b:{label:'Keep the founder', r:-1, v:2}} },
  { type:'milestone',label:'Phase 3',      band:'$900M',  pct:64, slot:3,   f:"The big, expensive, registrational trial. Hundreds of millions riding on a p-value you do not control.", sp:{type:'gate', slot:3, deviceFork:true} },
  { type:'value',    label:'$1B',          band:'$900M',  pct:66, k:'good', f:"The field's most-cited investigator called your mechanism 'genuinely interesting' from the podium. Your competitor hears their valuation deflating.", e:{c:2,r:3,v:1} },
  { type:'coin',     label:'Boot-strap It!',band:'$900M', pct:68, k:'swing',f:"Out of runway, you boot-strap the next milestone on grant funding and sheer will. Heroic if it works, a Chapter 7 filing if it doesn't.", e:{c:-1}, sp:{type:'coin', heads:{c:8,r:2}, tails:{c:-4,v:-2}} },
  { type:'deck',     label:'Draw: Funding 💵',band:'$900M',pct:70, k:'',    f:"Sell equity, smile at the board, promise the moon. The board makes you pull from the Funding deck to refill the war chest before the expensive part.", sp:{type:'deck', deck:'funding'} },
  { type:'hazard',   label:'Down Round',   band:'$900M',  pct:72, k:'bad',  f:"Ms. N. Vested, MBA leads a financing at half your last valuation 'to be supportive.' Your option pool is now a rounding error. She still wants a board seat.", e:{c:10,r:-2,v:-3}, sp:{type:'hazard'} },
  { type:'value',    label:'$1.5B',        band:'$900M',  pct:75, k:'good', f:"Strong Phase 3 readout. The primary endpoint held. Somewhere a biostatistician exhales for the first time since 2023.", dev:{f:"Strong pivotal readout. The primary endpoint held. Somewhere a biostatistician exhales for the first time since the first-in-human."}, e:{c:3,d:2,v:3} },
  { type:'fork',     label:'Get Acquired?',band:'$2.5B',  pct:78, k:'swing',f:"A strategic offers to buy you at a premium. Cash out and end the game a winner, or decline and gamble that the top of the track is real.", sp:{type:'choose', a:{label:'SELL! 💰', cashOut:true}, b:{label:'No thanks!', v:1}} },
  { type:'race',     label:'Surprise Competitor',band:'$2.5B',pct:80, k:'swing', f:"A rival you forgot existed just filed in your indication. If they read out first, you're second-to-market with a press release nobody reprints. Unless you sprint.", e:{r:-1}, sp:{type:'race', ahead:{v:2}, behind:{v:-3,r:-1}} },
  { type:'hazard',   label:'Government Shutdown',band:'$2.5B',pct:82, k:'bad', f:"FDA's user-fee work continues but new meetings freeze. Your PDUFA clock is fine; your sanity is not. Congress will fix this in 34 days, plus a fiscal cliff.", dev:{f:"FDA's user-fee work continues but new Q-Subs freeze. Your MDUFA clock is fine; your sanity is not. Congress will fix this in 34 days, plus a fiscal cliff."}, e:{c:-1,v:-1}, sp:{type:'hazard', skip:true} },
  { type:'value',    label:'$3B',          band:'$2.5B',  pct:84, k:'good', f:"Priority Review Voucher in hand. Use it, or sell it for ~$100M to a company that wants to rush a wrinkle cream. Capitalism!", dev:{f:"Parallel Review with CMS locked in — coverage and clearance arrive together. Sell the moment for ~$100M to someone who wants to rush it. Capitalism!"}, e:{c:5,v:2} },
  { type:'hazard',   label:'CMC / Mfg Failure',band:'$2.5B',pct:86, k:'bad', f:"Three consecutive batches fail dissolution spec. Your process is 'not yet validated,' a kind phrase for 'a science experiment with a PDUFA date.'", dev:{label:'Design V&V Failure', f:"Three consecutive lots fail design verification. Your process is 'not yet validated,' a kind phrase for 'a prototype with an MDUFA date.'"}, e:{c:-3,d:-1,r:-1,v:-2}, sp:{type:'hazard'} },
  { type:'deck',     label:'Draw: FDA 🏛️', band:'$2.5B',  pct:88, k:'',     f:"One last alignment meeting before you file. Pull from the FDA deck — goodwill now is worth a re-review avoided later.", sp:{type:'deck', deck:'fda'} },
  { type:'hazard',   label:'Refuse-to-File',band:'$5B',   pct:90, k:'bad',  f:"FDA won't even REVIEW your application. The 74-day letter lands like a slap with a federal seal. Your filing fee is non-refundable. So is your dignity.", dev:{label:'Refuse to Accept', f:"FDA won't even START the substantive review — your 510(k) flunks the Refuse-to-Accept checklist on a missing bench report. The clock never started. Your user fee, however, did."}, e:{c:-3,d:-1,r:-3,v:-3}, sp:{type:'hazard', skip:true} },
  { type:'funding',  label:'Crossover Round',band:'$5B',  pct:91, k:'good', f:"A crossover fund pre-empted your IPO. The bankers are circling. Top off the tank for Dr. Vance.", e:{c:30}, sp:{type:'funding'} },
  { type:'hazard',   label:'Complete Response Letter',band:'$5B',pct:93, k:'bad', f:"Not an approval. Not a denial. A CRL — the regulatory equivalent of 'we need to talk.' The deficiencies are 'CMC and clinical.' That is the whole drug.", dev:{label:'Not Substantially Equivalent', f:"Not a clearance. Not a denial. An NSE letter — your predicate doesn't hold, so you're a De Novo or a PMA now whether you budgeted for it or not. That is the whole device."}, e:{c:-3,d:-2,r:-2,v:-3}, sp:{type:'hazard', skip:true} },
  { type:'milestone',label:'NDA/BLA Submission',band:'$9B',pct:97, slot:4,  f:"You file. The application is 100,000+ pages. The reviewer reads all of it. This is the closest thing to love between a sponsor and the federal government.", sp:{type:'gate', slot:4, submission:true} },
  { type:'exit',     label:'FACE DR. VANCE',band:'$9B',   pct:97, slot:5,   f:"The end of the snake. Dr. Eleanor Vance, Division of Regulatory Reckoning, has read everything. She is not impressed. Her highest praise is 'this is adequate.' Make your case.", sp:{type:'exit'} },
];

// The four draw decks. A turn-start draw pulls a RANDOM card from the chosen deck
// (the player's agency moment); some board squares force a draw from a named deck.
// Capital is raw $M; data/reputation scaled; `ready` adds to readiness; flags reused.
const DECKS = {
  rnd: [
    { name:'Clean Study, By the Book', k:'good',  f:"Lab and clinical work, slow and costly, but it builds the kind of data that survives FDA review. O. Vrsink, PhD nods approvingly.", e:{c:-3,d:3}, ready:14 },
    { name:'Real-World Evidence Accepted', k:'good', f:"Registry data stands in for a control arm and FDA buys it. Your statistician, who fought for this, takes the rest of the day off. Earned.", e:{c:-1,d:3,r:1,v:1}, ready:10 },
    { name:'Expansion Cohort Surprise', dev:{name:'Off-Label Signal', f:"Surgeons start using your device in an anatomy you never studied, and it works. A second 510(k), or a promotional-claims violation. The reg lead is sweating."}, k:'swing', f:"Your dose-escalation cohort lights up in a tumor type you weren't studying. A new indication, or a multiplicity problem. The statistician is sweating.", e:{d:2,v:1}, ready:8 },
    { name:'Strong Phase 2 Readout', dev:{name:'Strong Feasibility Readout', f:"Your Early Feasibility Study cleared and the device behaved in vivo exactly as the bench promised, which it never does. The data is real this time. Bank it before FDA asks for the pivotal."}, k:'good', f:"The primary held and the safety table is boring in the best way. The data is real this time. Bank it before the market reprices you.", e:{c:2,d:2,r:1,v:2}, ready:12 },
    { name:'Site Data Integrity Finding', k:'bad', f:"One investigator may have invented some subjects. You exclude the site, FDA notices you noticed, and your power evaporates like ethanol off a swab.", e:{c:-2,d:-3,r:-2,v:-1}, ready:0 },
    { name:'Clean CMC Inspection', dev:{name:'Clean QMS Audit', f:"Zero nonconformities at your design-controls audit. The auditor closes the DHF and leaves early. Nobody on your team trusts it, and they are right to wait for the 483 that never comes."}, k:'good', f:"Zero observations at your fill-finish site. The investigators leave early. Nobody on your team trusts it, and they are right to wait for the EIR.", e:{d:1,r:3,v:1}, ready:6 },
  ],
  enroll: [
    { name:'Open the Sites', k:'swing', f:"Bring patients in. Faster progress than careful R&D, but rushing enrollment risks messier data. Dr. Vance keeps a ledger; this earns an integrity flag.", e:{c:-2,d:1,r:-1}, ready:20, integrity:1 },
    { name:'Enrollment Ahead of Schedule', k:'good', f:"Sites are filling slots faster than the Gantt chart allowed. Finance assumes you lied. You did not. Savor it; it will regress to the mean by Q3.", e:{c:-1,d:3,r:1,v:1}, ready:16 },
    { name:'Patient Advocacy Rallies', k:'good', f:"Real patients show up to your AdComm in matching t-shirts and break the panel's heart. The p-value of 0.061 suddenly feels rude to mention.", e:{c:1,r:4,v:1}, ready:6 },
    { name:'Pivotal Enrollment Shortfall', k:'bad', f:"Three sites haven't randomized a single patient since the kickoff dinner. The site PI 'is very excited,' per the monitoring report. The slope is flat.", e:{c:-2,d:-2,r:-1,v:-2}, ready:4 },
    { name:'Hire a CRO', k:'swing', f:"Outsource to professionals who run 40 studies at once and remember your name 60% of the time. Faster enrollment, faster burn.", e:{c:-3,d:3}, ready:18 },
  ],
  fda: [
    { name:'Request an Alignment Meeting', k:'good', f:"Ask the agency to align on your plan. Costs money and time, buys goodwill and a clearer path — and slows the competitor a half-step.", e:{c:-1,d:1,r:2}, ready:8 },
    { name:'Breakthrough Therapy Designation', dev:{name:'Breakthrough Device Designation', f:"FDA agrees your device is promising enough to skip ahead in line. You now get to email the same reviewer four times a week, and they have to answer. Bliss."}, k:'good', f:"FDA agrees your drug is promising enough to skip ahead in line. You now get to email the same reviewer four times a week, and they have to answer. Bliss.", e:{d:1,r:3,v:2}, ready:6 },
    { name:'Fast Track Granted', dev:{name:'STeP Acceptance', f:"Into the Safer Technologies Program — the expedited lane for devices that make care safer without quite earning Breakthrough. Slightly less glamorous, exactly as much paperwork."}, k:'good', f:"Rolling review unlocked. Submit your application in pieces, like a hostage negotiation where the hostage is your NDA and you are also the kidnapper.", e:{r:2,v:2}, ready:6 },
    { name:'Positive Type B Meeting', dev:{name:'Positive Pre-Sub Meeting', f:"CDRH agrees with your pivotal design in the Q-Sub written feedback. You frame the minutes. You will cite them in three years when the review team pretends they never said it."}, k:'good', f:"FDA agrees with your pivotal design in writing. You frame the minutes. You will cite them in three years when they pretend it never happened.", e:{d:2,r:2,v:1}, ready:8 },
    { name:'Clinical Hold', dev:{name:'IDE Disapproval', f:"FDA disapproves your IDE over a safety question. Enrollment stops. Four months proving one adverse event was operator technique and not your device. Lose a turn."}, k:'bad', f:"FDA has 'questions' about a safety signal. All dosing stops. Four months proving one elevated liver enzyme was the assay's fault, not yours. Lose a turn.", e:{c:-2,d:-1,r:-2,v:-2}, ready:0, skip:true },
    { name:'Reviewer Turnover', k:'bad', f:"Your primary reviewer left for industry. The new one hasn't read the file, disagrees about your endpoint, and emails 'just to align' Friday at 5:47pm.", e:{r:-2,v:-1}, ready:0 },
  ],
  funding: [
    { name:'Raise a Round', k:'good', f:"Sell equity, smile at the board, promise the moon. Refills the war chest. Prof. Goetta Grant raises with no goodwill hit; everyone else dilutes.", e:{c:18,r:-1}, ready:0, isRaise:true },
    { name:'Orphan Drug Designation', dev:{name:'Humanitarian Use Device', f:"Fewer than 8,000 patients a year, so you earn a Humanitarian Use Device designation and an HDE pathway that waives the effectiveness burden. Your accountant is thrilled — the rarest creature in deviceland."}, k:'good', f:"Seven years of exclusivity and a tax credit, because your disease is rare and your accountant is thrilled. Free money with a clear rationale — the rarest creature in biotech.", e:{c:16,r:1,v:2}, ready:0 },
    { name:'Priority Review Voucher', dev:{name:'Parallel Review Accepted', f:"FDA and CMS agree to review in parallel, so coverage lands the same week as clearance instead of three years later. Investors who cannot define 'NCD' wire you money anyway."}, k:'good', f:"You earned a PRV for your rare pediatric disease drug. Use it, or sell it for ~$100M to a company that wants to rush a wrinkle cream. Capitalism!", e:{c:22,v:2}, ready:0 },
    { name:'RMAT Designation', k:'good', f:"Your cell therapy is a Regenerative Medicine Advanced Therapy. Investors who cannot define 'potency assay' wire you money anyway. The answer was always yes.", e:{c:20,r:2,v:3}, ready:0 },
    { name:'Investor Down Round', k:'bad', f:"A financing at half your last valuation 'to be supportive.' Cash now, dignity later. She still wants a board seat.", e:{c:24,r:-2,v:-3}, ready:0 },
    { name:'The Boot-Strap Gambit', k:'good', f:"Out of runway, you boot-strap the next milestone on grant funding and sheer will. Heroic if it works, a Chapter 7 filing if it doesn't.", e:{c:16,r:2}, ready:0 },
  ],
};
const DECK_META = {
  rnd:    { label:'🔬 R&D',     suit:'♣', tag:'study' },
  enroll: { label:'🧪 Enroll',  suit:'♥', tag:'study' },
  fda:    { label:'🏛️ FDA',    suit:'♠', tag:'study' },
  funding:{ label:'💵 Funding', suit:'♦', tag:'money' },
};

// Funny leaderboard rank titles — regulatory AND founder/startup jabs.
function rankTitle(outcome, score){
  if(outcome==='approved'){
    if(score>=2600) return '🦄 Regulatory Unicorn';
    if(score>=2000) return '🏆 Regulatory Legend';
    if(score>=1400) return '🚀 On Track to Exit';
    return '✅ Approvable Human';
  }
  if(outcome==='acquired'){
    if(score>=1200) return '💰 Exited Before Series B';
    return '🤝 Took the Money (Smart)';
  }
  if(outcome==='bankrupt') return '💸 Never Raised Series B';
  if(outcome==='beaten_to_market') return '🥈 Scooped at the Buzzer';
  if(outcome==='clinical_hold') return '🛑 Permanent Hold Club';
  return '🔬 Still Enrolling (p=0.06 Forever)';
}

const WIN_COPY = { title:'APPROVED.', sub:'Your application met the standard for substantial evidence of effectiveness. Somewhere, Dr. Vance allows herself a single, measured nod. You drove a molecule from $100k to the top of the snake without going broke, blowing the endpoint, or getting scooped. That is not luck. That is regulatory strategy.' };
const ACQUIRED_COPY = { title:'ACQUIRED.', sub:'You took the buyout at the top of your valuation and handed the post-marketing commitments to someone with a bigger legal department. A partial win, and the smartest people in biotech would shake your hand. The molecule lives. So does your cap table.' };
const LOSE_COPY = {
  bankrupt:        { title:'YOU ARE OUT OF MONEY.', sub:'The science was sound — it almost always is. But the trial runs on capital, not hypotheses, and yours hit zero. The molecule goes back in the freezer. The mice are unmoved. Every great drug that never existed died exactly here. Excellent company.' },
  failed_endpoint: { title:'THE RUNWAY RAN OUT.', sub:'The clock beat you to the top of the snake. There is a promising subgroup — there is always a subgroup — but the board meeting is over and the term sheet expired. The drug may even work. Time declined to let it prove so.' },
  beaten_to_market:{ title:'YOU CAME IN SECOND.', sub:'A competitor you half-forgot read out first, filed first, and got their letter while yours was still climbing. Second-to-market is a real place, mostly populated by excellent drugs and modest revenue. Their CEO is doing a victory lap. You are doing a budget review.' },
  clinical_hold:   { title:'CLINICAL HOLD — PERMANENT.', sub:'You reached the submission gate with no goodwill left to spend. The safety questions never got good answers, and the hold became the ending. First, do no harm; also, do no approval.' },
};

// ============================================================================
// BOARD GEOMETRY — a boustrophedon (serpentine) snake. The ordered node centers
// ARE the avatar waypoint polyline (single source of truth: tiles + tokens + road
// all derive from nodeCenter()). 8 cols × 5 rows; START bottom-right, EXIT top.
// ============================================================================
const VB_W = 980, VB_H = 700;
const COLS = 8, ROWS = 5, MX = 70, MY = 80, CP = 120, RP = 135;
function nodeCenter(i){
  const snakeRow = Math.floor(i / COLS);          // 0 = bottom (start)
  const idxInRow = i % COLS;
  const leftToRight = (snakeRow % 2 === 1);        // row0 R->L, row1 L->R, ...
  const col = leftToRight ? idxInRow : (COLS - 1 - idxInRow);
  const visualRow = (ROWS - 1) - snakeRow;         // bottom snakeRow -> bottom of screen
  return { cx: MX + col * CP, cy: MY + visualRow * RP };
}
// Bake centers into the node table once.
const NODES = NODE_DATA.map((n, i) => Object.assign({ i }, n, nodeCenter(i)));

// Pathway-aware terminology: a card or square may carry a `dev:{name?,label?,f?}`
// device variant. On the device pathway we show the device-correct term (Pre-Sub,
// Breakthrough Device, HUD, Parallel Review, NSE…) instead of the drug/biologic one.
// The regulatory vocabulary is not interchangeable, and a tool with a regulatory
// SVP's name on it does not get to pretend it is.
function pwField(o, field){
  return (S && S.pathway === 'device' && o && o.dev && o.dev[field] != null) ? o.dev[field] : (o ? o[field] : undefined);
}

// ============================================================================
// STATE
// ============================================================================
let player = null;       // {first,last,email}
let chosenChar = null;
let S = null;
let spinner = null;      // the spinner controller (enable/disable)
const $ = (id) => document.getElementById(id);

function showScreen(id){
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  $(id).classList.add('active');
  window.scrollTo({ top:0, behavior:'smooth' });
}

// ============================================================================
// WEBAUDIO SFX — a pocket synth, zero asset files (ux-patterns.md Pattern 3).
// Sound is the cheapest dopamine in game design and the easiest to get wrong.
// Short, dry, comic. And ALWAYS a mute, because consent includes the right to silence.
// ============================================================================
window.SFX = (function(){
  let ctx=null, muted=(localStorage.getItem('tc_muted')==='1'), master=null;
  const ensure=()=>{ if(!ctx){ const AC=window.AudioContext||window.webkitAudioContext; if(AC) ctx=new AC(); }
                     if(ctx && ctx.state==='suspended') ctx.resume(); return ctx; };
  const bus=()=>{ const c=ensure(); if(!c) return null; if(!master){ master=c.createGain(); master.gain.value=muted?0:1; master.connect(c.destination);} return master; };
  function tone(freq,t0,dur,type='sine',gain=0.18,slideTo=null){ const c=ensure(),out=bus(); if(!c||!out)return;
    const o=c.createOscillator(),g=c.createGain(); o.type=type; o.frequency.setValueAtTime(freq,t0);
    if(slideTo) o.frequency.exponentialRampToValueAtTime(slideTo,t0+dur);
    g.gain.setValueAtTime(0.0001,t0); g.gain.exponentialRampToValueAtTime(gain,t0+0.008); g.gain.exponentialRampToValueAtTime(0.0001,t0+dur);
    o.connect(g); g.connect(out); o.start(t0); o.stop(t0+dur+0.02); }
  function noiseBurst(t0,dur,gain=0.12,hp=600){ const c=ensure(),out=bus(); if(!c||!out)return;
    const len=Math.floor(c.sampleRate*dur),buf=c.createBuffer(1,len,c.sampleRate),d=buf.getChannelData(0);
    for(let i=0;i<len;i++) d[i]=(Math.random()*2-1)*(1-i/len);
    const src=c.createBufferSource(); src.buffer=buf; const f=c.createBiquadFilter(); f.type='highpass'; f.frequency.value=hp;
    const g=c.createGain(); g.gain.setValueAtTime(gain,t0); g.gain.exponentialRampToValueAtTime(0.0001,t0+dur);
    src.connect(f); f.connect(g); g.connect(out); src.start(t0); src.stop(t0+dur); }
  return {
    flip(){ const c=ensure(); if(!c)return; const t=c.currentTime; noiseBurst(t,0.16,0.14,900); tone(520,t+0.05,0.10,'triangle',0.10,240); },
    whoosh(){ const c=ensure(); if(!c)return; const t=c.currentTime; noiseBurst(t,0.26,0.10,500); tone(300,t,0.26,'sine',0.07,760); },
    tick(){ const c=ensure(); if(!c)return; const t=c.currentTime; tone(1400,t,0.035,'square',0.06,1100); },
    spinnerTicks(ms){ const c=ensure(); if(!c)return; const t0=c.currentTime,total=ms/1000; let t=0,gap=0.045;
      while(t<total){ tone(1500,t0+t,0.03,'square',0.05,1150); t+=gap; gap*=1.14; } },
    coin(){ const c=ensure(); if(!c)return; const t=c.currentTime; tone(880,t,0.08,'square',0.10); tone(1320,t+0.07,0.12,'square',0.10); },
    thud(){ const c=ensure(); if(!c)return; const t=c.currentTime; tone(150,t,0.22,'sine',0.18,60); noiseBurst(t,0.10,0.06,200); },
    isMuted(){ return muted; },
    toggleMute(){ muted=!muted; localStorage.setItem('tc_muted',muted?'1':'0');
      if(master) master.gain.setTargetAtTime(muted?0:1, ensure().currentTime, 0.01); return muted; },
  };
})();
function wireMuteToggle(){
  const b=$('sfx-toggle'); if(!b)return;
  const paint=()=>{ b.textContent=SFX.isMuted()?'🔇':'🔊'; b.setAttribute('aria-label',SFX.isMuted()?'Unmute':'Mute'); };
  paint(); b.addEventListener('click',()=>{ SFX.toggleMute(); paint(); if(!SFX.isMuted()) SFX.tick(); });
}

// ============================================================================
// INIT / NAV
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  $('btn-begin').addEventListener('click', () => showScreen('screen-register'));
  $('btn-register').addEventListener('click', register);
  $('reg-email').addEventListener('keydown', e => { if(e.key==='Enter') register(); });
  $('nav-leaderboard').addEventListener('click', showLeaderboardStandalone);
  $('event-ok').addEventListener('click', closeEvent);
  $('btn-submit-review').addEventListener('click', submitReview);
  $('btn-review-continue').addEventListener('click', afterReview);
  $('btn-play-again').addEventListener('click', () => { $('overlay-end').classList.remove('active'); showScreen('screen-characters'); renderCharacters(); });
  $('gloss-close').addEventListener('click', () => $('overlay-glossary').classList.remove('active'));
  $('overlay-glossary').addEventListener('click', (e) => { if(e.target.id==='overlay-glossary') $('overlay-glossary').classList.remove('active'); });
  wireMuteToggle();
});

// ============================================================================
// REGISTER → CHARACTER SELECT → SEED → PLAY
// ============================================================================
function register(){
  const first=$('reg-first').value.trim(), last=$('reg-last').value.trim(), email=$('reg-email').value.trim();
  const err=$('reg-err');
  if(!first){ err.textContent='A first name, at least. Even a fake one.'; return; }
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){ err.textContent="That email doesn't look real. It doesn't have to be — just shaped like one."; return; }
  err.textContent=''; player={ first, last, email };
  showScreen('screen-characters'); renderCharacters();
}

function renderCharacters(){
  $('characters-grid').innerHTML = CHARACTERS.map(c => `
    <button class="founder-card sticker-tilt" data-char="${c.id}">
      <img class="founder-card__art" src="/static/img/founders/${c.id}.png" alt="${escapeHtml(c.name)} — ${escapeHtml(c.role)}" loading="lazy">
      <span class="founder-card__blurb">${escapeHtml(c.blurb)}</span>
    </button>`).join('');
  $('characters-grid').querySelectorAll('.founder-card').forEach(b =>
    b.addEventListener('click', () => { chosenChar=CHARACTERS.find(c=>c.id===b.dataset.char); startGame(); }));
}

async function startGame(){
  showScreen('screen-play');
  $('scenario-card').innerHTML = '<em>Dealing you a real product from the registry…</em>';
  let seed;
  try {
    const resp=await fetch('/api/game/seed');
    if(!resp.ok) throw new Error('seed '+resp.status);
    seed=await resp.json();
  } catch(e){
    $('scenario-card').innerHTML='<em>Could not reach the registry. Is the server up? ('+e+')</em>'; return;
  }
  buildState(seed); renderAll();
}

function buildState(seed){
  const pathway = PATHWAYS[seed.pathway] ? seed.pathway : 'drug';
  const d = seed.difficulty || 3;
  const ch = chosenChar;
  S = {
    seed, pathway, char:ch,
    boardIdx:0, competitorPos:0, turn:1,
    maxTurns: BASE_MAX_TURNS + (ch.extraTurns || 0),
    res: {
      capital: START_CAPITAL + (ch.start.capital || 0),
      data: 0 + (ch.start.data || 0),
      reputation: START_GOODWILL + (ch.start.reputation || 0),
      value: 0,
    },
    readiness:0, integrity:0, difficulty:d,
    status:'playing', outcome:null, log:[], reviewModifier:0,
    drewThisTurn:false, reviewOpened:false, clearedSubmission:false,
    raiseUsedNoHit:false, investorScoopSaved:false, devForkDone:false, dogSurge:0,
  };
  pushLog(`${ch.name} (${ch.role}) opens a ${PATHWAYS[pathway].label}. Difficulty ${d}/5. ${S.maxTurns} turns of runway. Draw a card, then spin to climb.`, 'turn');
}

// ============================================================================
// RENDER
// ============================================================================
function renderAll(){ renderScenario(); renderHUD(); renderTension(); renderGateStatus(); renderBoard(); positionTokens(false); renderActions(); renderLog(); }

// The objective line: the next un-cleared milestone gate + readiness toward it.
// On a phone the gate's "NEED N" tile text is too small to read; this says it plainly.
function renderGateStatus(){
  const el=$('gate-status'); if(!el) return;
  const g = NODES.find(n => n.type==='milestone' && n.i >= S.boardIdx);
  if(!g){ el.className='gate-status ready'; el.innerHTML='<span class="gs-label">Summit</span><span class="gs-name">Face Dr. Vance</span>'; return; }
  const need = MILESTONE_NEED[S.pathway][g.slot] || 0;
  const lab  = MILESTONE_LABEL[S.pathway][g.slot] || g.label;
  const have = Math.round(S.readiness);
  const ready = have >= need;
  const pct = need ? Math.min(100, have/need*100) : 100;
  el.className = 'gate-status' + (ready ? ' ready' : '');
  el.innerHTML =
    `<span class="gs-label">Next gate</span>` +
    `<span class="gs-name">${escapeHtml(lab)}</span>` +
    `<span class="gs-ready">readiness ${have} / ${need}${ready ? ' — ready, spin through' : ''}</span>` +
    `<span class="gs-bar"><i style="width:${pct}%"></i></span>`;
}

function renderScenario(){
  const s=S.seed;
  const nctUrl=`https://clinicaltrials.gov/study/${encodeURIComponent(s.nct_id)}`;
  $('scenario-card').innerHTML = `
    <div class="real-note">🔬 <strong>Your mission:</strong> climb this <strong>real</strong> product through the FDA. Dealt live from the
      <a href="https://clinicaltrials.gov" target="_blank" rel="noopener">ClinicalTrials.gov</a> registry —
      tap <a class="nct" href="${nctUrl}" target="_blank" rel="noopener">${escapeHtml(s.nct_id)}</a> to read the genuine trial record.</div>
    <span class="tag path">${S.pathway.toUpperCase()} · ${S.pathway==='device'?'510(k)/PMA':'NDA/BLA'}</span>
    ${s.therapeutic_area?`<span class="tag">${escapeHtml(s.therapeutic_area)}</span>`:''}
    ${s.product_category?`<span class="tag alt">${escapeHtml(s.product_category)}</span>`:''}
    ${s.device_class?`<span class="tag">Class ${escapeHtml(s.device_class)}</span>`:''}
    ${s.phase&&s.phase!=='NA'?`<span class="tag">${escapeHtml(s.phase)}</span>`:''}
    <h2>${escapeHtml(s.title)}</h2>
    <div class="meta">Playing as <strong>${escapeHtml(S.char.name)}</strong> · product: <strong>${escapeHtml(s.intervention_name||s.intervention_type||'an investigational product')}</strong>${s.sponsor?` · orig. sponsor ${escapeHtml(s.sponsor)}`:''}</div>`;
}

function renderHUD(){
  const r=S.res, capPct=r.capital/CAPITAL_BAR_MAX*100, turnsLeft=S.maxTurns-S.turn+1;
  const tile=(cls,ico,lab,val,pct,term)=>`<div class="res ${cls}" id="res-${cls}">
    <div class="ico">${ico}</div><div class="lab"><span class="jr" data-term="${term}">${lab}</span></div>
    <div class="val">${val}</div><div class="bar"><i style="width:${Math.max(0,Math.min(100,pct))}%"></i></div></div>`;
  $('hud').innerHTML =
    tile('value','💰','Product value', valueLabel(r.value), r.value, 'product value') +
    tile('capital','💵','Capital', '$'+Math.round(r.capital)+'M', capPct, 'capital') +
    tile('evidence','📊','Data', Math.round(r.data), r.data, 'data') +
    tile('reputation','🤝','Goodwill', Math.round(r.reputation), r.reputation, 'goodwill') +
    tile('time','⏳','Turns left', turnsLeft, turnsLeft/S.maxTurns*100, 'turns');
}
function renderTension(){ const p=Math.max(0,Math.min(100, S.competitorPos/FIRST_TO_FILE*100));
  $('tension-bar').style.width=p+'%'; $('tension-pct').textContent=Math.round(p)+'%'; }

// ----- THE BOARD: build the sticker-comic SVG once, then only move tokens -----
function renderBoard(){ $('board-svg').innerHTML = buildBoardSVG(); }

const TYPE_FACE = {
  start:'#5bb545', value:'#FAFAF5', funding:'#c7e3b1', hazard:'#ffb3a0',
  fork:'#d9c2ef', deck:'#FAFAF5', dice:'#fdf6a8', coin:'#fdf6a8', race:'#fdf6a8',
  milestone:'#e8e52a', exit:'#e8e52a',
};
function tileLabel(n){
  if(n.type==='milestone' || n.type==='exit'){ const lab=MILESTONE_LABEL[S.pathway][n.slot]; return lab || n.label; }
  return pwField(n,'label');
}
function tileSVG(n){
  const isGate = (n.type==='milestone' || n.type==='exit');
  const w = isGate ? 108 : 104, h = isGate ? 104 : 84;
  const face = TYPE_FACE[n.type] || '#FAFAF5';
  const x=-w/2, y=-h/2;
  const idTxt = `<text class="t-idx" x="${x+8}" y="${y+15}" font-size="10" font-weight="800" fill="#1b1b1b" opacity="0.5">${n.i}</text>`;
  let body='';
  if(isGate){
    const need = MILESTONE_NEED[S.pathway][n.slot] || 0;
    const ribbon = n.type==='exit' ? '#b3261a' : '#4a0873';
    const rlab = n.type==='exit' ? '★ DR. VANCE' : '⛓ GATE';
    body = `<path d="M${x} ${y+6} a6 6 0 0 1 6 -6 H${x+w-6} a6 6 0 0 1 6 6 V${y+26} H${x} Z" fill="${ribbon}"/>
      <text x="0" y="${y+18}" text-anchor="middle" font-weight="800" font-size="11" fill="#FAFAF5">${rlab}</text>
      <text x="0" y="${y+46}" text-anchor="middle" font-weight="800" font-size="15" fill="#1b1b1b">${escapeHtml(tileLabel(n))}</text>
      ${need?`<text x="0" y="${y+h-12}" text-anchor="middle" font-weight="800" font-size="10" fill="#4a0873">NEED ${need} READY</text>`:`<text x="0" y="${y+h-12}" text-anchor="middle" font-weight="800" font-size="11" fill="#b3261a">FILE!</text>`}
      <use href="#regstamp" x="${x+w-34}" y="${y+h-26}"/>`;
  } else if(n.type==='value'){
    body = `<rect x="${x}" y="${y}" width="${w}" height="22" rx="6" fill="#2bb8d8" opacity="0.9"/>
      <path d="M${x} ${y+22} H${x+w}" stroke="#1b1b1b" stroke-width="2"/>
      <text x="0" y="${y+16}" text-anchor="middle" font-weight="800" font-size="10" fill="#FAFAF5">VALUE</text>
      <text x="0" y="${y+52}" text-anchor="middle" font-weight="800" font-size="20" fill="#4a0873">${escapeHtml(n.label)}</text>`;
  } else {
    const kind = { start:'GO', funding:'FUNDING', hazard:'HAZARD', fork:'FORK', deck:'DRAW', dice:'EVENT', coin:'EVENT', race:'EVENT' }[n.type] || '';
    const kcol = { start:'#1b6b1f', funding:'#2f8a1c', hazard:'#b3261a', fork:'#4a0873', deck:'#4a0873', dice:'#8a6d00', coin:'#8a6d00', race:'#8a6d00' }[n.type] || '#4a0873';
    const big = n.type==='start' ? n.band : '';
    body = `<text x="0" y="${y+18}" text-anchor="middle" font-weight="800" font-size="10" fill="${kcol}">${kind}</text>
      ${big?`<text x="0" y="${y+44}" text-anchor="middle" font-weight="800" font-size="22" fill="#1b1b1b">${escapeHtml(big)}</text>
      <text x="0" y="${y+h-10}" text-anchor="middle" font-weight="700" font-size="10" fill="#1b6b1f">the garage</text>`
      :`<text x="0" y="${y+h/2+10}" text-anchor="middle" font-weight="800" font-size="13" fill="#1b1b1b">${escapeHtml(shortLabel(n.label))}</text>`}`;
  }
  return `<g id="tile-${n.i}" class="tile tile-${n.type}" transform="translate(${n.cx},${n.cy})">
    <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="6" fill="#1b1b1b" transform="translate(6,7)"/>
    <rect class="tile-face" x="${x}" y="${y}" width="${w}" height="${h}" rx="6" fill="${face}" stroke="#1b1b1b" stroke-width="4"/>
    <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="6" fill="url(#halftone)"/>
    ${idTxt}${body}</g>`;
}
function shortLabel(s){ return s.length>16 ? s.slice(0,15)+'…' : s; }

function buildBoardSVG(){
  // the raised cyan road = polyline through node centers, drawn behind the tiles.
  let d='M '+NODES[0].cx+' '+NODES[0].cy;
  for(let i=1;i<NODES.length;i++) d+=' L '+NODES[i].cx+' '+NODES[i].cy;
  const road = `<path d="${d}" fill="none" stroke="#1b1b1b" stroke-width="22" stroke-linejoin="round" stroke-linecap="round"/>
    <path d="${d}" fill="none" stroke="#3fc6e2" stroke-width="13" stroke-linejoin="round" stroke-linecap="round"/>
    <path d="${d}" fill="none" stroke="#FAFAF5" stroke-width="2.5" stroke-dasharray="2 12" stroke-linecap="round"/>`;
  const tiles = NODES.map(tileSVG).join('');
  return `<svg viewBox="0 0 ${VB_W} ${VB_H}" width="100%" preserveAspectRatio="xMidYMid meet"
      font-family="'Bricolage Grotesque','Inter',sans-serif" class="board-svg-el">
    <defs>
      <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
        <rect width="32" height="32" fill="#2bb8d8"/>
        <path d="M32 0H0V32" fill="none" stroke="#FAFAF5" stroke-width="2" opacity="0.4"/>
      </pattern>
      <pattern id="halftone" width="7" height="7" patternUnits="userSpaceOnUse">
        <circle cx="1" cy="1" r="1.15" fill="#1b1b1b" opacity="0.09"/>
      </pattern>
      <g id="regstamp"><rect width="30" height="22" rx="4" fill="#e8e52a" stroke="#1b1b1b" stroke-width="3"/>
        <text x="15" y="16" text-anchor="middle" font-weight="800" font-size="12" fill="#4a0873">REG</text></g>
    </defs>
    <rect x="0" y="0" width="${VB_W}" height="${VB_H}" fill="url(#grid)"/>
    <text x="28" y="40" font-weight="800" font-size="22" fill="#4a0873" opacity="0.85">YOUR PRODUCT'S VALUE →</text>
    ${road}${tiles}</svg>`;
}

// Tokens are HTML spans layered over the SVG; positioned by % of the viewBox so
// they stay glued to the responsive board. The cat rides above its tile, the dog below.
function tokenAnchor(idx, role){
  const n = NODES[Math.max(0, Math.min(NODES.length-1, Math.round(idx)))];
  return { x:n.cx, y:n.cy + (role==='cat' ? -46 : 46) };
}
function placeToken(el, vx, vy, sx=1, sy=1, arc=0){
  el.style.left = (vx/VB_W*100)+'%';
  el.style.top  = (vy/VB_H*100)+'%';
  el.style.transform = `translate(-50%,-50%) translateY(${-arc}px) scale(${sx.toFixed(3)},${sy.toFixed(3)})`;
}
function positionTokens(animate){
  const cat=$('board-cat'), dog=$('board-rival');
  const ca=tokenAnchor(S.boardIdx,'cat'), da=tokenAnchor(S.competitorPos,'dog');
  if(cat) placeToken(cat, ca.x, ca.y);
  if(dog) placeToken(dog, da.x, da.y);
  highlightTile(S.boardIdx);
}
function highlightTile(i){
  document.querySelectorAll('.tile.is-current').forEach(t=>t.classList.remove('is-current'));
  const t=document.getElementById('tile-'+i); if(t) t.classList.add('is-current');
}

// ----- ACTIONS: four deck stacks (the agency draw) + the spinner mount -----
function renderActions(){
  const drawn = S.drewThisTurn;
  const parked = parkedAtGate();
  let html = Object.keys(DECKS).map(k=>{
    const m=DECK_META[k];
    return `<button class="action card-play deck-${k}" data-deck="${k}" ${drawn?'disabled':''}>
      <span class="card-head"><span class="card-suit">${m.suit}</span>${m.label}</span>
      <span class="card-body"><span class="a-desc">${deckDesc(k)}</span></span></button>`;
  }).join('');
  $('actions').innerHTML = html;
  $('actions').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>onDeckDraw(b.dataset.deck)));
  // instruction line reflects the turn phase
  const lab=$('actions-label');
  if(lab){
    if(!drawn) lab.innerHTML = '🎴 <b>Your turn.</b> Draw a card from one of the four decks:';
    else if(parked) lab.innerHTML = '🔒 <b>Gate ahead.</b> Build readiness, then spin to break through:';
    else lab.innerHTML = '🎡 <b>Card drawn.</b> Now spin the wheel to climb the snake:';
  }
}
function deckDesc(k){
  return { rnd:'Build data that survives review. Slow, costly, clean.',
    enroll:'Open sites, enroll patients. Fast progress, messier data.',
    fda:'Meet the agency. Buys goodwill, slows the competition.',
    money:'', funding:'Raise the war chest. Refills capital; dilutes a little.' }[k] || '';
}
function parkedAtGate(){ const n=NODES[S.boardIdx]; if(!n||n.type!=='milestone') return false;
  return S.readiness < (MILESTONE_NEED[S.pathway][n.slot]||0); }

function renderLog(){ $('log-entries').innerHTML = S.log.slice().reverse().map(e=>`<div class="entry ${e.cls||''}">${e.text}</div>`).join(''); }
function pushLog(text,cls){ S.log.push({text,cls}); }

// ============================================================================
// TURN LOOP  —  DRAW (agency) → SPIN (fate) → CLIMB (cost) → LAND (consequence)
// ============================================================================

// (1) DRAW — player taps a deck. A random card flips face-up; its effect applies;
//     the idle burn hits (stalling is never free); the spinner unlocks.
function onDeckDraw(deckId){
  if(S.status!=='playing' || S.drewThisTurn) return;
  const deck = DECKS[deckId]; if(!deck) return;
  const card = deck[Math.floor(Math.random()*deck.length)];
  drawAndFlip(DECK_META[deckId].label, card, () => {
    applyCard(card, deckId);
    if(deckId==='fda') S.competitorPos = Math.max(0, S.competitorPos - 1); // engaging the agency buys breathing room
    S.res.capital -= IDLE_BURN;                                            // FIX-2: the lights stay on
    S.drewThisTurn = true;
    pushLog(`Turn ${S.turn}: drew “${pwField(card,'name')}” from ${DECK_META[deckId].label}.${card.integrity?' (integrity flag +1 — Dr. Vance keeps a ledger)':''}`, card.k==='bad'?'bad':card.k==='good'?'good':'turn');
    clamp();
    if(checkEnd()) return;
    if(card.skip){                                                         // Clinical Hold etc — you lose the spin this turn
      pushLog('Dosing stopped. You lose your spin and the turn passes.', 'bad');
      renderHUD(); renderActions();
      return endTurn();
    }
    renderHUD(); renderActions();
    if(spinner) spinner.enable();
  });
}

// Apply a drawn deck card with character passives (mirrors the 2018 board bonuses).
function applyCard(card, deckId){
  const tag = DECK_META[deckId].tag;
  let e = Object.assign({}, card.e || {});
  // Lawyer softens bad news; Doctor cheapens study burn; Professor raises bigger.
  if(S.char.badNewsShield){ if(e.c<0) e.c=Math.round(e.c*S.char.badNewsShield); if(e.r<0) e.r=Math.round(e.r*S.char.badNewsShield); }
  if(tag==='study' && S.char.studyCostMult && e.c<0) e.c=Math.round(e.c*S.char.studyCostMult);
  if(card.isRaise){
    if(S.char.raiseBonus) e.c=Math.round((e.c||0)*S.char.raiseBonus);
    if(S.char.raiseNoRepHit && !S.raiseUsedNoHit){ e.r=0; S.raiseUsedNoHit=true; }
  }
  applyDelta(rawToDelta(e));
  if(deckId==='rnd' && S.char.cleanBonus) S.res.data += S.char.cleanBonus;  // Scientist's kitchen-sink rigor
  if(card.ready) S.readiness += card.ready;
  if(card.integrity){ S.integrity += card.integrity; S.dogSurge = 1.5; }    // rushing wakes the competition
  // NOTE: card.skip (lose-a-turn) is handled by the CALLER (onDeckDraw / forcedDeckDraw),
  // never here — applyCard only mutates resources, it must not drive the turn loop.
}

// (3) SPIN → (4) CLIMB — wired from the spinner's onResult. Climb up to `steps`
// squares, burning capital each one. Gates HALT the climb until readiness is met;
// the submission gate ALWAYS halts (the only path to Dr. Vance). Bankruptcy can
// strike mid-climb — fail loud, right where the money runs out.
function onSpin(steps, capBonus){
  if(S.status!=='playing') return;
  if(capBonus) S.res.capital += capBonus;   // FIX-4: slow & frugal — a 1 isn't strictly worst
  climbSteps(steps);
}

function climbSteps(steps){
  let moved = 0;
  const hop = () => {
    if(moved >= steps || S.boardIdx >= NODES.length-1){ return afterClimb(); }
    const here = NODES[S.boardIdx];
    // To LEAVE a milestone gate you must pay its readiness need (FIX-1: gates halt).
    if(here.type==='milestone'){
      const need = MILESTONE_NEED[S.pathway][here.slot] || 0;
      if(here.sp.submission){
        if(S.readiness >= need){ S.reviewOpened=true; S.clearedSubmission=true; return openReview(); }
        return afterClimb();                  // parked at Dr. Vance's door, not ready
      }
      if(S.readiness < need){ return afterClimb(); }   // blocked — park ON the gate
      S.readiness -= need;                     // pay to pass; keep the remainder as a head start
      pushLog(`Cleared the ${MILESTONE_LABEL[S.pathway][here.slot]} gate.`, 'good');
      // Device player's single defining decision, at the Pivotal gate. P3 fix: step
      // OFF the gate FIRST, then fork — otherwise resolveChoice resumes the climb on the
      // same gate node, sees readiness already spent, and PARKS forever (device freeze).
      if(here.sp.deviceFork && S.pathway==='device' && !S.devForkDone){
        S.devForkDone = true;
        S.boardIdx += 1;
        S.res.value = Math.max(S.res.value, NODES[S.boardIdx].pct);
        S.res.capital -= burn(S.boardIdx);
        positionTokens(false);
        if(S.res.capital <= 0) return lose('bankrupt');
        S.pendingResume = { steps: steps - moved - 1 };   // -1 for the square just consumed
        return showChoice(DEVICE_FORK);
      }
    }
    // step forward one square
    S.boardIdx += 1;
    S.res.value = Math.max(S.res.value, NODES[S.boardIdx].pct);   // position IS value (never sinks below where you stand)
    S.res.capital -= burn(S.boardIdx);                            // climbing costs fuel
    animateHopTo(S.boardIdx, () => {
      renderHUD();
      if(S.res.capital <= 0){ return lose('bankrupt'); }
      moved++; hop();
    });
  };
  if(window.SFX) SFX.whoosh();
  hop();
}

// One comic squash/stretch hop of the cat to a node, then callback (ux-patterns Pattern 4).
function animateHopTo(idx, done){
  const el=$('board-cat'); const to=tokenAnchor(idx,'cat');
  highlightTile(idx);
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(reduce || !el){ placeToken(el, to.x, to.y); if(window.SFX) SFX.tick(); return done(); }
  const from = { x: parseFloat(el.style.left||'0')/100*VB_W, y: parseFloat(el.style.top||'0')/100*VB_H };
  const t0=performance.now(), dur=300;
  const easeOutBack=t=>{ const c1=1.70158,c3=c1+1; return 1+c3*Math.pow(t-1,3)+c1*Math.pow(t-1,2); };
  (function frame(now){
    let p=Math.min(1,(now-t0)/dur), e=easeOutBack(p);
    const x=from.x+(to.x-from.x)*e, y=from.y+(to.y-from.y)*e, arc=Math.sin(Math.PI*p)*22;
    let sx=1, sy=1;
    if(p<0.15){ const k=p/0.15; sx=1+0.18*(1-k); sy=1-0.22*(1-k); }
    else if(p<0.7){ sy=1.14; sx=0.9; }
    else { const k=(p-0.7)/0.3; sy=1-0.16*Math.sin(Math.PI*k); sx=1+0.16*Math.sin(Math.PI*k); }
    placeToken(el,x,y,sx,sy,arc);
    if(p<1) requestAnimationFrame(frame);
    else { placeToken(el,to.x,to.y,1,1,0); if(window.SFX) SFX.tick(); done(); }
  })(t0);
}

// After the climb settles: fire the LANDED square's trigger (pass-through squares
// don't fire — you only trip the wire you stop on).
function afterClimb(){
  clamp();
  if(checkEnd()) return;
  land(NODES[S.boardIdx]);
}

// (5) LAND — the landed square's consequence. Reuses the existing event machinery.
function land(sq){
  highlightTile(sq.i);
  if(sq.e) applyDelta(rawToDelta(sq.e));   // top-level raw deltas (existing path)
  const sp = sq.sp;
  if(!sp || sp.type==='none' || sq.type==='value' || sq.type==='start'){
    if(sq.type==='value' && sq.e) showEvent(sq, rawToDelta(sq.e), '', false);
    else { clamp(); return endTurn(); }
    return; // value event modal closes -> endTurn via closeEvent
  }
  switch(sp.type){
    case 'funding': if(window.SFX) SFX.coin(); showEvent(sq, rawToDelta(sq.e), '', false); break;
    case 'hazard': {
      let skip=false;
      if(sp.skip){ skip=true; }
      if(window.SFX) SFX.thud();
      if(sp.bankruptIfBroke && S.res.capital <= BANKRUPT_FLOOR){ showEvent(sq, rawToDelta(sq.e), ' — and the tank is dry', false); S._pendingBust=true; }
      showEvent(sq, rawToDelta(sq.e), '', skip);
      if(skip){ S.turn++; S.competitorPos += dogStep(); }
      break;
    }
    case 'coin': { const heads=Math.random()<0.5; const br=heads?sp.heads:sp.tails; const applied=rawToDelta(br); applyDelta(applied);
      showEvent(sq, applied, heads?' (the coin landed your way)':' (the coin did not)', false); break; }
    case 'dice': { const faces=['check','x','bang','at']; const f=faces[Math.floor(Math.random()*4)]; const br=sp[f]||{}; const applied=rawToDelta(br); applyDelta(applied);
      let skip=!!br.skip; if(skip){ S.turn++; S.competitorPos+=dogStep(); }
      showEvent(sq, applied, ` (rolled ${({check:'✓',x:'✗',bang:'!',at:'@'})[f]})`, skip); break; }
    case 'race': { const ahead=S.boardIdx >= S.competitorPos; const br=ahead?sp.ahead:sp.behind; const applied=rawToDelta(br); applyDelta(applied);
      showEvent(sq, applied, ahead?' (you were ahead)':' (you were behind)', false); break; }
    case 'fork':
      // P3: a broke player who lands on Get-Acquired is force-sold (the board's
      // "mandatory sell" lifeline) rather than bankrupting a square later — revives the
      // ACQUIRED outcome (0 in 360k bot games) as a real broke-at-the-top exit.
      if(sq.sp.a && sq.sp.a.cashOut && S.res.capital < BANKRUPT_FLOOR){
        S.status='won'; S.outcome='acquired';
        pushLog(`Out of runway, you took the forced buyout at ${valueLabel(S.res.value)}.`, 'good');
        return endGame();
      }
      return showChoice(sq);
    case 'deck': return forcedDeckDraw(sq);
    case 'exit': S.status='won'; S.outcome='approved'; return endGame();
    default: clamp(); return endTurn();
  }
}

// A board square that forces a draw from a named deck (the "Draw: R&D" etc squares).
function forcedDeckDraw(sq){
  const deckId = sq.sp.deck, deck = DECKS[deckId];
  const card = deck[Math.floor(Math.random()*deck.length)];
  applyCard(card, deckId);
  if(deckId==='fda') S.competitorPos = Math.max(0, S.competitorPos - 1);
  if(card.skip){ S.turn++; S.competitorPos += dogStep(); }   // a forced lose-a-turn still bites
  const synthetic = { t:`Forced draw — ${pwField(card,'name')}`, f:pwField(card,'f'), k:card.k };
  showEvent(synthetic, rawToDelta(card.e||{}), card.ready?` (+${card.ready} readiness)`:'', !!card.skip);
  // (sq.sp.alsoReg — the painted "draw twice" — is a v2 flourish; one pull for now.)
}

// ============================================================================
// CARD FLIP (deck draw) — the player's one moment of pure agency in a turn
// otherwise ruled by dice and regulators. Give it weight (ux-patterns Pattern 2).
// ============================================================================
function drawAndFlip(deckName, card, onSettled){
  const overlayEl=$('overlay-flip'), suit=DECK_META[Object.keys(DECK_META).find(k=>DECK_META[k].label===deckName)]?.suit || '★';
  const kind=card.k||'swing';
  overlayEl.querySelector('.flip-mount').innerHTML = `
    <div class="flip-scene"><div class="flip-card" id="flip-card">
      <div class="flip-back"><div class="reg-stamp">REG</div><div class="deck-name">${escapeHtml(deckName)}</div></div>
      <div class="flip-face ${kind}">
        <span class="fc-suit">${suit}</span>
        <div class="fc-kind">${kind==='good'?'✦ Good news':kind==='bad'?'⚠ Bad news':'⚖ It could go either way'}</div>
        <h3>${escapeHtml(pwField(card,'name'))}</h3>
        <div class="fc-flavor">${linkJargon(pwField(card,'f')||'')}</div>
        <div class="fc-effect">${effectChips(card)}</div>
      </div></div></div>
    <button class="btn-primary" id="flip-ok">Take it →</button>`;
  overlayEl.classList.add('active');
  const cardEl=overlayEl.querySelector('#flip-card');
  void cardEl.offsetWidth;
  if(window.SFX) SFX.flip();
  requestAnimationFrame(()=>requestAnimationFrame(()=>cardEl.classList.add('is-flipped')));
  const close=()=>{ overlayEl.classList.remove('active'); onSettled && onSettled(card); };
  overlayEl.querySelector('#flip-ok').addEventListener('click', close, { once:true });
}
function effectChips(card){
  const parts=[];
  const e=card.e||{};
  const lab={c:'$',d:'Data',r:'Goodwill',v:'Value'};
  for(const[k,v]of Object.entries(e)){ if(!v)continue; const num=k==='c'?`${v>0?'+':''}${v}M`:`${v>0?'+':''}${v*(k==='d'||k==='r'?6:1)}`;
    parts.push(`<span class="${v>0?'up':'down'}">${lab[k]} ${num}</span>`); }
  if(card.ready) parts.push(`<span class="up">Readiness +${card.ready}</span>`);
  if(card.integrity) parts.push(`<span class="down">⚑ integrity</span>`);
  if(card.skip) parts.push(`<span class="down">lose a turn</span>`);
  return parts.join(' &nbsp; ');
}

// ============================================================================
// EVENTS — board-square modal (reuses the existing #overlay-event card).
// ============================================================================
function showEvent(card, applied, note, skip){
  const box=$('event-card'); box.className='card-modal '+(card.k||'swing');
  $('event-kind').textContent = card.k==='good'?'✦ Good news':card.k==='bad'?'⚠ Bad news':'⚖ It could go either way';
  $('event-title').textContent = card.t || pwField(card,'label');
  $('event-flavor').innerHTML = linkJargon(pwField(card,'f')) + (note?escapeHtml(note):'');
  $('event-effect').innerHTML = effectSummary(applied, skip).replace(/^\(|\)$/g,'').split(', ').map(p=>`<span class="${/[-]/.test(p)||/lose/.test(p)?'down':'up'}">${p}</span>`).join(' &nbsp; ');
  $('overlay-event').classList.add('active');
  if(card.k==='bad') document.body.classList.add('shake');
}
function closeEvent(){
  $('overlay-event').classList.remove('active'); document.body.classList.remove('shake');
  clamp();
  if(S._pendingBust){ S._pendingBust=false; return lose('bankrupt'); }
  if(checkEnd()) return;
  endTurn();
}
function effectSummary(applied, skip){
  const names={capital:'$',data:'Data',reputation:'Goodwill',value:'Value'};
  const parts=[]; for(const[k,v]of Object.entries(applied||{})){ if(!v)continue; const raw=Math.round(v);
    parts.push(`${names[k]||k} ${v>0?'+':''}${raw}${k==='capital'?'M':''}`); }
  if(skip) parts.push('lose a turn');
  return parts.length?'('+parts.join(', ')+')':'(no net effect)';
}

// ----- Choice forks (Hire CRO / Fire CEO / Get Acquired / device 510k-vs-PMA) -----
let _choiceCard=null;
function showChoice(card){
  _choiceCard=card;
  $('choice-title').textContent = card.t || card.label;
  $('choice-flavor').innerHTML = linkJargon(card.f);
  const optBtn=(key,o)=>o?`<button class="btn-primary choice-opt" data-opt="${key}">${escapeHtml(o.label)}</button>`:'';
  $('choice-options').innerHTML = optBtn('a',card.sp.a)+optBtn('b',card.sp.b)+optBtn('c',card.sp.c);
  $('choice-options').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>resolveChoice(b.dataset.opt)));
  $('overlay-choice').classList.add('active');
}
function resolveChoice(key){
  const card=_choiceCard, opt=card.sp[key];
  $('overlay-choice').classList.remove('active');
  if(opt.cashOut){ S.status='won'; S.outcome='acquired'; pushLog(`Accepted the buyout at ${valueLabel(S.res.value)}. Exit before approval — a partial win.`, 'good'); return endGame(); }
  const applied=rawToDelta(opt); applyDelta(applied);
  pushLog(`${card.t||card.label}: chose “${opt.label}”. ${effectSummary(applied,false)}`, '');
  clamp();
  // device fork mid-climb: resume the remaining climb steps
  if(S.pendingResume){ const r=S.pendingResume; S.pendingResume=null; if(checkEnd())return; return climbSteps(r.steps); }
  if(checkEnd()) return;
  endTurn();
}

// ============================================================================
// END OF TURN — the dog gains, the clock ticks, control returns to the player.
// ============================================================================
function endTurn(noSpinHappened){
  if(S.status!=='playing'){ return; }
  advanceCompetitor();
  S.turn += 1;
  S.drewThisTurn = false;
  S.dogSurge = 0;
  clamp();
  if(checkEnd()) return;
  if(spinner) spinner.disable();
  renderAll();
}
function advanceCompetitor(){
  S.competitorPos += dogStep() + (S.dogSurge||0);
  if(S.competitorPos>=FIRST_TO_FILE && S.status==='playing' && !S.clearedSubmission){
    if(S.char.investorScoopSave && !S.investorScoopSaved){
      S.investorScoopSaved=true; S.competitorPos=30;
      pushLog("A delay at the competitor's site buys you one more turn.", 'good'); return;
    }
    lose('beaten_to_market');
  }
}

// ============================================================================
// CORE STATE MUTATION
// ============================================================================
function rawToDelta(raw){ const m={c:'capital',d:'data',r:'reputation',v:'value'}; const out={};
  for(const[k,v]of Object.entries(raw||{})){ if(m[k]) out[m[k]]=v; } return out; }
function applyDelta(delta){
  for(const[k,v]of Object.entries(delta||{})){
    if(!v) continue;
    if(k==='capital') S.res.capital += v;        // raw $M
    else if(k==='value') S.res.value += v;       // raw pct points (bonus above the position floor)
    else if(k in S.res) S.res[k] += v*(SCALE[k]||1);
    else if(k==='competitor') S.competitorPos += v;
  }
}
function clamp(){
  S.res.reputation=Math.max(0,Math.min(100,S.res.reputation));
  S.res.data=Math.max(0,Math.min(100,S.res.data));
  S.res.value=Math.max(0,Math.min(100,S.res.value));
  S.competitorPos=Math.max(0,S.competitorPos);
}

// ============================================================================
// FDA REVIEW (Dr. Eleanor Vance) — reached ONLY through the submission gate.
// ============================================================================
function openReview(){
  $('review-input-stage').style.display=''; $('review-result-stage').style.display='none';
  $('review-text').value='';
  $('review-reviewer').textContent='Dr. Eleanor Vance · Division of Regulatory Reckoning';
  $('overlay-review').classList.add('active'); $('review-text').focus();
}
async function submitReview(){
  const rationale=$('review-text').value.trim() || 'We respectfully submit our application for review.';
  $('btn-submit-review').disabled=true; $('btn-submit-review').textContent='Dr. Vance is reading…';
  let result;
  try {
    const resp=await fetch('/api/game/review',{ method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ pathway:S.pathway, therapeutic_area:S.seed.therapeutic_area, phase:S.seed.phase,
        submission_rationale:rationale, evidence_score:clampN(S.res.data), reputation_score:clampN(S.res.reputation),
        integrity_flags:S.integrity, product_name:S.seed.intervention_name }) });
    result=await resp.json();
  } catch(e){ result=localReview(); }
  $('btn-submit-review').disabled=false; $('btn-submit-review').textContent='Submit to FDA →';
  showReviewResult(result);
}
function clampN(v){ return Math.max(0,Math.min(100,Math.round(v))); }
function localReview(){
  // Mirror the server's data-dominant verdict (0.80*data + 0.15*rep − integrity*10,
  // thresholds 70/50/30) so a fetch-failure fallback isn't a different difficulty.
  const s = 0.80*S.res.data + 0.15*S.res.reputation - S.integrity*10;
  const v = s>=70?'APPROVED':s>=50?'APPROVABLE_WITH_DEFICIENCIES':s>=30?'COMPLETE_RESPONSE_LETTER':'REFUSE_TO_FILE';
  const mod={APPROVED:18,APPROVABLE_WITH_DEFICIENCIES:6,COMPLETE_RESPONSE_LETTER:-12,REFUSE_TO_FILE:-22}[v];
  return { verdict:v, reviewer_name:'Dr. Eleanor Vance (offline)', letter:'The Division has reviewed your submission.', score_modifier:mod, source:'scripted' };
}
let _pendingVerdict=null;
function showReviewResult(result){
  _pendingVerdict=result;
  $('review-input-stage').style.display='none'; $('review-result-stage').style.display='';
  const badge=$('review-badge'); badge.className='review-badge '+(result.source==='llm'?'llm':'scripted');
  badge.textContent=result.source==='llm'?'AI reviewer':'Reviewer';
  $('review-letter').textContent=result.letter;
  $('review-reviewer').textContent=result.reviewer_name||'Division of Regulatory Reckoning';
  $('review-verdict').textContent='VERDICT: '+result.verdict.replace(/_/g,' ');
}
function afterReview(){
  const v=_pendingVerdict; $('overlay-review').classList.remove('active');
  S.reviewModifier=v.score_modifier||0;
  if(v.verdict==='APPROVED'){
    S.boardIdx=NODES.length-1; S.res.value=Math.max(S.res.value,97); positionTokens(false);
    S.status='won'; S.outcome='approved';
    pushLog(`FDA: APPROVED. ${S.reviewModifier>=0?'+':''}${S.reviewModifier} to score.`, 'good'); return endGame();
  }
  if(S.res.reputation<=0){ return lose('clinical_hold'); }
  // Any non-approval: pay the fix cost, drop back to the submission gate, refile.
  const harsh = v.verdict==='REFUSE_TO_FILE' || v.verdict==='COMPLETE_RESPONSE_LETTER';
  applyDelta({ capital: harsh?-3:-2, reputation: harsh?-1:0 });
  const need=MILESTONE_NEED[S.pathway][4]||0;
  S.readiness=Math.max(0, need - (S.char.badNewsShield?4:2));   // P3: defang the refile death-spiral (was need-8/-12)
  S.reviewOpened=false;
  S.turn += 1;                                                  // P3: a refile costs ONE turn, not two — a real second swing
  S.competitorPos += dogStep();
  pushLog(`FDA: ${v.verdict.replace(/_/g,' ')}. Address the deficiencies and refile.`, 'bad');
  clamp();
  if(checkEnd()) return;
  if(spinner) spinner.disable();
  S.drewThisTurn=false;
  renderAll();
}

// ============================================================================
// WIN / LOSE / SCORE
// ============================================================================
function checkEnd(){
  if(S.status!=='playing') return true;
  if(S.res.capital<=0) return lose('bankrupt');
  if(S.competitorPos>=FIRST_TO_FILE && !S.clearedSubmission) return lose('beaten_to_market');
  if((S.maxTurns-S.turn+1)<=0) return lose('failed_endpoint');
  return false;
}
function lose(outcome){ if(S.status!=='playing') return true; S.status='lost'; S.outcome=outcome; endGame(); return true; }

function computeScore(){
  const valuePct=S.res.value, comp=Math.round(S.competitorPos/FIRST_TO_FILE*100);
  if(S.outcome==='approved'){
    const t=Math.max(0,S.maxTurns-S.turn+1);
    return Math.max(0, Math.round(1000 + t*25 + S.res.capital*4 + S.res.data*5 + S.res.reputation*3 + S.reviewModifier*15 + S.difficulty*120 - S.integrity*20 - comp));
  }
  if(S.outcome==='acquired'){
    return Math.max(0, Math.round(400 + valuePct*9 + S.res.capital*4 + S.res.data*2 + S.difficulty*80 - S.integrity*15));
  }
  // A loss is a "dignified failure" — scored by how far you climbed — but it must
  // NEVER out-rank a real win on the leaderboard (Race to Approval, not Race to
  // Bankruptcy). Cap it below the approval base (1000). (Phase-3 balance may refine.)
  const lossRaw = S.boardIdx*14 + valuePct*2 + S.res.data*0.5 + Math.max(0,S.res.capital)*0.5;
  return Math.max(0, Math.min(800, Math.round(lossRaw)));   // P3: cap 800 < win floor 1905; *14 keeps the gradient alive (early bust ~200, deep dignified failure ~770)
}

async function endGame(){
  const won=S.outcome==='approved', acquired=S.outcome==='acquired';
  const score=computeScore();
  const box=$('end-box'); box.className='end-modal '+(won||acquired?'won':'lost');
  const copy=won?WIN_COPY:acquired?ACQUIRED_COPY:(LOSE_COPY[S.outcome]||{title:'GAME OVER',sub:''});
  $('end-title').textContent=copy.title; $('end-sub').textContent=copy.sub;
  $('end-score').style.display=''; $('end-score').textContent=score.toLocaleString();
  $('end-title2').textContent=rankTitle(S.outcome, score);
  $('end-rank').textContent='Submitting your run…';
  $('overlay-end').classList.add('active');
  if(window.SFX){ if(won||acquired) SFX.coin(); else SFX.thud(); }
  let rankInfo=null;
  try {
    const resp=await fetch('/api/game/score',{ method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ first_name:player.first,last_name:player.last,email:player.email,score,turns_taken:S.turn,
        outcome:S.outcome==='acquired'?'approved':S.outcome,
        trial_nct_id:S.seed.nct_id,trial_title:S.seed.title,pathway:S.pathway,difficulty:String(S.difficulty)})});
    if(resp.ok) rankInfo=await resp.json();
  } catch(e){}
  $('end-rank').textContent = rankInfo
    ? `Rank #${rankInfo.your_rank} of ${rankInfo.total_players} sponsors${rankInfo.is_personal_best?' · personal best! 🎉':''}`
    : '(could not reach the leaderboard)';
  loadLeaderboard($('end-leaderboard'));
}

// ============================================================================
// LEADERBOARD
// ============================================================================
async function loadLeaderboard(tableEl){
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
function showLeaderboardStandalone(){
  const box=$('end-box'); box.className='end-modal';
  $('end-title').textContent='🏆 Hall of Sponsors'; $('end-title2').textContent='';
  $('end-sub').textContent='The fastest to FDA approval, the smartest exits, and the bravest failures.';
  $('end-score').style.display='none'; $('end-rank').textContent='';
  $('overlay-end').classList.add('active'); loadLeaderboard($('end-leaderboard'));
  $('btn-play-again').textContent = player?'Play again':'Play';
}

// ============================================================================
// UTIL
// ============================================================================
function flashRes(cls){ const el=$('res-'+cls); if(!el)return; el.classList.add('flash'); setTimeout(()=>el.classList.remove('flash'),500); }
function escapeHtml(s){ return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

// ============================================================================
// SPINNER — a comic die-cut wheel, lands honestly on 1..4 (ux-patterns Pattern 1).
// Chance with an honest face: the wheel must STOP where it SAYS, or the player
// stops trusting the board — and trust is the only currency a game really runs on.
// ============================================================================
const SPIN_WEDGES=[{n:1,fill:'#2bb8d8'},{n:2,fill:'#e8e52a'},{n:3,fill:'#5bb545'},{n:4,fill:'#f5841f'}];
function spinnerSVG(){
  const cx=74,cy=74,r=70; const pt=(deg)=>[cx+r*Math.cos(deg*Math.PI/180), cy+r*Math.sin(deg*Math.PI/180)];
  let paths='';
  SPIN_WEDGES.forEach((w,i)=>{ const a0=i*90-90,a1=a0+90; const [x0,y0]=pt(a0),[x1,y1]=pt(a1);
    paths+=`<path d="M${cx},${cy} L${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z" fill="${w.fill}" stroke="#1b1b1b" stroke-width="3"/>`;
    const [tx,ty]=pt(a0+45),mx=cx+(tx-cx)*0.62,my=cy+(ty-cy)*0.62;
    paths+=`<text x="${mx.toFixed(1)}" y="${(my+6).toFixed(1)}" text-anchor="middle" font-family="Bricolage Grotesque, sans-serif" font-weight="800" font-size="28" fill="#1b1b1b">${w.n}</text>`; });
  return `<svg viewBox="0 0 148 148" class="spinner-wheel" id="spin-wheel"><circle cx="74" cy="74" r="71" fill="none" stroke="#1b1b1b" stroke-width="5"/>${paths}</svg>`;
}
function makeSpinner(containerEl, onResult){
  containerEl.classList.add('spinner-wrap');
  containerEl.innerHTML = `<div class="spinner-stage"><div class="spinner-pointer"></div>${spinnerSVG()}<div class="spinner-hub">REG</div></div>
    <button class="spinner-btn" id="spin-go" disabled>SPIN ▶</button><div class="spinner-result" id="spin-out"></div>`;
  const wheel=containerEl.querySelector('#spin-wheel'), btn=containerEl.querySelector('#spin-go'), out=containerEl.querySelector('#spin-out');
  let turns=0;
  btn.addEventListener('click', ()=>{
    btn.disabled=true; out.textContent='';
    const steps=1+Math.floor(Math.random()*4);
    const targetCenter=(steps-1)*90+45, jitter=(Math.random()*36-18);
    turns+=4+Math.floor(Math.random()*2);
    wheel.style.transform=`rotate(${turns*360 - targetCenter + jitter}deg)`;
    if(window.SFX) SFX.spinnerTicks(2700);
    // P3 fix (double-climb): the 3100ms fallback used to fire onResult a SECOND time
    // (the SPIN button stays disabled through the whole climb, so its `if(btn.disabled)`
    // guard never blocked it), running climbSteps twice — double-burn, double-trigger.
    // A one-shot `settled` flag guarantees onResult fires exactly once.
    let settled=false;
    const done=()=>{ if(settled) return; settled=true;
      wheel.removeEventListener('transitionend',done);
      const capBonus = steps===1 ? 4 : 0;
      out.textContent=`Move ${steps} ${steps===1?'square (+$4M)':'squares'} →`;
      onResult(steps, capBonus); };
    wheel.addEventListener('transitionend', done, { once:true });
    setTimeout(done, 3100);   // safety net only; the settled guard prevents a second climb
  });
  return { enable(){ btn.disabled=false; }, disable(){ btn.disabled=true; }, el:btn };
}

// ============================================================================
// GLOSSARY — the self-building "learn more" dictionary (unchanged; every door openable)
// ============================================================================
const GLOSSARY_TERMS=[
  'Type B meeting','Type A meeting','dilute the cap table','cap table',
  'Complete Response Letter','refuse-to-file','refuse to file','primary endpoint',
  'benefit-risk','breakthrough therapy','breakthrough','orphan drug',
  'advisory committee','priority review voucher','substantial equivalence',
  'post-market surveillance','post-market','integrity flag','product value',
  'down round','Series B','boot-strap','bootstrap','expanded access','pivotal',
  'Form 483','510(k)','NDA/BLA','PDUFA','AdComm','RMAT','CMC','CRO','KOL','CRL',
  'IND','NDA','BLA','PMA','483','readiness','goodwill',
  'Get Acquired','acquisition','acquired','accelerated approval','surrogate endpoint',
  'confirmatory trial','real-world evidence','Warning Letter','De Novo','Q-Sub',
  'boxed warning','interim analysis','valuation',
  // device + biologic vocabulary — the Board Mode pathway-correct terms, so the
  // self-building dictionary can teach them too (tap to learn, generated on first ask).
  'Pre-Sub','Q-Sub','pre-submission','Safer Technologies Program','STeP','Breakthrough Device',
  'Humanitarian Use Device','HDE','HUD','Parallel Review','Not Substantially Equivalent','NSE',
  'IDE','Refuse to Accept','RTA','design controls','design verification','QMS','DHF','EIR',
  'Early Feasibility Study','EFS','MDUFA','CDRH','CMS','NCD','potency assay','predicate',
];
const GLOSSARY_SORTED=[...GLOSSARY_TERMS].sort((a,b)=>b.length-a.length);
function _escRe(s){ return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'); }
function linkJargon(text){
  if(!text) return '';
  const ph=[]; let work=String(text);
  for(const term of GLOSSARY_SORTED){
    const re=new RegExp('(?<![\\w/])('+_escRe(term)+')(?![\\w])','i');
    const m=work.match(re);
    if(m){ work=work.replace(re,' '+ph.length+' '); ph.push({term,hit:m[1]}); }
  }
  let html=escapeHtml(work);
  ph.forEach((p,i)=>{ html=html.replace(' '+i+' ', `<span class="jr" data-term="${escapeHtml(p.term)}" title="What's this? Tap to learn">${escapeHtml(p.hit)}</span>`); });
  return html;
}
async function openGlossary(term){
  $('gloss-term').textContent=term; $('gloss-def').textContent='Looking it up…'; $('gloss-actions').innerHTML='';
  $('overlay-glossary').classList.add('active');
  try { const r=await fetch('/api/game/glossary?term='+encodeURIComponent(term)); renderGloss(await r.json()); }
  catch(e){ $('gloss-def').textContent='Could not load a definition right now.'; }
}
function renderGloss(d){
  $('gloss-term').textContent=d.term; $('gloss-def').textContent=d.definition;
  const badge=d.source==='seed'?'<span class="gloss-badge seed">curated</span>':d.source==='llm'?'<span class="gloss-badge llm">AI-written</span>':'<span class="gloss-badge pending">brand new</span>';
  let html=badge; if(d.regenerable) html+='<button class="ghost-btn" id="gloss-regen">↻ Improve this</button>';
  $('gloss-actions').innerHTML=html;
  if(d.regenerable) $('gloss-regen').onclick=()=>regenGloss(d.term);
}
async function regenGloss(term){
  $('gloss-def').textContent='Asking the dictionary to do better…'; $('gloss-actions').innerHTML='';
  try { const r=await fetch('/api/game/glossary/regenerate?term='+encodeURIComponent(term),{method:'POST'}); renderGloss(await r.json()); }
  catch(e){ $('gloss-def').textContent='Could not regenerate right now.'; }
}
document.addEventListener('click', (e)=>{ const j=e.target.closest('.jr'); if(j&&j.dataset.term) openGlossary(j.dataset.term); });

// ============================================================================
// SPINNER MOUNT — wire the spinner into the play screen once the DOM is ready.
// The SPIN button stays disabled until a card is drawn this turn (the locked loop).
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
  const mount=$('spinner-mount');
  if(mount) spinner=makeSpinner(mount, (steps, capBonus)=>onSpin(steps, capBonus));
});
