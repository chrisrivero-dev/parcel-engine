import math
from typing import Optional

from geometry.curves import compute_tangent_curve
from models.schema import LineCall, CurveCall, Handedness, CurveType


# Survey azimuths in degrees, where 0 = North and angles increase clockwise.
_CONCAVITY_AZ = {
    "NORTH": 0.0,
    "NORTHERLY": 0.0,
    "NORTHEAST": 45.0,
    "NORTHEASTERLY": 45.0,
    "EAST": 90.0,
    "EASTERLY": 90.0,
    "SOUTHEAST": 135.0,
    "SOUTHEASTERLY": 135.0,
    "SOUTH": 180.0,
    "SOUTHERLY": 180.0,
    "SOUTHWEST": 225.0,
    "SOUTHWESTERLY": 225.0,
    "WEST": 270.0,
    "WESTERLY": 270.0,
    "NORTHWEST": 315.0,
    "NORTHWESTERLY": 315.0,
}


def _resolve_handedness(
    along_feature: Optional[str],
    incoming_az_deg: float,
) -> Optional[Handedness]:
    """
    Resolve LEFT/RIGHT from a CONCAVE direction label and incoming traverse azimuth.

    Returns None when the label is missing, not a recognized concavity direction,
    or the concavity direction is collinear / anti-collinear with the incoming leg.
    """
    if not along_feature:
        return None

    upper = along_feature.upper().strip()
    if not upper.startswith("CONCAVE "):
        return None

    direction = upper[len("CONCAVE "):].strip()
    concavity_az = _CONCAVITY_AZ.get(direction)
    if concavity_az is None:
        return None

    diff = (concavity_az - incoming_az_deg) % 360.0

    if diff < 1e-9 or abs(diff - 180.0) < 1e-9 or abs(diff - 360.0) < 1e-9:
        return None

    return Handedness.RIGHT if diff < 180.0 else Handedness.LEFT


def dms_to_degrees(dms):
    return (
        float(dms.deg)
        + float(dms.minutes) / 60.0
        + float(dms.seconds) / 3600.0
    )


def bearing_to_azimuth(bearing):
    """
    Convert a Bearing object to azimuth in decimal DEGREES (0 = North, clockwise).

    Handles all three structured bearing types:

    1. AzimuthBearing  (bearing.value has .azimuth DMS)
       Cardinals parsed as AzimuthBearing land here automatically:
         EAST  → DMS(90,0,0)  → 90°
         WEST  → DMS(270,0,0) → 270°
         NORTH → DMS(0,0,0)   → 0°
         SOUTH → DMS(180,0,0) → 180°

    2. QuadrantBearing (bearing.value has .quadrant_ns / .angle / .quadrant_ew)
       Quadrant rules:
         N θ E →        θ
         S θ E →  180 − θ
         S θ W →  180 + θ
         N θ W →  360 − θ

    3. Anything else → raises ValueError with diagnostic info.

    Callers must convert to radians before passing to math.sin / math.cos:
        az_rad = math.radians(bearing_to_azimuth(b))
    """
    v = bearing.value

    # ── AzimuthBearing ── (includes cardinal directions)
    if hasattr(v, "azimuth"):
        return dms_to_degrees(v.azimuth)

    # ── QuadrantBearing ──
    if hasattr(v, "quadrant_ns") and hasattr(v, "quadrant_ew") and hasattr(v, "angle"):
        theta = dms_to_degrees(v.angle)
        ns = v.quadrant_ns.upper()
        ew = v.quadrant_ew.upper()
        if   ns == "N" and ew == "E": return theta
        elif ns == "S" and ew == "E": return 180.0 - theta
        elif ns == "S" and ew == "W": return 180.0 + theta
        else:                         return 360.0 - theta  # N θ W

    raise ValueError(
        f"Unsupported bearing value type: {type(v).__name__!r} "
        f"on Bearing(raw_text={bearing.raw_text!r}, format={bearing.format!r})"
    )


def build_geometry(*, start_point=(0.0, 0.0), calls):
    start_x, start_y = start_point

    points = [(start_x, start_y)]
    curves: list = []

    current_x = start_x
    current_y = start_y
    current_azimuth_rad = 0.0  # radians, used internally for curve tangent tracking

    for call in calls:

        # =============================
        # LINE
        # =============================
        if isinstance(call, LineCall):
            az_deg = bearing_to_azimuth(call.bearing)
            az_rad = math.radians(az_deg)
            dist = call.distance.value

            current_azimuth_rad = az_rad

            dx = dist * math.sin(az_rad)
            dy = dist * math.cos(az_rad)

            current_x += dx
            current_y += dy

            points.append((current_x, current_y))

        # =============================
        # CURVE
        # =============================
        elif isinstance(call, CurveCall):
            params = call.params

            if params.radius is None:
                continue
            if params.delta is None and params.arc_length is None:
                continue

            incoming_az_deg = math.degrees(current_azimuth_rad)
            start_pt = (current_x, current_y)

            if params.handedness is not None:
                handedness = params.handedness
                handedness_source = "explicit"
            else:
                handedness = _resolve_handedness(call.along_feature, incoming_az_deg)
                handedness_source = "resolved_from_concavity" if handedness is not None else None
            if handedness is None:
                continue

            if params.delta is not None:
                delta_deg = dms_to_degrees(params.delta)
            else:
                delta_deg = (params.arc_length / params.radius) * (180.0 / math.pi)

            tangent_params = params.model_copy(
                update={"curve_type": CurveType.TANGENT, "handedness": handedness}
            )
            segments = max(12, int(abs(delta_deg)))

            try:
                end_pt, arc_pts = compute_tangent_curve(
                    (current_x, current_y),
                    incoming_az_deg,
                    tangent_params,
                    segments_per_curve=segments,
                )
            except ValueError:
                continue

            points.extend(arc_pts)
            current_x, current_y = end_pt

            sign_az = 1.0 if handedness == Handedness.RIGHT else -1.0
            current_azimuth_rad = math.radians(
                incoming_az_deg + sign_az * delta_deg
            ) % (2 * math.pi)

            curves.append({
                "call_id": call.id,
                "raw_text": call.raw_text,
                "radius": params.radius,
                "delta_deg": delta_deg,
                "arc_length": params.arc_length,
                "handedness": handedness.value,
                "handedness_source": handedness_source,
                "along_feature": call.along_feature,
                "start_point": start_pt,
                "end_point": end_pt,
            })

    return {
        "points": points,
        "curves": curves,
        "validation": {
            "closure": {
                "misclosure": math.hypot(
                    points[-1][0] - points[0][0],
                    points[-1][1] - points[0][1],
                )
            },
            "intersections": [],
            "curve_errors": [],
        },
    }
