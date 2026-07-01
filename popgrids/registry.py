"""Global registry: merge every region's catalog and candidate list.

Each region module (``popgrids.<region>.catalog``) exposes ``CATALOG``
(dataset_id -> CountryDataset) and ``CANDIDATES`` (surveyed-but-unwired). This
module merges them into one global view and resolves country -> region.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from popgrids.americas import catalog as _americas
from popgrids.asiapac import catalog as _asiapac
from popgrids.europe import catalog as _europe

if TYPE_CHECKING:
    from types import ModuleType

    from popgrids.schema import Candidate, CountryDataset

#: region name -> region catalog module
REGIONS: dict[str, ModuleType] = {
    "europe": _europe,
    "americas": _americas,
    "asiapac": _asiapac,
}


def _merge_catalog() -> dict[str, CountryDataset]:
    merged: dict[str, CountryDataset] = {}
    for module in REGIONS.values():
        merged.update(module.CATALOG)
    return merged


def _country_region_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name, module in REGIONS.items():
        for dataset in module.CATALOG.values():
            mapping[dataset.country] = name
        for candidate in module.CANDIDATES:
            mapping.setdefault(candidate.country, name)
    return mapping


#: every wired dataset across all regions
CATALOG: dict[str, CountryDataset] = _merge_catalog()
#: every surveyed-but-unwired country across all regions
CANDIDATES: tuple[Candidate, ...] = tuple(
    candidate for module in REGIONS.values() for candidate in module.CANDIDATES
)
_COUNTRY_REGION: dict[str, str] = _country_region_map()


def region_for_country(country: str) -> str | None:
    """Return the region name a country belongs to, or None."""
    return _COUNTRY_REGION.get(country.upper())


def available_countries() -> list[str]:
    """Return the sorted ISO-2 country codes with at least one wired dataset."""
    return sorted({dataset.country for dataset in CATALOG.values()})


def datasets_for_country(country: str) -> list[CountryDataset]:
    """Return all wired datasets for an ISO-2 ``country`` code."""
    return [
        dataset for dataset in CATALOG.values() if dataset.country == country.upper()
    ]


def vintages_for(country: str, level: str) -> list[int]:
    """Return the available vintages (years) for a country + unit level."""
    return sorted(
        {
            dataset.vintage
            for dataset in CATALOG.values()
            if dataset.country == country.upper() and dataset.unit_code == level
        },
    )
