# trialcat glossary service — v2.2 (16JUN2026)
"""A self-building glossary that teaches the jargon as you play.

The game is full of regulatory / clinical / startup terms a novice won't know
(Type B meeting, dilute the cap table, CRL, 510(k)...). This service makes every
one of them a "learn more" tap:

  1. Ships SEEDED with hand-written plain-language definitions, so the glossary
     is useful on day one with zero LLM spend.
  2. For a term it hasn't seen, it asks the (cheap, capped) LLM once, then SAVES
     the answer — so the glossary grows and gets better with use, and we never
     pay to define the same term twice.
  3. A regenerate path produces a fresh candidate and LLM-judges it against the
     stored one, keeping whichever is clearer. Definitions improve over time
     instead of drifting.

Philosophy: an educational game should explain itself. Every bit of jargon is a
door; this makes them all openable. And persistence means the labor of teaching
compounds — each player's curiosity leaves the next player a better glossary.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GlossaryTerm
from app.services.llm import chat

logger = logging.getLogger(__name__)


def _key(term: str) -> str:
    """Normalize a term to a dedup key: lowercase, collapse whitespace/punct."""
    return re.sub(r"[^a-z0-9 ]", "", term.strip().lower()).strip()


# Hand-written seed. Plain language for a smart non-expert, a little brand voice.
# Keyed by normalized term. These are the terms the game actually uses.
SEED: dict[str, str] = {
    "type b meeting": "A formal sit-down with the FDA at a key milestone (like before starting a pivotal trial). You bring questions, they give guidance in writing. The most valuable meetings in drug development — and the hardest to schedule.",
    "ind": "Investigational New Drug application. The paperwork you file with the FDA to be allowed to test a drug in humans for the first time. Clears you to start Phase 1.",
    "nda": "New Drug Application — the full dossier (often 100,000+ pages) you submit to the FDA asking them to approve a new drug for sale.",
    "bla": "Biologics License Application — the NDA's cousin for biologic products (antibodies, vaccines, cell/gene therapies) rather than small-molecule drugs.",
    "510k": "The faster FDA path for a medical device: you show it's 'substantially equivalent' to a device already on the market (a 'predicate'). Most devices clear this way.",
    "pma": "Premarket Approval — the FDA's most rigorous device path, for high-risk (Class III) devices. Requires real clinical evidence. Slow, expensive, lonely.",
    "crl": "Complete Response Letter. Not an approval, not a rejection — the FDA's 'we need to talk,' listing what's wrong with your application. You fix the deficiencies and resubmit.",
    "complete response letter": "The FDA's 'we cannot approve this yet' letter, listing the deficiencies you must fix before resubmitting. Not a denial — an invitation to do better, at length.",
    "refuse to file": "The FDA declines to even review your application because it's too incomplete (e.g. the pivotal data isn't there). The filing fee is non-refundable.",
    "form 483": "A list of 'objectionable conditions' an FDA inspector hands you after inspecting your facility. You have 15 business days to respond, in writing, convincingly.",
    "primary endpoint": "The single main outcome a clinical trial is designed to measure (e.g. 'overall survival'). Hit it with statistical significance and you have evidence; miss it and the trial 'failed' no matter what else looked good.",
    "benefit-risk": "The core FDA judgment: do this product's benefits outweigh its risks for the intended patients? Everything in a submission is really an argument about this.",
    "cmc": "Chemistry, Manufacturing, and Controls — proving you can make your product the same way, at quality, every time. CMC kills more applications than efficacy does.",
    "breakthrough therapy": "An FDA designation for drugs that show big early promise for serious conditions. Unlocks more FDA interaction and faster review.",
    "orphan drug": "A designation for drugs treating rare diseases — comes with 7 years of market exclusivity and tax credits. Rare 'free money with a clear rationale' in biotech.",
    "adcomm": "Advisory Committee meeting — a panel of outside experts publicly debates and votes on your product's benefit-risk while you sit in the front row, not allowed to talk.",
    "kol": "Key Opinion Leader — a top, highly-cited expert in a field whose public endorsement (or skepticism) moves investors, sites, and sometimes regulators.",
    "pdufa": "The Prescription Drug User Fee Act 'clock' — the deadline by which the FDA promises to act on your application. You will refresh your email a lot as it approaches.",
    "pivotal trial": "The big, expensive, registration-enabling trial (usually Phase 3) whose result determines whether you can file for approval. The whole company rides on its p-value.",
    "dilute the cap table": "Raising money by selling new shares, which shrinks everyone's existing ownership percentage (it 'dilutes' them). The classic founder trade: more cash now, a smaller slice of it later.",
    "down round": "Raising money at a LOWER company valuation than your last round. Painful: it signals trouble and dilutes early shareholders hard. Often led 'to be supportive.'",
    "series b": "A startup's second major venture-capital funding round (after the seed and Series A). Reaching it means investors believe you're working — never raising it is a quiet way to die.",
    "bootstrap": "Funding your company from revenue, grants, and sheer will instead of selling equity. Heroic when it works, a Chapter 7 filing when it doesn't.",
    "cro": "Contract Research Organization — a company you hire to run your clinical trial. Faster and pricier than doing it yourself; they juggle dozens of studies at once.",
    "type a meeting": "An urgent FDA meeting to resolve a stalled or disputed program — either to fix something in your favor, or to explain, gently, why your program is on fire.",
    "expanded access": "A way for patients to get an unapproved investigational drug outside a clinical trial when they're seriously ill and out of options ('compassionate use').",
    "substantial equivalence": "The 510(k) standard: showing your device is as safe and effective as a legally-marketed 'predicate' device. The art of saying this about a device from 1997 with a straight face.",
    "rmat": "Regenerative Medicine Advanced Therapy — a fast-track-style FDA designation for promising cell and gene therapies.",
    "priority review voucher": "A 'cut the line' token the FDA awards for developing certain rare-disease or tropical-disease drugs. Usable on a future application — or sellable for ~$100M.",
    "post-market surveillance": "Watching a product's safety AFTER it's approved and on the market, via adverse-event reports and studies. Approval is a starting line, not a finish line.",
    "integrity flag": "In this game: a marker you earn for cutting corners (enrolling fast and dirty, rushing CMC). Dr. Vance keeps a ledger; each flag hurts your final review.",
    "readiness": "In this game: how prepared your program is to clear the current regulatory stage. Build it up with study actions, then 'Advance' to move up the board.",
    "goodwill": "In this game: your standing with the FDA, key experts, and investors. It cushions bad news and helps at review. Burn it carelessly at your peril.",
    "product value": "In this game: your company's valuation, the board's spine — climb it from $100k to a $9B exit. The original board game's whole track.",
    "data": "In this game: the strength of your clinical and manufacturing evidence. The FDA reviewer weighs it heavily — a slick pitch can't rescue thin data.",
    "capital": "In this game: your cash on hand (in $M). Actions cost it; raising it dilutes you. Hit zero and you're out of money, no matter how good the science.",
    "competitor": "In this game: a rival racing toward your indication. If their progress bar hits 100% they read out and file first, and you're second-to-market.",
    "turns": "In this game: your remaining runway. Each action spends a turn. Generous, but dithering still costs you while the competitor keeps moving.",
}


def _llm_define(term: str) -> Optional[str]:
    """Ask the capped LLM for a plain-language definition. None if unavailable."""
    system = (
        "You are a friendly expert who explains regulatory, clinical, biotech, and "
        "startup-finance terms to a smart non-expert. Define the given term in 1-2 "
        "short, plain sentences. No jargon used to explain jargon. Be accurate and "
        "concrete. A touch of dry wit is fine; never more than a touch."
    )
    text = chat(system, f"Define this term for a beginner: {term}", max_tokens=90)
    if text:
        return text.strip().strip('"')
    return None


def _judge(term: str, old: str, new: str) -> str:
    """LLM-judge two definitions; return 'old' or 'new'. Defaults to 'new' on no LLM."""
    verdict = chat(
        "You judge which of two short definitions is clearer and more accurate for a "
        "non-expert. Reply with EXACTLY one word: OLD or NEW.",
        f"Term: {term}\nOLD: {old}\nNEW: {new}\nWhich is the better definition?",
        max_tokens=4,
    )
    if verdict and "OLD" in verdict.upper():
        return "old"
    return "new"


def get_definition(session: Session, term: str) -> GlossaryTerm:
    """Return a stored definition, creating it (seed → LLM → placeholder) if new."""
    k = _key(term)
    existing = session.scalar(select(GlossaryTerm).where(GlossaryTerm.term_key == k))
    if existing:
        return existing

    if k in SEED:
        gt = GlossaryTerm(term_key=k, term=term.strip(), definition=SEED[k], source="seed")
    else:
        text = _llm_define(term)
        gt = GlossaryTerm(
            term_key=k, term=term.strip(),
            definition=text or "We don't have a plain-language definition for this yet — try the regenerate button, or check back as the glossary grows.",
            source="llm" if text else "pending",
        )
    session.add(gt)
    session.commit()
    return gt


def regenerate_definition(session: Session, term: str) -> GlossaryTerm:
    """Produce a fresh LLM candidate and keep it only if the judge prefers it."""
    gt = get_definition(session, term)
    candidate = _llm_define(term)
    if not candidate:
        return gt  # no LLM available — nothing to improve with
    if gt.source in ("seed", "llm") and gt.definition:
        if _judge(term, gt.definition, candidate) == "old":
            gt.quality_score = (gt.quality_score or 0) + 1  # the stored one won; it's more trusted now
            session.commit()
            return gt
    gt.definition = candidate
    gt.source = "llm"
    gt.quality_score = 0
    session.commit()
    return gt


def seed_glossary(session: Session) -> int:
    """Upsert all seed terms on startup so the core glossary is always present."""
    added = 0
    for k, definition in SEED.items():
        if not session.scalar(select(GlossaryTerm.id).where(GlossaryTerm.term_key == k)):
            session.add(GlossaryTerm(term_key=k, term=k, definition=definition, source="seed"))
            added += 1
    if added:
        session.commit()
    return added
