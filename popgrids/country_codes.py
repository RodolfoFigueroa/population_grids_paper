"""ISO-3166 alpha-2 → alpha-3 mapping for the countries in the registry.

The catalog keys countries by ISO alpha-2 (with ``UK`` used for Great Britain to
match source codes); World Bank / ODIN key by alpha-3. This small map covers the
wired + surveyed countries; extend it as new countries are added. ``EU`` (the
GEOSTAT baseline) is intentionally absent — it is not a country.
"""

from __future__ import annotations

#: ISO alpha-2 -> alpha-3 for registry countries (UK -> GBR is the special case).
ISO2_TO_ISO3: dict[str, str] = {
    # Europe
    "AT": "AUT",
    "BE": "BEL",
    "CH": "CHE",
    "DE": "DEU",
    "DK": "DNK",
    "ES": "ESP",
    "FI": "FIN",
    "FR": "FRA",
    "GR": "GRC",
    "IE": "IRL",
    "IT": "ITA",
    "NL": "NLD",
    "NO": "NOR",
    "PL": "POL",
    "PT": "PRT",
    "SE": "SWE",
    "UK": "GBR",
    # Americas
    "US": "USA",
    "CA": "CAN",
    "MX": "MEX",
    "BR": "BRA",
    "CL": "CHL",
    "CO": "COL",
    "AR": "ARG",
    "EC": "ECU",
    "PE": "PER",
    "UY": "URY",
    # Asia-Pacific
    "AU": "AUS",
    "NZ": "NZL",
    "JP": "JPN",
    "KR": "KOR",
    "ID": "IDN",
    "PH": "PHL",
    "IN": "IND",
    "CN": "CHN",
    # Africa / other
    "ZA": "ZAF",
    "RU": "RUS",
}

#: reverse map (alpha-3 -> alpha-2), first wins.
ISO3_TO_ISO2: dict[str, str] = {v: k for k, v in ISO2_TO_ISO3.items()}


def to_iso3(iso2: str) -> str | None:
    """Return the ISO alpha-3 code for an alpha-2 code, or None if unknown."""
    return ISO2_TO_ISO3.get(iso2.upper())
