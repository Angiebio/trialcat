"""One-off script to fetch a small diverse sample of trials from CT.gov.

Run this manually when you want to refresh the fixture data. The output is
saved to ctgov_sample.json and used by the unit test suite as a stable,
network-free representation of the API shape. If CT.gov ever changes their
API, the integration test will fail and we'll know to re-run this script.

Usage:
    python backend/tests/fixtures/_fetch_samples.py
"""
import json
import sys
from pathlib import Path

import requests

# A diverse handful of NCT IDs covering different scenarios:
# - Drug trial (industry sponsor, multi-site)
# - Device trial (Phase III, US-only)
# - Biological / vaccine
# - Behavioral / observational
# - Stroke trial (international)
# - Old completed trial with full results
SAMPLE_NCT_IDS = [
    "NCT00943072",  # Regeneron VEGF Trap-Eye - drug, Phase 3, completed, multi-site
    "NCT04047563",  # Pharmazz stroke - drug, Phase 3, India sites
    "NCT01072877",  # Boston Scientific Polidocanol - device, Phase 3
    "NCT03889795",  # Pfizer COVID vaccine - biological, Phase 3, global
    "NCT04280705",  # Remdesivir - antiviral, Phase 3
    "NCT05012787",  # Cardiovascular device - newer
]

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
USER_AGENT = "trialcat/0.1 (https://trialcat.ai; contact@therealcat.ai)"
OUT_PATH = Path(__file__).parent / "ctgov_sample.json"


def fetch_one(session: requests.Session, nct_id: str) -> dict:
    """Fetch a single trial by NCT ID. Returns the raw API response dict."""
    url = f"{BASE_URL}/{nct_id}"
    print(f"  fetching {nct_id} ... ", end="", flush=True)
    response = session.get(url, params={"format": "json"}, timeout=30.0)
    response.raise_for_status()
    data = response.json()
    print(f"OK ({len(response.content)} bytes)")
    return data


def main() -> int:
    print(f"Fetching {len(SAMPLE_NCT_IDS)} sample trials from CT.gov v2 ...")
    samples = []

    # Note: using requests instead of httpx because CT.gov uses TLS fingerprint
    # blocking (JA3/JA4) that rejects httpx's TLS handshake. requests works.
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    for nct_id in SAMPLE_NCT_IDS:
        try:
            samples.append(fetch_one(session, nct_id))
        except Exception as e:
            print(f"FAILED: {e}")
            # Don't fail the whole run; we want whatever samples we can get
            continue

    if not samples:
        print("No samples fetched - aborting")
        return 1

    OUT_PATH.write_text(json.dumps(samples, indent=2), encoding="utf-8")
    print(f"\nSaved {len(samples)} trials to {OUT_PATH}")
    print(f"  ({OUT_PATH.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
