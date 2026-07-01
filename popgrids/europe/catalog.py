"""The committed, version-controlled catalog of European census datasets.

This module *is* the reproducibility spec: every URL, source CRS, attribute and
join key lives here under version control. ``verified=True`` marks entries whose
end-to-end download has been confirmed; ``verified=False`` entries are wired from
documented sources but their exact column names / resource ids must be confirmed
on first download (adapters validate columns and fail loudly, never default).

Coverage tiers (see ``docs/europe_census_data.md``):
* Tier A -- stable direct file/zip URL.
* Tier B -- paginated ArcGIS/OGC API (no key).
* Tier C -- order/login-gated; falls back to the 1 km baseline.
"""

from __future__ import annotations

from popgrids.schema import Candidate, CountryDataset, GeometryAccess, PopulationSource

# ISTAT publishes one zip per administrative region (codes 01..20).
_ISTAT_BASE = "https://www.istat.it/storage/cartografia/basi_territoriali/2021"
_ISTAT_URLS = tuple(f"{_ISTAT_BASE}/R{region:02d}_21.zip" for region in range(1, 21))


CATALOG: dict[str, CountryDataset] = {
    "DE_grid100m_2022": CountryDataset(
        dataset_id="DE_grid100m_2022",
        country="DE",
        unit_label="Zensus 2022 100 m population grid",
        unit_code="grid100m",
        vintage=2022,
        geometry=GeometryAccess(
            tier="A",
            method="direct_zip",
            urls=(
                "https://www.destatis.de/static/DE/zensus/gitterdaten/"
                "Zensus2022_Bevoelkerungszahl.zip",
            ),
            source_crs="EPSG:3035",
            unit_id_field="GITTER_ID_100m",
            archive_member_contains=("100m",),
            archive_member_suffix=".csv",
            geometry_kind="grid_csv_center",
            csv_separator=";",
            csv_encoding="utf-8",
            x_field="x_mp_100m",
            y_field="y_mp_100m",
            cell_size_m=100,
        ),
        population=PopulationSource(mode="bundled", attr="Einwohner"),
        licence="DL-DE/BY-2-0",
        attribution="© Statistisches Bundesamt (Destatis), Zensus 2022",
        verified=True,
        notes=(
            "Cell-centre coords (x_mp_100m/y_mp_100m); polygons built as 100 m "
            "squares. SDC: cell-key perturbation applied. Zip also holds 1 km / "
            "10 km grids; we select the 100 m CSV."
        ),
    ),
    "NL_grid100m_2024": CountryDataset(
        dataset_id="NL_grid100m_2024",
        country="NL",
        unit_label="CBS 100 m square statistics",
        unit_code="grid100m",
        vintage=2024,
        geometry=GeometryAccess(
            tier="A",
            method="direct_zip",
            urls=("https://download.cbs.nl/vierkant/100/2025-cbs_vk100_2024_v1.zip",),
            source_crs="EPSG:28992",
            unit_id_field="crs28992res100m",
            archive_member_suffix=".gpkg",
            geometry_kind="vector",
        ),
        population=PopulationSource(mode="bundled", attr="aantal_inwoners"),
        licence="CC BY 4.0",
        attribution="© CBS, Kaart van 100 meter bij 100 meter",
        verified=True,
        notes=(
            "Cell id 'crs28992res100m'. CBS applies SDC: suppressed cells carry "
            "negative sentinels (e.g. -99997), nulled by the non-negative guard."
        ),
    ),
    "FR_filosofi200m_2021": CountryDataset(
        dataset_id="FR_filosofi200m_2021",
        country="FR",
        unit_label="Filosofi 200 m grid (carreaux)",
        unit_code="grid200m",
        vintage=2021,
        geometry=GeometryAccess(
            tier="A",
            method="direct_file",
            urls=(
                "https://www.data.gouv.fr/api/1/datasets/r/"
                "b480cead-3f46-4b1b-a943-62a009b83f7a",
            ),
            source_crs="EPSG:3035",
            unit_id_field="idcar_200m",
            geometry_kind="vector",
        ),
        population=PopulationSource(mode="bundled", attr="ind"),
        licence="Licence Ouverte 2.0",
        attribution="© INSEE, Filosofi données carroyées 2021",
        verified=True,
        notes=(
            "Native GeoParquet (resource 302-redirects to carreaux-200m-met-3035; "
            "read via content sniffing). Metropole only; pop 'ind' = individuals."
        ),
    ),
    "FR_iris_2021": CountryDataset(
        dataset_id="FR_iris_2021",
        country="FR",
        unit_label="IRIS statistical units",
        unit_code="iris",
        vintage=2021,
        geometry=GeometryAccess(
            tier="A",
            method="direct_file",
            urls=(
                "https://data.geopf.fr/telechargement/download/CONTOURS-IRIS/"
                "CONTOURS-IRIS_3-0__SHP_LAMB93_FXX_2024-01-01/"
                "CONTOURS-IRIS_3-0__SHP_LAMB93_FXX_2024-01-01.7z",
            ),
            source_crs="EPSG:2154",
            unit_id_field="CODE_IRIS",
            archive_member_contains=("1_donnees",),
            archive_member_suffix=".shp",
            geometry_kind="vector",
        ),
        population=PopulationSource(
            mode="join",
            attr="P21_POP",
            table_url=(
                "https://www.insee.fr/fr/statistiques/fichier/8268806/"
                "base-ic-evol-struct-pop-2021_csv.zip"
            ),
            table_format="zip-csv",
            table_member_contains=("base-ic-evol",),
            table_separator=";",
            table_encoding="latin-1",
            join_key_geom="CODE_IRIS",
            join_key_pop="IRIS",
        ),
        licence="Licence Ouverte 2.0",
        attribution="© IGN CONTOURS-IRIS (Géoplateforme) + © INSEE",
        verified=True,
        notes=(
            "Geometry from IGN data.geopf.fr (.7z, métropole/FXX, EPSG:2154, "
            "millésime 2024). Population P21_POP from INSEE 'Population en 2021' "
            "(geography 2023) joined on CODE_IRIS=IRIS; minor IRIS-redraw drift "
            "leaves ~15 unmatched IRIS (pop NaN)."
        ),
    ),
    "IT_sezioni_2021": CountryDataset(
        dataset_id="IT_sezioni_2021",
        country="IT",
        unit_label="Sezioni di censimento (basi territoriali)",
        unit_code="sezioni",
        vintage=2021,
        geometry=GeometryAccess(
            tier="A",
            method="direct_zip",
            urls=_ISTAT_URLS,
            source_crs="EPSG:32632",
            unit_id_field="SEZ21_ID",
            archive_member_contains=("_wgs84",),
            archive_member_suffix=".shp",
            geometry_kind="vector",
        ),
        population=PopulationSource(mode="bundled", attr="POP21"),
        licence="CC BY 4.0",
        attribution="© ISTAT, Basi territoriali e variabili censuarie 2021",
        verified=True,
        notes=(
            "20 regional shapefile zips concatenated (SHP/R{NN}_21_WGS84.shp). "
            "Total population is bundled in the dbf (POP21), so no XLSX join is "
            "needed. SEZ21_ID is numeric so unit_id drops leading zeros "
            "(zero-pad to 13 digits = PRO_COM + SEZ(7) for the canonical code)."
        ),
    ),
    "UK_oa_2021": CountryDataset(
        dataset_id="UK_oa_2021",
        country="UK",
        unit_label="2021 Census Output Areas (England & Wales)",
        unit_code="oa",
        vintage=2021,
        geometry=GeometryAccess(
            tier="B",
            method="arcgis_hub",
            urls=(
                "https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
                "Output_Areas_2021_EW_BGC_V2/FeatureServer/0/query",
            ),
            source_crs="EPSG:4326",
            unit_id_field="OA21CD",
            geometry_kind="vector",
            query_params={
                "where": "1=1",
                "outFields": "OA21CD",
                "orderByFields": "OA21CD",
            },
            page_size=2000,
        ),
        population=PopulationSource(
            mode="join",
            attr="Residence type: Total; measures: Value",
            table_url="https://www.nomisweb.co.uk/output/census/2021/census2021-ts001.zip",
            table_format="zip-csv",
            table_member_contains=("ts001-oa",),
            join_key_geom="OA21CD",
            join_key_pop="geography code",
        ),
        licence="OGL v3.0 (ONS Open Geography + Census 2021)",
        attribution="© ONS Open Geography Portal; Nomis TS001 (ONS)",
        verified=True,
        notes=(
            "England & Wales only (Scotland/NI are separate). ArcGIS f=geojson "
            "returns EPSG:4326; paged by OA21CD (188,880 OAs). Population joins "
            "the OA-level TS001 CSV on 'geography code'."
        ),
    ),
    "ES_secciones_2021": CountryDataset(
        dataset_id="ES_secciones_2021",
        country="ES",
        unit_label="Secciones censales",
        unit_code="secciones",
        vintage=2021,
        geometry=GeometryAccess(
            tier="A",
            method="direct_zip",
            urls=("https://www.ine.es/censos2021/Cartografia_secc.zip",),
            source_crs="EPSG:25830",
            unit_id_field="CUSEC",
            archive_member_suffix=".shp",
            geometry_kind="vector",
        ),
        population=PopulationSource(
            mode="join",
            attr="t1_1",
            table_url="https://www.ine.es/censos2021/C2021_Indicadores.csv",
            table_format="csv",
            table_separator=",",
            join_key_geom="CUSEC",
            join_key_pop="_cusec",
            build_join_key_from=(("cpro", 2), ("cmun", 3), ("dist", 2), ("secc", 3)),
        ),
        licence="INE reuse terms (CC-BY style)",
        attribution="© INE, Censo 2021 + cartografía de secciones censales",
        verified=True,
        notes=(
            "Direct shapefile (Seccionado_2021/SECC_CE_20210101.shp, sections "
            "only, 36,333 rows). Population t1_1 from C2021_Indicadores.csv; CUSEC "
            "rebuilt from cpro+cmun+dist+secc (no single CUSEC column in the CSV)."
        ),
    ),
    "IE_small_areas_2022": CountryDataset(
        dataset_id="IE_small_areas_2022",
        country="IE",
        unit_label="Census 2022 Small Areas",
        unit_code="small_areas",
        vintage=2022,
        geometry=GeometryAccess(
            tier="B",
            method="arcgis_hub",
            urls=(
                "https://services-eu1.arcgis.com/BuS9rtTsYEV5C0xh/arcgis/rest/services/"
                "CensusHub2022_T1_1_SA/FeatureServer/0/query",
            ),
            source_crs="EPSG:4326",
            unit_id_field="SA_GEOGID_2022",
            geometry_kind="vector",
            query_params={
                "where": "1=1",
                "outFields": "SA_GEOGID_2022,T1_1AGETT",
                "orderByFields": "SA_GEOGID_2022",
            },
            page_size=2000,
        ),
        population=PopulationSource(mode="bundled", attr="T1_1AGETT"),
        licence="CC BY 4.0 (CSO / Tailte Éireann)",
        attribution="© CSO Ireland; Tailte Éireann (GeoHive)",
        verified=True,
        notes=(
            "Fused CensusHub2022_T1_1_SA service bundles geometry + population "
            "(T1_1AGETT total), so no join. ArcGIS f=geojson returns EPSG:4326; "
            "18,919 small areas, paged by SA_GEOGID_2022."
        ),
    ),
}


# Tier-C / pending-verification sources: order/login-gated, or with a documented
# landing page but no confirmed stable direct URL yet. Flagged here for coverage;
# they fall back to the 1 km baseline. Upgrade to a concrete adapter once the
# direct URL/credentials are resolved. Columns:
# (dataset_id, country, unit_label, unit_code, vintage, landing, crs, notes).
_GATED_SPECS: tuple[tuple[str, str, str, str, int, str, str, str], ...] = (
    (
        "AT_grid100m_2025",
        "AT",
        "Regionalstatistische Rastereinheiten 100 m",
        "grid100m",
        2025,
        "https://data.statistik.gv.at/web/meta.jsp?dataset=OGDEXT_RASTER_1",
        "EPSG:3035",
        "Grid geometry is open (OGDEXT_RASTER_1) but carries NO population; "
        "per-cell population is a separate ~320 MB INSPIRE PopulationDistribution "
        "GML (pd:value, xlink-keyed) needing a custom parser -- deferred.",
    ),
    (
        "FI_grid250m_2022",
        "FI",
        "Ruututietokanta 250 m",
        "grid250m",
        2022,
        "https://stat.fi/tup/ruututietokanta/index_en.html",
        "EPSG:3067",
        "Gated (agreement + login). Fall back to baseline 1 km.",
    ),
    (
        "DK_grid100m_2023",
        "DK",
        "Kvadratnet 100 m",
        "grid100m",
        2023,
        "https://www.dst.dk/en/TilSalg/produkter/geodata/kvadratnet",
        "EPSG:25832",
        "Order-only (contract). Fall back to baseline 1 km.",
    ),
    (
        "GR_blocks_2021",
        "GR",
        "Census building blocks / small areas",
        "blocks",
        2021,
        "https://www.statistics.gr/en/digital-cartographical-data",
        "EPSG:2100",
        "Limited public fine-grained download. Fall back to baseline 1 km.",
    ),
)

for _id, _country, _label, _code, _year, _landing, _crs, _note in _GATED_SPECS:
    CATALOG[_id] = CountryDataset(
        dataset_id=_id,
        country=_country,
        unit_label=_label,
        unit_code=_code,
        vintage=_year,
        geometry=GeometryAccess(
            tier="C",
            method="gated",
            urls=(_landing,),
            source_crs=_crs,
            unit_id_field="",
        ),
        population=PopulationSource(mode="bundled", attr=""),
        licence="see source",
        attribution=f"{_country} national statistical institute",
        notes=_note,
    )


# Tier-C countries wired to verified open direct sources.
CATALOG.update(
    {
        "PT_bgri_2021": CountryDataset(
            dataset_id="PT_bgri_2021",
            country="PT",
            unit_label="BGRI 2021 subsecções estatísticas",
            unit_code="bgri",
            vintage=2021,
            geometry=GeometryAccess(
                tier="A",
                method="direct_zip",
                urls=("https://mapas.ine.pt/download/filesGPG/2021/BGRI21_CONT.zip",),
                source_crs="EPSG:3763",
                unit_id_field="SUBSECCAO",
                archive_member_suffix=".gpkg",
                geometry_kind="vector",
            ),
            population=PopulationSource(mode="bundled", attr="N_INDIVIDUOS"),
            licence="INE reuse terms",
            attribution="© INE Portugal, BGRI Censos 2021",
            verified=True,
            notes=(
                "Mainland (Continente) only, EPSG:3763; population bundled "
                "(N_INDIVIDUOS). Azores/Madeira are separate files in other CRS."
            ),
        ),
        "BE_sectors_2022": CountryDataset(
            dataset_id="BE_sectors_2022",
            country="BE",
            unit_label="Statistical sectors",
            unit_code="sectors",
            vintage=2022,
            geometry=GeometryAccess(
                tier="C",
                method="gated",
                urls=(
                    "https://statbel.fgov.be/sites/default/files/files/opendata/"
                    "Statistische%20sectoren/"
                    "sh_statbel_statistical_sectors_31370_20220101.shp.zip",
                ),
                source_crs="EPSG:31370",
                unit_id_field="CD_SECTOR",
                archive_member_suffix=".shp",
                geometry_kind="vector",
            ),
            population=PopulationSource(
                mode="join",
                attr="TOTAL",
                table_url=(
                    "https://statbel.fgov.be/sites/default/files/files/opendata/"
                    "bevolking/sectoren/OPENDATA_SECTOREN_2024.zip"
                ),
                table_format="zip-csv",
                table_member_contains=("sectoren_2024",),
                table_separator="|",
                table_encoding="utf-8-sig",
                join_key_geom="CD_SECTOR",
                join_key_pop="CD_SECTOR",
            ),
            licence="Statbel open data",
            attribution="© Statbel (Belgium)",
            verified=False,
            notes=(
                "GATED by a statbel.fgov.be JS bot-wall (Reblaze) that a browser "
                "User-Agent does not bypass -- automated fetch gets an HTML "
                "challenge. Data is fully wired (2022 sector shp + 2024 pipe-.txt "
                "join on CD_SECTOR/TOTAL); download both URLs in a browser and "
                "point --raw-dir at them, or fetch via a headless browser."
            ),
        ),
        "CH_statpop100m_2024": CountryDataset(
            dataset_id="CH_statpop100m_2024",
            country="CH",
            unit_label="STATPOP 100 m population grid",
            unit_code="grid100m",
            vintage=2024,
            geometry=GeometryAccess(
                tier="A",
                method="direct_zip",
                urls=(
                    "https://dam-api.bfs.admin.ch/hub/api/dam/assets/36079999/master",
                ),
                source_crs="EPSG:2056",
                unit_id_field="RELI",
                archive_member_suffix=".csv",
                geometry_kind="grid_csv_lower_left",
                csv_separator=";",
                x_field="E_KOORD",
                y_field="N_KOORD",
                cell_size_m=100,
            ),
            population=PopulationSource(mode="bundled", attr="BBTOT"),
            licence="FSO/BFS open data (opendata.swiss)",
            attribution="© BFS, STATPOP 2024",
            verified=True,
            notes=(
                "CSV-in-zip; E_KOORD/N_KOORD are the hectare SW corner (LV95). "
                "BBTOT = total permanent residents; SDC: cell counts 1-3 -> 3."
            ),
        ),
        "NO_grid250m_2025": CountryDataset(
            dataset_id="NO_grid250m_2025",
            country="NO",
            unit_label="Befolkning på rutenett 250 m",
            unit_code="grid250m",
            vintage=2025,
            geometry=GeometryAccess(
                tier="A",
                method="direct_zip",
                urls=(
                    "https://nedlasting.geonorge.no/geonorge/Befolkning/"
                    "BefolkningsstatistikkRutenett250m2025/GML/"
                    "Befolkning_0000_Norge_25833_"
                    "BefolkningsstatistikkRutenett250m2025_GML.zip",
                ),
                source_crs="EPSG:25833",
                unit_id_field="ssbid250m",
                archive_member_suffix=".gml",
                geometry_kind="vector",
            ),
            population=PopulationSource(mode="bundled", attr="popTot"),
            licence="NLOD 1.0",
            attribution="© SSB (Statistics Norway), Geonorge",
            verified=True,
            notes="GML 3.2.1 from Geonorge; register-based 250 m grid (popTot).",
        ),
        "PL_grid500m_2021": CountryDataset(
            dataset_id="PL_grid500m_2021",
            country="PL",
            unit_label="NSP 2021 500 m population grid",
            unit_code="grid500m",
            vintage=2021,
            geometry=GeometryAccess(
                tier="A",
                method="direct_zip",
                urls=(
                    "https://geo.stat.gov.pl/atom-web/download/"
                    "?fileId=f3d55d7726903dee59a1a7a5957a07f0"
                    "&name=NSP2021_TOT_grid500m_SHP.zip",
                ),
                source_crs="EPSG:3035",
                unit_id_field="code",
                archive_member_suffix=".shp",
                geometry_kind="vector",
            ),
            population=PopulationSource(mode="bundled", attr="TOT"),
            licence="GUS open data",
            attribution="© GUS (Statistics Poland), NSP 2021",
            verified=True,
            notes="500 m INSPIRE grid (finest open); 'code' = INSPIRE id, TOT bundled.",
        ),
        "SE_grid1km_2024": CountryDataset(
            dataset_id="SE_grid1km_2024",
            country="SE",
            unit_label="Statistik på rutor 1 km",
            unit_code="grid1km",
            vintage=2024,
            geometry=GeometryAccess(
                tier="A",
                method="direct_file",
                urls=(
                    "https://geodata.scb.se/geoserver/stat/wfs?service=WFS&"
                    "REQUEST=GetFeature&version=1.1.0&"
                    "TYPENAMES=stat:befolkning_1km_2024&outputFormat=geopackage",
                ),
                source_crs="EPSG:3006",
                unit_id_field="rutid_scb",
                geometry_kind="vector",
            ),
            population=PopulationSource(mode="bundled", attr="beftotalt"),
            licence="SCB open geodata",
            attribution="© SCB (Statistics Sweden)",
            verified=True,
            notes=(
                "Open product is 1 km (250 m gated), EPSG:3006; overlaps the "
                "GEOSTAT 1 km baseline. WFS GeoPackage output; beftotalt bundled."
            ),
        ),
    },
)

# All European countries are wired (some as gated entries in CATALOG above), so
# there are no surveyed-but-unwired candidates for this region.
CANDIDATES: tuple[Candidate, ...] = ()
