# FILE: parcel_engine/geometry/bearings.py
# PURPOSE: Deterministic bearing parsing + conversion to azimuth (degrees)
# NOTES:
# - Azimuth convention: 0° = North, 90° = East, 180° = South, 270° = West
# - Quadrant bearing: N/S <angle> E/W
# - Basis rotation: optional (caller supplies rotation degrees; this file does not infer it)
# - No heuristics; invalid formats raise with ErrorCode.BAD_BEARING_FORMAT

from __future__ import annotations

from math import fmod
from typing import Optional

from models.errors import ErrorCode
from models.schema import (
    Bearing,
    BearingFormat,
    QuadrantBearing,
    AzimuthBearing,
    DirectionBasis,
)



def dms_to_degrees(dms: DMS) -> float:
    """
    Convert DMS to decimal degrees.
    Assumes DMS already validated by schema.
    """
    return float(dms.deg) + (float(dms.minutes) / 60.0) + (float(dms.seconds) / 3600.0)


def normalize_azimuth(deg: float) -> float:
    """
    Normalize to [0, 360).
    """
    # fmod can return negative; normalize carefully
    v = fmod(deg, 360.0)
    if v < 0:
        v += 360.0
    # Snap 360 -> 0
    if abs(v - 360.0) < 1e-12:
        return 0.0
    return v


def quadrant_to_azimuth(q: QuadrantBearing) -> float:
    """
    Convert quadrant bearing to azimuth degrees (0–360).
      N θ E => θ
      N θ W => 360-θ
      S θ E => 180-θ
      S θ W => 180+θ
    """
    theta = dms_to_degrees(q.angle)

    # Angle must be [0, 90] for a quadrant bearing
    if theta < 0.0 or theta > 90.0:
        raise ValueError(f"{ErrorCode.BAD_BEARING_FORMAT}: Quadrant angle out of range: {theta}")

    ns = q.quadrant_ns
    ew = q.quadrant_ew

    if ns == "N" and ew == "E":
        return normalize_azimuth(theta)
    if ns == "N" and ew == "W":
        return normalize_azimuth(360.0 - theta)
    if ns == "S" and ew == "E":
        return normalize_azimuth(180.0 - theta)
    if ns == "S" and ew == "W":
        return normalize_azimuth(180.0 + theta)

    # Should be unreachable due to schema literals
    raise ValueError(f"{ErrorCode.BAD_BEARING_FORMAT}: Invalid quadrant components: {ns} {ew}")


def azimuth_value_to_azimuth(a: AzimuthBearing) -> float:
    """
    Convert azimuth DMS to decimal degrees and normalize.
    """
    deg = dms_to_degrees(a.azimuth)
    # Azimuth can be 0–360 (schema allows up to 360); normalize handles 360 -> 0
    if deg < 0.0 or deg > 360.0:
        raise ValueError(f"{ErrorCode.BAD_BEARING_FORMAT}: Azimuth out of range: {deg}")
    return normalize_azimuth(deg)


def apply_basis_rotation(azimuth_deg: float, rotation_deg: float) -> float:
    """
    Apply a deterministic basis rotation.
    Positive rotation rotates azimuth clockwise (adds degrees).

    Example use:
      - Convert GRID to TRUE: rotation_deg = grid_to_true_rotation
      - Convert RECORD to TRUE: rotation_deg = record_to_true_rotation

    This function does not infer rotation; caller must supply it.
    """
    return normalize_azimuth(azimuth_deg + rotation_deg)


def bearing_to_azimuth_degrees(
    bearing: Bearing,
    *,
    target_basis: DirectionBasis = DirectionBasis.TRUE,
    basis_rotation_deg: Optional[float] = None,
) -> float:
    """
    Convert a Bearing model into azimuth degrees in the requested target_basis.

    Rules:
    - If bearing.format is UNKNOWN, hard fail.
    - If bearing.value missing when format known, schema should have already failed;
      still defend here.
    - If target_basis != bearing.basis, caller MUST supply basis_rotation_deg.
      No guessing allowed.
    """
    if bearing.format == BearingFormat.UNKNOWN:
        raise ValueError(f"{ErrorCode.BAD_BEARING_FORMAT}: Bearing format UNKNOWN: '{bearing.raw_text}'")

    if bearing.value is None:
        raise ValueError(f"{ErrorCode.BAD_BEARING_FORMAT}: Bearing value missing: '{bearing.raw_text}'")

    if bearing.format == BearingFormat.QUADRANT:
        if not isinstance(bearing.value, QuadrantBearing):
            raise ValueError(f"{ErrorCode.BAD_BEARING_FORMAT}: Expected QuadrantBearing: '{bearing.raw_text}'")
        az = quadrant_to_azimuth(bearing.value)
    elif bearing.format == BearingFormat.AZIMUTH:
        if not isinstance(bearing.value, AzimuthBearing):
            raise ValueError(f"{ErrorCode.BAD_BEARING_FORMAT}: Expected AzimuthBearing: '{bearing.raw_text}'")
        az = azimuth_value_to_azimuth(bearing.value)
    else:
        raise ValueError(f"{ErrorCode.BAD_BEARING_FORMAT}: Unsupported bearing format: {bearing.format}")

    # Basis handling (deterministic; no inference)
    if bearing.basis != target_basis:
        if basis_rotation_deg is None:
            raise ValueError(
                f"{ErrorCode.BAD_BEARING_FORMAT}: Basis mismatch ({bearing.basis} -> {target_basis}) "
                f"requires basis_rotation_deg"
            )
        az = apply_basis_rotation(az, basis_rotation_deg)

    return az
