import math

from geometry.curves import compute_tangent_curve
from models.schema import LineCall, CurveCall, Handedness, CurveType

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

            # Render only when the curve direction is explicit. Concavity alone
            # cannot resolve left/right without the incoming traverse direction,
            # so such curves are left unrendered (no fabricated geometry).
            if params.handedness is None:
                continue
            if params.radius is None:
                continue
            if params.delta is None and params.arc_length is None:
                continue

            if params.delta is not None:
                delta_deg = dms_to_degrees(params.delta)
            else:
                delta_deg = (params.arc_length / params.radius) * (180.0 / math.pi)

            incoming_az_deg = math.degrees(current_azimuth_rad)

            # The traverse supplies the incoming tangent, so render as a tangent
            # arc using the deterministic, tested curve solver.
            tangent_params = params.model_copy(update={"curve_type": CurveType.TANGENT})
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

            # RIGHT turns increase azimuth clockwise; LEFT turns decrease it.
            sign_az = 1.0 if params.handedness == Handedness.RIGHT else -1.0
            current_azimuth_rad = math.radians(
                incoming_az_deg + sign_az * delta_deg
            ) % (2 * math.pi)

            curves.append({
                "radius": params.radius,
                "delta_deg": delta_deg,
                "handedness": params.handedness.value,
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
