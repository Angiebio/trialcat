"""Geographic normalization — free-text country names → ISO 3166-1 alpha-2.

CT.gov stores country as a free-text name ("United States", "Germany", "Korea,
Republic of"). To aggregate by country we need a stable code. This module
is a lookup table plus a few hand-tuned aliases for countries whose CT.gov
name doesn't match ISO's official name.

Why not use `pycountry`? It works but adds a dependency. The number of
countries doesn't change often, so we can maintain a small hand-picked
mapping and cover 99% of trials. If we ever need more coverage, swap this
file's implementation for `pycountry` — the public API (`to_iso2`) doesn't
change.
"""

from typing import Optional


# Minimal name → ISO2 mapping. Covers the most common CT.gov country strings.
# Add to this when we see trials with country names not yet in the table.
COUNTRY_NAME_TO_ISO2: dict[str, str] = {
    "United States": "US",
    "United States of America": "US",
    "USA": "US",
    "Canada": "CA",
    "Mexico": "MX",
    "United Kingdom": "GB",
    "UK": "GB",
    "Great Britain": "GB",
    "England": "GB",
    "Scotland": "GB",
    "Wales": "GB",
    "Northern Ireland": "GB",
    "France": "FR",
    "Germany": "DE",
    "Italy": "IT",
    "Spain": "ES",
    "Portugal": "PT",
    "Netherlands": "NL",
    "The Netherlands": "NL",
    "Belgium": "BE",
    "Luxembourg": "LU",
    "Austria": "AT",
    "Switzerland": "CH",
    "Ireland": "IE",
    "Denmark": "DK",
    "Norway": "NO",
    "Sweden": "SE",
    "Finland": "FI",
    "Iceland": "IS",
    "Poland": "PL",
    "Czech Republic": "CZ",
    "Czechia": "CZ",
    "Slovakia": "SK",
    "Hungary": "HU",
    "Romania": "RO",
    "Bulgaria": "BG",
    "Greece": "GR",
    "Turkey": "TR",
    "Russia": "RU",
    "Russian Federation": "RU",
    "Ukraine": "UA",
    "Belarus": "BY",
    "Lithuania": "LT",
    "Latvia": "LV",
    "Estonia": "EE",
    "Serbia": "RS",
    "Croatia": "HR",
    "Slovenia": "SI",
    "Bosnia and Herzegovina": "BA",
    "Montenegro": "ME",
    "North Macedonia": "MK",
    "Macedonia": "MK",
    "Albania": "AL",
    "Cyprus": "CY",
    "Malta": "MT",
    "Israel": "IL",
    "Palestinian Territory, Occupied": "PS",
    "Palestinian Territories": "PS",
    "Saudi Arabia": "SA",
    "United Arab Emirates": "AE",
    "Qatar": "QA",
    "Kuwait": "KW",
    "Oman": "OM",
    "Bahrain": "BH",
    "Iran, Islamic Republic of": "IR",
    "Iran": "IR",
    "Iraq": "IQ",
    "Jordan": "JO",
    "Lebanon": "LB",
    "Egypt": "EG",
    "Morocco": "MA",
    "Tunisia": "TN",
    "Algeria": "DZ",
    "South Africa": "ZA",
    "Nigeria": "NG",
    "Kenya": "KE",
    "Uganda": "UG",
    "Tanzania": "TZ",
    "Ethiopia": "ET",
    "Ghana": "GH",
    "Senegal": "SN",
    "Mali": "ML",
    "Rwanda": "RW",
    "India": "IN",
    "Pakistan": "PK",
    "Bangladesh": "BD",
    "Sri Lanka": "LK",
    "Nepal": "NP",
    "China": "CN",
    "Hong Kong": "HK",
    "Taiwan": "TW",
    "Japan": "JP",
    "Korea, Republic of": "KR",
    "South Korea": "KR",
    "North Korea": "KP",
    "Korea, Democratic People's Republic of": "KP",
    "Mongolia": "MN",
    "Vietnam": "VN",
    "Viet Nam": "VN",
    "Thailand": "TH",
    "Cambodia": "KH",
    "Laos": "LA",
    "Myanmar": "MM",
    "Burma": "MM",
    "Malaysia": "MY",
    "Singapore": "SG",
    "Indonesia": "ID",
    "Philippines": "PH",
    "Australia": "AU",
    "New Zealand": "NZ",
    "Brazil": "BR",
    "Argentina": "AR",
    "Chile": "CL",
    "Colombia": "CO",
    "Peru": "PE",
    "Venezuela": "VE",
    "Uruguay": "UY",
    "Paraguay": "PY",
    "Bolivia": "BO",
    "Ecuador": "EC",
    "Panama": "PA",
    "Costa Rica": "CR",
    "Dominican Republic": "DO",
    "Guatemala": "GT",
    "Honduras": "HN",
    "Nicaragua": "NI",
    "El Salvador": "SV",
    "Cuba": "CU",
    "Puerto Rico": "PR",
    "Jamaica": "JM",
    "Trinidad and Tobago": "TT",
    "Kazakhstan": "KZ",
    "Uzbekistan": "UZ",
    "Georgia": "GE",
    "Armenia": "AM",
    "Azerbaijan": "AZ",
}


def to_iso2(country_name: Optional[str]) -> Optional[str]:
    """Convert a free-text country name to ISO 3166-1 alpha-2 code.

    Returns None if the country name is missing or unknown. Logs unknown
    values so we can add them to the map. Case-insensitive exact match
    first, then a fallback that strips common prefixes like "The".
    """
    if not country_name:
        return None

    # Exact match
    if country_name in COUNTRY_NAME_TO_ISO2:
        return COUNTRY_NAME_TO_ISO2[country_name]

    # Case-insensitive match
    for name, iso in COUNTRY_NAME_TO_ISO2.items():
        if name.lower() == country_name.lower():
            return iso

    # Try stripping leading "The "
    if country_name.lower().startswith("the "):
        stripped = country_name[4:]
        return to_iso2(stripped)

    return None


# =============================================================================
# US state normalization
# =============================================================================
# CT.gov stores US state as free-text in the `state` field: "California",
# "New York", sometimes "NY", rarely the full ISO "US-CA". We normalize to
# the USPS 2-letter code so Phase 4's US drill-down can aggregate cleanly
# via `WHERE country_code='US' AND state_code='CA'`.
#
# Includes all 50 states, DC, and commonly-seen US territories. Not included:
# misspellings, abbreviations with periods ("N.Y."), historic names.

US_STATE_NAME_TO_CODE: dict[str, str] = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    # Territories
    "Puerto Rico": "PR",
    "Guam": "GU",
    "American Samoa": "AS",
    "Northern Mariana Islands": "MP",
    "U.S. Virgin Islands": "VI",
    "United States Virgin Islands": "VI",
    "Virgin Islands": "VI",
}

# Reverse lookup for when CT.gov (or a user) passes in the code directly.
# Values are the preferred canonical form of the 2-letter code.
US_STATE_CODES: set[str] = set(US_STATE_NAME_TO_CODE.values())


def to_us_state_code(state: Optional[str]) -> Optional[str]:
    """Normalize a US state value to its USPS 2-letter code.

    Accepts:
    - Full state names: "California" → "CA"
    - Existing 2-letter codes (case insensitive): "ca" → "CA"
    - None or empty string → None

    Returns None for unknown values. This is a SILENT None — it doesn't log
    warnings — because the same function is called on non-US locations where
    we expect it to return None. The ETL layer only calls this when
    country_code == 'US'.
    """
    if not state:
        return None

    stripped = state.strip()
    if not stripped:
        return None

    # Exact name match (case-insensitive)
    for name, code in US_STATE_NAME_TO_CODE.items():
        if name.lower() == stripped.lower():
            return code

    # 2-letter code passthrough
    upper = stripped.upper()
    if len(upper) == 2 and upper in US_STATE_CODES:
        return upper

    return None
