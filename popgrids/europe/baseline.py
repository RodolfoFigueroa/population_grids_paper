"""Eurostat GEOSTAT Census 2021 1 km grid: the homogenized European baseline.

The only harmonized pan-European *census-enumeration* grid (EPSG:3035, INSPIRE
``GRD_ID``). Pinned to version V3. The exact total-population column code is
confirmed from the data dictionary inside the zip on first download, so the
total-population field is auto-detected from a small candidate list and the run
fails loudly if none is present.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from popgrids import __version__
from popgrids.crs import to_3035
from popgrids.europe.adapters import AdapterError
from popgrids.europe.standardize import build_cells_from_inspire_id
from popgrids.io import (
    download,
    extract_members,
    find_members,
    sha256_file,
    write_geoparquet,
)
from popgrids.provenance import (
    ProvenanceRecord,
    append_jsonl,
    git_commit,
    now_utc_iso,
    write_sidecar,
)

if TYPE_CHECKING:
    from pathlib import Path

    import requests

logger = logging.getLogger(__name__)

BASELINE_URL = (
    "https://gisco-services.ec.europa.eu/census/2021/Eurostat_Census-GRID_2021_V3.zip"
)
BASELINE_VERSION = "V3"
BASELINE_VINTAGE = 2021
BASELINE_ID_FIELD = "GRD_ID"
#: Candidate total-population column codes seen across GEOSTAT releases.
BASELINE_POP_CANDIDATES = ("T", "OBS_VALUE", "T_2021", "TOT_P_2021", "TOT_P")
BASELINE_LICENCE = "Eurostat/GISCO reuse (acknowledge source; grid download terms)"
BASELINE_ATTRIBUTION = "© Eurostat/GISCO, Census 2021 1 km population grid (V3)"


def _load_baseline_table(extract_dir: Path) -> pd.DataFrame:
    # The GEOSTAT parquet/csv is a plain table (GRD_ID + attributes); geometry is
    # derived from GRD_ID, avoiding the multi-GB GeoPackage.
    parquets = sorted(extract_dir.rglob("*.parquet"))
    if parquets:
        return pd.read_parquet(parquets[0])
    csvs = sorted(extract_dir.rglob("*.csv"))
    if csvs:
        return pd.read_csv(csvs[0])
    msg = f"No parquet/csv table found under {extract_dir}"
    raise AdapterError(msg)


def _pick_pop_field(frame: pd.DataFrame) -> str:
    for candidate in BASELINE_POP_CANDIDATES:
        if candidate in frame.columns:
            return candidate
    available = ", ".join(map(str, frame.columns))
    msg = (
        f"GEOSTAT baseline: no population column among {BASELINE_POP_CANDIDATES}. "
        f"Available: {available}"
    )
    raise AdapterError(msg)


def build_baseline(
    *,
    output_dir: Path,
    raw_dir: Path,
    session: requests.Session,
    force: bool,
) -> ProvenanceRecord | None:
    """Download and standardize the GEOSTAT 1 km baseline grid."""
    output_path = output_dir / "_baseline" / "geostat_grid1km_2021.parquet"
    if output_path.exists() and not force:
        logger.info("skip (exists): %s", output_path)
        return None

    base_raw = raw_dir / "_baseline"
    result = download(
        BASELINE_URL,
        base_raw / "Eurostat_Census-GRID_2021_V3.zip",
        session=session,
        force=force,
    )
    extract_dir = base_raw / "_extracted"
    # Extract only the plain table (parquet preferred), not the multi-GB
    # GeoPackage / CSV / rasters we never read.
    if find_members(result.path, suffix=".parquet"):
        extract_members(result.path, extract_dir, suffix=".parquet")
    elif find_members(result.path, suffix=".csv"):
        extract_members(result.path, extract_dir, suffix=".csv")
    else:
        msg = f"GEOSTAT zip has no parquet/csv table: {result.path}"
        raise AdapterError(msg)
    frame = _load_baseline_table(extract_dir)

    pop_field = _pick_pop_field(frame)
    # Drop the handful of per-country "*_unallocated" rows: population not
    # geolocated to a grid cell, so it has no INSPIRE id / geometry.
    is_grid = (
        frame[BASELINE_ID_FIELD]
        .astype("string")
        .str.startswith("CRS")
        .fillna(
            value=False,
        )
    )
    if not is_grid.all():
        dropped = frame.loc[~is_grid]
        unallocated = float(pd.to_numeric(dropped[pop_field], errors="coerce").sum())
        logger.warning(
            "dropping %d non-grid rows (e.g. *_unallocated); pop=%.0f not geolocated",
            len(dropped),
            unallocated,
        )
        frame = frame.loc[is_grid]
    gdf = build_cells_from_inspire_id(frame, BASELINE_ID_FIELD, "EPSG:3035")
    gdf["pop"] = pd.to_numeric(gdf[pop_field], errors="coerce").astype("float64")
    gdf["unit_id"] = gdf[BASELINE_ID_FIELD].astype("string")
    gdf["country"] = "EU"
    gdf["source"] = "EU_geostat_grid1km_2021"
    gdf["vintage"] = np.full(len(gdf), BASELINE_VINTAGE, dtype=np.int16)
    gdf["level"] = "grid1km"
    gdf = to_3035(
        gdf[["pop", "unit_id", "country", "source", "vintage", "level", "geometry"]],
    )
    write_geoparquet(gdf, output_path)

    record = ProvenanceRecord(
        dataset_id="EU_geostat_grid1km_2021",
        country="EU",
        source_urls=(BASELINE_URL,),
        source_crs="EPSG:3035",
        target_crs="EPSG:3035",
        population_mode="bundled",
        download_utc=now_utc_iso(),
        raw_sha256=result.sha256,
        raw_bytes=result.n_bytes,
        output_path=str(output_path),
        output_sha256=sha256_file(output_path),
        row_count=len(gdf),
        pop_total=float(gdf["pop"].sum()),
        tool="download_europe",
        package_version=__version__,
        git_commit=git_commit(),
        licence=BASELINE_LICENCE,
        attribution=BASELINE_ATTRIBUTION,
    )
    write_sidecar(record, output_path)
    append_jsonl(record, output_dir / "provenance.jsonl")
    logger.info("baseline written: %s (%d cells)", output_path, record.row_count)
    return record
