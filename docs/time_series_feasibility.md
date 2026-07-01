# Time-series feasibility (design note)

Can this pipeline support **temporal** census-vs-grid analysis? This note records
what is feasible and how the catalog represents it. The catalog is already
**vintage-aware**: each `CountryDataset` carries a `vintage` (year), so a country
can have several entries differing by year (e.g. `DE_grid100m_2011` +
`DE_grid100m_2022`); `popgrids.registry.vintages_for(country, level)` lists them,
and `download-census --vintage 2011` selects one. **No multi-year data is bulk
-downloaded yet** — this is a design/feasibility note.

## 1. Global gridded products (cell-level over decades)

| Product | Years | Grid stable? | Note |
|---|---|---|---|
| **GHSL GHS-POP R2023A** | 1975–2030, 5-yr (+2025/30 proj.) | yes (fixed Mollweide) | **best** long-run; explicitly multitemporal |
| **WorldPop unconstrained** | annual 2000–2020 | yes (fixed WGS84) | usable smooth annual series (modelled) |
| **GPW v4.11** | 2000, 2005, 2010, 2015, 2020 | yes | **weak** — 5 epochs interpolated from one census round |
| **LandScan** | annual ~2000–2023 | grid fixed, but **do not** trend | ambient pop + yearly method changes (ORNL caution) |

All are **modelled** disaggregations, so cell-level change conflates real change
with model/input change. GHSL is already used by the repo (`differences.ipynb`).

## 2. Enumerated census rounds on the stable 1 km INSPIRE grid (Europe)

**The strongest census time series.** The Eurostat **GEOSTAT 1 km grid net
(ETRS89-LAEA) is identical across 2006 / 2011 / 2021**, so cells compare directly:

- **2011 ↔ 2021** is robust (both enumerated/register-based on the common grid).
- **2006** is weaker (largely modelled/hybrid; method shift 2006→2011).

National 1 km census grids reinforce this at finer resolution: **Germany Zensus
2011 + 2022** (100 m, same INSPIRE grid), **Poland NSP 2011 + 2021** (1 km),
Portugal/Spain 1 km for 2021. Wiring a prior round = adding a catalog entry, e.g.
`DE_grid100m_2011`, `PL_grid1km_2011`, plus the `EU_geostat_grid1km_2011`
baseline.

## 3. Per-country annual register grids (strongest enumerated annual series)

Register-based countries reuse the **same grid every year** → genuine annual
cell-level trends (not modelled):

- **Switzerland STATPOP** — hectare (100 m), annual since 2010.
- **Norway SSB** — 250 m / 1 km, annual since 2001.
- **Sweden SCB** — 1 km, annual.
- **Netherlands CBS** — 100 m, near-annual.

## 4. Pitfalls (record in any temporal analysis)

1. **Redrawn units** — Spain *secciones*, Italy *sezioni* (403k→756k 2011→2021),
   UK Output Areas, France IRIS are redrawn between rounds; naive year-on-year
   joins break. Use **grids** or official **correspondence/best-fit lookups**.
2. **Method/input changes** — LandScan (cautioned), WorldPop/GHSL ancillary layers
   evolve, GEOSTAT 2006 vs 2011 differ.
3. **Modelled vs enumerated** — global grids are modelled (cell change ≠ observed);
   census/register grids are enumerated but apply small-cell suppression/imputation
   (notably France Filosofi, CBS).
4. **Concept mismatches** — LandScan = *ambient* (24-h) population; France Filosofi
   = *fiscal households/income*, not a headcount. Don't mix with residential counts.
5. **GPW v4** epochs are extrapolated from a single census round — not independent
   annual observations.

## Recommendation

For a defensible European census time series, anchor on **(2) the 1 km INSPIRE
grid 2011↔2021**, supplement long-run context with **(1) GHSL**, and use **(3)
CH/NO/SE/NL register grids** where annual cell-level resolution is needed. Adding
a historical vintage is just a catalog entry; the engine already handles it.
