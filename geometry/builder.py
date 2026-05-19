import math

from models.schema import LineCall, CurveCall, Handedness

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
            radius = params.radius

            # --- delta ---
            if params.delta is not None:
                delta_deg = dms_to_degrees(params.delta)
            elif params.arc_length is not None:
                delta_deg = (params.arc_length / radius) * (180 / math.pi)
            else:
                continue

            delta_rad = math.radians(delta_deg)

            # RIGHT = clockwise
            sign = -1 if params.handedness == Handedness.RIGHT else 1

            # --- center ---
            cx = current_x + radius * math.cos(current_azimuth_rad + sign * math.pi / 2)
            cy = current_y + radius * math.sin(current_azimuth_rad + sign * math.pi / 2)

            # --- start angle ---
            start_angle = math.atan2(current_y - cy, current_x - cx)

            # --- arc points ---
            steps = max(12, int(abs(delta_deg)))

            for i in range(1, steps + 1):
                angle = start_angle + sign * (delta_rad * i / steps)
                points.append((
                    cx + radius * math.cos(angle),
                    cy + radius * math.sin(angle),
                ))

            # --- update position and tangent azimuth ---
            current_x, current_y = points[-1]
            current_azimuth_rad = (current_azimuth_rad + sign * delta_rad) % (2 * math.pi)

            curves.append({
                "center": (cx, cy),
                "radius": radius,
                "start_angle": start_angle,
                "delta": delta_rad * sign,
                "handedness": params.handedness.value,
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
