"""Map any adapter-loaded GeoDataFrame onto the common output schema.

Every European output GeoParquet carries exactly :data:`OUTPUT_COLUMNS`, in
EPSG:3035, regardless of the source country or access tier.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from popgrids.crs import reproject

if TYPE_CHECKING:
    from collections.abc import Sequence

    from popgrids.schema import CountryDataset, GeometryAccess

#: INSPIRE grid id, e.g. ``CRS3035RES1000mN2683000E4285000`` -> (res, north, east)
#: of the cell's lower-left corner.
_INSPIRE_GRID_ID = re.compile(r"RES(\d+)mN(\d+)E(\d+)")

#: The exact column contract of every European output (geometry last).
OUTPUT_COLUMNS: tuple[str, ...] = (
    "pop",
    "unit_id",
    "country",
    "source",
    "vintage",
    "level",
    "geometry",
)
_HALF = 2.0


def require_columns(
    frame: pd.DataFrame,
    columns: Sequence[str],
    *,
    context: str,
) -> None:
    """Raise a loud, descriptive error if any expected column is missing."""
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        available = ", ".join(map(str, frame.columns))
        msg = (
            f"{context}: missing expected column(s) {missing}. "
            f"Available columns: {available}"
        )
        raise KeyError(msg)


def build_cell_polygons(
    frame: pd.DataFrame,
    geometry: GeometryAccess,
) -> gpd.GeoDataFrame:
    """Build square grid-cell polygons from a tabular CSV grid.

    Supports ``grid_csv_center`` (x/y are cell mid-points) and
    ``grid_csv_lower_left`` (x/y are the lower-left corner).
    """
    if (
        geometry.x_field is None
        or geometry.y_field is None
        or geometry.cell_size_m is None
    ):
        msg = "CSV grid geometry requires x_field, y_field and cell_size_m."
        raise ValueError(msg)
    require_columns(
        frame,
        [geometry.x_field, geometry.y_field],
        context="build_cell_polygons",
    )
    size = float(geometry.cell_size_m)
    x = pd.to_numeric(frame[geometry.x_field], errors="coerce").to_numpy(
        dtype="float64"
    )
    y = pd.to_numeric(frame[geometry.y_field], errors="coerce").to_numpy(
        dtype="float64"
    )
    if geometry.geometry_kind == "grid_csv_center":
        x_min, y_min = x - size / _HALF, y - size / _HALF
    else:
        x_min, y_min = x, y
    boxes = shapely.box(x_min, y_min, x_min + size, y_min + size)
    return gpd.GeoDataFrame(frame, geometry=boxes, crs=geometry.source_crs)


def build_cells_from_inspire_id(
    frame: pd.DataFrame,
    id_field: str,
    crs: str,
) -> gpd.GeoDataFrame:
    """Build square grid-cell polygons by parsing the INSPIRE ``GRD_ID``.

    The id encodes the cell resolution and the lower-left corner (LAEA), e.g.
    ``CRS3035RES1000mN2683000E4285000`` -> a 1000 m cell at (E=4285000,
    N=2683000).
    """
    require_columns(frame, [id_field], context="build_cells_from_inspire_id")
    parts = frame[id_field].astype("string").str.extract(_INSPIRE_GRID_ID)
    if parts.isna().to_numpy().any():
        msg = f"Unparseable INSPIRE grid id(s) in column {id_field!r}."
        raise ValueError(msg)
    size = pd.to_numeric(parts[0]).to_numpy(dtype="float64")
    north = pd.to_numeric(parts[1]).to_numpy(dtype="float64")
    east = pd.to_numeric(parts[2]).to_numpy(dtype="float64")
    boxes = shapely.box(east, north, east + size, north + size)
    return gpd.GeoDataFrame(frame, geometry=boxes, crs=crs)


def standardize(
    gdf: gpd.GeoDataFrame,
    dataset: CountryDataset,
) -> gpd.GeoDataFrame:
    """Rename/augment ``gdf`` to :data:`OUTPUT_COLUMNS`, reproject to target_crs."""
    pop_attr = dataset.population.attr
    unit_field = dataset.geometry.unit_id_field
    require_columns(
        gdf, [pop_attr, unit_field], context=f"standardize[{dataset.dataset_id}]"
    )

    result = gdf.copy()
    pop = pd.to_numeric(result[pop_attr], errors="coerce").astype("float64")
    # Population is non-negative; negatives are SDC sentinels (e.g. CBS -99997)
    # for suppressed cells -> treat as missing.
    result["pop"] = pop.where(pop >= 0)
    result["unit_id"] = result[unit_field].astype("string")
    result["country"] = dataset.country
    result["source"] = dataset.dataset_id
    result["vintage"] = np.full(len(result), dataset.vintage, dtype=np.int16)
    result["level"] = dataset.unit_code
    result["country"] = result["country"].astype("string")
    result["source"] = result["source"].astype("string")
    result["level"] = result["level"].astype("string")

    result = reproject(result, dataset.target_crs)
    return result[list(OUTPUT_COLUMNS)]
