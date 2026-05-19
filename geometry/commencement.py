# FILE: parcel_engine/geometry/commencement.py
# PURPOSE: Deterministically execute commencement calls (monument -> POB).
#
# RULES:
# - Commencement geometry is NOT part of the parcel boundary area.
# - This module only computes the POB and returns the commencement path for audit.
# - No guessing: missing monument coordinates or missing bearing/distance is a hard failure.
#
# INPUT:
# - start_point: known (x, y) for a monument or reference point
# - calls: ordered CommencementCall list
#
# OUTPUT:
# - (pob_point, path_points) where path_points includes the start and each subsequent vertex.

from __future__ import annotations

from typing import List, Optional, Tuple

from parcel_engine.models.errors import ErrorCode
from parcel_engine.models.schema import CommencementCall, DirectionBasis
from parcel_engine.geometry.bearings import bearing_to_azimuth_degrees
from parcel_engine.geometry.lines import compute_line


Point = Tuple[float, float]


def apply_commencement(
    start_point: Point,
    calls: List[CommencementCall],
    *,
    target_basis: DirectionBasis = DirectionBasis.TRUE,
    basis_rotation_deg: Optional[float] = None,
) -> Tuple[Point, List[Point]]:
    """
    Execute commencement calls in order starting from `start_point`.

    Hard failures:
    - If a call is missing bearing or distance (or distance.value), cannot proceed.
    - If bearing format is UNKNOWN or basis mismatch without rotation, cannot proceed.

    Returns:
    - pob: final point after all commencement calls
    - path: [start_point, p1, p2, ... pob]
    """
    if start_point is None:
        raise ValueError(f"{ErrorCode.NEEDS_REFERENCE_GEOMETRY}: start_point is required for commencement")

    current: Point = start_point
    path: List[Point] = [start_point]

    for call in calls:
        if call.bearing is None:
            raise ValueError(
                f"{ErrorCode.COMMENCEMENT_GAP}: Missing bearing on commencement call '{call.id}'"
            )
        if call.distance is None:
            raise ValueError(
                f"{ErrorCode.MISSING_DISTANCE}: Missing distance on commencement call '{call.id}'"
            )
        if call.distance.value is None:
            raise ValueError(
                f"{ErrorCode.MISSING_DISTANCE}: Distance value missing on commencement call '{call.id}'"
            )

        az = bearing_to_azimuth_degrees(
            call.bearing,
            target_basis=target_basis,
            basis_rotation_deg=basis_rotation_deg,
        )

        next_pt = compute_line(current, az, float(call.distance.value))
        current = next_pt
        path.append(current)

    pob = current
    return pob, path
