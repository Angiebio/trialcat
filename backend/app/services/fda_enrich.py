"""openFDA enrichment client — turn messy CT.gov names into real FDA facts.

This module is the ONE place in the codebase that talks to openFDA. Like
`ctgov_client`, the HTTP layer is sealed here; callers get plain dicts or None.

What it does:
- DEVICE: maps a CT.gov device intervention (usually a BRAND name like
  "ANGIOGUARD XP Emboli Capture Guidewire") to FDA's device/classification DB,
  yielding a real device class (I/II/III), the FDA medical-specialty review
  panel ("Cardiovascular", "Neurology", ...), a product code, and a regulation
  number.
- DRUG: maps a drug arm ("Simvastatin 40mg", "oseltamivir [Tamiflu]") to its
  established pharmacologic class (EPC) via the openFDA NDC directory, plus
  whether it's prescription or OTC.

Design notes (matching ctgov_client's contract):
- Uses `requests.Session` with a descriptive User-Agent (good API citizenship).
- Retries on 5xx and network errors with exponential backoff.
- Fails LOUD on our-side 4xx bugs (malformed query) — but treats openFDA's 404
  "no matches" as a legitimate empty result, NOT an error. openFDA returns 404
  when a search has zero hits; that's "we didn't find it", not "we broke".
- Polite rate limiting: a small sleep between calls so we stay under the no-key
  ceiling (~240 req/min). The real scarcity is the 1,000 req/day cap, which the
  ETL budgets separately.
- In-memory cache keyed by the lookup TOKEN (the generic noun / active
  ingredient), so 40 "stent" trials cost exactly one HTTP call.
- No PII anywhere. We only ever send generic nouns and drug names.

Philosophy: CT.gov names are how a sponsor markets a thing; FDA classification
is what the thing legally IS. This module is the translator between marketing
and regulation — and like any translator working from brand names to canonical
forms, it is honestly approximate. We bias toward "ballpark right" over
"precisely wrong": when the top hit is noisy, we trust the MODE of the top
results, because the crowd of matches knows more than any single record.
"""

import logging
import re
import time
from collections import Counter
from typing import Optional

import requests

from app.config import settings

logger = logging.getLogger(__name__)


class OpenFDAAPIError(Exception):
    """Raised when openFDA returns something we genuinely can't work with.

    Note: a 404 (zero search hits) is NOT wrapped in this — that's an expected
    "no match", returned to callers as None. This exception is for real
    breakage: 4xx that means our query is malformed, or 5xx exhausting retries.
    """


# -----------------------------------------------------------------------------
# Matching vocabularies — curated, deliberately small, tuned against the LIVE
# openFDA API and the REAL names in trialcat's DB (see roadmaps notes).
# -----------------------------------------------------------------------------

# Generic device nouns, SPECIFIC first. CT.gov device interventions are brand
# names; FDA's classification DB indexes generic nouns. We hunt the strongest
# (most specific) noun present in the brand string and query that. Order is
# priority: a "drug-eluting coronary stent" should resolve via "stent", not get
# swallowed by the ultra-generic "device". This list was mined from the actual
# 400 distinct device names in the DB across two tuning passes.
_SPECIFIC_DEVICE_NOUNS: tuple[str, ...] = (
    "neurostimulator", "defibrillator", "pacemaker", "guidewire",
    "videolaryngoscope", "laryngoscope", "bronchoscope", "colonoscope",
    "laparoscope", "gastroscope", "cystoscope", "endoscope", "stethoscope",
    "ventilator", "nebulizer", "nebuliser", "inhaler", "insulin pump",
    "infusion pump", "syringe", "autoinjector", "injector", "prosthesis",
    "prosthetic", "screw", "scaffold", "stent", "balloon", "electrode",
    "oximeter", "glucometer", "glucose meter", "glucose monitor",
    "glucose monitoring", "thermometer", "ultrasound", "transducer",
    "colonoscopy", "endoscopy", "spirometer", "spirometry", "ecg", "ekg",
    "eeg", "cochlear implant", "hearing aid", "dialyzer", "dialyser",
    "oxygenator", "wheelchair", "exoskeleton", "spectacles", "eyeglasses",
    "prism", "intraocular lens", "contact lens", "dressing", "bandage",
    "suture", "stapler", "forceps", "scalpel", "tourniquet", "cannula",
    "shunt", "expander", "splint", "orthosis", "brace", "occluder",
    "laryngeal mask", "face mask", "mask", "electrocautery", "cryoablation",
    "ablation", "laser", "robot", "vagus nerve stim", "nerve stimulation",
    "spinal cord stim", "deep brain stim", "stimulation", "stimulator",
    "monitor", "sensor", "scanner", "oxygen", "needle", "clip", "graft",
    "valve", "implant", "lens", "tens", "probe", "coil", "mesh", "plate",
    "app", "software", "instillation",
    # second tuning pass — high-confidence nouns from the real NO-NOUN tail
    "tms", "tdcs", "denervation", "thrombectomy", "plethysmograph",
    "plethysmography", "electromyograph", "echocardiogram", "echocardiography",
    "spectroscopy", "tomography", "magnetic resonance imaging",
    "magnetic resonance", "knee replacement", "hip replacement",
    "arthroplasty", "denture", "toothbrush", "compression stocking",
    "stocking", "appliance", "spray", "cream", "capsule", "pacing lead",
    "lead", "headset", "armband", "depressor", "sealant", "neuromodulation",
    "shockwave", "thermodilution",
)

# Ultra-generic fallback nouns — only consulted if NO specific noun matched.
# These produce noisy modes (a bare "device" matches everything), so they are
# the floor, not the ceiling, of our confidence.
_GENERIC_DEVICE_NOUNS: tuple[str, ...] = (
    "pump", "filter", "catheter", "tube", "wire", "scope", "device", "system",
)

# Nouns too generic to carry an HONEST medical specialty. openFDA's
# device_name:"system" / "device" corpus is dominated by microbiology test
# SYSTEMS, so the mode wrongly stamps "Microbiology" onto every "...System"
# brand name (a transcranial ultrasound system is NOT microbiology). For these
# nouns we trust NOTHING and return no-match — the keyword heuristic, which at
# least read "ultrasound"/"stimulator" out of the full name, stays in place.
# Subtraction is not enrichment: a decent guess beats a confident wrong answer.
_SPECIALTY_UNTRUSTWORTHY_NOUNS: frozenset[str] = frozenset({"device", "system"})

# Words that signal "this DRUG arm is not actually a queryable drug" — placebos,
# vehicles, shams, and standard-of-care comparators have no pharmacologic class.
_NON_DRUG_TOKENS: frozenset[str] = frozenset({
    "placebo", "vehicle", "standard", "care", "sham", "control", "saline",
    "comparator", "active", "best", "supportive", "usual", "no", "to", "or",
    "and", "plus", "group", "arm", "dose", "the", "of",
})

# Dosage / route / salt / formulation noise we strip to expose the active
# ingredient token. Salts (sodium, sulfate, ...) are stripped because openFDA
# indexes the base ingredient name.
_DRUG_NOISE_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"[\(\[].*?[\)\]]"), " "),  # parenthetical brand/notes
    (re.compile(r"\b\d+[.,]?\d*\s*(mg|mcg|g|ml|%|iu|units?|kg|w/w|v/v)\b", re.I), " "),
    (re.compile(r"\b\d+[.,]?\d*\b"), " "),  # bare numbers
    (re.compile(
        r"\b(tablet|tablets|capsule|capsules|cream|gel|patch|injection|"
        r"injectable|oral|iv|intravenous|solution|suspension|ointment|lozenge|"
        r"spray|inhaler|dose|doses|standard|of|care|inactivated|vaccine|"
        r"sodium|sulfate|sulphate|bromide|phosphate|besylate|succinate|mofetil|"
        r"hydrochloride|hcl|fumarate|maleate|mesylate|tartrate|acetate|citrate|"
        r"potassium|calcium|disodium|er|sr|xr|cr|la|odt|extended|release|"
        r"immediate)\b", re.I), " "),
)

# An investigational code like "AZD5718", "BMS-863233", "D3S-003", "SG001".
# These won't be in approved-drug DBs — recognizing them up front saves a wasted
# API call (and a wasted slice of the daily budget) and avoids the homeopathic
# false-positives that short alphanumeric tokens trigger.
_INVESTIGATIONAL_CODE_RE = re.compile(r"^[A-Za-z]{1,4}[-\s]?\d{2,6}(-\d+)?[A-Za-z]?$")

# Pharm-class tag priority. EPC (Established Pharmacologic Class) is FDA's
# canonical "what kind of drug is this" label and what a regulatory pro wants;
# fall back to mechanism (MoA), chemical structure (CS), physiologic effect (PE).
_PHARM_TAG_PRIORITY: tuple[str, ...] = ("[EPC]", "[MoA]", "[CS]", "[PE]")


def _normalize_device_class(raw: Optional[str]) -> Optional[str]:
    """Map openFDA device_class ('1'/'2'/'3') to FDA Roman numerals (I/II/III).

    openFDA also emits 'N', 'U', 'f' for unclassified/special cases; those map
    to None — we'd rather say "we don't know" than invent a class.
    """
    return {"1": "I", "2": "II", "3": "III"}.get(str(raw).strip()) if raw else None


def _pick_pharm_class(pharm_list: Optional[list[str]]) -> Optional[str]:
    """From openFDA's pharm_class list, pick the most useful label by tag.

    A drug carries several classifications (EPC, MoA, CS, PE). We prefer the
    EPC — it's the human-meaningful "this is a beta-blocker" answer — and walk
    down the priority ladder if no EPC is present.
    """
    if not pharm_list:
        return None
    for tag in _PHARM_TAG_PRIORITY:
        for p in pharm_list:
            if p.endswith(tag):
                return p
    return pharm_list[0]


class FDAEnrichClient:
    """Synchronous openFDA client for device + drug enrichment.

    Usage:
        client = FDAEnrichClient()
        dev = client.classify_device("ANGIOGUARD XP Emboli Capture Guidewire")
        # -> {"device_class": "II", "product_category": "Cardiovascular",
        #     "product_code": "...", "regulation_number": "...",
        #     "matched_term": "guidewire"}
        drug = client.classify_drug("Simvastatin 40mg")
        # -> {"product_category": "HMG-CoA Reductase Inhibitor [EPC]",
        #     "source": "openFDA NDC (Rx)"}

    Both classifiers return None on no-match — the caller (ETL) decides the
    fallback (keep heuristic value for devices; "Investigational / Unclassified"
    for drugs).
    """

    # Public so the ETL can label no-match drug arms consistently.
    DRUG_NO_MATCH_LABEL = "Investigational / Unclassified"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        user_agent: Optional[str] = None,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
        polite_sleep_seconds: float = 0.30,
    ):
        self.base_url = (base_url or settings.openfda_api_base).rstrip("/")
        # Empty string means "no key" — openFDA still works, just throttled.
        self.api_key = api_key if api_key is not None else settings.openfda_api_key
        self.user_agent = user_agent or settings.ctgov_user_agent
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        # 0.30s between calls keeps us well under ~240/min even with retries.
        # Persistence is a virtue, but so is not getting our IP throttled.
        self.polite_sleep_seconds = polite_sleep_seconds

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent})

        # Token-keyed caches. The whole point: many trials share one generic
        # noun / ingredient, so we pay openFDA once per DISTINCT token, not once
        # per row. None is a valid, cached answer ("we looked, it's not there").
        self._device_cache: dict[str, Optional[dict]] = {}
        self._drug_cache: dict[str, Optional[dict]] = {}

        # How many real HTTP calls we've made — the ETL reads this to enforce
        # the daily budget. Cache hits don't count; they're free.
        self.api_calls_made = 0

    # -------------------------------------------------------------------------
    # Public — devices
    # -------------------------------------------------------------------------

    def extract_device_noun(self, name: str) -> Optional[str]:
        """Find the strongest generic device noun inside a brand-y name.

        Returns the most specific noun present, or a generic fallback noun, or
        None if the string contains no recognizable device noun at all (common
        for brand-only names like "Nerivio" and procedures like "acupuncture").
        """
        if not name:
            return None
        low = name.lower()
        for noun in _SPECIFIC_DEVICE_NOUNS:
            if re.search(r"\b" + re.escape(noun) + r"\b", low):
                return noun
        for noun in _GENERIC_DEVICE_NOUNS:
            if re.search(r"\b" + re.escape(noun) + r"\b", low):
                return noun
        return None

    def classify_device(self, name: str) -> Optional[dict]:
        """Classify a CT.gov device intervention via openFDA.

        Returns a dict with normalized class, FDA medical specialty as
        product_category, product_code, regulation_number, and the matched
        generic term — or None if we can't extract a noun or openFDA has nothing.
        """
        noun = self.extract_device_noun(name)
        if not noun:
            return None
        result = self._lookup_device_noun(noun)
        if result is None:
            return None
        # Stamp which token produced this so the ETL/notes can audit matches.
        return {**result, "matched_term": noun}

    def _lookup_device_noun(self, noun: str) -> Optional[dict]:
        """Query openFDA for one generic noun, with caching + the MODE strategy.

        The single top hit for a generic noun is unreliable (the first "stent"
        record is an intracranial coil-assist stent with specialty "Unknown").
        So we pull the top N records and take the MOST COMMON class and the most
        common NON-"Unknown" specialty. The crowd is wiser than the head record.
        """
        if noun in self._device_cache:
            return self._device_cache[noun]

        # Some nouns are too generic to mean anything specific. Don't spend a
        # call or risk a confidently-wrong specialty — cache the no-match and
        # let the keyword heuristic keep the floor.
        if noun in _SPECIALTY_UNTRUSTWORTHY_NOUNS:
            self._device_cache[noun] = None
            return None

        data = self._request_json(
            f"{self.base_url}/device/classification.json",
            params={"search": f'device_name:"{noun}"', "limit": 25},
        )
        # _request_json returns None for the openFDA "no results" 404.
        results = (data or {}).get("results") or []
        if not results:
            self._device_cache[noun] = None
            return None

        classes: Counter = Counter()
        specialties: Counter = Counter()
        for res in results:
            c = _normalize_device_class(res.get("device_class"))
            if c:
                classes[c] += 1
            s = res.get("medical_specialty_description")
            if s and s != "Unknown":  # "Unknown" is noise, not a category
                specialties[s] += 1

        top_class = classes.most_common(1)[0][0] if classes else None
        top_specialty = specialties.most_common(1)[0][0] if specialties else None

        if not top_class and not top_specialty:
            self._device_cache[noun] = None
            return None

        # Pull product_code/regulation from a record CONSISTENT with the mode,
        # so the metadata we report actually belongs to the class we report —
        # not a stray top hit that disagrees with the crowd.
        rep = next(
            (
                r for r in results
                if _normalize_device_class(r.get("device_class")) == top_class
                and r.get("medical_specialty_description") == top_specialty
            ),
            results[0],
        )

        result = {
            "device_class": top_class,
            "product_category": top_specialty,  # FDA review-panel specialty
            "product_code": rep.get("product_code") or None,
            "regulation_number": rep.get("regulation_number") or None,
        }
        self._device_cache[noun] = result
        return result

    # -------------------------------------------------------------------------
    # Public — drugs
    # -------------------------------------------------------------------------

    def clean_drug_name(self, raw: str) -> str:
        """Strip dosage/route/salt/formulation noise to expose the ingredient.

        "Warfarin Sodium 3 MG" -> "warfarin". The salt and the dose are how a
        protocol writes it; the ingredient is what FDA indexes.
        """
        s = raw.lower()
        for rx, repl in _DRUG_NOISE_PATTERNS:
            s = rx.sub(repl, s)
        s = re.sub(r"[^a-z\s\-/]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _drug_candidate_tokens(self, cleaned: str) -> list[str]:
        """Yield plausible active-ingredient tokens, longest first.

        Active ingredients tend to be long, distinctive words; combo arms list
        several ("Pemetrexed/ Carboplatin"). We try the longest first because
        it's the least likely to be a stopword and the most likely to be the
        true drug. Tokens shorter than 4 chars are dropped — they're either
        stopwords or investigational-code fragments that trigger garbage hits.
        """
        toks: list[str] = []
        for p in re.split(r"[/\s]+", cleaned):
            p = p.strip("-")
            if len(p) < 4 or p in _NON_DRUG_TOKENS:
                continue
            toks.append(p)
        toks.sort(key=len, reverse=True)
        return toks

    def classify_drug(self, name: str) -> Optional[dict]:
        """Classify a CT.gov drug arm via the openFDA NDC directory.

        Returns {"product_category": <pharm class OR Rx/OTC label>, "source": ...}
        or None if the arm is a placebo/sham/investigational code or simply
        isn't in openFDA (expected for the many investigational arms — the ETL
        buckets those as "Investigational / Unclassified").
        """
        if not name:
            return None

        # Fast rejections — no API call spent on things that can't possibly match.
        if _INVESTIGATIONAL_CODE_RE.match(name.strip()):
            return None
        lowered_words = set(name.lower().split())
        if lowered_words & {"placebo", "vehicle", "sham"}:
            return None

        cleaned = self.clean_drug_name(name)
        for token in self._drug_candidate_tokens(cleaned):
            result = self._lookup_drug_token(token)
            if result is not None:
                return result
        return None

    def _lookup_drug_token(self, token: str) -> Optional[dict]:
        """Query openFDA NDC for one ingredient token, with caching + guards.

        The NDC search is fuzzy and combo-products abound, so we VERIFY each hit:
        the token must appear as a real word in the matched product's generic
        name, the product must be a finished human Rx/OTC drug (not bulk "for
        further processing"), and for multi-ingredient products the token must be
        the LEAD ingredient — otherwise "Clotrimazole ... Hyaluronic Acid" would
        wrongly tag hyaluronic acid as an antifungal.
        """
        if token in self._drug_cache:
            return self._drug_cache[token]

        data = self._request_json(
            f"{self.base_url}/drug/ndc.json",
            params={"search": f'generic_name:"{token}"', "limit": 20},
        )
        results = (data or {}).get("results") or []
        if not results:
            self._drug_cache[token] = None
            return None

        word_re = re.compile(r"\b" + re.escape(token) + r"\b")
        fallback: Optional[dict] = None
        answer: Optional[dict] = None

        for res in results:
            product_type = res.get("product_type") or ""
            if product_type not in ("HUMAN PRESCRIPTION DRUG", "HUMAN OTC DRUG"):
                continue  # skip bulk / animal / "for further processing"
            generic = (res.get("generic_name") or "").lower()
            if not word_re.search(generic):
                continue  # fuzzy hit that doesn't really contain our token

            # Count ingredients across every separator openFDA uses, including
            # the " - " that homeopathic listings abuse. A stew of ingredients
            # makes the single pharm_class meaningless for our token.
            ingredient_count = (
                generic.count(",") + generic.count(" and ")
                + generic.count(" - ") + 1
            )
            first_ingredient = re.split(r"[,/]| and | - ", generic)[0].strip()
            token_is_lead = bool(word_re.search(first_ingredient))

            pharm = _pick_pharm_class(res.get("pharm_class"))
            rx_otc = "Rx" if product_type == "HUMAN PRESCRIPTION DRUG" else "OTC"

            if pharm and ingredient_count <= 3 and token_is_lead:
                # Strong match: real lead ingredient, has a class, not a mega-combo.
                answer = {
                    "product_category": pharm,
                    "source": f"openFDA NDC ({rx_otc})",
                }
                break
            if fallback is None and token_is_lead:
                # We at least know Rx-vs-OTC even when pharm_class is absent.
                fallback = {
                    "product_category": f"{rx_otc}-only" if rx_otc == "Rx" else "OTC",
                    "source": f"openFDA NDC ({rx_otc}, no pharm class)",
                }

        result = answer or fallback
        self._drug_cache[token] = result
        return result

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------

    def _request_json(self, url: str, params: dict) -> Optional[dict]:
        """GET an openFDA URL with retries. Returns parsed JSON, or None on 404.

        openFDA's 404 means "your search matched zero records" — a normal,
        expected outcome for our investigational arms and unknown devices. We
        return None for it (the caller treats None as no-match) rather than
        raising, because raising on every miss would turn graceful degradation
        into a crash storm.

        Other 4xx are OUR bug (malformed query) and fail loud. 5xx and network
        errors are openFDA's problem and we retry with exponential backoff.

        Every real call sleeps `polite_sleep_seconds` first and increments the
        call counter, so the ETL can honor the daily budget and we stay a good
        API citizen.
        """
        if self.api_key:
            # openFDA reads the key from the api_key query param.
            params = {**params, "api_key": self.api_key}

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            # Polite pacing happens on the way IN to each network attempt.
            time.sleep(self.polite_sleep_seconds)
            self.api_calls_made += 1
            try:
                resp = self._session.get(url, params=params, timeout=30.0)

                if resp.status_code == 404:
                    # Zero matches — not an error, just an empty answer.
                    logger.debug("openFDA 404 (no matches) for %s %s", url, params.get("search"))
                    return None

                if 400 <= resp.status_code < 500:
                    # Genuine client error (bad query syntax) — our bug, fail loud.
                    raise OpenFDAAPIError(
                        f"openFDA returned {resp.status_code} for {url} "
                        f"params={params}: {resp.text[:200]}"
                    )

                resp.raise_for_status()
                return resp.json()

            except requests.HTTPError as e:
                last_exc = e
                logger.warning(
                    "openFDA 5xx on attempt %s/%s: %s",
                    attempt, self.max_retries, e,
                )
            except requests.RequestException as e:
                last_exc = e
                logger.warning(
                    "openFDA network error on attempt %s/%s: %s",
                    attempt, self.max_retries, e,
                )

            if attempt < self.max_retries:
                time.sleep(self.backoff_seconds * (2 ** (attempt - 1)))

        raise OpenFDAAPIError(
            f"openFDA request failed after {self.max_retries} attempts: {last_exc}"
        )
