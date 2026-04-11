"""Geo normalization tests — country and US state."""

from app.services.geo import to_iso2, to_us_state_code


class TestCountryNormalization:
    def test_united_states(self):
        assert to_iso2("United States") == "US"

    def test_united_states_of_america(self):
        assert to_iso2("United States of America") == "US"

    def test_united_kingdom(self):
        assert to_iso2("United Kingdom") == "GB"

    def test_germany(self):
        assert to_iso2("Germany") == "DE"

    def test_case_insensitive(self):
        assert to_iso2("germany") == "DE"
        assert to_iso2("GERMANY") == "DE"

    def test_the_netherlands(self):
        # Both variants should resolve
        assert to_iso2("Netherlands") == "NL"
        assert to_iso2("The Netherlands") == "NL"

    def test_korea(self):
        assert to_iso2("Korea, Republic of") == "KR"
        assert to_iso2("South Korea") == "KR"

    def test_unknown_country(self):
        assert to_iso2("Nowherestan") is None

    def test_none_input(self):
        assert to_iso2(None) is None

    def test_empty_string(self):
        assert to_iso2("") is None


class TestUSStateNormalization:
    def test_full_name_california(self):
        assert to_us_state_code("California") == "CA"

    def test_full_name_new_york(self):
        assert to_us_state_code("New York") == "NY"

    def test_full_name_case_insensitive(self):
        assert to_us_state_code("california") == "CA"
        assert to_us_state_code("NEW YORK") == "NY"

    def test_code_passthrough(self):
        assert to_us_state_code("CA") == "CA"
        assert to_us_state_code("NY") == "NY"

    def test_code_lowercase_passthrough(self):
        assert to_us_state_code("ca") == "CA"

    def test_dc(self):
        assert to_us_state_code("District of Columbia") == "DC"
        assert to_us_state_code("DC") == "DC"

    def test_puerto_rico(self):
        assert to_us_state_code("Puerto Rico") == "PR"
        assert to_us_state_code("PR") == "PR"

    def test_virgin_islands_variants(self):
        assert to_us_state_code("Virgin Islands") == "VI"
        assert to_us_state_code("U.S. Virgin Islands") == "VI"
        assert to_us_state_code("United States Virgin Islands") == "VI"

    def test_unknown_state(self):
        assert to_us_state_code("Atlantis") is None

    def test_none_input(self):
        assert to_us_state_code(None) is None

    def test_empty_string(self):
        assert to_us_state_code("") is None

    def test_whitespace_stripped(self):
        assert to_us_state_code("  California  ") == "CA"

    def test_two_letter_non_state_rejected(self):
        # "XX" is not a real state code — should return None, not echo
        assert to_us_state_code("XX") is None


class TestLoaderIntegration:
    """Verify that state_code is populated for US locations when loading."""

    def test_state_code_populated_for_us_location(self, db_session, samples_by_nct):
        from sqlalchemy import select

        from app.etl.loader import load_trial
        from app.models import Location

        raw = samples_by_nct["NCT00943072"]  # VEGF Trap-Eye, US sites
        load_trial(db_session, raw)
        db_session.commit()

        # Check the Arizona site we know is first in the fixture
        arizona = db_session.scalars(
            select(Location).where(
                Location.trial_nct_id == "NCT00943072",
                Location.city == "Phoenix",
            )
        ).first()
        assert arizona is not None
        assert arizona.country_code == "US"
        assert arizona.state == "Arizona"
        assert arizona.state_code == "AZ"
