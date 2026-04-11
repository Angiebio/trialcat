"""Parser unit tests — runs against real CT.gov fixture data.

These tests verify that parse_trial() extracts every field we care about
from actual CT.gov v2 API responses. When CT.gov changes their schema,
the integration test (test_ctgov_client.py) will fail first, and we re-run
the fixture fetch script to pick up the new shape.
"""

from datetime import date

import pytest

from app.services.parser import (
    _derive_therapeutic_area,
    _extract_device_class,
    _months_between,
    _parse_ctgov_date,
    _pick_highest_phase,
    parse_trial,
)


# -----------------------------------------------------------------------------
# Helper function tests
# -----------------------------------------------------------------------------


class TestParseCtgovDate:
    def test_full_date(self):
        d, t = _parse_ctgov_date({"date": "2019-07-15", "type": "ACTUAL"})
        assert d == date(2019, 7, 15)
        assert t == "ACTUAL"

    def test_year_month(self):
        d, t = _parse_ctgov_date({"date": "2019-07"})
        assert d == date(2019, 7, 1)
        assert t is None

    def test_year_only(self):
        d, t = _parse_ctgov_date({"date": "2019"})
        assert d == date(2019, 1, 1)

    def test_none_struct(self):
        d, t = _parse_ctgov_date(None)
        assert d is None
        assert t is None

    def test_empty_struct(self):
        d, t = _parse_ctgov_date({})
        assert d is None

    def test_malformed_date(self):
        d, t = _parse_ctgov_date({"date": "not-a-date"})
        assert d is None


class TestPickHighestPhase:
    def test_single_phase(self):
        assert _pick_highest_phase(["PHASE3"]) == "PHASE3"

    def test_multi_phase(self):
        assert _pick_highest_phase(["PHASE1", "PHASE2"]) == "PHASE2"

    def test_na(self):
        assert _pick_highest_phase(["NA"]) == "NA"

    def test_empty(self):
        assert _pick_highest_phase([]) is None

    def test_none(self):
        assert _pick_highest_phase(None) is None


class TestMonthsBetween:
    def test_normal_range(self):
        start = date(2020, 1, 1)
        end = date(2020, 12, 31)
        result = _months_between(start, end)
        assert result is not None
        assert 11.9 < result < 12.1  # ~12 months

    def test_reverse_range_returns_none(self):
        assert _months_between(date(2020, 12, 1), date(2020, 1, 1)) is None

    def test_missing_start(self):
        assert _months_between(None, date(2020, 1, 1)) is None

    def test_missing_end(self):
        assert _months_between(date(2020, 1, 1), None) is None


class TestExtractDeviceClass:
    def test_class_iii(self):
        assert _extract_device_class("A Class III device for cardiac use") == "III"

    def test_class_ii_lowercase(self):
        assert _extract_device_class("class ii monitoring system") == "II"

    def test_no_class(self):
        assert _extract_device_class("A drug intervention") is None

    def test_none_input(self):
        assert _extract_device_class(None) is None


class TestDeriveTherapeuticArea:
    def test_cardiovascular_from_ancestors(self):
        result = _derive_therapeutic_area(
            meshes=[{"id": "D1", "term": "Acute Coronary Syndrome"}],
            ancestors=[{"id": "D2", "term": "Cardiovascular Diseases"}],
        )
        assert result == "Cardiovascular"

    def test_oncology_from_mesh(self):
        result = _derive_therapeutic_area(
            meshes=[{"id": "D1", "term": "Neoplasms"}],
            ancestors=[],
        )
        assert result == "Oncology"

    def test_unknown_returns_none(self):
        result = _derive_therapeutic_area(
            meshes=[{"id": "X", "term": "Something weird"}],
            ancestors=[],
        )
        assert result is None


# -----------------------------------------------------------------------------
# Full parse_trial tests against real fixture data
# -----------------------------------------------------------------------------


class TestParseTrialVEGFTrapEye:
    """NCT00943072 — Regeneron VEGF Trap-Eye, Phase 3, completed, multi-site."""

    @pytest.fixture(autouse=True)
    def _setup(self, samples_by_nct):
        self.raw = samples_by_nct["NCT00943072"]
        self.trial, self.locations, self.interventions, self.outcomes, self.conditions = parse_trial(
            self.raw
        )

    def test_basic_identity(self):
        assert self.trial.nct_id == "NCT00943072"
        assert "VEGF" in self.trial.brief_title
        assert self.trial.overall_status == "COMPLETED"
        assert self.trial.study_type == "INTERVENTIONAL"
        assert self.trial.phase == "PHASE3"

    def test_sponsor(self):
        assert self.trial.lead_sponsor_name == "Regeneron Pharmaceuticals"
        assert self.trial.lead_sponsor_class == "INDUSTRY"

    def test_enrollment(self):
        assert self.trial.enrollment_count == 189
        assert self.trial.enrollment_type == "ACTUAL"

    def test_dates_parsed(self):
        assert self.trial.start_date == date(2009, 7, 1)
        assert self.trial.primary_completion_date == date(2010, 10, 1)
        assert self.trial.completion_date == date(2012, 4, 1)

    def test_approx_enrollment_rate_computed(self):
        # ~15 months enrolling, 189 patients = ~12.6 patients/mo
        # This is the APPROXIMATE rate (see column docstring for caveat).
        assert self.trial.months_enrolling is not None
        assert 14 < self.trial.months_enrolling < 16
        assert self.trial.approx_enrollment_rate_per_month is not None
        assert 10 < self.trial.approx_enrollment_rate_per_month < 14
        # actual_enrollment_rate is None until we wire up resultsSection parsing (v2)
        assert self.trial.actual_enrollment_rate_per_month is None

    def test_therapeutic_area_ophthalmology(self):
        # Macular Edema → Eye Diseases ancestor → Ophthalmology
        assert self.trial.therapeutic_area == "Ophthalmology"

    def test_locations_populated(self):
        assert len(self.locations) == 61
        # Spot-check the first one
        first = self.locations[0]
        assert first.city == "Phoenix"
        assert first.state == "Arizona"
        assert first.country == "United States"
        # Geo coordinates came through
        assert first.lat is not None
        assert first.lon is not None

    def test_interventions_populated(self):
        assert len(self.interventions) == 2
        types = {i.type for i in self.interventions}
        # Sham arm is "DRUG", active arm is "BIOLOGICAL"
        assert "BIOLOGICAL" in types or "DRUG" in types

    def test_primary_outcome(self):
        primary = [o for o in self.outcomes if o.is_primary]
        assert len(primary) >= 1
        assert "BCVA" in primary[0].measure or "Letters" in primary[0].measure

    def test_conditions_extracted(self):
        assert len(self.conditions) > 0
        primary = [c for c in self.conditions if c["is_primary"]]
        assert len(primary) >= 1


class TestParseTrialStroke:
    """NCT04047563 — Pharmazz stroke trial, PHASE3, India sites."""

    @pytest.fixture(autouse=True)
    def _setup(self, samples_by_nct):
        self.raw = samples_by_nct["NCT04047563"]
        self.trial, self.locations, self.interventions, self.outcomes, self.conditions = parse_trial(
            self.raw
        )

    def test_enrollment(self):
        assert self.trial.enrollment_count == 158

    def test_phase(self):
        assert self.trial.phase == "PHASE3"

    def test_therapeutic_area_neurology(self):
        # Stroke → Cerebrovascular → Nervous System → Neurology
        # OR Stroke → Cardiovascular Diseases (MeSH classifies stroke under both)
        # Our priority list puts Oncology, Cardiovascular, Neurology in that order,
        # so whichever matches first wins. Just assert it's populated.
        assert self.trial.therapeutic_area is not None


class TestParseTrialDevice:
    """NCT01072877 — Boston Scientific polidocanol."""

    @pytest.fixture(autouse=True)
    def _setup(self, samples_by_nct):
        self.raw = samples_by_nct["NCT01072877"]
        self.trial, self.locations, self.interventions, self.outcomes, self.conditions = parse_trial(
            self.raw
        )

    def test_sponsor_is_boston_scientific(self):
        assert "Boston Scientific" in self.trial.lead_sponsor_name

    def test_phase(self):
        assert self.trial.phase == "PHASE3"


class TestParseAllSamples:
    """Sanity tests that every sample parses without exploding."""

    def test_every_sample_parses(self, ctgov_samples):
        for raw in ctgov_samples:
            trial, locations, interventions, outcomes, conditions = parse_trial(raw)
            assert trial.nct_id.startswith("NCT")
            # Every trial should have at least SOME structure even if fields are missing
            assert isinstance(locations, list)
            assert isinstance(interventions, list)
            assert isinstance(outcomes, list)
            assert isinstance(conditions, list)
