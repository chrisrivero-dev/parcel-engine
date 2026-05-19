# FILE: parcel_engine/geometry/curves.py
# PURPOSE: Deterministic curve geometry (tangent + non-tangent)
#
# CONVENTIONS:
# - Coordinates are Cartesian (x, y)
# - Azimuth convention (survey): 0°=North, 90°=East (clockwise)
# - For curve point generation we use math angles from +X axis (CCW) internally.
#
# HARD RULES:
# - No inference of curve parameters.
# - Tangent curves require a known incoming tangent azimuth (prior line/curve tangent).
# - Non-tangent curves require explicit anchor(s). If insufficient, raise NON_TANGENT_AMBIGUITY.
#
# OUTPUT:
# - compute_* functions return (end_point, sampled_points)
#   where sampled_points includes points along the arc (excluding the start, including the end).

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from models.errors import ErrorCode
from models.schema import (
    CurveParams,
    CurveType,
    Handedness,
    DirectionBasis,
)
from geometry.bearings import bearing_to_azimuth_degrees


Point = Tuple[float, float]


# ============================================================
# Helpers
# ============================================================

def _unit_from_azimuth(azimuth_deg: float) -> Tuple[float, float]:
    """
    Azimuth (survey): 0°=North, 90°=East
    Convert to unit direction vector in (x, y).
    """
    r = math.radians(azimuth_deg)
    dx = math.sin(r)
    dy = math.cos(r)
    return dx, dy

def _left_normal(dx, dy):
    return (-dy, dx)

def _right_normal(dx, dy):
    return (dy, -dx)




def _distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _normalize_angle_rad(theta: float) -> float:
    """
    Normalize angle to [-pi, pi) not strictly required; kept for stability.
    """
    while theta >= math.pi:
        theta -= 2.0 * math.pi
    while theta < -math.pi:
        theta += 2.0 * math.pi
    return theta


def _derive_delta_radians(params: CurveParams) -> float:
    """
    Deterministically derive delta (radians) from provided params.
    Allowed deterministic inputs:
    - delta (DMS)
    - arc_length + radius
    - chord_length + radius

    Raises CURVE_INCOMPLETE if no derivation possible.
    """
    if params.delta is not None:
        deg = (params.delta.deg + params.delta.minutes / 60.0 + params.delta.seconds / 3600.0)
        if deg <= 0.0:
            raise ValueError(f"{ErrorCode.CURVE_INCOMPLETE}: Delta must be > 0")
        return math.radians(deg)

    if params.arc_length is not None and params.radius is not None:
        if params.arc_length <= 0 or params.radius <= 0:
            raise ValueError(f"{ErrorCode.CURVE_INCOMPLETE}: arc_length and radius must be > 0")
        return params.arc_length / params.radius  # radians = s / r

    if params.chord_length is not None and params.radius is not None:
        if params.chord_length <= 0 or params.radius <= 0:
            raise ValueError(f"{ErrorCode.CURVE_INCOMPLETE}: chord_length and radius must be > 0")
        # delta = 2*asin(c/(2r))
        ratio = params.chord_length / (2.0 * params.radius)
        if ratio <= 0.0 or ratio > 1.0:
            raise ValueError(f"{ErrorCode.CURVE_PARAM_MISMATCH}: chord_length incompatible with radius")
        return 2.0 * math.asin(ratio)

    raise ValueError(f"{ErrorCode.CURVE_INCOMPLETE}: Cannot derive delta (need delta or arc_length+radius or chord_length+radius)")


def _require_radius(params: CurveParams) -> float:
    if params.radius is None or params.radius <= 0:
        raise ValueError(f"{ErrorCode.CURVE_INCOMPLETE}: radius is required and must be > 0")
    return float(params.radius)


def _require_handedness(params: CurveParams) -> Handedness:
    if params.handedness is None:
        raise ValueError(f"{ErrorCode.CURVE_INCOMPLETE}: handedness is required (left/right)")
    return params.handedness


def _sample_arc_points(
    center: Point,
    start_pt: Point,
    delta_rad: float,
    handedness: Handedness,
    segments: int,
) -> List[Point]:
    """
    Sample points along the arc from start_pt by sweeping delta_rad.
    - Left: CCW sweep in math-angle space
    - Right: CW sweep in math-angle space

    Returns points excluding the start_pt and including the end_pt.
    """
    if segments < 2:
        segments = 2

    cx, cy = center
    sx, sy = start_pt

    start_ang = math.atan2(sy - cy, sx - cx)
    sign = 1.0 if handedness == Handedness.LEFT else -1.0



    pts: List[Point] = []
    for i in range(1, segments + 1):
        t = i / segments
        ang = start_ang + sign * delta_rad * t
        x = cx + math.cos(ang) * _distance(center, start_pt)
        y = cy + math.sin(ang) * _distance(center, start_pt)
        pts.append((x, y))

    return pts


# ============================================================
# Tangent curve
# ============================================================

def compute_tangent_curve(
    start: Point,
    incoming_tangent_azimuth_deg: float,
    params: CurveParams,
    *,
    segments_per_curve: int = 64,
) -> Tuple[Point, List[Point]]:
    """
    Compute a tangent circular arc beginning at `start` (PC).
    Requires:
      - incoming_tangent_azimuth_deg (deterministic; from prior line/curve)
      - params.radius
      - params.handedness
      - delta derivable (delta OR arc_length+radius OR chord_length+radius)

    Returns:
      (end_point, sampled_points_along_arc)
    """
    if params.curve_type != CurveType.TANGENT:
        raise ValueError(f"{ErrorCode.UNKNOWN_ELEMENT}: compute_tangent_curve called with non-tangent params")

    radius = _require_radius(params)
    handedness = _require_handedness(params)
    delta_rad = _derive_delta_radians(params)

    dx, dy = _unit_from_azimuth(incoming_tangent_azimuth_deg)

    if handedness == Handedness.LEFT:
        nx, ny = _left_normal(dx, dy)
    else:
        nx, ny = _right_normal(dx, dy)

    # Center is offset from PC by radius in the normal direction
    cx = start[0] + nx * radius
    cy = start[1] + ny * radius
    center = (cx, cy)

    arc_points = _sample_arc_points(center, start, delta_rad, handedness, segments_per_curve)
    end_pt = arc_points[-1]

    return end_pt, arc_points


# ============================================================
# Non-tangent curve (STRICT: no inference)
# ============================================================

def compute_non_tangent_curve(
    start: Point,
    params: CurveParams,
    *,
    target_basis: DirectionBasis = DirectionBasis.TRUE,
    basis_rotation_deg: Optional[float] = None,
    segments_per_curve: int = 64,
) -> Tuple[Point, List[Point]]:
    """
    Compute a non-tangent curve beginning at `start` (PC), ONLY when explicit anchors exist.

    Supported deterministic anchor set (minimum):
      - radius
      - handedness
      - delta derivable
      - radial_bearing_to_pc provided (bearing from CENTER -> PC)

    If the above is not present, raise NON_TANGENT_AMBIGUITY (hard stop).
    No fallback assumptions (no "assume tangent", no "assume chord bearing", etc).
    """
    if params.curve_type != CurveType.NON_TANGENT:
        raise ValueError(f"{ErrorCode.UNKNOWN_ELEMENT}: compute_non_tangent_curve called with tangent params")

    # Enforce minimum anchors
    radius = _require_radius(params)
    handedness = _require_handedness(params)
    delta_rad = _derive_delta_radians(params)

    if params.radial_bearing_to_pc is None:
        raise ValueError(
            f"{ErrorCode.NON_TANGENT_AMBIGUITY}: Missing radial_bearing_to_pc (CENTER -> PC). "
            "Non-tangent curve cannot be computed deterministically."
        )

    # Convert radial bearing to azimuth
    radial_az_center_to_pc = bearing_to_azimuth_degrees(
        params.radial_bearing_to_pc,
        target_basis=target_basis,
        basis_rotation_deg=basis_rotation_deg,
    )

    # We need vector from PC to center, which is opposite of CENTER->PC
    radial_az_pc_to_center = (radial_az_center_to_pc + 180.0) % 360.0
    ux, uy = _unit_from_azimuth(radial_az_pc_to_center)

    # Center coordinate
    center = (start[0] + ux * radius, start[1] + uy * radius)

    # Now we can sweep the arc from PC around center by delta.
    arc_points = _sample_arc_points(center, start, delta_rad, handedness, segments_per_curve)
    end_pt = arc_points[-1]

    return end_pt, arc_points


# ============================================================
# Dispatcher (builder will use this)
# ============================================================

def compute_curve(
    start: Point,
    params: CurveParams,
    *,
    incoming_tangent_azimuth_deg: Optional[float] = None,
    target_basis: DirectionBasis = DirectionBasis.TRUE,
    basis_rotation_deg: Optional[float] = None,
    segments_per_curve: int = 64,
) -> Tuple[Point, List[Point]]:
    """
    Deterministic dispatcher for curves.

    - Tangent curves require incoming_tangent_azimuth_deg (hard required)
    - Non-tangent curves require explicit anchors (see compute_non_tangent_curve)

    Returns:
      (end_point, sampled_points)
    """
    if params.curve_type == CurveType.TANGENT:
        if incoming_tangent_azimuth_deg is None:
            raise ValueError(
                f"{ErrorCode.NEEDS_REFERENCE_GEOMETRY}: Tangent curve requires incoming_tangent_azimuth_deg"
            )
        return compute_tangent_curve(
            start,
            incoming_tangent_azimuth_deg,
            params,
            segments_per_curve=segments_per_curve,
        )

    if params.curve_type == CurveType.NON_TANGENT:
        return compute_non_tangent_curve(
            start,
            params,
            target_basis=target_basis,
            basis_rotation_deg=basis_rotation_deg,
            segments_per_curve=segments_per_curve,
        )

    raise ValueError(f"{ErrorCode.UNKNOWN_ELEMENT}: Unknown curve_type: {params.curve_type}")
