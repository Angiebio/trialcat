"""Parser — turn raw CT.gov API JSON into trialcat model instances.

This is where the messy reality of CT.gov data meets the clean structure of
our SQLAlchemy models. Every field extraction is deliberate: we handle missing
fields, partial dates, inconsistent casing, and the general chaos of
real-world clinical trial data.

Design rules:
1. Parser is PURE — no DB writes. It returns model instances ready to be
   added to a session by the ETL layer. This makes testing trivial.
2. Parser is FORGIVING on data but STRICT on structure. If the CT.gov API
   changes shape, we fail loud. If a field is missing, we use None.
3. All date parsing goes through one helper so partial dates ("2019",
   "2019-07", "2019-07-15") are handled consistently.
"""

import logging
import re
from datetime import date
from typing import Optional

from app.models import (
    Condition,
    Intervention,
    Location,
    Outcome,
    Trial,
    TrialCondition,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Therapeutic area mapping
# -----------------------------------------------------------------------------
# MeSH Tree top-level categories (C = Diseases). We map the most relevant
# first-level MeSH ancestor to a broad therapeutic area label. This table is
# intentionally small; Phase 8 can replace it with a full MeSH tree walk.
#
# The mapping picks the FIRST match from a prioritized list of ancestor
# terms — so if a trial is tagged with both "Cardiovascular Diseases" and
# "Infections", we pick based on order.
#
# Ordering note: this list is priority-ordered. When a trial has multiple
# MeSH ancestors (which is common — "Retinal Vein Occlusion" has both
# "Eye Diseases" AND "Venous Thrombosis" → Cardiovascular), the FIRST match
# wins. So we put specialty areas before general circulatory/nervous
# categories: an eye trial should read as Ophthalmology, not Cardiovascular.
# A stroke trial should read as Neurology, not Cardiovascular. Etc.
MESH_TO_THERAPEUTIC_AREA = [
    # Most specific specialties first
    ("Neoplasms", "Oncology"),
    ("Eye Diseases", "Ophthalmology"),
    ("Skin Diseases", "Dermatology"),
    ("Stomatognathic Diseases", "Dental/Oral"),
    ("Mental Disorders", "Psychiatry"),
    ("Nervous System Diseases", "Neurology"),
    ("Female Urogenital Diseases and Pregnancy Complications", "Women's Health"),
    ("Urogenital Diseases", "Urology"),
    ("Endocrine System Diseases", "Endocrinology"),
    ("Hemic and Lymphatic Diseases", "Hematology"),
    ("Immune System Diseases", "Immunology"),
    # General organ-system categories
    ("Respiratory Tract Diseases", "Respiratory"),
    ("Digestive System Diseases", "Gastroenterology"),
    ("Musculoskeletal Diseases", "Musculoskeletal"),
    ("Cardiovascular Diseases", "Cardiovascular"),
    # Cross-cutting categories last
    ("Metabolic Diseases", "Metabolic"),
    ("Infections", "Infectious Disease"),
    ("Congenital, Hereditary, and Neonatal Diseases and Abnormalities", "Pediatric/Genetic"),
    ("Wounds and Injuries", "Trauma"),
    ("Pathological Conditions, Signs and Symptoms", "Other"),
]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _parse_ctgov_date(date_struct: Optional[dict]) -> tuple[Optional[date], Optional[str]]:
    """Parse a CT.gov date struct into (date, type).

    CT.gov dates come as dicts like:
        {"date": "2019-07-15", "type": "ACTUAL"}
        {"date": "2019-07"}
        {"date": "2019"}

    Partial dates are filled in with '01' for missing parts (month, day).
    Returns (None, None) if the struct is missing entirely.
    """
    if not date_struct:
        return None, None

    raw = date_struct.get("date")
    dtype = date_struct.get("type")

    if not raw:
        return None, dtype

    parts = raw.split("-")
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day), dtype
    except (ValueError, IndexError) as e:
        logger.warning("Failed to parse CT.gov date '%s': %s", raw, e)
        return None, dtype


def _pick_highest_phase(phases: Optional[list[str]]) -> Optional[str]:
    """Given a list of phases, return the highest one.

    A trial can list multiple phases (e.g., ["PHASE1", "PHASE2"] for a
    combined phase 1/2 study). For our purposes the highest phase is the
    one we want to filter on.
    """
    if not phases:
        return None
    order = ["NA", "EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE3", "PHASE4"]
    indexed = [(order.index(p) if p in order else -1, p) for p in phases]
    indexed.sort(reverse=True)
    return indexed[0][1] if indexed else None


def _months_between(start: Optional[date], end: Optional[date]) -> Optional[float]:
    """Rough month delta between two dates (for enrollment rate calculation).

    Uses 30.44 days per month — good enough for the aggregate stats we show.
    Returns None if either date is missing or if end <= start.
    """
    if not start or not end:
        return None
    days = (end - start).days
    if days <= 0:
        return None
    return round(days / 30.44, 2)


# Heuristic regex for device class extraction from intervention description.
# FDA device classes are I, II, III. We match "Class III" / "class ii" etc.
DEVICE_CLASS_RE = re.compile(r"\bclass\s+(i{1,3})\b", re.IGNORECASE)


def _extract_device_class(description: Optional[str]) -> Optional[str]:
    """Heuristically pull device class from free-text description."""
    if not description:
        return None
    match = DEVICE_CLASS_RE.search(description)
    if not match:
        return None
    return match.group(1).upper()


# Ordered keyword → device product-category map. Order is priority: the FIRST
# bucket whose keywords appear in the intervention name wins, so we list the
# specific/strong signals before the generic ones (a "drug-eluting stent" should
# read as Cardiovascular, not get swallowed by "Drug Delivery"). This is the
# granularity below "DEVICE" that a regulatory professional reasons in — the
# product family, which maps loosely to FDA review divisions and panels.
# Heuristic and deliberately small; Phase 8 can swap it for the FDA product-code
# (GMDN / FDA classification database) cross-reference.
_DEVICE_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Software / Digital Health", (
        "software", "algorithm", "mobile app", "smartphone", "digital health",
        "artificial intelligence", "machine learning", "deep learning",
        "decision support", "telehealth", "telemedicine", "virtual reality",
        "mobile application", "app-based", "digital therapeutic", "chatbot",
    )),
    ("Cardiovascular", (
        "stent", "catheter", "balloon", "pacemaker", "defibrillator", "icd",
        "heart valve", "valve", "angioplast", "coronary", "vascular", "aortic",
        "endovascular", "occluder", "cardiac lead", "left atrial", "tavr", "tavi",
    )),
    ("Neurostimulation", (
        "stimulat", "electrode", "deep brain", "spinal cord stim", "neuromodulat",
        "tms", "transcranial", "vagus", "cochlear", "neurostimul",
    )),
    ("Orthopedic / Implant", (
        "implant", "prosthe", "orthop", "knee", "hip joint", "spinal", "screw",
        "fixation", "bone graft", "arthroplast", "intervertebral",
    )),
    ("Imaging / Diagnostic Equipment", (
        "mri", "ct scan", "ultrasound", "x-ray", "xray", "pet scan", "spect",
        "scanner", "imaging", "endoscop", "colonoscop", "tomograph",
    )),
    ("Surgical / Ablation", (
        "robot", "laser", "ablation", "surgical", "scalpel", "stapler",
        "forceps", "cautery", "cryoablation", "radiofrequency",
    )),
    ("Drug Delivery / Infusion", (
        "infusion pump", "injector", "infusion", "inhaler", "autoinjector",
        "delivery system", "insulin pump", "syringe pump",
    )),
    ("Respiratory", (
        "ventilat", "cpap", "oxygen", "nebuliz", "respirator",
    )),
    ("Monitoring / Sensor", (
        "monitor", "sensor", "continuous glucose", "glucose meter", "holter",
        "biosensor", "wearable",
    )),
    ("Wound Care", (
        "dressing", "wound", "bandage", "negative pressure",
    )),
]


def _classify_device_product(name: Optional[str], description: Optional[str]) -> Optional[str]:
    """Bucket a DEVICE intervention into a coarse product category by name.

    We search the name first (high signal, low noise) then fall back to the
    description. Returns 'Other Device' when it's clearly a device but matches
    no bucket, so the drill-down never silently drops devices on the floor —
    "unclassified" is itself an honest, filterable answer.
    """
    haystack = " ".join(p for p in (name, description) if p).lower()
    if not haystack:
        return None
    for category, keywords in _DEVICE_CATEGORY_KEYWORDS:
        if any(kw in haystack for kw in keywords):
            return category
    return "Other Device"


def _derive_therapeutic_area(
    meshes: list[dict],
    ancestors: list[dict],
) -> Optional[str]:
    """Walk MeSH meshes + ancestors to find the broadest therapeutic area.

    We combine the direct MeSH assignments and their ancestors, then look for
    the first match in our prioritized MESH_TO_THERAPEUTIC_AREA list.
    """
    all_terms = set()
    for m in meshes:
        all_terms.add(m.get("term"))
    for a in ancestors:
        all_terms.add(a.get("term"))

    for mesh_term, area in MESH_TO_THERAPEUTIC_AREA:
        if mesh_term in all_terms:
            return area
    return None


# -----------------------------------------------------------------------------
# Main parser
# -----------------------------------------------------------------------------


def parse_trial(raw: dict) -> tuple[Trial, list[Location], list[Intervention], list[Outcome], list[dict]]:
    """Parse a single raw CT.gov study dict into trialcat model instances.

    Returns a tuple of:
        (Trial, [Location], [Intervention], [Outcome], [condition_info])

    where condition_info is a list of dicts like
        {"mesh_id": str | None, "term": str, "is_primary": bool, "broad": str | None}
    which the ETL layer uses to upsert into the Conditions table (because
    conditions are shared across trials and need dedup logic).
    """
    proto = raw.get("protocolSection", {})
    derived = raw.get("derivedSection", {})

    # --- Identification ---
    id_mod = proto.get("identificationModule", {})
    nct_id = id_mod.get("nctId")
    if not nct_id:
        raise ValueError("Trial missing NCT ID — this should never happen")

    # --- Dates ---
    status_mod = proto.get("statusModule", {})
    start_date, start_type = _parse_ctgov_date(status_mod.get("startDateStruct"))
    primary_completion_date, pc_type = _parse_ctgov_date(
        status_mod.get("primaryCompletionDateStruct")
    )
    completion_date, c_type = _parse_ctgov_date(status_mod.get("completionDateStruct"))

    # --- Enrollment ---
    design_mod = proto.get("designModule", {})
    enr_info = design_mod.get("enrollmentInfo") or {}
    enrollment_count = enr_info.get("count")
    enrollment_type = enr_info.get("type")

    # --- Computed enrollment rate (APPROXIMATE) ---
    # See Trial.approx_enrollment_rate_per_month docstring for the full
    # caveat. In short: we use primary_completion_date as a proxy for
    # "end of enrollment" because CT.gov doesn't give us a real enrollment
    # end date. This overestimates duration for trials with long primary
    # endpoints (overestimate duration → underestimate rate). The v2 ETL
    # will fill `actual_enrollment_rate_per_month` from resultsSection when
    # available.
    enrollment_end = primary_completion_date or completion_date
    months_enrolling = _months_between(start_date, enrollment_end)
    approx_enrollment_rate = None
    if enrollment_count and months_enrolling and months_enrolling > 0:
        approx_enrollment_rate = round(enrollment_count / months_enrolling, 2)

    # --- Sponsor ---
    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    lead = sponsor_mod.get("leadSponsor") or {}

    # --- Phase ---
    phase = _pick_highest_phase(design_mod.get("phases"))

    # --- Therapeutic area from MeSH ---
    cbm = derived.get("conditionBrowseModule") or {}
    therapeutic_area = _derive_therapeutic_area(
        cbm.get("meshes") or [],
        cbm.get("ancestors") or [],
    )

    # --- Build Trial instance ---
    trial = Trial(
        nct_id=nct_id,
        brief_title=id_mod.get("briefTitle"),
        official_title=id_mod.get("officialTitle"),
        brief_summary=proto.get("descriptionModule", {}).get("briefSummary"),
        lead_sponsor_name=lead.get("name"),
        lead_sponsor_class=lead.get("class"),
        overall_status=status_mod.get("overallStatus"),
        study_type=design_mod.get("studyType"),
        phase=phase,
        start_date=start_date,
        start_date_type=start_type,
        primary_completion_date=primary_completion_date,
        primary_completion_date_type=pc_type,
        completion_date=completion_date,
        completion_date_type=c_type,
        enrollment_count=enrollment_count,
        enrollment_type=enrollment_type,
        approx_enrollment_rate_per_month=approx_enrollment_rate,
        actual_enrollment_rate_per_month=None,  # v2: populate from resultsSection
        months_enrolling=months_enrolling,
        therapeutic_area=therapeutic_area,
    )

    # --- Locations ---
    contacts_mod = proto.get("contactsLocationsModule") or {}
    locations: list[Location] = []
    for loc in contacts_mod.get("locations") or []:
        geo = loc.get("geoPoint") or {}
        locations.append(
            Location(
                trial_nct_id=nct_id,
                facility=loc.get("facility"),
                city=loc.get("city"),
                state=loc.get("state"),
                country=loc.get("country"),
                country_code=None,  # filled in by the ETL layer via iso_country module
                zip=loc.get("zip"),
                lat=geo.get("lat"),
                lon=geo.get("lon"),
                site_status=loc.get("status"),
            )
        )

    # --- Interventions ---
    arms_mod = proto.get("armsInterventionsModule") or {}
    interventions: list[Intervention] = []
    for iv in arms_mod.get("interventions") or []:
        desc = iv.get("description")
        iv_type = iv.get("type")
        iv_name = iv.get("name")
        is_device = iv_type == "DEVICE"
        interventions.append(
            Intervention(
                trial_nct_id=nct_id,
                type=iv_type,
                name=iv_name,
                description=desc,
                device_class_hint=_extract_device_class(desc) if is_device else None,
                product_category=_classify_device_product(iv_name, desc) if is_device else None,
            )
        )

    # --- Outcomes ---
    outcomes_mod = proto.get("outcomesModule") or {}
    outcomes: list[Outcome] = []
    for po in outcomes_mod.get("primaryOutcomes") or []:
        outcomes.append(
            Outcome(
                trial_nct_id=nct_id,
                measure=po.get("measure") or "",
                description=po.get("description"),
                time_frame=po.get("timeFrame"),
                is_primary=True,
            )
        )
    for so in outcomes_mod.get("secondaryOutcomes") or []:
        outcomes.append(
            Outcome(
                trial_nct_id=nct_id,
                measure=so.get("measure") or "",
                description=so.get("description"),
                time_frame=so.get("timeFrame"),
                is_primary=False,
            )
        )

    # --- Conditions (returned as dicts, not Condition instances, because
    # the ETL layer needs to dedupe against the existing Conditions table) ---
    condition_info: list[dict] = []
    meshes = cbm.get("meshes") or []
    primary_conditions = (proto.get("conditionsModule") or {}).get("conditions") or []

    # Primary conditions — from the trial's own list
    for cond_term in primary_conditions:
        # Try to find matching mesh_id
        mesh_id = None
        for m in meshes:
            if m.get("term", "").lower() == cond_term.lower():
                mesh_id = m.get("id")
                break
        condition_info.append(
            {
                "mesh_id": mesh_id,
                "term": cond_term,
                "is_primary": True,
                "broad": therapeutic_area,
            }
        )

    # Additional mesh terms that weren't in primary list
    seen_terms = {c["term"].lower() for c in condition_info}
    for m in meshes:
        term = m.get("term")
        if term and term.lower() not in seen_terms:
            condition_info.append(
                {
                    "mesh_id": m.get("id"),
                    "term": term,
                    "is_primary": False,
                    "broad": therapeutic_area,
                }
            )

    return trial, locations, interventions, outcomes, condition_info
