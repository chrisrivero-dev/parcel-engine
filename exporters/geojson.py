# FILE: parcel_engine/exporters/geojson.py
# PURPOSE: Export parcel geometry to GeoJSON (truth-only; no geometry changes)
#
# RULES:
# - Outputs a FeatureCollection
# - Boundary exported as Polygon if closed, otherwise LineString
# - Commencement path exported as LineString (optional)
# - Coordinates are emitted as-is (x, y) -> (lon, lat style ordering assumed by consumer)
# - No CRS transformation here

from __future__ import annotations

from typing import Any, Dict, List, Tuple, Optional

Point = Tuple[float, float]


def _is_closed(points: List[Point]) -> bool:
    return len(points) >= 2 and points[0] == points[-1]


def _coords(points: List[Point]) -> List[List[float]]:
    # GeoJSON expects [x, y] arrays
    return [[float(x), float(y)] for x, y in points]


def export_geojson(
    *,
    boundary_points: List[Point],
    commencement_path: Optional[List[Point]] = None,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Export geometry to a GeoJSON FeatureCollection.

    Parameters:
    - boundary_points: ordered boundary vertices (POB first)
    - commencement_path: optional path from monument to POB
    - properties: optional properties to attach to boundary feature

    Returns:
    - GeoJSON FeatureCollection (dict)
    """
    features: List[Dict[str, Any]] = []
    props = properties or {}

    # ----------------------------
    # Boundary feature
    # ----------------------------
    if _is_closed(boundary_points):
        geometry = {
            "type": "Polygon",
            "coordinates": [
                _coords(boundary_points)
            ],
        }
    else:
        geometry = {
            "type": "LineString",
            "coordinates": _coords(boundary_points),
        }

    features.append({
        "type": "Feature",
        "properties": props,
        "geometry": geometry,
    })

    # ----------------------------
    # Commencement path (optional)
    # ----------------------------
    if commencement_path and len(commencement_path) >= 2:
        features.append({
            "type": "Feature",
            "properties": {
                "type": "commencement_path"
            },
            "geometry": {
                "type": "LineString",
                "coordinates": _coords(commencement_path),
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
