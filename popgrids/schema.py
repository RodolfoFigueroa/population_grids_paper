"""Frozen dataclasses describing each European census dataset in the catalog.

The catalog is keyed by ``dataset_id`` (not country) because some countries
expose several "finest" layers (e.g. France: a 200 m grid *and* IRIS polygons).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AccessMethod = Literal[
    "direct_zip",
    "direct_file",
    "ogc_api",
    "arcgis_hub",
    "wfs",
    "gated",
]
Tier = Literal["A", "B", "C"]
#: How geometry is materialised from the (possibly tabular) source.
GeometryKind = Literal["vector", "grid_csv_center", "grid_csv_lower_left"]
PopulationMode = Literal["bundled", "join"]
TableFormat = Literal["csv", "xlsx", "zip-csv", "zip-xlsx"]


@dataclass(frozen=True, slots=True)
class GeometryAccess:
    """Where and how the geometry (and bundled attributes) are fetched."""

    tier: Tier
    method: AccessMethod
    urls: tuple[str, ...]
    source_crs: str
    unit_id_field: str
    archive_member_contains: tuple[str, ...] = ()
    archive_member_suffix: str | None = None
    layer: str | None = None
    geometry_kind: GeometryKind = "vector"
    # CSV-grid parameters (used when geometry_kind starts with "grid_csv").
    csv_separator: str = ";"
    csv_encoding: str = "utf-8"
    x_field: str | None = None
    y_field: str | None = None
    cell_size_m: int | None = None
    # Tier-B API paging.
    query_params: dict[str, str] = field(default_factory=dict)
    page_size: int | None = None


@dataclass(frozen=True, slots=True)
class PopulationSource:
    """Where the total-population value comes from."""

    mode: PopulationMode
    attr: str
    table_url: str | None = None
    table_format: TableFormat | None = None
    table_member_contains: tuple[str, ...] = ()
    table_separator: str = ","
    table_encoding: str = "utf-8"
    table_skiprows: int = 0  # title rows to skip (xlsx)
    table_sheet_contains: str | None = None  # only read xlsx sheets whose name matches
    join_key_geom: str | None = None
    join_key_pop: str | None = None
    # Build ``join_key_pop`` by zero-padding and concatenating these
    # ``(column, width)`` parts (e.g. Spain CUSEC = cpro(2)+cmun(3)+dist(2)+secc(3)).
    build_join_key_from: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class CountryDataset:
    """A single finest-resolution census dataset for one country."""

    dataset_id: str
    country: str  # ISO-3166-1 alpha-2 (UK used for GB to match source codes).
    unit_label: str
    unit_code: str
    vintage: int
    geometry: GeometryAccess
    population: PopulationSource
    licence: str
    attribution: str
    # Output CRS. Europe normalizes to EPSG:3035 (the catalog default); non-European
    # datasets set this explicitly (EPSG:4326 or a regional equal-area).
    target_crs: str = "EPSG:3035"
    verified: bool = False
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Candidate:
    """A surveyed-but-unwired country: appears in the coverage list, not yet built."""

    country: str  # ISO-3166-1 alpha-2
    unit_label: str  # finest official census unit
    latest_census: int  # most recent census year
    open_finest_year: int | None  # most recent census open at finest resolution
    tier: Tier  # A/B/C access tier (same scheme as CountryDataset.geometry.tier)
    agency: str
    bundled: bool | None = None  # population bundled in geometry vs separate join
    notes: str = ""
