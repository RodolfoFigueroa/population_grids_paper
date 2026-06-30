"""Command-line entrypoint: ``download-europe`` (and ``scripts/download_europe.py``).

Acquire European census population layers into local GeoParquet:

* ``--layers fine``      per-country finest census layers (default);
* ``--layers baseline``  the Eurostat GEOSTAT 1 km homogenized grid;
* ``--layers reference`` the GHS-UCDB urban-centre reference layer;
* ``--layers all``       all of the above.

Examples::

    download-europe --countries DE
    download-europe --layers all --force
    download-europe --list
    download-europe --countries DE FR --cities "Munich" "Paris"
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
import requests

from popgrids.europe.adapters import GatedDatasetError
from popgrids.europe.baseline import build_baseline
from popgrids.europe.catalog import CATALOG, datasets_for_country
from popgrids.europe.cities import build_reference, clip_to_centre, select_centres
from popgrids.europe.pipeline import output_path_for, run_dataset
from popgrids.io import build_session, write_geoparquet

if TYPE_CHECKING:
    from popgrids.europe.schema import CountryDataset

logger = logging.getLogger(__name__)

_LAYER_CHOICES = ("fine", "baseline", "reference", "all")
_DATASET_ERRORS = (
    RuntimeError,  # AdapterError + pyogrio DataSourceError both subclass this
    requests.RequestException,
    OSError,
    ValueError,
    KeyError,
)


def build_parser() -> argparse.ArgumentParser:
    """Construct the ``download-europe`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="download-europe",
        description="Download European census population data into GeoParquet.",
    )
    parser.add_argument("--layers", choices=_LAYER_CHOICES, default="fine")
    parser.add_argument("--countries", nargs="*", default=None, metavar="ISO2")
    parser.add_argument("--datasets", nargs="*", default=None, metavar="DATASET_ID")
    parser.add_argument("--cities", nargs="*", default=None, metavar="NAME")
    parser.add_argument("--vintage", type=int, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("data/europe"))
    parser.add_argument("--raw-dir", type=Path, default=None)
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
    if args.vintage is not None:
        datasets = [dataset for dataset in datasets if dataset.vintage == args.vintage]
    return datasets


def print_catalog() -> None:
    """Print the catalog coverage table (no network access)."""
    header = ("dataset_id", "ctry", "level", "tier", "year", "method", "verified")
    rows = [
        (
            dataset.dataset_id,
            dataset.country,
            dataset.unit_code,
            dataset.geometry.tier,
            str(dataset.vintage),
            dataset.geometry.method,
            "yes" if dataset.verified else "no",
        )
        for dataset in sorted(CATALOG.values(), key=lambda item: item.dataset_id)
    ]
    widths = [
        max(len(row[col]) for row in (header, *rows)) for col in range(len(header))
    ]
    for row in (header, *rows):
        print("  ".join(value.ljust(widths[col]) for col, value in enumerate(row)))


def _slug(name: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in name.lower()).strip("-")


def _clip_cities(
    produced: list[tuple[CountryDataset, Path]],
    args: argparse.Namespace,
    session: requests.Session,
) -> None:
    output_dir: Path = args.output_dir
    raw_dir: Path = args.raw_dir or (output_dir / "_raw")
    reference_path = output_dir / "_reference" / "ghs_ucdb_R2024A.parquet"
    if not reference_path.exists():
        build_reference(
            output_dir=output_dir, raw_dir=raw_dir, session=session, force=args.force
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
    *,
    output_dir: Path,
    raw_dir: Path,
    session: requests.Session,
    force: bool,
) -> list[tuple[CountryDataset, Path]]:
    produced: list[tuple[CountryDataset, Path]] = []
    for dataset in datasets:
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
        if record is not None or output_path_for(dataset, output_dir).exists():
            produced.append((dataset, output_path_for(dataset, output_dir)))
    return produced


def main(argv: list[str] | None = None) -> int:
    """Run the ``download-europe`` CLI; return a process exit code."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.list_catalog:
        print_catalog()
        return 0

    output_dir: Path = args.output_dir
    raw_dir: Path = args.raw_dir or (output_dir / "_raw")
    session = build_session()
    try:
        if args.layers in {"baseline", "all"}:
            build_baseline(
                output_dir=output_dir,
                raw_dir=raw_dir,
                session=session,
                force=args.force,
            )
        if args.layers in {"reference", "all"}:
            build_reference(
                output_dir=output_dir,
                raw_dir=raw_dir,
                session=session,
                force=args.force,
            )
        if args.layers in {"fine", "all"}:
            produced = _run_fine(
                _select_datasets(args),
                output_dir=output_dir,
                raw_dir=raw_dir,
                session=session,
                force=args.force,
            )
            if args.cities:
                _clip_cities(produced, args, session)
    finally:
        session.close()
    if args.clean_raw and raw_dir.exists():
        shutil.rmtree(raw_dir)
        logger.info("removed raw cache: %s", raw_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
