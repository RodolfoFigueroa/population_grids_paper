"""Census datasets for the Americas.

Wired datasets go in ``CATALOG``; surveyed-but-unwired countries go in
``CANDIDATES`` (see ``docs/global_census_availability.md``). Non-European
datasets set ``target_crs`` explicitly (the schema default EPSG:3035 is European).
"""

from __future__ import annotations

from popgrids.schema import Candidate, CountryDataset, GeometryAccess, PopulationSource

# USA: 2020 TIGER/Line tabblock20 is distributed per state (FIPS); POP20 bundled.
_US_FIPS = (
    "01",
    "02",
    "04",
    "05",
    "06",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "51",
    "53",
    "54",
    "55",
    "56",
)
_US_TIGER = "https://www2.census.gov/geo/tiger/TIGER2020/TABBLOCK20"
_US_URLS = tuple(f"{_US_TIGER}/tl_2020_{fips}_tabblock20.zip" for fips in _US_FIPS)


CATALOG: dict[str, CountryDataset] = {
    "US_blocks_2020": CountryDataset(
        dataset_id="US_blocks_2020",
        country="US",
        unit_label="2020 Census blocks",
        unit_code="blocks",
        vintage=2020,
        geometry=GeometryAccess(
            tier="A",
            method="direct_zip",
            urls=_US_URLS,
            source_crs="EPSG:4269",
            unit_id_field="GEOID20",
            archive_member_suffix=".shp",
            geometry_kind="vector",
        ),
        population=PopulationSource(mode="bundled", attr="POP20"),
        target_crs="EPSG:4326",
        licence="Public domain (U.S. Government work)",
        attribution="U.S. Census Bureau, 2020 Census (TIGER/Line)",
        verified=True,
        notes=(
            "51 per-state tabblock20 zips concatenated (50 states + DC). POP20 is "
            "bundled in the .dbf (no API join). Counts carry 2020 DAS noise."
        ),
    ),
    "CA_db_2021": CountryDataset(
        dataset_id="CA_db_2021",
        country="CA",
        unit_label="2021 Census dissemination blocks",
        unit_code="db",
        vintage=2021,
        geometry=GeometryAccess(
            tier="A",
            method="direct_zip",
            urls=(
                "https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/"
                "boundary-limites/files-fichiers/ldb_000b21a_e.zip",
            ),
            source_crs="EPSG:3347",
            unit_id_field="DBUID",
            archive_member_suffix=".shp",
            geometry_kind="vector",
        ),
        population=PopulationSource(
            mode="join",
            attr="DBPOP2021_IDPOP2021",
            table_url=(
                "https://www12.statcan.gc.ca/census-recensement/2021/geo/aip-pia/"
                "attribute-attribs/files-fichiers/2021_92-151_X.zip"
            ),
            table_format="zip-csv",
            table_member_contains=("92-151",),
            table_encoding="latin-1",
            join_key_geom="DBUID",
            join_key_pop="DBUID_IDIDU",
        ),
        target_crs="EPSG:4326",
        licence="Statistics Canada Open Licence",
        attribution="Statistics Canada, 2021 Census (boundary + GAF 92-151-X)",
        verified=True,
        notes=(
            "Cartographic DB boundary (land-mass) joined to the Geographic "
            "Attribute File (GAF) on DBUID; population DBPOP2021_IDPOP2021."
        ),
    ),
    "BR_setores_2022": CountryDataset(
        dataset_id="BR_setores_2022",
        country="BR",
        unit_label="Setores censitários 2022",
        unit_code="setores",
        vintage=2022,
        geometry=GeometryAccess(
            tier="A",
            method="direct_zip",
            urls=(
                "https://geoftp.ibge.gov.br/organizacao_do_territorio/"
                "malhas_territoriais/"
                "malhas_de_setores_censitarios__divisoes_intramunicipais/"
                "censo_2022/setores/shp/BR/BR_setores_CD2022.zip",
            ),
            source_crs="EPSG:4674",
            unit_id_field="CD_SETOR",
            archive_member_suffix=".shp",
            geometry_kind="vector",
        ),
        population=PopulationSource(
            mode="join",
            attr="v0001",
            table_url=(
                "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
                "Agregados_por_Setores_Censitarios/Agregados_por_Setor_csv/"
                "Agregados_por_setores_basico_BR_20260520.zip"
            ),
            table_format="zip-csv",
            table_member_contains=("basico",),
            table_separator=";",
            table_encoding="latin-1",
            join_key_geom="CD_SETOR",
            join_key_pop="CD_SETOR",
        ),
        target_crs="EPSG:4326",
        licence="Public data (IBGE), attribution required",
        attribution="© IBGE, Censo Demográfico 2022 (malha + Agregados)",
        verified=True,
        notes=(
            "National setor shapefile (Deflate64 zip → system-unzip fallback; admin "
            "fields only). Population V0001 (Total de pessoas) joined from "
            "Agregados_por_setores_basico_BR.csv on CD_SETOR (';'-delimited, UTF-8)."
        ),
    ),
}

CANDIDATES: tuple[Candidate, ...] = (
    Candidate(
        "MX",
        "manzana / AGEB",
        2020,
        2020,
        "A",
        "INEGI",
        bundled=False,
        notes="Already in the repo via PostGIS; INEGI Marco Geoestadístico + ITER.",
    ),
    Candidate(
        "CL",
        "manzana-entidad",
        2024,
        2024,
        "A",
        "INE Chile",
        bundled=True,
        notes="Newest census in the survey (published Dec 2025).",
    ),
    Candidate(
        "CO",
        "manzana",
        2018,
        2018,
        "A",
        "DANE",
        bundled=True,
        notes="MGN integrado carries census variables.",
    ),
    Candidate(
        "AR",
        "radio censal",
        2022,
        2022,
        "B",
        "INDEC",
        bundled=False,
        notes="Portal Geoestadístico / GeoNode + REDATAM join.",
    ),
    Candidate("EC", "sector censal", 2022, 2022, "B", "INEC", bundled=False),
    Candidate(
        "PE",
        "manzana",
        2017,
        2017,
        "C",
        "INEI",
        bundled=False,
        notes="manzana population officially restricted.",
    ),
    Candidate(
        "UY",
        "segmento censal",
        2023,
        2011,
        "C",
        "INE",
        bundled=False,
        notes="2023 geo microdata rolling out.",
    ),
)
