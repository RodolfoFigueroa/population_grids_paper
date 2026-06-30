"""Provenance records for every produced dataset (sidecar JSON + append log).

The committed, version-controlled reproducibility spec is the catalog itself
(``popgrids/europe/catalog.py``). These records capture what actually happened
on a given run: source URLs, hashes, sizes, row counts and totals. They live
next to the (gitignored) data. For the external OneDrive ``data_downloaded.xlsx``
audit log we only print a ready-to-paste row -- it is updated manually.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_TIMEOUT = 10


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """A single dataset's acquisition provenance."""

    dataset_id: str
    country: str
    source_urls: tuple[str, ...]
    source_crs: str
    target_crs: str
    population_mode: str
    download_utc: str
    raw_sha256: str
    raw_bytes: int
    output_path: str
    output_sha256: str
    row_count: int
    pop_total: float
    tool: str
    package_version: str
    git_commit: str | None
    licence: str
    attribution: str


def now_utc_iso() -> str:
    """Return the current UTC time as a timezone-aware ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def git_commit() -> str | None:
    """Return the current ``HEAD`` commit hash, or ``None`` if unavailable."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(
            [git, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_TIMEOUT,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return result.stdout.strip() or None


def write_sidecar(record: ProvenanceRecord, output_path: Path) -> Path:
    """Write ``{output_path}.provenance.json`` and return its path."""
    sidecar = output_path.with_name(output_path.name + ".provenance.json")
    sidecar.write_text(json.dumps(asdict(record), indent=2, sort_keys=True) + "\n")
    return sidecar


def append_jsonl(record: ProvenanceRecord, log_path: Path) -> None:
    """Append ``record`` as one JSON line to the append-only run log."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")


def xlsx_row_hint(record: ProvenanceRecord) -> str:
    """Return a tab-separated row to paste into the OneDrive audit log."""
    return "\t".join(
        [
            record.dataset_id,
            ", ".join(record.source_urls),
            record.download_utc,
            record.raw_sha256,
            str(record.row_count),
        ],
    )
