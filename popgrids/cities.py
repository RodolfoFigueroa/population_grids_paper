"""GHS Urban Centre Database (GHS-UCDB): city reference + optional clipping.

GHS-UCDB R2024A urban-centre polygons (derived from GHSL SMOD class-30 cells)
are the primary way to *define* cities, consistent with the repo's existing GHSL
use. By default this is downloaded as a standalone reference layer; it can also
clip a national census layer to specific cities (the optional ``--cities`` flow).

Exact R2024A column names are confirmed on first download (R2019A used
``UC_NM_MN`` / ``ID_HDC_G0`` / ``CTR_MN_ISO`` / ``P15``); they are auto-detected
from candidate lists and the run fails loudly if none match.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import geopandas as gpd
import pandas as pd

from popgrids.adapters import AdapterError
from popgrids.crs import CRS_LAEA_EUROPE, CRS_WGS84
from popgrids.io import download, extract_members, write_geoparquet

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    import requests

logger = logging.getLogger(__name__)

UCDB_URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/GHS_UCDB_GLOBE_R2024A/"
    "GHS_UCDB_GLOBE_R2024A/V1-2/GHS_UCDB_GLOBE_R2024A_V1_2.zip"
)
UCDB_VERSION = "R2024A V1-2"
# Column-name candidates span GHS-UCDB R2019A (UC_NM_MN/ID_HDC_G0/CTR_MN_*) and
# R2024A (GC_*_2025); detected at runtime and validated loudly if none match.
_NAME_CANDIDATES = ("UC_NM_MN", "GC_UCN_MAI_2025", "UC_NM_MN_2025", "name")
_ID_CANDIDATES = ("ID_HDC_G0", "ID_UC_G0", "ID_UC_G", "id")
_COUNTRY_CANDIDATES = (
    "CTR_MN_ISO",
    "GC_CNT_GAD_ISO3_2025",
    "GC_CNT_GAD_2025",
    "GC_CNT_UNN_2025",
    "CTR_MN_NM",
)
_POP_CANDIDATES = ("P15", "GC_POP_TOT_2025", "POP_2025", "P_2020")
_HALF = 2.0

#: European countries by ISO3 *and* common GADM/UN names. R2024A general
#: characteristics carry a country *name* (no ISO3), so we match either form and
#: fall back to keeping all centres if nothing matches (format surprise).
EUROPE_COUNTRIES: frozenset[str] = frozenset(
    {
        # ISO3
        "ALB",
        "AND",
        "AUT",
        "BEL",
        "BGR",
        "BIH",
        "BLR",
        "CHE",
        "CYP",
        "CZE",
        "DEU",
        "DNK",
        "ESP",
        "EST",
        "FIN",
        "FRA",
        "GBR",
        "GRC",
        "HRV",
        "HUN",
        "IRL",
        "ISL",
        "ITA",
        "LIE",
        "LTU",
        "LUX",
        "LVA",
        "MDA",
        "MKD",
        "MLT",
        "MNE",
        "NLD",
        "NOR",
        "POL",
        "PRT",
        "ROU",
        "SRB",
        "SVK",
        "SVN",
        "SWE",
        "UKR",
        "XKX",
        # Names (GADM / UN style)
        "Albania",
        "Andorra",
        "Austria",
        "Belarus",
        "Belgium",
        "Bosnia and Herzegovina",
        "Bulgaria",
        "Croatia",
        "Cyprus",
        "Czechia",
        "Czech Republic",
        "Denmark",
        "Estonia",
        "Finland",
        "France",
        "Germany",
        "Greece",
        "Hungary",
        "Iceland",
        "Ireland",
        "Italy",
        "Kosovo",
        "Latvia",
        "Liechtenstein",
        "Lithuania",
        "Luxembourg",
        "Malta",
        "Moldova",
        "Montenegro",
        "Netherlands",
        "North Macedonia",
        "Macedonia",
        "Norway",
        "Poland",
        "Portugal",
        "Romania",
        "Serbia",
        "Slovakia",
        "Slovenia",
        "Spain",
        "Sweden",
        "Switzerland",
        "Ukraine",
        "United Kingdom",
    },
)


def _pick(frame: gpd.GeoDataFrame, candidates: Sequence[str], *, what: str) -> str:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    available = ", ".join(map(str, frame.columns))
    msg = f"GHS-UCDB: no {what} column among {candidates}. Available: {available}"
    raise AdapterError(msg)


def load_ucdb(
    *,
    raw_dir: Path,
    session: requests.Session,
    force: bool,
) -> gpd.GeoDataFrame:
    """Download (cached) and read the GHS-UCDB urban-centre polygons."""
    result = download(
        UCDB_URL,
        raw_dir / "_reference" / "GHS_UCDB_GLOBE_R2024A_V1_2.zip",
        session=session,
        force=force,
    )
    extract_dir = raw_dir / "_reference" / "_extracted"
    # Extract only the GeoPackage, not the 176 MB Excel attribute table / PDF.
    extract_members(result.path, extract_dir, suffix=".gpkg")
    gpkgs = sorted(extract_dir.rglob("*.gpkg"))
    if not gpkgs:
        msg = f"No GeoPackage found in GHS-UCDB archive under {extract_dir}"
        raise AdapterError(msg)
    gpkg = gpkgs[0]
    # The GeoPackage exposes many theme layers; the "general characteristics"
    # one carries name/id/country/population + geometry.
    names = [str(name) for name in gpd.list_layers(gpkg)["name"]]
    general = next((name for name in names if "GENERAL" in name.upper()), None)
    return gpd.read_file(gpkg, layer=general, engine="pyogrio")


def standardize_ucdb(
    gdf: gpd.GeoDataFrame, *, europe_only: bool = True
) -> gpd.GeoDataFrame:
    """Return UCDB with ``uc_id``/``uc_name``/``country``/``pop`` + geometry."""
    name_field = _pick(gdf, _NAME_CANDIDATES, what="name")
    id_field = _pick(gdf, _ID_CANDIDATES, what="id")
    country_field = _pick(gdf, _COUNTRY_CANDIDATES, what="country")
    pop_field = _pick(gdf, _POP_CANDIDATES, what="population")

    frame = gdf.copy()
    frame["uc_id"] = frame[id_field].astype("string")
    frame["uc_name"] = frame[name_field].astype("string")
    frame["country"] = frame[country_field].astype("string")
    frame["pop"] = pd.to_numeric(frame[pop_field], errors="coerce").astype("float64")
    columns = ["uc_id", "uc_name", "country", "pop", "geometry"]
    out = gpd.GeoDataFrame(frame[columns], geometry="geometry", crs=gdf.crs)
    if europe_only:
        filtered = out[out["country"].isin(EUROPE_COUNTRIES)]
        if filtered.empty:
            logger.warning(
                "Europe filter matched 0 of %d centres (country=%r); keeping all",
                len(out),
                country_field,
            )
        else:
            out = filtered
    return out.to_crs(CRS_WGS84)


def build_reference(
    *,
    output_dir: Path,
    raw_dir: Path,
    session: requests.Session,
    force: bool,
    europe_only: bool = True,
) -> Path | None:
    """Write the GHS-UCDB urban-centre reference layer to ``_reference/``."""
    output_path = output_dir / "_reference" / "ghs_ucdb_R2024A.parquet"
    if output_path.exists() and not force:
        logger.info("skip (exists): %s", output_path)
        return None
    gdf = load_ucdb(raw_dir=raw_dir, session=session, force=force)
    reference = standardize_ucdb(gdf, europe_only=europe_only)
    write_geoparquet(reference, output_path)
    logger.info("UCDB reference written: %s (%d centres)", output_path, len(reference))
    return output_path


def select_centres(
    reference: gpd.GeoDataFrame, names: Sequence[str]
) -> gpd.GeoDataFrame:
    """Return UCDB rows whose ``uc_name`` case-insensitively matches ``names``."""
    wanted = {name.casefold() for name in names}
    mask = reference["uc_name"].str.casefold().isin(wanted)
    selected = reference[mask]
    found = set(selected["uc_name"].str.casefold())
    missing = sorted(name for name in names if name.casefold() not in found)
    if missing:
        logger.warning("cities not found in GHS-UCDB: %s", ", ".join(missing))
    return selected


def clip_to_centre(
    national: gpd.GeoDataFrame,
    centre: gpd.GeoDataFrame,
    *,
    mode: str = "centroid",
) -> gpd.GeoDataFrame:
    """Return the ``national`` cells/units that fall inside ``centre``.

    ``mode='centroid'`` keeps a unit when its centroid lies in the urban centre
    (no double counting); ``mode='area-weighted'`` keeps intersecting units and
    scales ``pop`` by the intersected area fraction (introduces fractional people).
    """
    centre_3035 = centre.to_crs(CRS_LAEA_EUROPE)
    union = centre_3035.union_all()
    target = national.to_crs(CRS_LAEA_EUROPE)
    if mode == "centroid":
        inside = target.geometry.centroid.within(union)
        return target[inside]
    clipped = target.clip(union)
    frac = clipped.geometry.area / target.geometry.area.reindex(clipped.index)
    clipped = clipped.copy()
    clipped["pop"] = clipped["pop"] * frac.to_numpy()
    return clipped
