"""Census datasets for Asia-Pacific.

Wired datasets go in ``CATALOG``; surveyed-but-unwired countries go in
``CANDIDATES`` (see ``docs/global_census_availability.md``). Non-European
datasets set ``target_crs`` explicitly (the schema default EPSG:3035 is European).
"""

from __future__ import annotations

from popgrids.schema import Candidate, CountryDataset, GeometryAccess, PopulationSource

CATALOG: dict[str, CountryDataset] = {
    "AU_mb_2021": CountryDataset(
        dataset_id="AU_mb_2021",
        country="AU",
        unit_label="2021 Census Mesh Blocks",
        unit_code="mb",
        vintage=2021,
        geometry=GeometryAccess(
            tier="A",
            method="direct_zip",
            urls=(
                "https://www.abs.gov.au/statistics/standards/"
                "australian-statistical-geography-standard-asgs/"
                "edition-3-july-2021-june-2026/access-and-downloads/"
                "digital-boundary-files/MB_2021_AUST_SHP_GDA2020.zip",
            ),
            source_crs="EPSG:7844",
            unit_id_field="MB_CODE21",
            archive_member_suffix=".shp",
            geometry_kind="vector",
        ),
        population=PopulationSource(
            mode="join",
            attr="Person",
            table_url=(
                "https://www.abs.gov.au/census/guide-census-data/mesh-block-counts/"
                "2021/Mesh%20Block%20Counts%2C%202021.xlsx"
            ),
            table_format="xlsx",
            table_skiprows=6,
            table_sheet_contains="Table",
            join_key_geom="MB_CODE21",
            join_key_pop="MB_CODE_2021",
        ),
        target_crs="EPSG:4326",
        licence="CC BY 4.0",
        attribution="© ABS, 2021 Census (ASGS Edition 3 Mesh Blocks + counts)",
        verified=True,
        notes=(
            "Mesh Block shapefile (geometry only) joined to the ABS 'Mesh Block "
            "Counts 2021' xlsx (12 state sheets concatenated) on MB_CODE_2021; "
            "Person = total usual residents."
        ),
    ),
}

CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        "NZ",
        "Statistical Area 1 (SA1)",
        2023,
        2023,
        "B",
        "Stats NZ",
        bundled=False,
        notes="SA1 free; meshblock census counts are paid.",
    ),
    Candidate(
        "JP",
        "chōchō-moku (small area)",
        2020,
        2020,
        "B",
        "e-Stat",
        bundled=False,
        notes="boundary + table join on KEY_CODE; API available.",
    ),
    Candidate(
        "KR", "jipgyegu (집계구)", 2020, 2020, "B", "SGIS / KOSTAT", bundled=False
    ),
    Candidate(
        "PH",
        "barangay",
        2020,
        2020,
        "C",
        "PSA",
        bundled=False,
        notes="population open; official boundaries via HDX.",
    ),
    Candidate(
        "ID",
        "kelurahan / village",
        2020,
        2020,
        "C",
        "BPS",
        bundled=False,
        notes="no clean open boundary+pop bundle.",
    ),
    Candidate(
        "IN",
        "district / sub-district",
        2011,
        2011,
        "C",
        "ORGI",
        bundled=False,
        notes="2021 census delayed; finest open is district.",
    ),
    Candidate(
        "CN",
        "county",
        2020,
        2020,
        "C",
        "NBS",
        bundled=False,
        notes="no open enumeration-area geometry+population.",
    ),
)
