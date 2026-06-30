"""Reusable IO core: streamed/resumable HTTP download, hashing, zip, GeoParquet.

Designed to be region-agnostic so ``popgrids.europe`` (and future
``popgrids.latam`` / ``popgrids.usa``) share the same fetch + write primitives.
"""

from __future__ import annotations

import hashlib
import logging
import sys
import zipfile
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING

import geopandas as gpd
import py7zr
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib3.util.retry import Retry

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1 << 20  # 1 MiB streaming chunks.
#: (connect, read) timeout in seconds for every request.
TIMEOUT: tuple[int, int] = (10, 60)
RETRY_TOTAL = 5
RETRY_BACKOFF = 1.0
RETRY_STATUSES = (
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.INTERNAL_SERVER_ERROR,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
)
_PARQUET_SUFFIXES = {".parquet", ".pq"}
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 popgrids/0.1"
)


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """Outcome of a single :func:`download` call."""

    path: Path
    sha256: str
    n_bytes: int
    from_cache: bool


def build_session() -> requests.Session:
    """Return a :class:`requests.Session` with sensible retry/backoff."""
    retry = Retry(
        total=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=tuple(int(status) for status in RETRY_STATUSES),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    # A browser-like User-Agent: several official open-data servers reject the
    # default "python-requests" agent (or serve a bot-challenge page) for files
    # that a normal browser downloads fine.
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of ``path`` (streamed, constant memory)."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK_SIZE), b""):
            hasher.update(block)
    return hasher.hexdigest()


def download(
    url: str,
    dest: Path,
    *,
    session: requests.Session | None = None,
    force: bool = False,
    resume: bool = True,
) -> DownloadResult:
    """Stream ``url`` to ``dest`` with resume support and integrity hashing.

    Idempotent: an existing ``dest`` is returned untouched unless ``force`` is
    set (the analog of the notebook ``asset_exists`` skip-guard). Partial
    downloads are staged in a ``.part`` sidecar and atomically renamed on
    completion, with an HTTP ``Range`` request to resume when the server allows.
    """
    dest = Path(dest)
    if dest.exists() and not force:
        logger.info("cached: %s", dest)
        return DownloadResult(
            dest, sha256_file(dest), dest.stat().st_size, from_cache=True
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    owns_session = session is None
    session = session or build_session()
    part = dest.with_name(dest.name + ".part")
    existing = part.stat().st_size if (resume and part.exists() and not force) else 0
    if force and part.exists():
        part.unlink()
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    response: requests.Response | None = None
    try:
        response = session.get(url, stream=True, timeout=TIMEOUT, headers=headers)
        response.raise_for_status()
        append = existing > 0 and response.status_code == HTTPStatus.PARTIAL_CONTENT
        total = int(response.headers.get("Content-Length", 0)) + (
            existing if append else 0
        )
        mode = "ab" if append else "wb"
        with (
            part.open(mode) as handle,
            tqdm(
                total=total or None,
                initial=existing if append else 0,
                unit="B",
                unit_scale=True,
                desc=dest.name,
                disable=not sys.stderr.isatty(),
            ) as bar,
        ):
            for chunk in response.iter_content(CHUNK_SIZE):
                handle.write(chunk)
                bar.update(len(chunk))
    finally:
        if response is not None:
            response.close()
        if owns_session:
            session.close()

    part.replace(dest)
    digest = sha256_file(dest)
    logger.info("downloaded %s (%d bytes)", dest, dest.stat().st_size)
    return DownloadResult(dest, digest, dest.stat().st_size, from_cache=False)


def _is_safe_member(member: str, dest_dir: Path) -> bool:
    target = (dest_dir / member).resolve()
    return target == dest_dir.resolve() or target.is_relative_to(dest_dir.resolve())


def is_archive(archive: Path) -> bool:
    """Return True if ``archive`` is a supported (zip or 7z) archive."""
    return zipfile.is_zipfile(archive) or py7zr.is_7zfile(archive)


def list_archive_members(archive: Path) -> list[str]:
    """Return the member names inside a zip or 7z ``archive``."""
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            return zf.namelist()
    if py7zr.is_7zfile(archive):
        with py7zr.SevenZipFile(archive) as archive_7z:
            return archive_7z.getnames()
    msg = f"Not a supported archive (zip/7z): {archive}"
    raise ValueError(msg)


def find_members(
    archive: Path,
    *,
    contains: Sequence[str] = (),
    suffix: str | None = None,
) -> list[str]:
    """Return members whose name matches every ``contains`` token and ``suffix``."""
    members = list_archive_members(archive)
    tokens = [token.lower() for token in contains]
    return [
        name
        for name in members
        if all(token in name.lower() for token in tokens)
        and (suffix is None or name.lower().endswith(suffix.lower()))
    ]


def extract_zip(
    archive: Path,
    dest_dir: Path,
    *,
    members: Iterable[str] | None = None,
) -> list[Path]:
    """Extract ``members`` (or all) from ``archive`` with a zip-slip guard."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(archive) as zf:
        names = list(members) if members is not None else zf.namelist()
        for name in names:
            if not _is_safe_member(name, dest_dir):
                msg = f"Unsafe (zip-slip) member path: {name!r}"
                raise ValueError(msg)
            zf.extract(name, dest_dir)
            extracted.append(dest_dir / name)
    return extracted


def extract_members(
    archive: Path,
    dest_dir: Path,
    *,
    contains: Sequence[str] = (),
    suffix: str | None = None,
) -> list[Path]:
    """Extract only the members matching ``contains``/``suffix``.

    For a matched ``.shp`` target, its sidecar files (``.dbf``/``.shx``/``.prj``
    …) are extracted too. This avoids unpacking large unused archive members
    (e.g. a multi-GB GeoPackage we never read).
    """
    targets = find_members(archive, contains=contains, suffix=suffix)
    if not targets:
        msg = (
            f"No member in {Path(archive).name} matched "
            f"contains={tuple(contains)} suffix={suffix}"
        )
        raise ValueError(msg)
    if py7zr.is_7zfile(archive):
        # py7zr targeted extraction of deeply-nested members is brittle; extract
        # the whole archive (IGN .7z archives are small).
        dest_dir = Path(dest_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        with py7zr.SevenZipFile(archive) as archive_7z:
            archive_7z.extractall(path=dest_dir)
        return [dest_dir / name for name in list_archive_members(archive)]
    selected = set(targets)
    shp_bases = [
        name[: -len(".shp")] for name in targets if name.lower().endswith(".shp")
    ]
    if shp_bases:
        selected.update(
            name
            for name in list_archive_members(archive)
            if any(name.startswith(f"{base}.") for base in shp_bases)
        )
    return extract_zip(archive, dest_dir, members=sorted(selected))


def read_vector(
    path: Path,
    *,
    layer: str | None = None,
    columns: Sequence[str] | None = None,
) -> gpd.GeoDataFrame:
    """Read a vector file or GeoParquet into a GeoDataFrame (pyogrio engine)."""
    path = Path(path)
    if path.suffix.lower() in _PARQUET_SUFFIXES:
        frame = gpd.read_parquet(path)
        return frame[list(columns)] if columns else frame
    return gpd.read_file(
        path,
        layer=layer,
        columns=list(columns) if columns else None,
        engine="pyogrio",
    )


def write_geoparquet(gdf: gpd.GeoDataFrame, path: Path) -> None:
    """Write ``gdf`` to ``path`` as GeoParquet (atomic via a temp file)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    gdf.to_parquet(tmp)
    tmp.replace(path)
    logger.info("wrote GeoParquet %s", path)
