# European census population data — sources, workflow & current data

This document describes how the repo acquires **European census population data**
for the census-vs-gridded-population comparison (against products such as GHSL
`GHS_POP`). It covers the data sources, the reproducible download workflow, the
output format, and the current state of the wired datasets.

The workflow lives in the `popgrids` package (`popgrids/europe/`) and is driven
by the `download-europe` CLI (or `scripts/download_europe.py`).

---

## 1. The three layers

European census geography is **not homogenized below 1 km**. The single
harmonized, true-census-enumeration product across Europe is the Eurostat
**1 km grid**; anything finer (the "US census-block equivalent") is published
**country by country** by each national statistical institute (NSI), in
differing units, formats and CRSs. The workflow therefore produces three
complementary layers:

| Layer | What | Resolution | Homogenized? | CLI |
|---|---|---|---|---|
| **Baseline** | Eurostat GEOSTAT Census 2021 grid | 1 km | Yes (EU + EFTA) | `--layers baseline` |
| **Fine (national)** | NSI finest census units | 100 m grids / output areas / census sections | No (per-country) | `--layers fine` (default) |
| **Reference** | GHS-UCDB urban-centre polygons | city polygons | Yes (global) | `--layers reference` |

The **fine national layers** are the core deliverable (block/block-group
granularity). The **1 km baseline** is the homogenized comparator and the
fallback where fine national data is gated. The **GHS-UCDB reference** is how
"cities" are defined for the comparison/urban-rural step (it is *not* used to
clip at download time by default — outputs are whole-country).

> **Note on the JRC 100 m grid.** Eurostat/JRC also publish a 100 m
> *Census Population Grid 2021* (DOI `10.2905/JRC.VP18KXG`). It is a **modelled**
> dasymetric disaggregation of the 1 km census counts, **not** enumerated census
> data, and is deliberately **excluded** from the census layers here.

---

## 2. Quick start

```bash
uv sync                                   # installs deps incl. pyarrow + the popgrids package
uv run download-europe --list             # show the coverage table (no network)

uv run download-europe --countries DE     # one country (Germany 100 m grid)
uv run download-europe --layers baseline  # the Eurostat 1 km baseline
uv run download-europe --layers reference # the GHS-UCDB urban-centre reference
uv run download-europe --layers all --force   # everything, re-downloading

# optional: clip a country's fine layer to specific cities (GHS-UCDB)
uv run download-europe --countries DE FR --cities "Munich" "Paris"
```

Useful flags: `--datasets DE_grid100m_2022 ...` (finer than `--countries`),
`--vintage 2021`, `--output-dir <path>` (default `data/europe`),
`--raw-dir <path>` (cache location; default `<output-dir>/_raw`),
`--clip-mode {centroid,area-weighted}`, `--force`, `--clean-raw`,
`--log-level DEBUG`.

Downloads are **streamed, resumable and idempotent**: an existing output is
skipped unless `--force` is passed. Raw archives are cached under
`data/europe/_raw/` so re-runs do not re-download. Gated sources (see §4) log a
warning and are skipped (use the 1 km baseline instead).

**Disk use.** Only the matching member of each archive is extracted (e.g. for
the 540 MB baseline zip just the 73 MB table, not the 1.2 GB GeoPackage). Output
GeoParquet for the full wired set is ~1–1.5 GB; the raw cache adds a few GB
during a run. Pass `--clean-raw` to delete `data/europe/_raw/` after a
successful run (or point `--raw-dir` outside any cloud-synced folder).

---

## 3. Data sources

Every source is encoded in the version-controlled catalog
(`popgrids/europe/catalog.py`) — that file is the authoritative, reproducible
spec (URLs, source CRS, attributes, join keys). `verified` marks entries whose
end-to-end run has been confirmed; unverified entries are wired from documented
sources but their exact column names / resource ids are confirmed on first
download (adapters validate columns and **fail loudly**, never silently default).

### Fine national layers

| Country | Unit | Vintage | Tier | Access | Source CRS | Pop. | Status |
|---|---|---|---|---|---|---|---|
| DE | Zensus 2022 100 m grid | 2022 | A | direct zip | EPSG:3035 | bundled (`Einwohner`) | ✅ verified |
| NL | CBS 100 m squares | 2024 | A | direct zip | EPSG:28992 | bundled (`aantal_inwoners`) | ✅ verified |
| FR | Filosofi 200 m grid | 2021 | A | direct file | EPSG:3035 | bundled (`ind`) | ✅ verified |
| FR | IRIS units | 2021 | A | direct file (.7z) | EPSG:2154 | join INSEE `P21_POP` (`CODE_IRIS=IRIS`) | ✅ verified |
| IT | Sezioni di censimento | 2021 | A | direct zip ×20 | EPSG:32632 | bundled (`POP21`) | ✅ verified |
| ES | Secciones censales | 2021 | A | direct zip | EPSG:25830 | join INE `t1_1` (CUSEC rebuilt) | ✅ verified |
| UK | Output Areas (E&W) | 2021 | B | ArcGIS Hub | EPSG:4326 (geojson) | join Nomis TS001 (`OA21CD`=`geography code`) | ✅ verified (E&W only) |
| IE | Small Areas | 2022 | B | ArcGIS Hub | EPSG:4326 (geojson) | bundled (`T1_1AGETT`) | ✅ verified |
| PT | BGRI subsecções | 2021 | A | direct zip | EPSG:3763 | bundled (`N_INDIVIDUOS`) | ✅ verified (mainland) |
| CH | STATPOP 100 m grid | 2024 | A | direct zip (CSV) | EPSG:2056 | bundled (`BBTOT`) | ✅ verified |
| NO | 250 m grid | 2025 | A | direct zip (GML) | EPSG:25833 | bundled (`popTot`) | ✅ verified |
| PL | NSP 500 m grid | 2021 | A | direct zip | EPSG:3035 | bundled (`TOT`) | ✅ verified |
| SE | 1 km grid | 2024 | A | WFS GeoPackage | EPSG:3006 | bundled (`beftotalt`) | ✅ verified (1 km) |
| BE | Statistical sectors | 2022 | C | bot-walled | EPSG:31370 | join (`TOTAL`) | wired, gated |
| AT | 100 m grid | 2025 | C | direct zip | EPSG:3035 | INSPIRE-GML pop | wired, deferred |

### Baseline & reference

| Layer | Source | Version | CRS | URL |
|---|---|---|---|---|
| Baseline | Eurostat GEOSTAT Census grid 1 km | V3 | EPSG:3035 | `gisco-services.ec.europa.eu/census/2021/Eurostat_Census-GRID_2021_V3.zip` |
| Reference | GHS Urban Centre Database (GHS-UCDB) | R2024A V1-2 | ESRI:54009 → EPSG:4326 | `jeodpp.jrc.ec.europa.eu/.../GHS_UCDB_GLOBE_R2024A_V1_2.zip` |

GHS-UCDB urban centres are dissolved GHSL **SMOD class-30** (≥1,500 inh/km²)
clusters, consistent with the repo's existing GHSL use.

---

## 4. Coverage & caveats

- **Tier A** (stable direct file/zip): DE, NL, FR (grid + IRIS), IT, ES, PT, CH,
  NO, PL, SE. → fetch + convert (+ join where the population is a separate table).
- **Tier B** (paginated ArcGIS/OGC API, no key): UK, IE. → API pagination
  (+ population join for UK).
- **Tier C** (still not auto-downloadable): **FI** (250 m, agreement+login),
  **DK** (100 m, order-only), **GR** (limited public data), **BE** (a
  statbel.fgov.be JS bot-wall blocks automated fetch — fully wired, but needs a
  browser/headless download), and **AT** (grid geometry is open but per-cell
  population is a 320 MB INSPIRE-GML needing a custom parser — deferred). These
  **fall back to the 1 km baseline**; BE/AT are wired in the catalog and only
  need the download path resolved.
- **Baseline coverage:** EU + EFTA (NO, CH, LI). **No UK, no Iceland**; **France
  excludes overseas regions**.
- **UK = England & Wales only** via the wired Output Areas dataset; Scotland
  (NRS) and Northern Ireland (NISRA) are separate and not yet added.
- **Statistical Disclosure Control (SDC):** national census counts carry
  perturbation/rounding/suppression (e.g. German cell-key method). Part of any
  census-vs-grid discrepancy is **disclosure noise, not modelling error** — do
  not treat the counts as exact, and expect suppressed/zero small cells.
- **2011 ↔ 2021 comparability:** the 2011 GEOSTAT grid was partly modelled/hybrid;
  2021 is census-based. Same 1 km INSPIRE grid, but treat the methodological
  change explicitly if comparing rounds.

\* PT is currently flagged Tier C (portal download) pending a confirmed direct URL.

---

## 5. Output schema & layout

Every output GeoParquet carries exactly these columns, normalized to
**EPSG:3035**:

| column | type | meaning |
|---|---|---|
| `pop` | float64 | total resident population (post-SDC, as published) |
| `unit_id` | string | source cell/unit id (`GITTER_ID_100m`, `OA21CD`, `CODE_IRIS`, …) |
| `country` | string | ISO-3166-1 alpha-2 (`UK` for Great Britain, matching source codes) |
| `source` | string | catalog `dataset_id` |
| `vintage` | int16 | reference year |
| `level` | string | unit code (`grid100m`, `oa`, `iris`, …) |
| `geometry` | polygon | cell/unit geometry |

```
data/europe/
├── _raw/{country}/<original-file>                 # cached downloads (gitignored)
├── _baseline/geostat_grid1km_2021.parquet         # 1 km homogenized grid
├── _reference/ghs_ucdb_R2024A.parquet             # GHS-UCDB urban centres (EPSG:4326)
├── {country}/national_{level}_{year}.parquet      # e.g. DE/national_grid100m_2022.parquet
├── {country}/{cityslug}_{level}_{year}.parquet    # only when --cities is used
├── {country}/national_{level}_{year}.parquet.provenance.json
└── provenance.jsonl                               # append-only run log
```

**CRS policy.** Outputs are normalized to EPSG:3035 (official INSPIRE/GEOSTAT
equal-area CRS); the native source CRS is preserved in the provenance record.
GHSL ships in Mollweide (ESRI:54009) — that reconciliation is **deferred to the
comparison step** (`differences.ipynb`), so these outputs stay a clean,
CRS-uniform census product. The GHS-UCDB reference is kept in EPSG:4326 (it is
global; reprojecting world geometries to the Europe-only 3035 is inappropriate).

---

## 6. Licensing & attribution

Each dataset's licence and required attribution string live in the catalog and
are copied into every provenance record. Key obligations:

- **Eurostat/GISCO** (baseline, GHS-UCDB via JRC): free reuse **with source
  acknowledgement**; the GEOSTAT census **population figures carry extra
  download/acceptance conditions** — cite Eurostat/GISCO and the dataset version.
- **National statistical institutes**: each has its own reuse terms (e.g.
  Germany DL-DE/BY-2.0; France Licence Ouverte 2.0; UK OGL v3.0 + Census 2021).
  Acknowledge the NSI as recorded in the provenance `attribution` field.

When adding data, also update the OneDrive `data_downloaded.xlsx` audit log (see
§7).

---

## 7. Provenance & reproducibility

- The committed reproducibility spec is `popgrids/europe/catalog.py`
  (version-controlled URLs/CRS/keys).
- Each output gets a `*.provenance.json` sidecar and one line in
  `data/europe/provenance.jsonl`, recording: source URLs, source/target CRS,
  download UTC timestamp, raw + output SHA-256, raw bytes, row count, population
  total, package version, git commit, licence and attribution.
- For the external OneDrive `data_downloaded.xlsx`, the records are **not**
  auto-written (the file lives outside the repo). Paste a row manually — a
  ready-to-paste tab-separated row is available via
  `popgrids.provenance.xlsx_row_hint(record)`.

---

## 8. Current data status

_Last updated: 2026-06-29._

- **Verified end-to-end (downloaded & written to GeoParquet):**
  - `DE_grid100m_2022` — 3,088,037 cells, 82.57 M population (≈ Germany's
    Zensus 2022 total), EPSG:3035 100 m polygons.
  - **Baseline** GEOSTAT 1 km V3 — 4,595,919 cells, 455.7 M population (EU+EFTA);
    13 per-country `*_unallocated` rows (434,787 people not geolocated) dropped.
    Geometry is derived from the INSPIRE `GRD_ID` (the parquet ships without
    geometry), avoiding the 2.5 GB GeoPackage.
  - **Reference** GHS-UCDB R2024A V1-2 — 915 European urban centres (filtered
    from the global ~11,422), EPSG:4326.
  - **City clip** (`--cities`) — e.g. Munich → 18,650 cells, 1.65 M people.
  - `NL_grid100m_2024` — 392,107 cells, 17.3 M population (cell id
    `crs28992res100m`; CBS negative SDC sentinels nulled by the non-negative
    guard); EPSG:3035.
  - `FR_filosofi200m_2021` — 2,287,884 cells, 63.0 M population (metropolitan
    France; native GeoParquet read via content sniffing); EPSG:3035.
  - `FR_iris_2021` — 48,569 IRIS, 65.5 M population (IGN `.7z` geometry +
    INSEE `P21_POP` join on `CODE_IRIS=IRIS`; ~15 unmatched IRIS).
  - `IT_sezioni_2021` — 756,376 sections, 59.0 M population (20 regional
    shapefiles concatenated; `POP21` bundled, no join).
  - `ES_secciones_2021` — 36,333 sections, 47.4 M population (INE shapefile +
    `C2021_Indicadores.csv`, CUSEC rebuilt from `cpro+cmun+dist+secc`; 0
    unmatched).
  - `UK_oa_2021` — 188,880 Output Areas, 59.6 M population (ONS ArcGIS, 95 paged
    requests; Nomis TS001 join on `geography code`; 0 unmatched). E&W only.
  - `IE_small_areas_2022` — 18,919 small areas, 5,149,139 population (exact CSO
    2022 total; fused `CensusHub2022_T1_1_SA` service, population bundled).
  - `PT_bgri_2021` — 203,264 subsections, 9.86 M (mainland; `N_INDIVIDUOS`
    bundled). `CH_statpop100m_2024` — 347,736 cells, 9.12 M (CSV grid,
    SW-corner coords). `NO_grid250m_2025` — 224,761 cells, 5.59 M (GML).
    `PL_grid500m_2021` — 1,252,059 cells, 38.0 M (INSPIRE shapefile).
    `SE_grid1km_2024` — 115,062 cells, 10.56 M (WFS GeoPackage).
- **13 fine-layer datasets verified** (DE, NL, FR×2, IT, ES, UK, IE, PT, CH, NO,
  PL, SE), each matching its national census/population total, plus the 1 km
  baseline and the GHS-UCDB reference. Total fine-layer GeoParquet ≈ 1.8 GB.
- **Still gated** (fall back to the 1 km baseline): **FI, DK, GR** (genuinely
  order/login-gated), **BE** (statbel JS bot-wall — wired, needs a browser), and
  **AT** (open geometry, but population is an INSPIRE-GML needing a custom parser).
  Optional next: UK Scotland (NRS) / Northern Ireland (NISRA).
- Run `uv run download-europe --list` for the live coverage table.

---

## 9. Extending the catalog

To add a country, add one `CountryDataset` to `popgrids/europe/catalog.py` and
pick an existing access `method`:

- **direct file/zip** → `method="direct_zip"` or `"direct_file"` (auto-detects
  zip / parquet / gpkg / shapefile / CSV grid). For CSV grids set
  `geometry_kind`, `x_field`/`y_field`, `cell_size_m`.
- **paginated API** → `method="arcgis_hub"` or `"ogc_api"` with `query_params`
  and `page_size`.
- **population join** → set `population.mode="join"` with `table_url`,
  `table_format`, and the `join_key_geom` / `join_key_pop` keys.

New adapter *code* is needed only for a genuinely new access protocol (add a
class and register it in `ADAPTER_REGISTRY`). Adapters validate expected columns
and raise descriptive errors listing the available columns, so a wrong
attribute/key name fails loudly on first run rather than producing silent nulls.

### Known gotchas

- `pyarrow` is required for GeoParquet (added to `pyproject.toml`).
- **Resolved on first download** (now hard-confirmed): GEOSTAT total-population
  column is `T`, keyed by `GRD_ID` in `ESTAT_Census_2021_V3.parquet` (plain
  table → geometry built from `GRD_ID`). GHS-UCDB R2024A columns are
  `GC_UCN_MAI_2025` (name), `ID_UC_G0` (id), `GC_CNT_GAD_2025` (country *name*,
  no ISO3), `GC_POP_TOT_2025` (population), in the
  `..._THEME_GENERAL_CHARACTERISTICS_...` layer.
- **Still to confirm on first run:** France IRIS/Filosofi attribute names and
  the IGN resource id; Nomis TS001 header; the ISTAT section join field and
  current regional-zip path; NL/IE bundled column names.
- Large files: baseline ~540 MB, GHS-UCDB ~264 MB — caching + skip-if-exists is
  essential.
- CSV encodings (German/French umlauts) are set per-dataset in the catalog.
