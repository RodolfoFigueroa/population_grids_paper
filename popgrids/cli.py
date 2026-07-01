"""Command-line entrypoint: ``download-census`` (alias ``download-europe``).

Acquire the finest official census population per country into local GeoParquet,
across regions (Europe, Americas, Asia-Pacific, …):

* ``--layers fine``      per-country finest census layers (default);
* ``--layers baseline``  the Eurostat GEOSTAT 1 km homogenized grid (Europe);
* ``--layers reference`` the GHS-UCDB urban-centre reference layer (global);
* ``--layers all``       all of the above.

Outputs go to ``<output-dir>/<region>/<country>/…`` (e.g. ``data/europe/DE/…``,
``data/americas/CA/…``); the GHS-UCDB reference and GEOSTAT baseline live under
``data/europe/`` (Europe-scoped today).

Examples::

    download-census --list
    download-census --countries DE CA
    download-census --region americas --layers fine
    download-census --countries DE FR --cities "Munich" "Paris"
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
import pandas as pd
import requests

from popgrids.adapters import GatedDatasetError
from popgrids.cities import build_reference, clip_to_centre, select_centres
from popgrids.europe.baseline import build_baseline
from popgrids.io import build_session, write_geoparquet
from popgrids.pipeline import output_path_for, run_dataset
from popgrids.quality import build_quality_table, load_quality_table
from popgrids.registry import (
    CANDIDATES,
    CATALOG,
    datasets_for_country,
    region_for_country,
)

if TYPE_CHECKING:
    from popgrids.schema import CountryDataset

logger = logging.getLogger(__name__)

_LAYER_CHOICES = ("fine", "baseline", "reference", "quality", "all")
_EUROPE = "europe"
_DATASET_ERRORS = (
    RuntimeError,  # AdapterError + pyogrio DataSourceError both subclass this
    requests.RequestException,
    OSError,
    ValueError,
    KeyError,
)


def build_parser() -> argparse.ArgumentParser:
    """Construct the ``download-census`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="download-census",
        description="Download official census population data into GeoParquet.",
    )
    parser.add_argument("--layers", choices=_LAYER_CHOICES, default="fine")
    parser.add_argument("--countries", nargs="*", default=None, metavar="ISO2")
    parser.add_argument("--datasets", nargs="*", default=None, metavar="DATASET_ID")
    parser.add_argument("--region", default=None, metavar="REGION")
    parser.add_argument("--cities", nargs="*", default=None, metavar="NAME")
    parser.add_argument("--vintage", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument(
        "--odin",
        type=Path,
        default=None,
        help="optional ODIN export CSV (iso3,odin_pop_vital) for --layers quality",
    )
    parser.add_argument(
        "--clip-mode",
        choices=("centroid", "area-weighted"),
        default="centroid",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--clean-raw",
        action="store_true",
        dest="clean_raw",
        help="remove the raw download/extract cache after a successful run",
    )
    parser.add_argument("--list", action="store_true", dest="list_catalog")
    parser.add_argument("--log-level", default="INFO")
    return parser


def _region_dirs(base: Path, region: str | None) -> tuple[Path, Path]:
    """Return (output_dir, raw_dir) for a region under ``base``."""
    region_dir = base / (region or "other")
    return region_dir, region_dir / "_raw"


def _select_datasets(args: argparse.Namespace) -> list[CountryDataset]:
    if args.datasets:
        datasets = [CATALOG[name] for name in args.datasets]
    elif args.countries:
        datasets = [
            dataset
            for country in args.countries
            for dataset in datasets_for_country(country)
        ]
    else:
        datasets = list(CATALOG.values())
    if args.region is not None:
        datasets = [
            dataset
            for dataset in datasets
            if region_for_country(dataset.country) == args.region
        ]
    if args.vintage is not None:
        datasets = [dataset for dataset in datasets if dataset.vintage == args.vintage]
    return datasets


def _quality_map(quality_path: Path) -> dict[str, tuple[str, str]]:
    """Return {iso2: (spi_overall, census_availability)} formatted for display."""
    table = load_quality_table(quality_path)
    if table is None:
        return {}

    def fmt(value: object, digits: int) -> str:
        return "-" if value is None or pd.isna(value) else f"{float(value):.{digits}f}"

    return {
        str(row["iso2"]): (
            fmt(row["spi_overall"], 0),
            fmt(row["census_availability"], 1),
        )
        for _, row in table.iterrows()
        if pd.notna(row["iso2"])
    }


def print_catalog(quality_path: Path) -> None:
    """Print the coverage table (wired datasets + surveyed candidates; no network)."""
    quality = _quality_map(quality_path)
    header = (
        "dataset_id",
        "region",
        "ctry",
        "level",
        "tier",
        "year",
        "method",
        "ok",
        "spi",
        "cens",
    )
    rows = [
        (
            dataset.dataset_id,
            region_for_country(dataset.country) or "?",
            dataset.country,
            dataset.unit_code,
            dataset.geometry.tier,
            str(dataset.vintage),
            dataset.geometry.method,
            "yes" if dataset.verified else "no",
            quality.get(dataset.country, ("-", "-"))[0],
            quality.get(dataset.country, ("-", "-"))[1],
        )
        for dataset in sorted(CATALOG.values(), key=lambda item: item.dataset_id)
    ]
    widths = [
        max(len(row[col]) for row in (header, *rows)) for col in range(len(header))
    ]
    for row in (header, *rows):
        print("  ".join(value.ljust(widths[col]) for col, value in enumerate(row)))
    if CANDIDATES:
        print("\nSurveyed candidates (not yet wired):")
        for cand in sorted(CANDIDATES, key=lambda c: (c.tier, c.country)):
            print(
                f"  [{cand.tier}] {cand.country:3} {cand.unit_label} "
                f"(census {cand.latest_census}, open {cand.open_finest_year})",
            )


def _slug(name: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in name.lower()).strip("-")


def _clip_cities(
    produced: list[tuple[CountryDataset, Path]],
    args: argparse.Namespace,
    session: requests.Session,
) -> None:
    europe_dir = args.output_dir / _EUROPE
    raw_dir = args.raw_dir or (europe_dir / "_raw")
    reference_path = europe_dir / "_reference" / "ghs_ucdb_R2024A.parquet"
    if not reference_path.exists():
        build_reference(
            output_dir=europe_dir, raw_dir=raw_dir, session=session, force=args.force
        )
    reference = gpd.read_parquet(reference_path)
    centres = select_centres(reference, args.cities)
    for dataset, output_path in produced:
        national = gpd.read_parquet(output_path)
        country_centres = centres[centres["country"].notna()]
        for _, centre in country_centres.iterrows():
            single = gpd.GeoDataFrame([centre], geometry="geometry", crs=reference.crs)
            clipped = clip_to_centre(national, single, mode=args.clip_mode)
            if clipped.empty:
                continue
            slug = _slug(str(centre["uc_name"]))
            name = f"{slug}_{dataset.unit_code}_{dataset.vintage}.parquet"
            write_geoparquet(clipped, output_path.parent / name)


def _run_fine(
    datasets: list[CountryDataset],
    base: Path,
    session: requests.Session,
    *,
    force: bool,
) -> list[tuple[CountryDataset, Path]]:
    produced: list[tuple[CountryDataset, Path]] = []
    for dataset in datasets:
        output_dir, raw_dir = _region_dirs(base, region_for_country(dataset.country))
        try:
            record = run_dataset(
                dataset,
                output_dir=output_dir,
                raw_dir=raw_dir,
                session=session,
                force=force,
            )
        except GatedDatasetError as exc:
            logger.warning("gated, skipping (use the 1 km baseline instead): %s", exc)
            continue
        except _DATASET_ERRORS:
            logger.exception("failed: %s", dataset.dataset_id)
            continue
        output_path = output_path_for(dataset, output_dir)
        if record is not None or output_path.exists():
            produced.append((dataset, output_path))
    return produced


def main(argv: list[str] | None = None) -> int:
    """Run the ``download-census`` CLI; return a process exit code."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    base: Path = args.output_dir
    if args.list_catalog:
        print_catalog(base / "quality" / "country_quality.parquet")
        return 0

    europe_dir = base / _EUROPE
    session = build_session()
    try:
        if args.layers in {"quality", "all"}:
            build_quality_table(session, base, odin_csv=args.odin, force=args.force)
        if args.layers in {"baseline", "all"}:
            build_baseline(
                output_dir=europe_dir,
                raw_dir=europe_dir / "_raw",
                session=session,
                force=args.force,
            )
        if args.layers in {"reference", "all"}:
            build_reference(
                output_dir=europe_dir,
                raw_dir=europe_dir / "_raw",
                session=session,
                force=args.force,
            )
        if args.layers in {"fine", "all"}:
            produced = _run_fine(
                _select_datasets(args), base, session, force=args.force
            )
            if args.cities:
                _clip_cities(produced, args, session)
    finally:
        session.close()
    if args.clean_raw and base.exists():
        for raw in base.rglob("_raw"):
            shutil.rmtree(raw, ignore_errors=True)
        logger.info("removed raw caches under %s", base)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
