"""Shared per-dataset pipeline: fetch -> (join) -> standardize -> write + log."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from popgrids import __version__
from popgrids.adapters import (
    get_adapter,
    join_population,
    load_population_table,
)
from popgrids.io import sha256_file, write_geoparquet
from popgrids.provenance import (
    ProvenanceRecord,
    append_jsonl,
    git_commit,
    now_utc_iso,
    write_sidecar,
)
from popgrids.standardize import standardize

if TYPE_CHECKING:
    from pathlib import Path

    import requests

    from popgrids.schema import CountryDataset

logger = logging.getLogger(__name__)


def output_path_for(dataset: CountryDataset, output_dir: Path) -> Path:
    """Return the national GeoParquet path for ``dataset``."""
    name = f"national_{dataset.unit_code}_{dataset.vintage}.parquet"
    return output_dir / dataset.country / name


def run_dataset(
    dataset: CountryDataset,
    *,
    output_dir: Path,
    raw_dir: Path,
    session: requests.Session,
    force: bool,
) -> ProvenanceRecord | None:
    """Acquire and process one dataset; return its provenance record.

    Returns ``None`` when the output already exists and ``force`` is not set
    (the idempotency skip-guard).
    """
    output_path = output_path_for(dataset, output_dir)
    if output_path.exists() and not force:
        logger.info("skip (exists): %s", output_path)
        return None

    country_raw = raw_dir / dataset.country
    adapter = get_adapter(dataset.geometry.method)
    results = adapter.fetch(dataset, raw_dir=country_raw, session=session, force=force)
    geometry = adapter.load_geometry(dataset, results)

    if dataset.population.mode == "join":
        table = load_population_table(
            dataset.population,
            raw_dir=country_raw,
            session=session,
            force=force,
        )
        geometry = join_population(geometry, table, dataset)

    gdf = standardize(geometry, dataset)
    write_geoparquet(gdf, output_path)

    record = ProvenanceRecord(
        dataset_id=dataset.dataset_id,
        country=dataset.country,
        source_urls=dataset.geometry.urls,
        source_crs=dataset.geometry.source_crs,
        target_crs=dataset.target_crs,
        population_mode=dataset.population.mode,
        download_utc=now_utc_iso(),
        raw_sha256=results[0].sha256,
        raw_bytes=sum(result.n_bytes for result in results),
        output_path=str(output_path),
        output_sha256=sha256_file(output_path),
        row_count=len(gdf),
        pop_total=float(gdf["pop"].sum()),
        tool="download_europe",
        package_version=__version__,
        git_commit=git_commit(),
        licence=dataset.licence,
        attribution=dataset.attribution,
    )
    write_sidecar(record, output_path)
    append_jsonl(record, output_dir / "provenance.jsonl")
    logger.info(
        "wrote %s (%d rows, pop=%.0f)",
        output_path,
        record.row_count,
        record.pop_total,
    )
    return record
