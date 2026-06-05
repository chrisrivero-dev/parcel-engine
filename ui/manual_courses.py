from __future__ import annotations

from models.schema import (
    AzimuthBearing,
    Bearing,
    BearingFormat,
    DirectionBasis,
    Distance,
    DMS,
    LineCall,
)
from transcription.lines import parse_line_chunk
from transcription.normalize import normalize


_CARDINAL_AZIMUTH = {"N": 0, "S": 180, "E": 90, "W": 270}
_CARDINAL_WORDS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}


def build_manual_line(direction: str, distance: str, idx: int) -> LineCall:
    """
    Build a LineCall from manually-entered direction text and distance text.

    Supported direction formats:
      - Quadrant DMS:  N 45°32'10" E,  N45°32'10"E,  NORTH 45°32'10" EAST
      - Pure cardinal: N, S, E, W
      - Cardinal word: NORTH, SOUTH, EAST, WEST

    Raises ValueError with a human-readable message on failure.
    """
    direction = (direction or "").strip()
    distance = (distance or "").strip()

    if not direction:
        raise ValueError("missing direction")
    if not distance:
        raise ValueError("missing distance")

    try:
        dist_value = float(distance)
    except ValueError as exc:
        raise ValueError(f"distance not numeric: {distance!r}") from exc

    if dist_value <= 0:
        raise ValueError(f"distance must be positive: {dist_value}")

    normalized_dir = normalize(direction).upper().strip()

    cardinal_letter = None
    if normalized_dir in _CARDINAL_AZIMUTH:
        cardinal_letter = normalized_dir
    elif normalized_dir in _CARDINAL_WORDS:
        cardinal_letter = _CARDINAL_WORDS[normalized_dir]

    if cardinal_letter is not None:
        az_deg = _CARDINAL_AZIMUTH[cardinal_letter]
        return LineCall(
            id=f"L{idx}",
            raw_text=f"{cardinal_letter} {dist_value}",
            bearing=Bearing(
                raw_text=cardinal_letter,
                format=BearingFormat.AZIMUTH,
                value=AzimuthBearing(
                    azimuth=DMS(deg=az_deg, minutes=0, seconds=0.0)
                ),
                basis=DirectionBasis.TRUE,
                confidence=1.0,
            ),
            distance=Distance(raw_text=str(dist_value), value=dist_value),
        )

    combined = f"{normalize(direction)} {dist_value}"
    parsed = parse_line_chunk(combined, idx)
    if parsed is None:
        raise ValueError(f"could not parse direction: {direction!r}")

    parsed.id = f"L{idx}"
    parsed.distance = Distance(raw_text=str(dist_value), value=dist_value)
    return parsed


# ===========================================================================
# Curve row support  (appended by apply_curve_table_build_support.py)
# ===========================================================================
__CURVE_TABLE_BUILD_APPLIED__ = True

import re as _cv_re

from models.schema import (
    CurveCall as _CV_CurveCall,
    CurveParams as _CV_CurveParams,
    CurveType as _CV_CurveType,
    DMS as _CV_DMS,
    Handedness as _CV_Handedness,
)

# Direction cell -> handedness mapping.  Accepts L/R/LEFT/RIGHT/CW/CCW/LH/RH
# in any case so technicians don't have to type a specific token.
_CV_HANDEDNESS_MAP = {
    "L": _CV_Handedness.LEFT, "LEFT": _CV_Handedness.LEFT,
    "LH": _CV_Handedness.LEFT, "CCW": _CV_Handedness.LEFT,
    "R": _CV_Handedness.RIGHT, "RIGHT": _CV_Handedness.RIGHT,
    "RH": _CV_Handedness.RIGHT, "CW": _CV_Handedness.RIGHT,
}

# Delta angle: full DMS (45 30 00), deg+min (45 30), bare deg (45), or
# decimal degrees (45.5).  Symbols are optional; whitespace tolerated.
_CV_DELTA_DMS_RE = _cv_re.compile(
    r"^\s*(?P<deg>\d+(?:\.\d+)?)"
    r"\s*°?\s*"
    r"(?:(?P<min>\d{1,2}(?:\.\d+)?)\s*'?\s*)?"
    r"(?:(?P<sec>\d{1,2}(?:\.\d+)?)\s*\"?\s*)?"
    r"$"
)


def _cv_parse_handedness(text):
    key = (text or "").strip().upper()
    if not key:
        raise ValueError("missing handedness (LEFT or RIGHT)")
    if key not in _CV_HANDEDNESS_MAP:
        raise ValueError(
            f"unknown handedness {text!r} (expected LEFT, RIGHT, L, R, CW, or CCW)"
        )
    return _CV_HANDEDNESS_MAP[key]


def _cv_parse_delta_dms(text):
    raw = (text or "").strip()
    if not raw:
        raise ValueError("missing delta")
    m = _CV_DELTA_DMS_RE.match(raw)
    if m is None:
        raise ValueError(f"could not parse delta angle: {text!r}")

    deg_str = m.group("deg")
    deg_val = float(deg_str)
    minutes_token = m.group("min")
    seconds_token = m.group("sec")

    if minutes_token is None and seconds_token is None and "." in deg_str:
        # Pure decimal degrees -> split into DMS so each field stays in range.
        whole = int(deg_val)
        frac_min = (deg_val - whole) * 60.0
        minutes = int(frac_min)
        seconds = round((frac_min - minutes) * 60.0, 6)
        if seconds >= 60.0:
            seconds = 0.0
            minutes += 1
        if minutes >= 60:
            minutes = 0
            whole += 1
        return _CV_DMS(deg=whole, minutes=minutes, seconds=seconds)

    deg_int = int(deg_val)
    minutes = int(minutes_token) if minutes_token is not None else 0
    seconds = float(seconds_token) if seconds_token is not None else 0.0
    if not (0 <= deg_int <= 360):
        raise ValueError(f"delta degrees out of range: {deg_int}")
    if not (0 <= minutes < 60):
        raise ValueError(f"delta minutes out of range: {minutes}")
    if not (0.0 <= seconds < 60.0):
        raise ValueError(f"delta seconds out of range: {seconds}")
    return _CV_DMS(deg=deg_int, minutes=minutes, seconds=seconds)


def _cv_parse_positive_float(text, label):
    raw = (text or "").strip()
    if not raw:
        raise ValueError(f"missing {label}")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{label} not numeric: {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{label} must be positive: {value}")
    return value


def build_manual_curve(direction, radius, delta, arc="", idx=1):
    """Build a :class:`CurveCall` from manually-entered COGO table strings.

    Reads:
      - direction: handedness word    (LEFT / RIGHT / L / R / CW / CCW)
      - radius:    positive float
      - delta:     DMS string         (full DMS, deg+min, or decimal degrees)
      - arc:       positive float     (optional alternative to delta)

    Either ``delta`` or ``arc`` must be present.  Raises :class:`ValueError`
    with a row-specific human-readable message on any validation failure;
    never returns a partial / silently-coerced call.
    """
    handedness = _cv_parse_handedness(direction)
    radius_val = _cv_parse_positive_float(radius, "radius")

    delta_dms = None
    if (delta or "").strip():
        delta_dms = _cv_parse_delta_dms(delta)

    arc_val = None
    if (arc or "").strip():
        arc_val = _cv_parse_positive_float(arc, "arc length")

    if delta_dms is None and arc_val is None:
        raise ValueError("missing delta or arc length (at least one required)")

    params = _CV_CurveParams(
        curve_type=_CV_CurveType.TANGENT,
        radius=radius_val,
        delta=delta_dms,
        arc_length=arc_val,
        handedness=handedness,
        confidence=1.0,
    )

    parts = [handedness.value.upper(), f"R={radius_val}"]
    if delta_dms is not None:
        parts.append(
            f"Δ={delta_dms.deg}°{delta_dms.minutes:02d}'{int(delta_dms.seconds):02d}\""
        )
    if arc_val is not None:
        parts.append(f"L={arc_val}")

    return _CV_CurveCall(
        id=f"C{idx}",
        raw_text=" ".join(parts),
        params=params,
        confidence=1.0,
    )
