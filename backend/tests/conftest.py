"""Pytest shared fixtures.

Loads the saved CT.gov sample data once per session and exposes individual
trials by NCT ID for test use. This is the foundation of our "synthetic but
real" testing approach — we test against actual API data captured to disk.
"""

import json
from pathlib import Path

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ctgov_sample.json"


@pytest.fixture(scope="session")
def ctgov_samples() -> list[dict]:
    """All sample CT.gov trial dicts loaded from the fixture file."""
    if not FIXTURE_PATH.exists():
        pytest.fail(
            f"Missing fixture file at {FIXTURE_PATH}. "
            f"Run `python backend/tests/fixtures/_fetch_samples.py` to create it."
        )
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def samples_by_nct(ctgov_samples) -> dict[str, dict]:
    """Index of sample trials keyed by NCT ID for targeted tests."""
    return {
        s["protocolSection"]["identificationModule"]["nctId"]: s
        for s in ctgov_samples
    }
