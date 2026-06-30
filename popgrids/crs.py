"""Coordinate reference system constants and reprojection helpers.

All European outputs are normalised to EPSG:3035 (ETRS89-LAEA Europe), the
official INSPIRE/GEOSTAT equal-area CRS, so that cross-country layers, the 1 km
baseline grid and any area-weighted clipping stay correct without per-dataset
special-casing. The native source CRS is preserved in the provenance record.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyproj import CRS

if TYPE_CHECKING:
    import geopandas as gpd

#: Official INSPIRE / GEOSTAT equal-area CRS for Europe.
CRS_LAEA_EUROPE = "EPSG:3035"
#: Geographic CRS (lon/lat).
CRS_WGS84 = "EPSG:4326"
#: GHSL native CRS (World Mollweide). Reconciliation is deferred to the
#: comparison step; it appears here only for documentation/selection.
CRS_MOLLWEIDE = "ESRI:54009"


def reproject(gdf: gpd.GeoDataFrame, target_crs: str) -> gpd.GeoDataFrame:
    """Return ``gdf`` reprojected to ``target_crs`` (no-op when already there)."""
    if gdf.crs is None:
        msg = "GeoDataFrame has no CRS; cannot reproject."
        raise ValueError(msg)
    target = CRS.from_user_input(target_crs)
    if gdf.crs.equals(target):
        return gdf
    return gdf.to_crs(target)


def to_3035(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reproject ``gdf`` to the standard European output CRS (EPSG:3035)."""
    return reproject(gdf, CRS_LAEA_EUROPE)
