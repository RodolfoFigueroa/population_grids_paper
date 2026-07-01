# Global census-data availability survey

Which countries publish **recent, openly-downloadable, finest-resolution census
geography + population** — the input for deciding what to wire into the pipeline
beyond Europe. Tiers match the European pipeline:

- **Tier A** — stable direct file/zip download.
- **Tier B** — API / ArcGIS / portal, automatable without login.
- **Tier C** — gated (login / order / fee) or no open finest-resolution data.

"Open finest yr" = the most recent census whose finest unit is actually open
with population (a 2022 census may still only have 2010-era open geography).

> These rows are an availability assessment from NSI documentation and portal
> metadata, not a per-URL download test. Exact field names, CRS and join keys are
> confirmed at ingest (the adapters validate columns and fail loudly).

---

## North America

| Country | Finest unit | Census | Open yr | Open? | Pop | Format | Tier | Agency |
|---|---|---|---|---|---|---|---|---|
| **USA** | Census block → block group | 2020 | 2020 | yes | join (TIGER ⨝ PL94 / Census API on GEOID) | Shapefile + CSV/API | A/B | US Census Bureau |
| **Canada** | Dissemination block → DA | 2021 | 2021 | yes | bundled (DB boundary carries counts) | Shapefile/GML/FileGDB + Esri REST | A | Statistics Canada |
| **Mexico** | manzana → AGEB | 2020 | 2020 | yes | join (Marco Geoestadístico ⨝ ITER on CVEGEO) | Shapefile + CSV | A | INEGI |

Mexico is already in the repo via PostGIS (`census_2020_ageb`); it can be added to
the new pipeline as `americas` later.

## Latin America

| Country | Finest unit | Census | Open yr | Pop | Tier | Agency |
|---|---|---|---|---|---|---|
| **Brazil** | setor censitário | 2022 | 2022 | join (malha ⨝ Agregados on CD_SETOR) | A | IBGE |
| **Chile** | manzana-entidad | 2024 | 2024 | bundled (DB + cartography) | A/B | INE Chile |
| **Colombia** | manzana | 2018 | 2018 | bundled (MGN integrado) | A/B | DANE |
| **Argentina** | radio censal | 2022 | 2022 | join (REDATAM) | B | INDEC |
| **Ecuador** | sector censal / manzana | 2022 | 2022 | join | B | INEC |
| **Peru** | manzana | 2017 | 2017 | partial (manzana pop restricted) | B/C | INEI |
| **Uruguay** | segmento censal | 2023 | 2011 | partial (2023 geo microdata rolling out) | B/C | INE |

## Asia-Pacific

| Country | Finest unit | Census | Open yr | Pop | Tier | Agency |
|---|---|---|---|---|---|---|
| **Australia** | Mesh Block → SA1 | 2021 | 2021 | bundled (GeoPackage/DataPacks) | A | ABS |
| **New Zealand** | SA1 (meshblock counts paid) | 2023 | 2023 | join (SA1 ⨝ Aotearoa Data Explorer) | A/B | Stats NZ |
| **Japan** | chōchō-moku (small area) | 2020 | 2020 | join on KEY_CODE + API | B | e-Stat |
| **South Korea** | jipgyegu (집계구) | 2020 | 2020 | boundary + stats files + Open API | B | SGIS / KOSTAT |
| **Indonesia** | village / kelurahan | 2020 | ~2020 | weak (no clean open boundary+pop) | C | BPS |
| **Philippines** | barangay | 2020 | 2020 | partial (pop open; boundaries via HDX) | B/C | PSA |
| **India** | district / sub-district (open) | 2011 | 2011 | district-level only (2021 census delayed) | C | ORGI |
| **China** | county-level (open) | 2020 | 2020 | county only | C | NBS |

## Africa & Middle East

| Country | Finest unit | Census | Open yr | Pop | Tier | Agency |
|---|---|---|---|---|---|---|
| **South Africa** | Small Area Layer (SAL) | 2022 | 2011 (SAL) / 2022 (ward) | partial (2022 SAL+pop is CD/on-request) | B/C | Stats SA |
| Most of Sub-Saharan Africa & Middle East | enumeration area | varies | — | no open EA census; use OCHA **COD-PS** + WorldPop/GHSL | C | NSIs / HDX |

---

## Ranked shortlist to wire next (non-European)

1. **USA** — 2020 blocks; TIGER + Census API; finest granularity at scale. (A/B)
2. **Canada** — 2021 dissemination blocks; population bundled; clean direct download. (A)
3. **Brazil** — 2022 setores; nationwide shapefile + Agregados join. (A)
4. **Australia** — 2021 Mesh Blocks; GeoPackage bundles counts. (A)
5. **Chile** — 2024 manzana (newest census). (A/B)
6. **New Zealand** — 2023 SA1. (A/B)
7. **Colombia** — 2018 manzana, MGN integrado. (A/B)
8. **Argentina** — 2022 radios. (B)
9. **Japan** — 2020 small areas. (B)
10. **South Korea** — 2020 jipgyegu. (B)

The first four are **wired and verified** against their exact national totals:
**USA** 8,132,968 blocks / 331,449,281; **Brazil** 468,099 setores / 203,080,756;
**Canada** 498,547 dissemination blocks / 36,991,971; **Australia** 368,286 mesh
blocks / 25,418,422 — all in EPSG:4326. The rest are encoded as `CANDIDATES` in
the region catalogs (shown by `download-census --list`).

Ingest gotchas resolved while wiring: US `POP20` is bundled in `tabblock20`
(no join); Canada/Australia/Brazil need joins (GAF CSV / xlsx / Agregados CSV);
ABS counts are a multi-sheet xlsx with title/footer rows; IBGE zips use
**Deflate64** (system-`unzip` fallback); the IBGE CSV is latin-1 with lowercase
`v0001`. Shapefiles truncate field names to 10 chars (AU `MB_CODE21`).

## No open finest-resolution census (coarse admin / gridded fallback only)
**India** (2021 census delayed; open = district), **China** (county only),
**Russia** (admin only), and **most of Sub-Saharan Africa & the Middle East**.
For these, the standard fallback is **OCHA/HDX COD-PS** admin-unit population plus
**WorldPop/GHSL** ~100 m gridded layers (out of scope for this per-country census
pipeline, but the comparison step already uses GHSL).

## Cross-cutting notes
- **Population bundled** (in the boundary file): Canada DB, Australia Mesh Blocks,
  Colombia MGN integrado, Chile 2024. Everyone else needs a **join** on a unit key
  (GEOID / CVEGEO / CD_SETOR / KEY_CODE / radio code).
- ArcGIS Hub portals (Chile INE, some DANE/IBGE mirrors) look gated but expose
  FeatureServer/REST → Tier B automatable.
- Per-country `target_crs` is set explicitly for non-European datasets (the schema
  default EPSG:3035 is European); the comparison step handles final alignment with
  the gridded product.
