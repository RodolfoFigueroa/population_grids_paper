"""Per-country data-quality reference from open sources (World Bank SPI + ODIN).

World Economics' Population Data Quality Ratings are proprietary and bot-blocked,
so we use the **open** alternatives:

* **World Bank SPI** (CC BY 4.0, ISO3, JSON API): ``IQ.SPI.OVRL`` overall
  statistical-performance score (0-100) and ``SPI.D4.1.1.POPU`` Population &
  Housing census availability (1.0 = census in last 10 yr, 0.5 = last 20 yr, 0).
  The census item lives in SPI database ``source=83``.
* **ODIN** (Open Data Watch) Category-1 "Population & Vital Statistics" score —
  optional, ingested from a user-exported CSV (no clean API).

These score the **statistical system's capacity / openness and census recency**,
NOT the enumeration accuracy of a specific census — treat as a reliability proxy.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from popgrids.country_codes import ISO3_TO_ISO2
from popgrids.io import TIMEOUT
from popgrids.provenance import now_utc_iso

if TYPE_CHECKING:
    from pathlib import Path

    import requests

logger = logging.getLogger(__name__)

WB_API = "https://api.worldbank.org/v2"
SPI_OVERALL = "IQ.SPI.OVRL"
SPI_CENSUS = "SPI.D4.1.1.POPU"
SPI_DATABASE_SOURCE = 83
_PAGE_SIZE = 20000  # large enough to return every country in one page
# Recent years to scan for the latest non-null (census uses mrv, not mrnev).
_MRV_YEARS = 5
_ISO3_LEN = 3
_WB_PAYLOAD_PARTS = 2  # World Bank JSON responses are [metadata, records]
QUALITY_SOURCE = "World Bank SPI (IQ.SPI.OVRL + SPI.D4.1.1.POPU), CC BY 4.0"


def _fetch_indicator(
    session: requests.Session,
    code: str,
    *,
    source: int | None = None,
) -> dict[str, dict[str, object]]:
    """Fetch the most-recent non-empty value per country for a WB indicator."""
    params: dict[str, str] = {"format": "json", "per_page": str(_PAGE_SIZE)}
    if source is not None:
        # mrnev is rejected with an explicit source DB; scan recent years instead.
        params["source"] = str(source)
        params["mrv"] = str(_MRV_YEARS)
    else:
        params["mrnev"] = "1"
    url = f"{WB_API}/country/all/indicator/{code}"
    out: dict[str, dict[str, object]] = {}
    page = 1
    while True:
        payload = session.get(
            url, params={**params, "page": str(page)}, timeout=TIMEOUT
        ).json()
        if (
            not isinstance(payload, list)
            or len(payload) < _WB_PAYLOAD_PARTS
            or not payload[1]
        ):
            break
        meta, records = payload[0], payload[1]
        for rec in records:
            country = rec.get("country") or {}
            iso3 = rec.get("countryiso3code") or country.get("id", "")
            value = rec.get("value")
            if len(iso3) != _ISO3_LEN or value is None:
                continue
            # Records are date-descending per country; keep the first (latest) non-null.
            out.setdefault(
                iso3,
                {
                    "value": value,
                    "year": rec.get("date"),
                    "name": country.get("value"),
                },
            )
        if page >= int(meta.get("pages", 1)):
            break
        page += 1
    logger.info("WB %s: %d countries", code, len(out))
    return out


def _merge_odin(frame: pd.DataFrame, odin_csv: Path) -> pd.DataFrame:
    """Merge an ODIN export (CSV with ``iso3`` + ``odin_pop_vital`` columns)."""
    odin = pd.read_csv(odin_csv, dtype={"iso3": str})
    if "iso3" not in odin.columns or "odin_pop_vital" not in odin.columns:
        logger.warning(
            "ODIN csv %s lacks iso3/odin_pop_vital columns; skipping", odin_csv
        )
        return frame
    return frame.merge(odin[["iso3", "odin_pop_vital"]], on="iso3", how="left")


def build_quality_table(
    session: requests.Session,
    output_dir: Path,
    *,
    odin_csv: Path | None = None,
    force: bool = False,
) -> Path:
    """Fetch World Bank SPI (+ optional ODIN) into a per-country reference table."""
    out_path = output_dir / "quality" / "country_quality.parquet"
    if out_path.exists() and not force:
        logger.info("skip (exists): %s", out_path)
        return out_path

    overall = _fetch_indicator(session, SPI_OVERALL)
    census = _fetch_indicator(session, SPI_CENSUS, source=SPI_DATABASE_SOURCE)
    rows = [
        {
            "iso3": iso3,
            "iso2": ISO3_TO_ISO2.get(iso3),
            "country_name": (overall.get(iso3) or census.get(iso3) or {}).get("name"),
            "spi_overall": (overall.get(iso3) or {}).get("value"),
            "spi_overall_year": (overall.get(iso3) or {}).get("year"),
            "census_availability": (census.get(iso3) or {}).get("value"),
            "census_avail_year": (census.get(iso3) or {}).get("year"),
        }
        for iso3 in sorted(set(overall) | set(census))
    ]
    frame = pd.DataFrame(rows)
    frame["odin_pop_vital"] = pd.NA
    if odin_csv is not None:
        frame = _merge_odin(frame, odin_csv)
    frame["fetched_utc"] = now_utc_iso()
    frame["source"] = QUALITY_SOURCE
    frame["licence"] = "CC BY 4.0"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path)
    frame.to_csv(out_path.with_suffix(".csv"), index=False)
    logger.info("quality table written: %s (%d countries)", out_path, len(frame))
    return out_path


def load_quality_table(path: Path) -> pd.DataFrame | None:
    """Return the quality table if present, else None."""
    return pd.read_parquet(path) if path.exists() else None
