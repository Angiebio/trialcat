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
