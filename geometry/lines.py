# FILE: parcel_engine/geometry/lines.py
# PURPOSE: Deterministic straight-line segment computation
# NOTES:
# - Coordinate system is Cartesian (x, y)
# - Azimuth convention: 0° = North, 90° = East
# - Distance units already resolved upstream (no unit conversion here)
# - No snapping, no closure logic, no assumptions

from __future__ import annotations

import math
from typing import Tuple


Point = Tuple[float, float]


def azimuth_to_unit_vector(azimuth_deg: float) -> Tuple[float, float]:
    """
    Convert azimuth (degrees) to a unit direction vector.

    Azimuth reference:
      0°   = North  = (0, +1)
      90°  = East   = (+1, 0)
      180° = South  = (0, -1)
      270° = West   = (-1, 0)
    """
    # Convert azimuth to radians measured clockwise from North
    radians = math.radians(azimuth_deg)

    dx = math.sin(radians)
    dy = math.cos(radians)

    return dx, dy


def compute_line(
    start: Point,
    azimuth_deg: float,
    distance: float,
) -> Point:
    """
    Compute the endpoint of a straight-line segment.

    Parameters:
    - start: (x, y)
    - azimuth_deg: bearing already converted to azimuth degrees
    - distance: linear distance (> 0)

    Returns:
    - end point (x, y)
    """
    if distance <= 0:
        raise ValueError("Distance must be positive for line computation")

    dx_unit, dy_unit = azimuth_to_unit_vector(azimuth_deg)

    end_x = start[0] + dx_unit * distance
    end_y = start[1] + dy_unit * distance

    return (end_x, end_y)
