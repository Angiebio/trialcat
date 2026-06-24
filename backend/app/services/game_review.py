# trialcat FDA-reviewer service — v2.1 (16JUN2026)
"""Dr. Eleanor Vance, Division of Regulatory Reckoning — judges your submission.

Two tiers, always returns a verdict:
  1. _llm_review() — cheap, hard-capped OpenRouter call (services/llm.py). Sends a
     sanitized, PII-free digest; parses one of four standard regulatory verdicts.
  2. _scripted_review() — deterministic Vance letters keyed to your data/integrity.

The reviewer weighs DATA heavily and narrative lightly — a slick sentence cannot
rescue a thin package. That's the whole joke (and the whole truth): data >
narrative. Enthusiasm is not substantial evidence.
"""

from __future__ import annotations

import re
from typing import Optional

from app.schemas.game import ReviewRequest, ReviewResponse, ReviewVerdict
from app.services.llm import chat

REVIEWER_NAME = "Dr. Eleanor Vance, Division of Regulatory Reckoning"

# Score modifier per verdict, clamped to the design's [-25, +20].
_MOD = {
    "APPROVED": 18,
    "APPROVABLE_WITH_DEFICIENCIES": 6,
    "COMPLETE_RESPONSE_LETTER": -12,
    "REFUSE_TO_FILE": -22,
}

# Vance's voice: deadpan accuracy, federal cadence, no exclamation points, never
# cruel, secretly pro-science. Humor from understatement, not jokes.
_SYSTEM_PROMPT = (
    "You are Dr. Eleanor Vance, a primary reviewer at the U.S. FDA in a satirical "
    "clinical-trials strategy game. Read the player's sanitized submission digest "
    "and respond exactly as a real FDA reviewer would: measured, exacting, "
    "scrupulously professional federal cadence. Never cruel, never any exclamation "
    "points, dry and understated. Use REAL regulatory concepts correctly (substantial "
    "evidence of effectiveness, adequate and well-controlled studies, primary endpoint, "
    "benefit-risk, CMC, deficiency, Complete Response Letter, 21 CFR). Weigh DATA "
    "heavily and the narrative lightly; enthusiasm is not substantial evidence. Output "
    "2-4 sentences, then a final line that is EXACTLY one of: 'VERDICT: APPROVED', "
    "'VERDICT: APPROVABLE_WITH_DEFICIENCIES', 'VERDICT: COMPLETE_RESPONSE_LETTER', "
    "'VERDICT: REFUSE_TO_FILE'. High data + coherent program earns APPROVED; thin data "
    "earns deficiencies or a CRL; missing pivotal evidence earns REFUSE_TO_FILE; "
    "integrity shortcuts push toward CRL/RTF."
)

# Scripted Dr. Vance letters per verdict (LLM off / over budget). {pathway} fills in.
_SCRIPTED = {
    "APPROVED": [
        "The evidence is adequate, the benefit-risk assessment is favorable, and the CMC section is, remarkably, complete. It is the considered determination of this division that your {pathway} application is approved. Try to contain yourself.",
        "Two adequate and well-controlled studies, a coherent safety database, and a label we can both live with. This is approvable. I will note for the record that this was not luck; it was design.",
    ],
    "APPROVABLE_WITH_DEFICIENCIES": [
        "Your application is approvable, with deficiencies. The clinical case holds, but the statistical analysis plan handled missing data optimistically and the labeling overreaches. Address the enclosed items and we will proceed.",
        "We can see the approval from here; you are not there yet. Tighten the secondary analyses, justify the population, and resolve the open CMC question. This is a request for information, not a rejection.",
    ],
    "COMPLETE_RESPONSE_LETTER": [
        "This is a Complete Response Letter. The clinical data are suggestive but fall short of substantial evidence of effectiveness, and the deficiencies in the CMC section are not minor. This is not a denial. It is an invitation to do better, in writing, at length.",
        "We are unable to approve this {pathway} application in its present form. The primary endpoint was met nominally, but the effect size strains the definition of clinically meaningful. Address the deficiencies and resubmit. We will be here. We are always here.",
    ],
    "REFUSE_TO_FILE": [
        "Upon initial review we have determined that this application is not sufficiently complete to permit a substantive review. The pivotal efficacy data are, to use a technical term, absent. We are refusing to file. The filing fee is non-refundable. So it goes.",
        "This {pathway} application does not contain the adequate and well-controlled investigations required to support the proposed indication. Enthusiasm, while abundant, is not a regulatory pathway. Returned without substantive review.",
    ],
}

_RIGOR_TERMS = (
    "endpoint", "primary", "statistical", "significan", "power", "confidence",
    "safety", "adverse", "benefit-risk", "benefit/risk", "indication", "label",
    "control", "randomi", "blind", "predicate", "substantial equivalence", "pma",
    "510", "biocompat", "efficacy", "evidence", "non-inferior", "superiority",
)


def _rigor(text: str) -> int:
    t = text.lower()
    return sum(1 for term in _RIGOR_TERMS if term in t)


def _classify(req: ReviewRequest) -> ReviewVerdict:
    """Verdict from the metrics. Data dominates; integrity shortcuts hurt."""
    score = (
        0.80 * req.evidence_score
        + 0.15 * req.reputation_score
        + _rigor(req.submission_rationale) * 4
        - req.integrity_flags * 10
    )
    if len(req.submission_rationale) < 50:
        score -= 8
    # Verdict is DATA-DOMINANT (0.80*data): max your evidence and you approve, with
    # reputation + rigor as bonus margin and integrity shortcuts (-10/flag) the real
    # penalty. The old 0.55*data/0.25*rep + 78 bar was a knife-edge (needed data~97 AND
    # rep~100 at once) that the 28-turn clock almost never reached. Keeps "data > narrative."
    if score >= 70:
        return "APPROVED"
    if score >= 50:
        return "APPROVABLE_WITH_DEFICIENCIES"
    if score >= 30:
        return "COMPLETE_RESPONSE_LETTER"
    return "REFUSE_TO_FILE"


def _scripted_review(req: ReviewRequest, verdict: Optional[ReviewVerdict] = None) -> ReviewResponse:
    verdict = verdict or _classify(req)
    letters = _SCRIPTED[verdict]
    letter = letters[len(req.submission_rationale) % len(letters)].format(pathway=req.pathway)
    return ReviewResponse(
        verdict=verdict, reviewer_name=REVIEWER_NAME, letter=letter,
        score_modifier=_MOD[verdict], source="scripted",
    )


def _llm_review(req: ReviewRequest) -> Optional[ReviewResponse]:
    """Cheap, capped OpenRouter reviewer. Sanitized digest only — never any PII."""
    digest = (
        f"PROGRAM DIGEST (sanitized):\n"
        f"- pathway: {req.pathway}\n"
        f"- therapeutic_area: {req.therapeutic_area or 'unspecified'}\n"
        f"- phase: {req.phase or 'unspecified'}\n"
        f"- product: {req.product_name or 'an investigational product'}\n"
        f"- evidence/data strength (0-100): {req.evidence_score}\n"
        f"- regulatory goodwill (0-100): {req.reputation_score}\n"
        f"- integrity shortcuts taken: {req.integrity_flags}\n"
        f"- sponsor's submission rationale: \"{req.submission_rationale[:500]}\"\n"
        f"Render your verdict."
    )
    text = chat(_SYSTEM_PROMPT, digest)
    if not text:
        return None

    m = re.search(r"VERDICT:\s*(APPROVED|APPROVABLE_WITH_DEFICIENCIES|COMPLETE_RESPONSE_LETTER|REFUSE_TO_FILE)", text)
    if not m:
        return None  # model didn't follow format — fall back to scripted
    verdict: ReviewVerdict = m.group(1)  # type: ignore[assignment]
    letter = text[: m.start()].strip() or text.strip()
    return ReviewResponse(
        verdict=verdict, reviewer_name=REVIEWER_NAME, letter=letter,
        score_modifier=_MOD[verdict], source="llm",
    )


def generate_review(req: ReviewRequest) -> ReviewResponse:
    """Public entry. Try the (capped) LLM; always fall back to a scripted letter.

    We constrain the LLM's verdict to never wildly contradict the data: if the
    metrics scream REFUSE_TO_FILE, a hallucinated APPROVED is overridden. The
    model writes the prose; the data still gets the final word — as it should.
    """
    scripted_verdict = _classify(req)
    llm = _llm_review(req)
    if llm is None:
        return _scripted_review(req, scripted_verdict)

    # Guardrail: keep the LLM honest against the metrics. It may move one tier,
    # not invent an approval for an empty package.
    order = ["REFUSE_TO_FILE", "COMPLETE_RESPONSE_LETTER", "APPROVABLE_WITH_DEFICIENCIES", "APPROVED"]
    if abs(order.index(llm.verdict) - order.index(scripted_verdict)) > 1:
        # Trust the data's verdict, keep the model's prose.
        return ReviewResponse(
            verdict=scripted_verdict, reviewer_name=llm.reviewer_name,
            letter=llm.letter, score_modifier=_MOD[scripted_verdict], source="llm",
        )
    return llm
