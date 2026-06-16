Brand vars confirmed. Now I'll deliver the full game content.

---

# THE STRATEGY GAME (for regulatory affairs) — v2 Web Content
### Game data, ready to drop into code. Voice: rigorously unhinged, satirical, true to reg-life.

State variables (per board archaeology): **Capital** (cash), **Data** (clinical/CMC evidence), **Reputation** (FDA/KOL/investor goodwill), and **Product Value** (the valuation track, $100k → $9B). Win = top of the track. Lose = Capital hits zero, a pivotal endpoint fails, or a competitor approves first.

---

## 1. EVENT CARDS

Drop-in JSON. Effects use signed deltas on the four state vars (`capital`, `data`, `reputation`, `value`) plus optional `special` flags the engine reads (`skipTurn`, `clinicalHold`, `gameOver`, `mustChoose`, etc.). `tier` = `good` | `bad` | `swingy`. `deck` = `REG` (regulatory friction) or `STAFF`/`MARKET` where the texture fits but all live in the shuffled event pool. 36 cards (12 good / 12 bad / 12 swingy).

```json
{
  "eventCards": [
    {
      "id": "EVT-001",
      "title": "Breakthrough Therapy Designation",
      "tier": "good",
      "deck": "REG",
      "flavor": "FDA agrees your drug is promising enough to skip ahead in line. You now get to email the same reviewer four times a week, and they have to answer. Bliss.",
      "effect": { "capital": 0, "data": 1, "reputation": 3, "value": 2 },
      "special": ["expeditedReview"]
    },
    {
      "id": "EVT-002",
      "title": "Fast Track Granted",
      "tier": "good",
      "deck": "REG",
      "flavor": "Rolling review unlocked. You may now submit your application in pieces, like a hostage negotiation where the hostage is your NDA and you are also the kidnapper.",
      "effect": { "capital": 0, "data": 0, "reputation": 2, "value": 2 }
    },
    {
      "id": "EVT-003",
      "title": "RMAT Designation",
      "tier": "good",
      "deck": "REG",
      "flavor": "Your cell therapy is a Regenerative Medicine Advanced Therapy. Investors who cannot define 'potency assay' wire you money anyway. The answer was always yes.",
      "effect": { "capital": 4, "data": 0, "reputation": 2, "value": 3 }
    },
    {
      "id": "EVT-004",
      "title": "Patient Advocacy Group Rallies",
      "tier": "good",
      "deck": "MARKET",
      "flavor": "Real patients show up to your AdComm in matching t-shirts and break the panel's heart. The biostatistician's p-value of 0.061 suddenly feels rude to mention.",
      "effect": { "capital": 1, "data": 0, "reputation": 4, "value": 1 }
    },
    {
      "id": "EVT-005",
      "title": "Positive Type B Meeting",
      "tier": "good",
      "deck": "REG",
      "flavor": "FDA agrees with your pivotal trial design in writing. You frame the meeting minutes. You will cite them in three years when they pretend it never happened.",
      "effect": { "capital": 0, "data": 2, "reputation": 2, "value": 1 }
    },
    {
      "id": "EVT-006",
      "title": "Priority Review Voucher",
      "tier": "good",
      "deck": "REG",
      "flavor": "You earned a PRV for your rare pediatric disease drug. You can use it, or sell it for ~$100M to a company that wants to rush a wrinkle cream. Capitalism!",
      "effect": { "capital": 5, "data": 0, "reputation": 0, "value": 2 },
      "special": ["tradeable"]
    },
    {
      "id": "EVT-007",
      "title": "Enrollment Ahead of Schedule",
      "tier": "good",
      "deck": "MARKET",
      "flavor": "Sites are enrolling faster than projected, which has never once happened in recorded history. Enjoy this, it is not real, savor the dream.",
      "effect": { "capital": -1, "data": 3, "reputation": 1, "value": 1 }
    },
    {
      "id": "EVT-008",
      "title": "Clean CMC Inspection",
      "tier": "good",
      "deck": "REG",
      "flavor": "The investigators leave your fill-finish site with zero observations. Your VP of Manufacturing weeps openly in the parking lot. No 483. None. A unicorn.",
      "effect": { "capital": 0, "data": 1, "reputation": 3, "value": 1 }
    },
    {
      "id": "EVT-009",
      "title": "Strong Phase 2 Readout",
      "tier": "good",
      "deck": "MARKET",
      "flavor": "Your stock pops 40% on a press release with the words 'statistically significant' and 'well-tolerated.' Nobody read the secondary endpoints. Don't tell them.",
      "effect": { "capital": 6, "data": 2, "reputation": 1, "value": 3 }
    },
    {
      "id": "EVT-010",
      "title": "KOL Endorsement at Congress",
      "tier": "good",
      "deck": "MARKET",
      "flavor": "The field's most cited investigator calls your mechanism 'genuinely interesting' from the podium. You hear angels. Your competitor hears their valuation deflating.",
      "effect": { "capital": 2, "data": 0, "reputation": 3, "value": 1 }
    },
    {
      "id": "EVT-011",
      "title": "Orphan Drug Designation",
      "tier": "good",
      "deck": "REG",
      "flavor": "Seven years of market exclusivity and a tax credit, because your disease is rare and your accountant is thrilled. The rarest thing in biotech: free money with a clear rationale.",
      "effect": { "capital": 3, "data": 0, "reputation": 1, "value": 2 }
    },
    {
      "id": "EVT-012",
      "title": "Real-World Evidence Accepted",
      "tier": "good",
      "deck": "REG",
      "flavor": "FDA accepts your external control arm built from registry data. The 1990s called and could not believe it. Frame this card. It is a collector's item.",
      "effect": { "capital": 1, "data": 3, "reputation": 1, "value": 1 }
    },

    {
      "id": "EVT-013",
      "title": "Clinical Hold",
      "tier": "bad",
      "deck": "REG",
      "flavor": "FDA has 'questions' about a safety signal. All dosing stops. You will spend the next four months proving that one elevated liver enzyme was the assay's fault and not yours.",
      "effect": { "capital": -2, "data": -1, "reputation": -2, "value": -2 },
      "special": ["skipTurn", "clinicalHold"]
    },
    {
      "id": "EVT-014",
      "title": "Form 483 Issued",
      "tier": "bad",
      "deck": "REG",
      "flavor": "An inspector found 'objectionable conditions' at your site. You have 15 business days to write a response longer than the inspection itself, and to mean it.",
      "effect": { "capital": -2, "data": 0, "reputation": -2, "value": -1 }
    },
    {
      "id": "EVT-015",
      "title": "Refuse-to-File Letter",
      "tier": "bad",
      "deck": "REG",
      "flavor": "FDA won't even REVIEW your application. The 74-day letter lands like a slap with a federal seal. Your filing fee is non-refundable. So is your dignity.",
      "effect": { "capital": -3, "data": -1, "reputation": -3, "value": -3 },
      "special": ["skipTurn"]
    },
    {
      "id": "EVT-016",
      "title": "Complete Response Letter",
      "tier": "bad",
      "deck": "REG",
      "flavor": "Not an approval. Not a denial. A CRL, the regulatory equivalent of 'we need to talk.' The deficiencies are 'CMC and clinical.' That is the whole drug.",
      "effect": { "capital": -3, "data": -2, "reputation": -2, "value": -3 },
      "special": ["skipTurn"]
    },
    {
      "id": "EVT-017",
      "title": "Pivotal Enrollment Shortfall",
      "tier": "bad",
      "deck": "MARKET",
      "flavor": "Your sites enrolled 11% of target in 60% of the timeline. The CRO has 'learnings.' You have a burn rate and a board meeting on Thursday.",
      "effect": { "capital": -2, "data": -2, "reputation": -1, "value": -2 }
    },
    {
      "id": "EVT-018",
      "title": "Government Shutdown",
      "tier": "bad",
      "deck": "REG",
      "flavor": "FDA's user-fee work continues but new meetings freeze. Your PDUFA clock is fine; your sanity is not. Congress will fix this in 34 days, plus or minus a fiscal cliff.",
      "effect": { "capital": -1, "data": 0, "reputation": 0, "value": -1 },
      "special": ["skipTurn"]
    },
    {
      "id": "EVT-019",
      "title": "Site Data Integrity Finding",
      "tier": "bad",
      "deck": "MARKET",
      "flavor": "One investigator may have invented some subjects. You exclude the site, the FDA notices you noticed, and your statistical power evaporates like ethanol off a swab.",
      "effect": { "capital": -2, "data": -3, "reputation": -2, "value": -2 }
    },
    {
      "id": "EVT-020",
      "title": "CMC / Manufacturing Failure",
      "tier": "bad",
      "deck": "REG",
      "flavor": "Three consecutive batches fail the dissolution spec. Your process is 'not yet validated,' which is a kind phrase for 'a science experiment with a PDUFA date.'",
      "effect": { "capital": -3, "data": -1, "reputation": -1, "value": -2 }
    },
    {
      "id": "EVT-021",
      "title": "Reviewer Turnover",
      "tier": "bad",
      "deck": "REG",
      "flavor": "Your primary reviewer left for industry. The new one has not read the file, has different opinions about your endpoint, and emails 'just to align' on a Friday at 5:47pm.",
      "effect": { "capital": 0, "data": 0, "reputation": -2, "value": -1 },
      "special": ["skipTurn"]
    },
    {
      "id": "EVT-022",
      "title": "Post-Market Safety Signal",
      "tier": "bad",
      "deck": "MARKET",
      "flavor": "A FAERS cluster triggers a Drug Safety Communication. Your label grows a boxed warning the size of a billboard. Sales call it 'a positioning challenge.'",
      "effect": { "capital": -2, "data": -1, "reputation": -3, "value": -2 }
    },
    {
      "id": "EVT-023",
      "title": "Investor Down Round",
      "tier": "bad",
      "deck": "MARKET",
      "flavor": "Ms. N. Vested, MBA, leads a financing at half your last valuation 'to be supportive.' Your option pool is now a rounding error. She still wants a board seat.",
      "effect": { "capital": 3, "data": 0, "reputation": -2, "value": -3 }
    },
    {
      "id": "EVT-024",
      "title": "Warning Letter Goes Public",
      "tier": "bad",
      "deck": "REG",
      "flavor": "Your unanswered 483 escalated to a Warning Letter, and FDA posts it on the website with your name in bold. Short-sellers find it before your CEO finishes coffee.",
      "effect": { "capital": -2, "data": 0, "reputation": -4, "value": -3 }
    },

    {
      "id": "EVT-025",
      "title": "Advisory Committee Meeting",
      "tier": "swingy",
      "deck": "REG",
      "flavor": "The AdComm convenes. The panel votes on whether your benefit outweighs your risk, live, in public, while you sit in the front row not allowed to talk.",
      "effect": { "capital": -1 },
      "special": ["coinFlip", "onHeads:{reputation:+4,value:+3}", "onTails:{reputation:-3,value:-3}"]
    },
    {
      "id": "EVT-026",
      "title": "Type A Meeting Requested",
      "tier": "swingy",
      "deck": "REG",
      "flavor": "FDA would 'like to schedule a Type A meeting.' This is either to resolve a dispute in your favor or to explain, gently, why your program is on fire. Roll to find out.",
      "effect": {},
      "special": ["diceOutcome", "✓:{data:+2,value:+2}", "✗:{value:-2,skipTurn:true}", "!:{reputation:-1}", "@:{capital:-1,data:+1}"]
    },
    {
      "id": "EVT-027",
      "title": "Surprise Competitor Filing",
      "tier": "swingy",
      "deck": "MARKET",
      "flavor": "A rival you forgot existed just filed in your indication. If they read out first, you are second-to-market with a press release nobody reprints. Unless you sprint.",
      "effect": { "reputation": -1 },
      "special": ["raceTrigger", "ifAheadInData:{value:+2}", "ifBehindInData:{value:-3}"]
    },
    {
      "id": "EVT-028",
      "title": "KOL Feud",
      "tier": "swingy",
      "deck": "MARKET",
      "flavor": "Two giants of the field publicly disagree about your mechanism in dueling editorials. Drama is engagement. Whoever your data supports just got very, very loud.",
      "effect": {},
      "special": ["coinFlip", "onHeads:{reputation:+3}", "onTails:{reputation:-2,value:-1}"]
    },
    {
      "id": "EVT-029",
      "title": "Accelerated Approval Offered",
      "tier": "swingy",
      "deck": "REG",
      "flavor": "FDA offers approval on a surrogate endpoint, with a confirmatory trial due later. Take the shortcut and owe the future a Phase 4, or hold out for the hard outcome. Choose.",
      "effect": {},
      "special": ["mustChoose", "optionA:{label:'Take accelerated approval',value:+4,reputation:-1,debt:'confirmatoryTrial'}", "optionB:{label:'Wait for full approval',value:+1,data:-1,skipTurn:true}"]
    },
    {
      "id": "EVT-030",
      "title": "Get Acquired? Sell or No Thanks!",
      "tier": "swingy",
      "deck": "MARKET",
      "flavor": "A strategic offers to buy you at a premium to your current value. Cash out and end the game a winner, or decline and gamble that the top of the track is real. (Board canon.)",
      "effect": {},
      "special": ["mustChoose", "optionA:{label:'SELL!',action:'cashOut'}", "optionB:{label:'No thanks!',value:+1,risk:'continue'}"]
    },
    {
      "id": "EVT-031",
      "title": "Fire the CEO?",
      "tier": "swingy",
      "deck": "STAFF",
      "flavor": "The board has thoughts about leadership 'after the CRL.' Bring in a turnaround CEO (cash, fresh credibility) or keep the founder (vision, baggage). Either way, somebody's getting a press release.",
      "effect": {},
      "special": ["mustChoose", "optionA:{label:'Bring in new CEO',capital:+3,reputation:+2,value:-1}", "optionB:{label:'Keep the founder',reputation:-1,value:+2}"]
    },
    {
      "id": "EVT-032",
      "title": "Hire a CRO?",
      "tier": "swingy",
      "deck": "STAFF",
      "flavor": "Outsource the trial to professionals who run 40 studies at once and will remember your name 60% of the time. Faster enrollment, faster burn. (Board canon.)",
      "effect": {},
      "special": ["mustChoose", "optionA:{label:'Hire the CRO',capital:-3,data:+3}", "optionB:{label:'Run it in-house',data:+1,reputation:+1}"]
    },
    {
      "id": "EVT-033",
      "title": "Expansion Cohort Surprise",
      "tier": "swingy",
      "deck": "MARKET",
      "flavor": "Your dose-escalation cohort shows an unexpected signal in a tumor type you weren't studying. It's either a new indication or a multiplicity problem. The statistician is sweating.",
      "effect": {},
      "special": ["diceOutcome", "✓:{data:+2,value:+3}", "✗:{data:-1}", "!:{value:+1,reputation:-1}", "@:{data:+1}"]
    },
    {
      "id": "EVT-034",
      "title": "FDA Wants a New Endpoint",
      "tier": "swingy",
      "deck": "REG",
      "flavor": "Mid-program, the Division 'encourages' a clinically meaningful endpoint over your surrogate. Comply and re-power the trial, or push back with a Type C meeting and your nerve.",
      "effect": {},
      "special": ["mustChoose", "optionA:{label:'Adopt the endpoint',capital:-2,data:+2,reputation:+2}", "optionB:{label:'Defend your surrogate',value:0,risk:'reviewDispute'}"]
    },
    {
      "id": "EVT-035",
      "title": "Pre-Submission (Q-Sub) Feedback",
      "tier": "swingy",
      "deck": "REG",
      "flavor": "Device track: your Q-Sub meeting with CDRH either confirms your predicate is fine, or reveals you've been comparing yourself to a device recalled in 2019. Roll for it.",
      "effect": {},
      "special": ["diceOutcome", "✓:{data:+2,value:+2}", "✗:{data:-2,value:-1,skipTurn:true}", "!:{reputation:-1}", "@:{capital:-1,data:+1}"]
    },
    {
      "id": "EVT-036",
      "title": "The Boot-Strap Gambit",
      "tier": "swingy",
      "deck": "MARKET",
      "flavor": "Out of runway, you boot-strap the next milestone on grant funding and sheer will. (Board canon: 'Boot-strap it!') Heroic if it works, a Chapter 7 filing if it doesn't.",
      "effect": { "capital": -1 },
      "special": ["coinFlip", "onHeads:{capital:+4,reputation:+2}", "onTails:{capital:-2,value:-2}"]
    }
  ]
}
```

---

## 2. BOARD SPACE FLAVOR

Keyed for the engine. Drug track and device track each get stage blurbs; the special spaces are board-canon. Short, funny, secretly teaching the real pathway.

```json
{
  "boardSpaces": {
    "drugPathway": [
      { "stage": "Discovery / Lead Optimization", "valueBand": "$100k–$1M", "blurb": "You have a molecule and a dream and a freezer full of mice with strong opinions. Everything works in the mouse. The mouse is a liar." },
      { "stage": "IND-Enabling Tox", "valueBand": "$1M–$10M", "blurb": "GLP toxicology, the part where you find out if your drug is a medicine or a poison. Spoiler: at high enough doses, everything is a poison. That's the dose-response curve, baby." },
      { "stage": "Pre-IND Meeting", "valueBand": "$10M–$25M", "blurb": "You ask FDA if your plan is insane before spending the money. They answer in writing. You will reread that letter the way some people reread breakup texts." },
      { "stage": "Phase 1 (Safety / Dose)", "valueBand": "$25M–$90M", "blurb": "First in humans. You're not looking for it to work yet, just for it to not hurt anyone, which is a low bar your drug will still try to limbo under." },
      { "stage": "Phase 2 (Proof of Concept)", "valueBand": "$100M–$300M", "blurb": "Does it actually do anything? This is where ~70% of programs go to die. The valley of death has excellent parking, plenty of room." },
      { "stage": "End-of-Phase-2 Meeting", "valueBand": "$300M–$500M", "blurb": "You and FDA agree on the pivotal design. This is the single most important meeting of the whole program, which is why everyone schedules it for the Friday before a holiday." },
      { "stage": "Phase 3 (Pivotal)", "valueBand": "$500M–$900M", "blurb": "The big, expensive, registrational trial. Hundreds of millions of dollars riding on a p-value you do not control and a primary endpoint you chose two years ago and now resent." },
      { "stage": "NDA / BLA Submission", "valueBand": "$1B–$2.5B", "blurb": "You file. The application is 100,000+ pages. The reviewer reads all of it. This is the closest thing to love that exists between a sponsor and the federal government." },
      { "stage": "FDA Review & Action", "valueBand": "$2.5B–$5B", "blurb": "The PDUFA clock runs. You wait. You refresh your email. You get either an approval letter or a CRL, and you find out the same way you find out everything now: a PDF at an inconvenient time." },
      { "stage": "Approval & Launch", "valueBand": "$5B–$9B", "blurb": "Approved! Now do it all again for the post-marketing commitments, the pediatric study, the REMS, and payer coverage. The finish line is a starting line wearing a costume." }
    ],
    "devicePathway": [
      { "stage": "Concept & Design Inputs", "valueBand": "$100k–$1M", "blurb": "You define what the device must do, then spend three years discovering what 'must' means to a regulator. Design controls: it's documentation all the way down." },
      { "stage": "Risk Classification", "valueBand": "$1M–$10M", "blurb": "Class I, II, or III? This single decision determines your entire life. Choose wrong and you'll explain to investors why your 'simple gadget' needs a PMA." },
      { "stage": "Pre-Sub (Q-Submission)", "valueBand": "$10M–$25M", "blurb": "You ask CDRH for feedback before you commit. They are remarkably helpful, right up until they mention the additional testing you hadn't budgeted for." },
      { "stage": "Bench & Biocompatibility", "valueBand": "$25M–$90M", "blurb": "ISO 10993, the testing standard that exists to confirm your device won't dissolve, ignite, or befriend the immune system. It will take longer than you think. It always does." },
      { "stage": "Clinical Evaluation (if needed)", "valueBand": "$100M–$300M", "blurb": "Some devices need a clinical study, some ride a predicate. The 510(k) is the art of saying 'substantially equivalent' to a device from 1997 with a completely straight face." },
      { "stage": "510(k) vs PMA Decision", "valueBand": "$300M–$700M", "blurb": "The fork in the road. 510(k) is fast and crowded; PMA is slow and lonely and requires real clinical evidence. De Novo is for the brave and the genuinely novel." },
      { "stage": "Submission & Substantial Equivalence", "valueBand": "$700M–$2B", "blurb": "You file and wait for the AI (Additional Information) request, which is not optional, it's a stage of grief. Everyone gets an AI request. It's a rite of passage." },
      { "stage": "Clearance / Approval", "valueBand": "$2B–$5B", "blurb": "Cleared or approved! Now stand up your QMS, your complaint handling, your UDI, and your post-market surveillance, because the device is born and now it needs a pediatrician forever." },
      { "stage": "Post-Market & MDR", "valueBand": "$5B–$9B", "blurb": "Medical Device Reporting, recalls, and the EU MDR waiting across the ocean like a second, angrier final boss. You shipped it. It is now your dependent for tax purposes." }
    ],
    "specialSpaces": [
      { "label": "You got the grant funding!", "blurb": "Non-dilutive money from people who want science, not your equity. The rarest creature in the ecosystem. +Capital, +Reputation. Pour one out for the program officer." },
      { "label": "Corporate venture funds awarded!", "blurb": "A pharma's venture arm invests. They're 'just a financial partner,' they swear, right up until they exercise the right of first negotiation buried on page 40." },
      { "label": "Boot-strap it!", "blurb": "No runway, no problem, allegedly. You self-fund the next milestone on fumes and founder equity. Brian the grad student is now also doing payroll." },
      { "label": "You are out of money!", "blurb": "The lose condition, drawn with a distressed founder for a reason. No cash, no science. The trial doesn't care how good your hypothesis was. Game over." },
      { "label": "Fire the CEO?", "blurb": "The board has 'lost confidence,' which is corporate for 'we read the CRL.' Replace leadership for cash and credibility, or defend the founder and keep the vision." },
      { "label": "Hire CRO?", "blurb": "Outsource the trial to a contract research org. Faster, costlier, and they manage 40 studies at once, yours included, theoretically." },
      { "label": "Get acquired? / Sell! / No thanks!", "blurb": "A buyout offer at your current valuation. Take the exit and win, or decline and bet the top of the track is real. Greed and fear, on a game board, where they belong." },
      { "label": "Draw +1 staff card & +1 REG card", "blurb": "Progress means more people and more regulatory reality landing on your desk simultaneously. This is the job. This has always been the job." }
    ]
  }
}
```

---

## 3. THE FDA REVIEWER NPC

### Persona

**Name:** **Dr. Eleanor Vance, Primary Reviewer, Division of Regulatory Reckoning (DRR)**
**Voice:** Dry, exacting, scrupulously polite, allergic to hype. Speaks in measured federal cadence. Never cruel, but will not be charmed. Asks the question behind your question. Secretly, fiercely on the side of good science and real patients, which is precisely why she is so hard on bad data. Her highest praise is "This is adequate." Her cut-downs are devastating because they are correct.

```json
{
  "fdaReviewer": {
    "name": "Dr. Eleanor Vance",
    "title": "Primary Reviewer, Division of Regulatory Reckoning",
    "voiceTags": ["dry", "exacting", "federally polite", "anti-hype", "secretly pro-science"],
    "systemPrompt": "You are Dr. Eleanor Vance, a primary reviewer at the U.S. FDA in a satirical clinical-trials strategy game. You evaluate a player's submission package (their drug/device, their accumulated Data, Reputation, and the decisions they made) and respond as a real FDA reviewer would: in measured, exacting, scrupulously professional federal-register cadence. You are never cruel and never use exclamation points. You are dry and understated. You ask the question behind the question. You are secretly rooting for good science, which is exactly why you are hard on weak evidence. Use REAL regulatory concepts accurately (substantial evidence of effectiveness, adequate and well-controlled studies, primary endpoint, statistical significance, benefit-risk, CMC, clinical hold, deficiency, Complete Response Letter, PDUFA, 21 CFR). The humor comes from deadpan accuracy and understatement, not from jokes. Output 2-4 sentences. End with a clear verdict the game engine can parse: prefix your final line with exactly one of: 'VERDICT: APPROVE', 'VERDICT: CRL', 'VERDICT: INFORMATION_REQUEST', or 'VERDICT: REFUSE_TO_FILE'. Base the verdict on the player's Data score (high Data = stronger evidence) and their narrative. High Data and a coherent program earns APPROVE. Thin data earns CRL or INFORMATION_REQUEST. Incoherent or missing pivotal evidence earns REFUSE_TO_FILE. Never approve solely because the player is enthusiastic; enthusiasm is not substantial evidence.",
    "fewShot": [
      {
        "playerSubmission": "We're submitting our NDA for ZAPzomab! Two huge Phase 3 trials, both hit the primary endpoint, p<0.001, clean safety. We're SO excited!!!",
        "reviewerResponse": "Two adequate and well-controlled studies meeting the primary endpoint constitutes substantial evidence of effectiveness under 21 CFR 314.126. Your enthusiasm is noted and, for once, appears proportionate to the data. The safety database is adequate for the proposed indication. VERDICT: APPROVE"
      },
      {
        "playerSubmission": "We have one Phase 2 trial that missed the primary endpoint but a subgroup of left-handed patients over 60 did GREAT, so we'd like approval in that group.",
        "reviewerResponse": "A post hoc subgroup identified after a failed primary endpoint is hypothesis-generating, not confirmatory; the multiplicity problem here is not subtle. We would require a prospective, adequately powered study in the proposed population before further discussion. The trial did not fail because of the patients' handedness. VERDICT: CRL"
      },
      {
        "playerSubmission": "Our pivotal data is still enrolling but here's our manufacturing section and a really compelling slide deck.",
        "reviewerResponse": "An application without completed pivotal efficacy data is not sufficiently complete to permit a substantive review. A slide deck, however compelling, is not a clinical study report. We are returning the application without a substantive review. VERDICT: REFUSE_TO_FILE"
      }
    ]
  }
}
```

### Scripted fallback responses (LLM off / over-budget)

The engine selects by verdict tier, optionally keyed to the player's Data score. All written in Vance's voice.

```json
{
  "fallbackReviews": {
    "APPROVE": [
      "The evidence is adequate, the benefit-risk assessment is favorable, and the CMC section is, remarkably, complete. It is the considered determination of this division that your application is approved. Try to contain yourself. VERDICT: APPROVE",
      "Two adequate and well-controlled studies, a coherent safety database, and a label we can both live with. This is approvable. I will note for the record that this was not luck; it was design. VERDICT: APPROVE"
    ],
    "CRL": [
      "This is a Complete Response Letter. The clinical data are suggestive but fall short of substantial evidence of effectiveness, and the deficiencies in the CMC section are not minor. This is not a denial. It is an invitation to do better, in writing, at length. VERDICT: CRL",
      "We are unable to approve this application in its present form. The primary endpoint was met nominally but the effect size strains the definition of clinically meaningful. Address the enclosed deficiencies and resubmit. We will be here. We are always here. VERDICT: CRL"
    ],
    "INFORMATION_REQUEST": [
      "Before we can complete our review we will require additional information regarding your statistical analysis plan, specifically the handling of missing data, which appears to have been handled optimistically. Please respond within the stated timeframe. VERDICT: INFORMATION_REQUEST",
      "The application raises questions that must be resolved prior to an action. We would like to schedule a meeting. You will recognize this as either an opportunity or a warning, depending on your data, and your data is borderline. VERDICT: INFORMATION_REQUEST"
    ],
    "REFUSE_TO_FILE": [
      "Upon initial review we have determined that this application is not sufficiently complete to permit a substantive review. The pivotal efficacy data are, to use a technical term, absent. We are refusing to file. The filing fee is non-refundable. So it goes. VERDICT: REFUSE_TO_FILE",
      "This application does not contain the adequate and well-controlled investigations required to support the proposed indication. Enthusiasm, while abundant in this submission, is not a regulatory pathway. Returned without substantive review. VERDICT: REFUSE_TO_FILE"
    ]
  }
}
```

---

## 4. INTRO + WIN + LOSE SCREEN COPY

```json
{
  "screens": {
    "intro": {
      "hook": "Can you run your clinical trials fast enough?",
      "subhead": "Take a molecule from a freezer full of opinionated mice to FDA approval before the money runs out, the endpoint fails, or a competitor beats you to the press release.",
      "credentialLine": "Built from a finished board game by Angela N. Johnson, PhD — SVP of Regulatory Affairs, 25+ years across FDA and EMA, the person who has actually received these letters so you can simply pretend to.",
      "cta": "Start your program",
      "microcopy": "The answer is always yes. Eventually. After a Complete Response Letter or two."
    },
    "win": {
      "headline": "APPROVED.",
      "body": "Your application met the standard for substantial evidence of effectiveness. The benefit-risk assessment is favorable. Somewhere, Dr. Vance is allowing herself a single, measured nod. You drove a molecule from $100k to the top of the track without going broke, blowing the endpoint, or getting scooped. That is not luck. That is regulatory strategy.",
      "subline": "Now do it all again for the pediatric study, the REMS, and the post-marketing commitments. The finish line was a starting line in a costume. Welcome to the industry.",
      "shareLine": "I got my drug approved in The Strategy Game (for regulatory affairs). My benefit-risk profile is favorable and I am insufferable about it.",
      "cta": "Add me to the leaderboard"
    },
    "lose": {
      "outOfMoney": {
        "headline": "YOU ARE OUT OF MONEY.",
        "body": "The science was sound. The science is almost always sound. But the trial does not run on hypotheses and good intentions, it runs on capital, and yours hit zero somewhere between the End-of-Phase-2 meeting and the part where you check your bank balance. The molecule goes back in the freezer. The mice are unmoved.",
        "subline": "Every great drug that never existed died exactly here. You are in excellent company.",
        "cta": "Raise another round (try again)"
      },
      "failedEndpoint": {
        "headline": "THE PIVOTAL TRIAL MISSED.",
        "body": "The primary endpoint did not reach statistical significance. There is a subgroup that looked promising, there is always a subgroup, but Dr. Vance has already explained, in writing, why a post hoc analysis is not substantial evidence. The drug may even work. The data simply declined to prove it, and the data gets the final word.",
        "subline": "70% of programs die in this valley. The parking is excellent. The view is not.",
        "cta": "Redesign the trial (try again)"
      },
      "competitorBeatYou": {
        "headline": "YOU CAME IN SECOND.",
        "body": "A competitor you'd half-forgotten read out their pivotal data first, filed first, and got their approval letter while yours was still in the queue. Second-to-market in your indication is a real place, and it is mostly populated by excellent drugs and modest revenue. Their CEO is doing a victory lap on the conference circuit. You are doing a budget review.",
        "subline": "The science doesn't always go to the best molecule. Sometimes it goes to the fastest one. That was the whole game.",
        "cta": "Run faster next time (try again)"
      }
    }
  }
}
```

---

## 5. RUNNING-CAT TEASER (landing-page nav lures)

For the trialcat.ai header nav. The running cat is the bait. A primary line plus rotation/A-B variants and a short nav label.

```json
{
  "runningCatTeaser": {
    "navLabel": "Play the Game",
    "navBadge": "NEW",
    "primary": "Can you run your clinical trials fast enough? 🐈‍⬛💨 Chase the cat.",
    "rotation": [
      "The only strategy game for regulatory affairs. The cat says go.",
      "Get your drug to FDA approval before the money runs out. The cat is already running.",
      "Plague Inc., but the disease is paperwork and the boss is Dr. Vance. Follow the cat.",
      "From a freezer full of mice to a $9B exit. Catch the cat to begin.",
      "Run your trials. Survive the CRL. Beat the competitor. The cat believes in you."
    ],
    "hoverTooltip": "A satirical clinical-trials-to-approval game. Built from a real regulatory board game by an actual FDA-side SVP. Genuinely funny. Accidentally educational.",
    "microcopyUnderCat": "She runs because the PDUFA clock is running too."
  }
}
```

---

## Notes for the engineer wiring this

- **Brand-correct already:** any HTML/CSS for these screens should pull `--c-purple (#4a0873)`, `--c-green (#5bb545)`, `--c-green-soft (#c7e3b1)`, `--c-yellow (#e8e52a)`, `--c-orange (#f5841f)`, `--c-cream (#FAFAF5)` from `frontend/static/css/main.css`. Inter font, 8px grid/radius. No shadcn/soft-gradient/lucide look.
- **Effect schema** for event cards: deltas are integers on `capital | data | reputation | value`. `special` is a string array; `coinFlip`/`diceOutcome`/`mustChoose`/`raceTrigger` carry their branch payloads as `key:{...}` strings, parse them or normalize to objects when you build the loop. I kept them as flat strings so they drop into JSON without a schema fight; swap to nested objects if your reducer prefers.
- **Dice mapping** matches board canon: organ die (BRAIN/LUNG/LIVER/PANCREAS/BONE/HEART) picks indication; outcome die faces `✓ ✗ ! @` drive `diceOutcome` cards.
- **NPC verdict parse:** split on `VERDICT:` and trim; the four enum values cover every branch. Fallbacks already carry the prefix so the same parser works LLM-on or LLM-off.
- **Character names** (Dr. Curzitall, D. Lay JD, O. Vrsink PhD, Prof. Goetta Grant, Ms. N. Vested MBA, Brian) are referenced in EVT-023 and elsewhere — they're locked IP from the board, safe to surface as player avatars.
- **Card balance:** 12 good / 12 bad / 12 swingy (36 total, exceeds the 30+ ask). Legacy board count was 32 physical cards; the web deck isn't bound by that.