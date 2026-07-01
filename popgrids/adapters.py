"""Per-source adapters: turn a catalog entry into a native-CRS GeoDataFrame.

Two axes are kept orthogonal:

* **geometry access** -- selected by ``geometry.method`` from
  :data:`ADAPTER_REGISTRY` (direct file/zip vs. paginated Tier-B API);
* **population source** -- handled uniformly *after* geometry load
  (``bundled`` vs. ``join``), so adding a country is usually just a catalog
  entry plus an existing adapter.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, NamedTuple, Protocol, runtime_checkable

import geopandas as gpd
import pandas as pd

from popgrids.io import (
    TIMEOUT,
    DownloadResult,
    download,
    extract_members,
    extract_zip,
    find_members,
    is_archive,
    read_vector,
    sha256_file,
)
from popgrids.standardize import build_cell_polygons, require_columns

if TYPE_CHECKING:
    from pathlib import Path

    import requests

    from popgrids.schema import CountryDataset, PopulationSource

logger = logging.getLogger(__name__)

_PARQUET_MAGIC = b"PAR1"
_MAX_FILENAME = 80
_DEFAULT_PAGE = 2000


class AdapterError(RuntimeError):
    """Raised when an adapter cannot produce a usable geometry frame."""


class GatedDatasetError(RuntimeError):
    """Raised for sources behind a login/order wall (no automated download)."""

    def __init__(self, dataset_id: str, notes: str) -> None:
        message = (
            f"{dataset_id} is gated and cannot be auto-downloaded. {notes}".strip()
        )
        super().__init__(message)
        self.dataset_id = dataset_id


@runtime_checkable
class Adapter(Protocol):
    """Fetch raw artifacts and load them into a native-CRS GeoDataFrame."""

    def fetch(
        self,
        dataset: CountryDataset,
        *,
        raw_dir: Path,
        session: requests.Session,
        force: bool,
    ) -> list[DownloadResult]: ...

    def load_geometry(
        self,
        dataset: CountryDataset,
        results: list[DownloadResult],
    ) -> gpd.GeoDataFrame: ...


def _filename_for(url: str, dataset: CountryDataset, index: int) -> str:
    tail = url.rstrip("/").rsplit("/", 1)[-1].split("?")[0]
    if "." in tail and 0 < len(tail) <= _MAX_FILENAME:
        return tail
    return f"{dataset.dataset_id}_{index}"


def _looks_like_parquet(path: Path) -> bool:
    if path.suffix.lower() in {".parquet", ".pq"}:
        return True
    with path.open("rb") as handle:
        return handle.read(4) == _PARQUET_MAGIC


def _ensure_crs(gdf: gpd.GeoDataFrame, source_crs: str) -> gpd.GeoDataFrame:
    if gdf.crs is None:
        return gdf.set_crs(source_crs)
    return gdf


def _archive_suffix(dataset: CountryDataset) -> str | None:
    suffix = dataset.geometry.archive_member_suffix
    if suffix is None and dataset.geometry.geometry_kind.startswith("grid_csv"):
        return ".csv"
    return suffix


def _read_target(dataset: CountryDataset, path: Path) -> gpd.GeoDataFrame:
    geometry = dataset.geometry
    if geometry.geometry_kind.startswith("grid_csv"):
        frame = pd.read_csv(
            path,
            sep=geometry.csv_separator,
            encoding=geometry.csv_encoding,
            low_memory=False,
        )
        return build_cell_polygons(frame, geometry)
    if _looks_like_parquet(path):
        gdf = gpd.read_parquet(path)
    else:
        gdf = read_vector(path, layer=geometry.layer)
    return _ensure_crs(gdf, geometry.source_crs)


def _looks_like_html(path: Path) -> bool:
    with path.open("rb") as handle:
        head = handle.read(64).lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html"))


def _read_one(dataset: CountryDataset, downloaded: Path) -> gpd.GeoDataFrame:
    if is_archive(downloaded):
        contains = dataset.geometry.archive_member_contains
        suffix = _archive_suffix(dataset)
        members = find_members(downloaded, contains=contains, suffix=suffix)
        if not members:
            msg = (
                f"{dataset.dataset_id}: no archive member matched "
                f"contains={contains} suffix={suffix} in {downloaded.name}"
            )
            raise AdapterError(msg)
        extract_dir = downloaded.parent / f"_extracted_{dataset.dataset_id}"
        extract_members(downloaded, extract_dir, contains=contains, suffix=suffix)
        return _read_target(dataset, extract_dir / sorted(members)[0])
    if _looks_like_html(downloaded):
        msg = (
            f"{dataset.dataset_id}: downloaded an HTML page, not data "
            f"({downloaded.name}); the source is likely bot-walled or needs a browser."
        )
        raise AdapterError(msg)
    return _read_target(dataset, downloaded)


class FileAdapter:
    """Direct-download adapter (zip / parquet / gpkg / shapefile / csv grid)."""

    def fetch(
        self,
        dataset: CountryDataset,
        *,
        raw_dir: Path,
        session: requests.Session,
        force: bool,
    ) -> list[DownloadResult]:
        results: list[DownloadResult] = []
        for index, url in enumerate(dataset.geometry.urls):
            name = _filename_for(url, dataset, index)
            results.append(download(url, raw_dir / name, session=session, force=force))
        return results

    def load_geometry(
        self,
        dataset: CountryDataset,
        results: list[DownloadResult],
    ) -> gpd.GeoDataFrame:
        frames = [_read_one(dataset, result.path) for result in results]
        if len(frames) == 1:
            return frames[0]
        combined = pd.concat(frames, ignore_index=True)
        return gpd.GeoDataFrame(combined, geometry="geometry", crs=frames[0].crs)


class PagingSpec(NamedTuple):
    """How to drive offset/limit pagination for a Tier-B API."""

    page_size: int
    offset_key: str
    limit_key: str


def _paginate_features(
    session: requests.Session,
    base_url: str,
    base_params: dict[str, str],
    spec: PagingSpec,
) -> list[dict]:
    features: list[dict] = []
    offset = 0
    while True:
        params = {
            **base_params,
            spec.limit_key: str(spec.page_size),
            spec.offset_key: str(offset),
        }
        response = session.get(base_url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("features", [])
        features.extend(batch)
        exceeded = bool(payload.get("exceededTransferLimit"))
        logger.info(
            "%s: fetched %d features (offset=%d)", base_url, len(features), offset
        )
        if not batch or (len(batch) < spec.page_size and not exceeded):
            break
        offset += len(batch)
    return features


def _assemble_geojson(
    dataset: CountryDataset,
    raw_dir: Path,
    features: list[dict],
    *,
    force: bool,
) -> list[DownloadResult]:
    out = raw_dir / f"{dataset.dataset_id}.geojson"
    if out.exists() and not force:
        return [
            DownloadResult(out, sha256_file(out), out.stat().st_size, from_cache=True)
        ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return [DownloadResult(out, sha256_file(out), out.stat().st_size, from_cache=False)]


class ArcGisHubAdapter:
    """Paginated ArcGIS FeatureServer ``query`` endpoint (e.g. ONS, GeoHive)."""

    def fetch(
        self,
        dataset: CountryDataset,
        *,
        raw_dir: Path,
        session: requests.Session,
        force: bool,
    ) -> list[DownloadResult]:
        out = raw_dir / f"{dataset.dataset_id}.geojson"
        if out.exists() and not force:
            return [
                DownloadResult(
                    out, sha256_file(out), out.stat().st_size, from_cache=True
                )
            ]
        page = dataset.geometry.page_size or _DEFAULT_PAGE
        params = {**dataset.geometry.query_params, "f": "geojson"}
        features = _paginate_features(
            session,
            dataset.geometry.urls[0],
            params,
            PagingSpec(page, "resultOffset", "resultRecordCount"),
        )
        return _assemble_geojson(dataset, raw_dir, features, force=force)

    def load_geometry(
        self,
        dataset: CountryDataset,
        results: list[DownloadResult],
    ) -> gpd.GeoDataFrame:
        gdf = gpd.read_file(results[0].path, engine="pyogrio")
        return _ensure_crs(gdf, dataset.geometry.source_crs)


class OgcApiAdapter:
    """Paginated OGC API - Features ``items`` endpoint (e.g. INE GeoServer)."""

    def fetch(
        self,
        dataset: CountryDataset,
        *,
        raw_dir: Path,
        session: requests.Session,
        force: bool,
    ) -> list[DownloadResult]:
        out = raw_dir / f"{dataset.dataset_id}.geojson"
        if out.exists() and not force:
            return [
                DownloadResult(
                    out, sha256_file(out), out.stat().st_size, from_cache=True
                )
            ]
        page = dataset.geometry.page_size or _DEFAULT_PAGE
        params = {**dataset.geometry.query_params, "f": "json"}
        features = _paginate_features(
            session,
            dataset.geometry.urls[0],
            params,
            PagingSpec(page, "offset", "limit"),
        )
        return _assemble_geojson(dataset, raw_dir, features, force=force)

    def load_geometry(
        self,
        dataset: CountryDataset,
        results: list[DownloadResult],
    ) -> gpd.GeoDataFrame:
        gdf = gpd.read_file(results[0].path, engine="pyogrio")
        return _ensure_crs(gdf, dataset.geometry.source_crs)


class GatedAdapter:
    """Adapter for order/login-gated sources; always raises a typed error."""

    def fetch(
        self,
        dataset: CountryDataset,
        *,
        raw_dir: Path,
        session: requests.Session,
        force: bool,
    ) -> list[DownloadResult]:
        del raw_dir, session, force
        raise GatedDatasetError(dataset.dataset_id, dataset.notes)

    def load_geometry(
        self,
        dataset: CountryDataset,
        results: list[DownloadResult],
    ) -> gpd.GeoDataFrame:
        del results
        raise GatedDatasetError(dataset.dataset_id, dataset.notes)


def _extract_table_member(path: Path, population: PopulationSource) -> Path:
    suffixes = (
        {".xlsx", ".xls"} if population.table_format == "zip-xlsx" else {".csv", ".txt"}
    )
    extract_dir = path.parent / f"_poptable_{path.stem}"
    extract_zip(path, extract_dir)
    members = [
        candidate
        for candidate in extract_dir.rglob("*")
        if candidate.suffix.lower() in suffixes
        and all(
            token.lower() in candidate.name.lower()
            for token in population.table_member_contains
        )
    ]
    # Prefer the data file over a "meta_..." metadata companion.
    non_meta = [c for c in members if "meta" not in c.name.lower()]
    candidates = sorted(non_meta or members)
    if not candidates:
        msg = f"No table in {path.name} matched {population.table_member_contains}"
        raise AdapterError(msg)
    return candidates[0]


def _read_population_table(path: Path, population: PopulationSource) -> pd.DataFrame:
    read_path = path
    if population.table_format in {"zip-csv", "zip-xlsx"}:
        read_path = _extract_table_member(path, population)
    # Read everything as string: preserves leading zeros in code columns and
    # keeps join keys exact; the population attr is coerced to numeric later.
    if population.table_format in {"xlsx", "zip-xlsx"}:
        sheets = pd.read_excel(
            read_path,
            sheet_name=None,
            dtype=str,
            skiprows=population.table_skiprows,
        )
        wanted = population.table_sheet_contains
        frames = [
            df
            for name, df in sheets.items()
            if wanted is None or wanted.lower() in name.lower()
        ]
        return pd.concat(frames, ignore_index=True)
    return pd.read_csv(
        read_path,
        sep=population.table_separator,
        encoding=population.table_encoding,
        dtype=str,
        low_memory=False,
    )


def _build_join_key(table: pd.DataFrame, population: PopulationSource) -> pd.DataFrame:
    parts = [(col, width) for col, width in population.build_join_key_from]
    require_columns(table, [col for col, _ in parts], context="population join key")
    key = None
    for col, width in parts:
        padded = table[col].astype("string").str.zfill(width)
        key = padded if key is None else key.str.cat(padded)
    result = table.copy()
    result[population.join_key_pop] = key
    return result


def load_population_table(
    population: PopulationSource,
    *,
    raw_dir: Path,
    session: requests.Session,
    force: bool,
) -> pd.DataFrame:
    """Download and read the separate population table for ``join`` datasets."""
    if population.table_url is None:
        msg = "join population source has no table_url"
        raise AdapterError(msg)
    name = (
        population.table_url.rstrip("/").rsplit("/", 1)[-1].split("?")[0] or "poptable"
    )
    result = download(
        population.table_url, raw_dir / name, session=session, force=force
    )
    table = _read_population_table(result.path, population)
    if population.build_join_key_from:
        table = _build_join_key(table, population)
    return table


def join_population(
    geometry: gpd.GeoDataFrame,
    table: pd.DataFrame,
    dataset: CountryDataset,
) -> gpd.GeoDataFrame:
    """Left-join the population ``table`` onto ``geometry`` on the catalog keys."""
    population = dataset.population
    geom_key = population.join_key_geom
    pop_key = population.join_key_pop
    if geom_key is None or pop_key is None:
        msg = f"{dataset.dataset_id}: join requires join_key_geom and join_key_pop"
        raise AdapterError(msg)
    require_columns(geometry, [geom_key], context=f"{dataset.dataset_id} geometry")
    require_columns(
        table, [pop_key, population.attr], context=f"{dataset.dataset_id} pop table"
    )
    slim = table[[pop_key, population.attr]].copy()
    slim[pop_key] = slim[pop_key].astype("string")
    # Drop null/duplicate keys (e.g. xlsx footer-note rows) so the m:1 join is valid.
    slim = slim.dropna(subset=[pop_key]).drop_duplicates(subset=[pop_key], keep="first")
    # Avoid a column-name collision when geometry and table share the key name
    # (e.g. Belgium CD_SECTOR == CD_SECTOR): rename the table key before merge.
    right_key = pop_key
    if pop_key in geometry.columns:
        right_key = f"_popkey_{pop_key}"
        slim = slim.rename(columns={pop_key: right_key})
    merged = geometry.copy()
    merged[geom_key] = merged[geom_key].astype("string")
    return merged.merge(
        slim, left_on=geom_key, right_on=right_key, how="left", validate="m:1"
    )


ADAPTER_REGISTRY: dict[str, Adapter] = {
    "direct_zip": FileAdapter(),
    "direct_file": FileAdapter(),
    "arcgis_hub": ArcGisHubAdapter(),
    "ogc_api": OgcApiAdapter(),
    "gated": GatedAdapter(),
}


def get_adapter(method: str) -> Adapter:
    """Return the adapter registered for ``method`` (raises if unknown)."""
    try:
        return ADAPTER_REGISTRY[method]
    except KeyError as exc:
        msg = f"No adapter registered for access method {method!r}"
        raise AdapterError(msg) from exc
