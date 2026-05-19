from __future__ import annotations

import re
from typing import List, Tuple

from models.errors import ErrorCode
from models.schema import (
    AzimuthBearing,
    Bearing,
    BearingFormat,
    CurveCall,
    CurveParams,
    CurveType,
    DirectionBasis,
    Distance,
    DMS,
    Handedness,
    LineCall,
    QuadrantBearing,
)


WORD_TO_CARDINAL = {
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
    "N": "N",
    "S": "S",
    "E": "E",
    "W": "W",
}

CARDINAL_TO_AZIMUTH = {
    "N": 0,
    "E": 90,
    "S": 180,
    "W": 270,
}

CARDINAL_RE = re.compile(
    r"""
    ^\s*
    (?P<dir>N|S|E|W)
    \s+
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:feet|foot|ft)?\.?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
COMPACT_NO_SPACE_QUADRANT_RE = re.compile(
    r"""
    (?P<ns>NORTH|SOUTH|N|S)
    (?P<deg>\d{1,3})
    \s*[°]
    (?P<min>\d{1,2})
    \s*[']
    (?P<sec>\d{1,2}(?:\.\d+)?)
    \s*(?:["])?
    (?P<ew>EAST|WEST|E|W)
    \s*
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:FEET|FOOT|FT)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

LINE_QUADRANT_RE = re.compile(
    r"""
    ^\s*
    (?P<ns>N|S)
    \s*
    (?P<deg>\d{1,3})
    \s*°
    \s*
    (?P<min>\d{1,2})
    \s*'
    \s*
    (?P<sec>\d{1,2}(?:\.\d+)?)
    \s*"
    \s*
    (?P<ew>E|W)
    \s+
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:feet|foot|ft)?\.?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

LINE_QUADRANT_OPTIONAL_SECONDS_RE = re.compile(
    r"""
    ^\s*
    (?P<ns>N|S)
    \s*
    (?P<deg>\d{1,3})
    \s*°
    \s*
    (?P<min>\d{1,2})
    \s*'
    (?:\s*(?P<sec>\d{1,2}(?:\.\d+)?)\s*")?
    \s*
    (?P<ew>E|W)
    \s+
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:feet|foot|ft)?\.?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

LINE_AZIMUTH_RE = re.compile(
    r"""
    ^\s*
    (?P<deg>\d{1,3})
    \s*°
    \s*
    (?P<min>\d{1,2})
    \s*'
    \s*
    (?P<sec>\d{1,2}(?:\.\d+)?)
    \s*"
    \s+
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:feet|foot|ft)?\.?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

CURVE_RE = re.compile(
    r"""
    ^\s*
    (?:
        (?:(?:THENCE|ALONG)\s+)?
        (?:ALONG\s+)?
        (?:SAID\s+)?
        (?:A\s+)?
        CURVE
    )
    (?:\s+TO\s+THE)?\s+
    (?P<hand>RIGHT|LEFT)
    .*?
    (?:
        \bHAVING\s+A\s+RADIUS\s+OF\b
        |
        \bRADIUS\s+(?:OF\s+)?
    )
    \s*
    (?P<radius>\d+(?:\.\d+)?)
    \s*(?:FEET|FOOT|FT)\b
    (?:
        .*?
        \b(?:AN\s+)?ARC(?:\s+LENGTH)?(?:\s+OF)?\b
        \s*(?P<arc>\d+(?:\.\d+)?)
        \s*(?:FEET|FOOT|FT)\b
    )?
    (?:
        .*?
        \b(?:CENTRAL\s+ANGLE|DELTA)(?:\s+OF)?\b
        \s*(?P<deg>\d{1,3})
        \s*(?:DEGREES?|°)
        \s*(?P<min>\d{1,2})?
        \s*(?:MINUTES?|')?
        \s*(?P<sec>\d{1,2}(?:\.\d+)?)?
        \s*(?:SECONDS?|")?
    )?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


NARRATIVE_CURVE_RE = re.compile(
    r"""
    (?:
        \bTHENCE\b
        .*?
    )?
    \bALONG\s+
    (?:SAID\s+)?
    (?:A\s+)?
    CURVE\b
    .*?
    \b(?:TO\s+THE\s+)?(?P<hand>RIGHT|LEFT)\b
    .*?
    (?:
        \bHAVING\s+A\s+RADIUS\s+OF\b
        |
        \bRADIUS\s+OF\b
        |
        \bRADIUS\b
    )
    \s*(?P<radius>\d+(?:\.\d+)?)\s*(?:FEET|FOOT|FT)\b
    (?:
        .*?
        \b(?:AN\s+)?ARC(?:\s+LENGTH)?(?:\s+OF)?\b
        \s*(?P<arc>\d+(?:\.\d+)?)\s*(?:FEET|FOOT|FT)\b
    )?
    (?:
        .*?
        \b(?:CENTRAL\s+ANGLE|DELTA)(?:\s+OF)?\b
        \s*(?P<deg>\d{1,3})
        \s*(?:DEGREES?|°)
        \s*(?P<min>\d{1,2})?
        \s*(?:MINUTES?|')?
        \s*(?P<sec>\d{1,2}(?:\.\d+)?)?
        \s*(?:SECONDS?|")?
    )?
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


def _dms(deg: str, minutes: str | None, seconds: str | None) -> DMS:
    min_val = int(minutes) if minutes not in (None, "") else 0
    sec_val = float(seconds) if seconds not in (None, "") else 0.0
    return DMS(deg=int(deg), minutes=min_val, seconds=sec_val)


def _distance(raw: str) -> Distance:
    return Distance(raw_text=raw, value=float(raw))

def _normalize_legal_text(text: str) -> str:
    """
    Normalize OCR/legal-description punctuation and spacing.
    """
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")

    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "º": "°",
        "˚": "°",
        "–": "-",
        "—": "-",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    return " ".join(text.split())



def _bearing_from_words(
    ns_word: str,
    deg: str,
    minutes: str,
    seconds: str | None,
    ew_word: str,
) -> Bearing:
    ns = WORD_TO_CARDINAL[ns_word.upper()]
    ew = WORD_TO_CARDINAL[ew_word.upper()]

    min_text = minutes if minutes not in (None, "") else "0"
    sec_text = seconds if seconds not in (None, "") else "0"
    return Bearing(
        raw_text=f'{ns} {deg}°{min_text}\'{sec_text}" {ew}',
        format=BearingFormat.QUADRANT,
        value=QuadrantBearing(
            quadrant_ns=ns,
            angle=_dms(deg, minutes, seconds),
            quadrant_ew=ew,
        ),
        basis=DirectionBasis.TRUE,
        confidence=1.0,
    )

def _line_call_from_match(match, idx: int) -> LineCall:
    return LineCall(
        id=f"L{idx}",
        raw_text=match.group(0).strip(),
        bearing=_bearing_from_words(
            match.group("ns"),
            match.group("deg"),
            match.group("min"),
            match.groupdict().get("sec"),
            match.group("ew"),
        ),
        distance=_distance(match.group("dist")),
    )

# Compact quadrant with optional minutes/seconds (e.g. "N 0° E 100", "S 45°30' W 250")
COMPACT_QUADRANT_RE = re.compile(
    r"""
    (?P<ns>N|S)
    \s+
    (?P<deg>\d{1,3})
    \s*°
    (?:                          # optional minutes
        \s*(?P<min>\d{1,2})
        \s*[']
        (?:                      # optional seconds
            \s*(?P<sec>\d{1,2}(?:\.\d+)?)
            \s*(?:["])?
        )?
    )?
    \s*
    (?P<ew>E|W)
    \s*,?\s*
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:FEET|FOOT|FT)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


WORDY_QUADRANT_RE = re.compile(
    r"""
    (?P<ns>NORTH|SOUTH)
    \s+
    (?P<deg>\d{1,3})
    \s*[°]
    \s*
    (?P<min>\d{1,2})
    \s*[']
    \s*
    (?P<sec>\d{1,2}(?:\.\d+)?)
    \s*(?:["])?
    \s+
    (?P<ew>EAST|WEST)
    \s+
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:FEET|FOOT|FT)?
    """,
    re.IGNORECASE | re.VERBOSE,
)
def _try_line_patterns(line: str, idx: int) -> LineCall | None:
    patterns = [
        LINE_QUADRANT_RE,
        LINE_QUADRANT_OPTIONAL_SECONDS_RE,
        WORDY_QUADRANT_RE,
        COMPACT_NO_SPACE_QUADRANT_RE,
        COMPACT_ANY_QUADRANT_RE,  # fallback catch-all
    ]

    for pattern in patterns:
        match = pattern.search(line)
        if match:
            return _build_line_from_match(match, idx)

    return None

# Lookahead that marks the start of a new compact call within a single line.
# Matches before N/S+deg° or before a cardinal word followed by a distance.
_COMPACT_BOUNDARY_RE = re.compile(
    r'(?<!^)(?=\b(?:N|S)\s+\d{1,3}°|\b(?:EAST|WEST|NORTH|SOUTH)\s*,?\s*\d)',
    re.IGNORECASE,
)


def _split_chunks(text: str) -> List[str]:
    text = text.replace("\r", "\n")
    raw_chunks: List[str] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        for chunk in line.split(";"):
            chunk = chunk.strip()
            if not chunk:
                continue
            # If the chunk looks like compact multi-call (no THENCE, has °),
            # split on call boundaries so each call reaches the parse loop alone.
            # Skip splitting if the chunk contains a full quadrant bearing
            # (NORTH/SOUTH … EAST/WEST) — those are narrative, not compact.
            _HAS_FULL_QUADRANT = re.compile(
                r'\b(?:NORTH|SOUTH)\b.{0,80}\b(?:EAST|WEST)\b',
                re.IGNORECASE | re.DOTALL,
            )
            if ('°' in chunk
                    and 'THENCE' not in chunk.upper()
                    and not _HAS_FULL_QUADRANT.search(chunk)):
                sub = [s.strip() for s in _COMPACT_BOUNDARY_RE.split(chunk) if s.strip()]
                raw_chunks.extend(sub)
            else:
                raw_chunks.append(chunk)

    normalized: List[str] = []
    for chunk in raw_chunks:
        lower = chunk.lower()
        if lower.startswith("thence "):
            chunk = chunk[7:].strip()
        normalized.append(chunk)

    return normalized

def _clean_ocr_text(text: str) -> str:
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "º": "°",
        "˚": "°",
        "–": "-",
        "—": "-",
        "|": "1",
        "l00": "100",
        "I00": "100",
        "O°": "0°",
        "o°": "0°",
        "0 ": "0 ",
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # Normalise word forms first so space-collapse catches the newly-inserted symbols
    text = re.sub(r'\bDEGREES?\b', '°', text, flags=re.IGNORECASE)
    text = re.sub(r'\bMINUTES?\b', "'", text, flags=re.IGNORECASE)
    text = re.sub(r'\bSECONDS?\b', '"', text, flags=re.IGNORECASE)

    # Collapse whitespace around DMS symbols (runs after word substitution)
    text = re.sub(r"(?<=\d)\s+°", "°", text)
    text = re.sub(r"°\s+(?=\d)", "°", text)
    text = re.sub(r"(?<=\d)\s+'", "'", text)
    text = re.sub(r"'\s+(?=\d)", "'", text)
    text = re.sub(r'(?<=\d)\s+"', '"', text)
    text = re.sub(r'"\s+(?=\w)', '" ', text)

    text = " ".join(text.split())

    # Expand bare degree-only bearing (e.g. "50°" with no minutes/seconds)
    # to canonical "50°00'00\"" so all downstream regex can match uniformly.
    text = re.sub(r"(\d{1,3})°(?![\d'])", lambda m: m.group(1) + "°00'00\"", text)

    return text

NARRATIVE_LINE_RE = re.compile(
    r"""
    (?P<ns>NORTH|SOUTH|N|S)
    \s*
    (?P<deg>\d{1,3})
    \s*[°]
    \s*
    (?P<min>\d{1,2})
    \s*[']
    \s*
    (?P<sec>\d{1,2}(?:\.\d+)?)
    \s*(?:["])?
    \s*
    (?P<ew>EAST|WEST|E|W)
    \s+
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:FEET|FOOT|FT)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ============================================================
# Reference tie extraction (non-traverse, informational only)
# ============================================================

_SPB_BEARING_RE = re.compile(
    r"SAID\s+POINT\s+BEING\s+"
    r"(?P<ns>NORTH|SOUTH)\s+(?P<deg>\d{1,3})\s*(?:DEGREES?\s+|\u00b0)\s*"
    r"(?P<min>\d{1,2})\s*['\u2019\"]\s*(?P<sec>\d{1,2}(?:\.\d+)?)\s*[\"\u201d]\s+"
    r"(?P<ew>EAST|WEST)[,\s]+"
    r"(?P<dist>\d+(?:\.\d+)?)\s+FEET?\s+FROM\s+"
    r"(?P<monument>.+?)(?=;|\.|,\s*THENCE|$)",
    re.IGNORECASE | re.DOTALL,
)

_AS_MEASURED_RE = re.compile(
    r"(?P<dist>\d+(?:\.\d+)?)\s+FEET?\s+"
    r"(?P<direction>SOUTHEASTERLY|NORTHEASTERLY|SOUTHWESTERLY|NORTHWESTERLY"
    r"|EASTERLY|WESTERLY|NORTHERLY|SOUTHERLY)"
    r"[,\s]+AS\s+MEASURED\s+ALONG\s+(?P<feature>[^,]+?)\s+FROM\s+"
    r"(?P<monument>.+?)(?=;|\.|,\s*SAID|\d+(?:\.\d+)?\s+FEET|$)",
    re.IGNORECASE | re.DOTALL,
)


def _extract_reference_ties(clean_text: str, traverse_calls) -> list:
    """
    Extract SAID POINT BEING and AS MEASURED ALONG reference ties from cleaned
    deed text.  Returns a list of dicts with kind, bearing/distance/monument info.
    These MUST NOT be passed to build_geometry — they are informational only.
    Render as dashed lines in the UI.
    """
    norm = clean_text.replace("\r", " ").replace("\n", " ")
    norm = norm.replace("\u2018", "'").replace("\u2019", "'")
    norm = norm.replace("\u201c", '"').replace("\u201d", '"')
    norm = " ".join(norm.split())

    ties = []
    tie_idx = 1

    # --- SAID POINT BEING: bearing + distance FROM monument ---
    for m in _SPB_BEARING_RE.finditer(norm):
        ns = "N" if m.group("ns").upper() == "NORTH" else "S"
        ew = "E" if m.group("ew").upper() == "EAST" else "W"
        ties.append({
            "id": f"RT{tie_idx}",
            "raw_text": m.group(0).strip(),
            "kind": "bearing_from_monument",
            "bearing_ns": ns,
            "bearing_deg": m.group("deg"),
            "bearing_min": m.group("min"),
            "bearing_sec": m.group("sec"),
            "bearing_ew": ew,
            "distance": float(m.group("dist")),
            "from_monument": m.group("monument").strip().rstrip(".,"),
        })
        tie_idx += 1

    # --- AS MEASURED ALONG: linear distance along a line feature ---
    for m in _AS_MEASURED_RE.finditer(norm):
        ties.append({
            "id": f"RT{tie_idx}",
            "raw_text": m.group(0).strip(),
            "kind": "linear_along_line",
            "direction_word": m.group("direction").upper(),
            "distance": float(m.group("dist")),
            "along_feature": m.group("feature").strip(),
            "from_monument": m.group("monument").strip().rstrip(".,"),
        })
        tie_idx += 1

    return ties


# ============================================================
# Implicit closure synthesis
# ============================================================

_POB_RE = re.compile(
    r"TO\s+THE\s+(?:TRUE\s+)?POINT\s+OF\s+BEGINNING",
    re.IGNORECASE,
)
_CLOSURE_TOL = 0.01  # feet — within this is considered already closed


def _dms_to_deg_float(dms) -> float:
    return dms.deg + dms.minutes / 60.0 + dms.seconds / 3600.0


def _bearing_az_deg(bearing) -> float:
    v = bearing.value
    if hasattr(v, "azimuth"):
        return _dms_to_deg_float(v.azimuth)
    theta = _dms_to_deg_float(v.angle)
    ns, ew = v.quadrant_ns.upper(), v.quadrant_ew.upper()
    if   ns == "N" and ew == "E": return theta
    elif ns == "S" and ew == "E": return 180.0 - theta
    elif ns == "S" and ew == "W": return 180.0 + theta
    else:                         return 360.0 - theta  # N θ W


def _calls_endpoint(calls, start=(0.0, 0.0)):
    import math as _math
    x, y = start
    for call in calls:
        if not hasattr(call, "bearing"):
            continue  # CurveCall — skip
        az = _math.radians(_bearing_az_deg(call.bearing))
        x += call.distance.value * _math.sin(az)
        y += call.distance.value * _math.cos(az)
    return x, y


def _synthesize_closure_call(
    calls: list,
    original_text: str,
    idx: int,
    start: tuple = (0.0, 0.0),
):
    """
    If the original text ends with a POB instruction and the traverse does
    not close, compute and return a synthetic LineCall that closes it.
    Returns None if the parcel is already closed or there is no POB phrase.
    The synthetic call carries raw_text prefixed with "[DERIVED]" so renderers
    can identify it without schema changes.
    """
    import math as _math

    if not _POB_RE.search(original_text):
        return None

    end_x, end_y = _calls_endpoint(calls, start)
    dist = _math.hypot(end_x, end_y)

    if dist < _CLOSURE_TOL:
        return None  # already closed

    # Vector from current endpoint back to start
    dx = start[0] - end_x
    dy = start[1] - end_y
    az_deg = _math.degrees(_math.atan2(dx, dy)) % 360

    # Convert azimuth to quadrant bearing
    if az_deg <= 90.0:
        ns, theta, ew = "N", az_deg,        "E"
    elif az_deg <= 180.0:
        ns, theta, ew = "S", 180.0 - az_deg, "E"
    elif az_deg <= 270.0:
        ns, theta, ew = "S", az_deg - 180.0, "W"
    else:
        ns, theta, ew = "N", 360.0 - az_deg, "W"

    theta_deg = int(theta)
    theta_min = int((theta - theta_deg) * 60)
    theta_sec = round(((theta - theta_deg) * 60 - theta_min) * 60, 2)
    
    # Normalise floating-point carry-over before constructing DMS
    if theta_sec >= 59.9995:
        theta_sec = 0.0
        theta_min += 1
    if theta_min >= 60:
        theta_min = 0
        theta_deg += 1

    bearing = Bearing(
        raw_text=f"[DERIVED] {ns} {theta_deg}\u00b0{theta_min}\'{theta_sec}\" {ew}",
        format=BearingFormat.QUADRANT,
        value=QuadrantBearing(
            quadrant_ns=ns,
            angle=DMS(deg=theta_deg, minutes=theta_min, seconds=theta_sec),
            quadrant_ew=ew,
        ),
        basis=DirectionBasis.ASSUMED,
        confidence=0.5,
    )

    return LineCall(
        id=f"L{idx}_CLOSURE",
        raw_text=f"[DERIVED] {round(dist, 4)} FT TO THE POINT OF BEGINNING",
        bearing=bearing,
        distance=_distance(str(round(dist, 4))),
    )


def parse_legal_description(text: str) -> Tuple[List[LineCall | CurveCall], List[str]]:
    calls: List[LineCall | CurveCall] = []
    errors: List[str] = []

    # -------------------------------------------------
    # STEP 1: CLEAN INPUT
    # -------------------------------------------------
    clean_text = _clean_ocr_text(text)

    # -------------------------------------------------
    # STEP 2: PROSE → STRUCTURED (🔥 CRITICAL)
    # -------------------------------------------------
    prose_courses = _extract_prose_courses(clean_text)

    if prose_courses.strip():
        clean_text = prose_courses

    # -------------------------------------------------
    # STEP 3: SPLIT INTO PARSEABLE CHUNKS
    # -------------------------------------------------
    chunks = _split_chunks(clean_text)

    # -------------------------------------------------
    # STEP 4: PRIMARY PARSE LOOP
    # -------------------------------------------------
    last_bearing: Bearing | None = None
    for idx, raw_line in enumerate(chunks, start=1):
        line = raw_line.strip().rstrip(";,.")
        line = line.replace("THENCE", "").strip()
        line = re.sub(r"\s+", " ", line)

        if not line:
            continue

        # ---------------------------------------------
        # CARDINAL (E, W, N, S)
        # ---------------------------------------------
        m_card = CARDINAL_RE.match(line)
        if m_card:
            direction = m_card.group("dir").upper()
            azimuth_deg = CARDINAL_TO_AZIMUTH[direction]

            calls.append(
                LineCall(
                    id=f"L{idx}",
                    raw_text=line,
                    bearing=Bearing(
                        raw_text=direction,
                        format=BearingFormat.AZIMUTH,
                        value=AzimuthBearing(
                            azimuth=DMS(deg=azimuth_deg, minutes=0, seconds=0.0)
                        ),
                        basis=DirectionBasis.TRUE,
                        confidence=1.0,
                    ),
                    distance=_distance(m_card.group("dist")),
                )
            )
            continue

        # ---------------------------------------------
        # PROSE QUADRANT  (narrative bearing: "BEING NORTH 50 DEGREES ... WEST, 100 FEET")
        # Searches raw_line (before THENCE strip) so BEING/FROM/THEN prefixes are visible.
        # ---------------------------------------------
        m_pq = _PROSE_QUADRANT_RE.search(raw_line)
        if m_pq:
            ns = WORD_TO_CARDINAL[m_pq.group("ns").upper()]
            ew = WORD_TO_CARDINAL[m_pq.group("ew").upper()]
            deg = m_pq.group("deg")
            minutes = m_pq.group("min")
            seconds = m_pq.group("sec")
            b = Bearing(
                raw_text=line,
                format=BearingFormat.QUADRANT,
                value=QuadrantBearing(
                    quadrant_ns=ns,
                    quadrant_ew=ew,
                    angle=_dms(deg, minutes, seconds),
                ),
                basis=DirectionBasis.TRUE,
                confidence=0.8,
            )
            calls.append(LineCall(
                id=f"L{idx}",
                raw_text=line,
                bearing=b,
                distance=_distance(m_pq.group("dist")),
            ))
            last_bearing = b
            continue

        # ---------------------------------------------
        # QUADRANT LINE
        # ---------------------------------------------
        line_call = _try_line_patterns(line, idx)
        if line_call is not None:
            last_bearing = line_call.bearing
            calls.append(line_call)
            continue

        # ---------------------------------------------
        # AZIMUTH
        # ---------------------------------------------
        m_az = LINE_AZIMUTH_RE.match(line)
        if m_az:
            calls.append(
                LineCall(
                    id=f"L{idx}",
                    raw_text=line,
                    bearing=Bearing(
                        raw_text=f'{m_az.group("deg")}°{m_az.group("min")}\'{m_az.group("sec")}"',
                        format=BearingFormat.AZIMUTH,
                        value=AzimuthBearing(
                            azimuth=_dms(
                                m_az.group("deg"),
                                m_az.group("min"),
                                m_az.group("sec"),
                            )
                        ),
                        basis=DirectionBasis.TRUE,
                        confidence=1.0,
                    ),
                    distance=_distance(m_az.group("dist")),
                )
            )
            continue
        # ---------------------------------------------
        # CURVE
        # ---------------------------------------------
        m_curve = CURVE_RE.match(line)
        if m_curve:
            hand = m_curve.group("hand").lower()
            radius = float(m_curve.group("radius"))

            deg = m_curve.group("deg")
            minutes = m_curve.group("min")
            sec = m_curve.group("sec")
            arc = m_curve.group("arc")

            delta = None
            if deg is not None and minutes is not None:
                delta = _dms(deg, minutes, sec)

            arc_length = None
            if arc is not None:
                try:
                    parsed_arc = float(arc)
                    if parsed_arc > 0:
                        arc_length = parsed_arc
                except ValueError:
                    arc_length = None

            if delta is None and arc_length is None:
                errors.append(
                    f"{ErrorCode.CURVE_INCOMPLETE.value}: line {idx}: '{line}'"
                )
                continue

            curve_kwargs = {
                "curve_type": CurveType.TANGENT,
                "radius": radius,
                "handedness": Handedness.RIGHT if hand == "right" else Handedness.LEFT,
                "confidence": 1.0,
            }

            if delta is not None:
                curve_kwargs["delta"] = delta

            if arc_length is not None:
                curve_kwargs["arc_length"] = arc_length

            calls.append(
                CurveCall(
                    id=f"C{idx}",
                    raw_text=line,
                    params=CurveParams(**curve_kwargs),
                )
            )
            continue

        # ---------------------------------------------
        # WORDY CARDINAL  (e.g. "EAST 120.00 FEET")
        # ---------------------------------------------
        m_wcard = _WORDY_CARDINAL_RE.match(line)
        if m_wcard:
            single = _WORD_TO_SINGLE[m_wcard.group("dir").upper()]
            az_deg = CARDINAL_TO_AZIMUTH[single]
            b = Bearing(
                raw_text=m_wcard.group("dir"),
                format=BearingFormat.AZIMUTH,
                value=AzimuthBearing(azimuth=DMS(deg=az_deg, minutes=0, seconds=0.0)),
                basis=DirectionBasis.TRUE,
                confidence=1.0,
            )
            calls.append(LineCall(id=f"L{idx}", raw_text=line, bearing=b,
                                  distance=_distance(m_wcard.group("dist"))))
            last_bearing = b
            continue

        # ---------------------------------------------
        # CURVE-APPROX  (arc dist, no radius → LineCall using last bearing)
        # ---------------------------------------------
        m_arc = _ARC_ONLY_CURVE_RE.search(line)
        if m_arc and last_bearing is not None:
            calls.append(LineCall(
                id=f"L{idx}",
                raw_text=line,
                bearing=last_bearing,
                distance=_distance(m_arc.group("dist")),
            ))
            continue

        # ---------------------------------------------
        # IGNORE NARRATIVE JUNK (NOT ERRORS)
        # ---------------------------------------------
        print(f"[PARSE FAIL] {line}")
        if any(keyword in line.upper() for keyword in [
            "BEGINNING",
            "COMMENCING",
            "POINT OF BEGINNING",
            "TRUE POINT OF BEGINNING",
            "TRACT",
            "RECORDED",
            "OFFICIAL RECORDS",
            "MAP RECORDED",
            "COUNTY",
            "LOT",
            "SECTION",
        ]):
            continue

        # ---------------------------------------------
        # UNKNOWN
        # ---------------------------------------------
        errors.append(f"{ErrorCode.UNKNOWN_ELEMENT.value}: line {idx}: '{line}'")

    # -------------------------------------------------
    # STEP 5: REFERENCE TIE EXTRACTION
    # -------------------------------------------------
    reference_ties = _extract_reference_ties(
        _clean_ocr_text(text), calls
    )

    # -------------------------------------------------
    # STEP 5b: IMPLICIT CLOSURE SYNTHESIS
    # -------------------------------------------------
    closure_call = _synthesize_closure_call(
        calls, text, idx=len(calls) + 1
    )
    if closure_call is not None:
        calls.append(closure_call)

    # -------------------------------------------------
    # STEP 6: SUCCESS PATH
    # -------------------------------------------------
    if calls:
        return calls, errors

    # -------------------------------------------------
    # STEP 6: FULL NARRATIVE FALLBACK
    # -------------------------------------------------
    narrative_calls, narrative_errors = _extract_narrative_calls(clean_text)

    if narrative_calls:
        return narrative_calls, narrative_errors

    return calls, errors

def _extract_narrative_calls(text: str) -> Tuple[List[LineCall | CurveCall], List[str]]:
    """
    Extract line/curve calls from full narrative legal descriptions.

    This does a global regex search over the entire paragraph and appends
    every valid metes-and-bounds match in encounter order.
    """

    
    normalized = _normalize_legal_text(_clean_ocr_text(text))

    calls: List[LineCall | CurveCall] = []
    errors: List[str] = []

    line_idx = 1
    for m in NARRATIVE_LINE_RE.finditer(normalized):
        calls.append(
            LineCall(
                id=f"L{line_idx}",
                raw_text=m.group(0).strip(),
                bearing=_bearing_from_words(
                    m.group("ns"),
                    m.group("deg"),
                    m.group("min"),
                    m.group("sec"),
                    m.group("ew"),
                ),
                distance=_distance(m.group("dist")),
            )
        )
        line_idx += 1

        curve_idx = 1

    for m in NARRATIVE_CURVE_RE.finditer(normalized):

        radius = float(m.group("radius"))

        # --- SAFE DELTA PARSE ---
        delta = None
        if m.group("deg") and m.group("min"):
            delta = _dms(
                m.group("deg"),
                m.group("min"),
                m.group("sec"),
            )

        # --- SAFE ARC PARSE ---
        arc_length = None
        if m.group("arc"):
            try:
                parsed_arc = float(m.group("arc"))
                if parsed_arc > 0:
                    arc_length = parsed_arc
            except ValueError:
                arc_length = None

        # --- CRITICAL VALIDATION ---
        if delta is None and arc_length is None:
            continue

        curve_kwargs = {
            "curve_type": CurveType.TANGENT,
            "radius": radius,
            "handedness": Handedness.RIGHT if m.group("hand").upper() == "RIGHT" else Handedness.LEFT,
            "confidence": 1.0,
        }

        if delta is not None:
            curve_kwargs["delta"] = delta

        if arc_length is not None:
            curve_kwargs["arc_length"] = arc_length

        calls.append(
            CurveCall(
                id=f"C{curve_idx}",
                raw_text=m.group(0).strip(),
                params=CurveParams(**curve_kwargs),
            )
        )

        curve_idx += 1

    if calls:
        return calls, errors

    return [], errors

COMPACT_ANY_QUADRANT_RE = re.compile(
    r"""
    (?P<ns>N|S)
    \s*
    (?P<deg>\d{1,3})
    \s*[°º]
    \s*
    (?P<min>\d{1,2})
    \s*['’]
    \s*
    (?:(?P<sec>\d{1,2}(?:\.\d+)?)\s*(?:["”])?)?
    \s*
    (?P<ew>E|W)
    \s*
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:FEET|FOOT|FT)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


WORDY_QUADRANT_RE = re.compile(
    r"""
    (?P<ns>NORTH|SOUTH)
    \s+
    (?P<deg>\d{1,3})
    \s*[°º]
    \s*
    (?P<min>\d{1,2})
    \s*['’]
    \s*
    (?:(?P<sec>\d{1,2}(?:\.\d+)?)\s*(?:["”])?)?
    \s*,?\s*
    (?P<ew>EAST|WEST)
    \s*,?\s*
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:FEET|FOOT|FT)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _build_line_from_match(match, idx: int) -> LineCall:
    return LineCall(
        id=f"L{idx}",
        raw_text=match.group(0).strip(),
        bearing=_bearing_from_words(
            match.group("ns"),
            match.group("deg"),
            match.group("min"),
            match.groupdict().get("sec"),
            match.group("ew"),
        ),
        distance=_distance(match.group("dist")),
    )


def _try_line_patterns(line: str, idx: int) -> LineCall | None:
    patterns = [
        LINE_QUADRANT_RE,
        LINE_QUADRANT_OPTIONAL_SECONDS_RE,
        WORDY_QUADRANT_RE,
        COMPACT_NO_SPACE_QUADRANT_RE,
        COMPACT_ANY_QUADRANT_RE,
        COMPACT_QUADRANT_RE,
    ]

    for pattern in patterns:
        match = pattern.search(line)
        if match:
            return _build_line_from_match(match, idx)

    return None

def _extract_prose_courses(text: str) -> str:
    normalized = text.replace("\r", " ").replace("\n", " ")
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = normalized.replace("”", '"').replace("“", '"')
    normalized = " ".join(normalized.split())

    lines: List[str] = []

    thence_spans = []
    for m in PROSE_COURSE_RE.finditer(normalized):
        thence_spans.append((m.start(), m.end()))
        ns = "N" if m.group("ns").upper() == "NORTH" else "S"
        ew = "E" if m.group("ew").upper() == "EAST" else "W"
        lines.append(f'{ns}{m.group("deg")}°{m.group("min")}\'{(m.group("sec") or "0")}" {ew} {m.group("dist")} FT')

    # Second pass: non-THENCE boundary segments — bearing + dist + "TO A POINT",
    # excluding descriptive/reference clauses and anything inside a THENCE span.
    _NON_THENCE_RE = re.compile(
        r"""(?P<ns>NORTH|SOUTH)\s+
            (?P<deg>\d{1,3})\s*(?:DEGREES?\s+|\u00b0)\s*
            (?P<min>\d{1,2})\s*['\u2019"]\s*
            (?P<sec>\d{1,2}(?:\.\d+)?)\s*["\u201d]\s*
            (?P<ew>EAST|WEST)[,\s]+
            (?P<dist>\d+(?:\.\d+)?)\s+FEET\s+TO\s+A\s+POINT""",
        re.IGNORECASE | re.VERBOSE,
    )
    _EXCLUSIONS = ("SAID POINT BEING", "FROM THE", "AS MEASURED", "ALONG")

    for m in _NON_THENCE_RE.finditer(normalized):
        if any(s <= m.start() <= e for s, e in thence_spans):
            continue
        cs = normalized.rfind(";", 0, m.start())
        cs = cs + 1 if cs >= 0 else 0
        ce = normalized.find(";", m.end())
        ce = ce if ce >= 0 else len(normalized)
        clause = normalized[cs:ce]
        if any(ex in clause.upper() for ex in _EXCLUSIONS):
            # Allow SAID POINT BEING if it contains a full bearing
            if "SAID POINT BEING" not in clause.upper():
                continue
        ns = "N" if m.group("ns").upper() == "NORTH" else "S"
        ew = "E" if m.group("ew").upper() == "EAST" else "W"
        lines.append(f'{ns}{m.group("deg")}°{m.group("min")}\'{(m.group("sec") or "0")}" {ew} {m.group("dist")} FT')


    # Third pass: cardinal THENCE clauses (THENCE EAST|WEST|NORTH|SOUTH dist FEET)
    for m in _PROSE_CARDINAL_RE.finditer(normalized):
        if any(s <= m.start() <= e for s, e in thence_spans):
            continue
        single = _WORD_TO_SINGLE[m.group("dir").upper()]
        lines.append(f'{single} {m.group("dist")} FT')

    # Fourth pass: curve THENCE clauses — emit raw clause for CURVE_RE in parse loop
    for m in _PROSE_CURVE_RE.finditer(normalized):
        if any(s <= m.start() <= e for s, e in thence_spans):
            continue
        clause = re.sub(r"^THENCE\s+", "", m.group(0).strip(), flags=re.IGNORECASE)
        lines.append(clause)

    # Fifth pass: any remaining THENCE clause not covered by earlier passes.
    # Emit the raw clause (THENCE stripped) so the parse loop handles it.
    # This catches cardinal-with-comma and any other variant we have not
    # explicitly matched above.
    all_thence_spans = [
        (m.start(), m.end())
        for pattern in (PROSE_COURSE_RE, _PROSE_CARDINAL_RE, _PROSE_CURVE_RE)
        for m in pattern.finditer(normalized)
    ]
    for m in re.finditer(r'\bTHENCE\b', normalized, re.IGNORECASE):
        if any(s <= m.start() <= e for s, e in all_thence_spans):
            continue
        # Clause ends at the next THENCE, semicolon, or end of string
        next_thence = re.search(r'\bTHENCE\b', normalized[m.end():], re.IGNORECASE)
        next_semi = normalized.find(";", m.end())
        offsets = [o for o in (
            m.end() + next_thence.start() if next_thence else None,
            next_semi if next_semi >= 0 else None,
        ) if o is not None]
        clause_end = min(offsets) if offsets else len(normalized)
        clause = re.sub(
            r"^THENCE\s*", "",
            normalized[m.start():clause_end].strip(),
            flags=re.IGNORECASE,
        ).strip()
        if clause:
            lines.append(clause)

    return "\n".join(lines)

PROSE_COURSE_RE = re.compile(
    r"""
    THENCE\s+
    (?P<ns>NORTH|SOUTH)\s+
    (?P<deg>\d{1,3})\s*(?:DEGREES?\s+|°)\s*
    (?P<min>\d{1,2})\s*[’'"]\s*
    (?:(?P<sec>\d{1,2}(?:\.\d+)?)\s*[\xe2\x80\x9d"]\s*)?
    (?P<ew>EAST|WEST)
    .*?
    (?P<dist>\d+(?:\.\d+)?)\s+FEET(?=\s+TO\b|[,;.]|$)
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL,
)


# Cardinal direction THENCE clause (e.g. THENCE EAST 120.00 FEET TO A POINT)
_PROSE_CARDINAL_RE = re.compile(
    r"THENCE\s+(?P<dir>EAST|WEST|NORTH|SOUTH)\s+"
    r"(?P<dist>\d+(?:\.\d+)?)\s+FEET(?=\s+TO\b|[,;.]|$)",
    re.IGNORECASE,
)

# Curve THENCE clause — arc-labelled distance takes priority over radius
_PROSE_CURVE_RE = re.compile(
    r"THENCE\s+(?:ALONG\s+)?A\s+CURVE\s+TO\s+THE\s+(?P<hand>RIGHT|LEFT)"
    r".*?"
    r"\bARC(?:\s+LENGTH)?(?:\s+OF)?\s+(?P<dist>\d+(?:\.\d+)?)\s+FEET(?=\s+TO\b|[,;.]|$)",
    re.IGNORECASE | re.DOTALL,
)

# Wordy cardinal in parse loop (fallback / direct input path)
_WORDY_CARDINAL_RE = re.compile(
    r"^\s*(?P<dir>EAST|WEST|NORTH|SOUTH)\s*,?\s+"
    r"(?P<dist>\d+(?:\.\d+)?)\s*(?:FEET|FOOT|FT)?(?=\s+TO\b|[,;.]|$)",
    re.IGNORECASE,
)

# Arc-only curve in parse loop (no radius → straight-line approx using last bearing)
_ARC_ONLY_CURVE_RE = re.compile(
    r"(?:ALONG\s+)?A\s+CURVE\s+TO\s+THE\s+(?P<hand>RIGHT|LEFT)"
    r".*?"
    r"\bARC(?:\s+LENGTH)?(?:\s+OF)?\s+(?P<dist>\d+(?:\.\d+)?)\s+FEET(?=\s+TO\b|[,;.]|$)",
    re.IGNORECASE | re.DOTALL,
)

_WORD_TO_SINGLE = {"EAST": "E", "WEST": "W", "NORTH": "N", "SOUTH": "S"}

# Prose quadrant: matches wordy or shorthand quadrant bearings embedded in narrative
# (e.g. 'SAID POINT BEING NORTH 50 DEGREES 00' 30" WEST, 100.00 FEET')
_PROSE_QUADRANT_RE = re.compile(
    r"(?:THENCE|BEING|FROM|THEN)\s+"
    r"(?P<ns>NORTH|SOUTH)\s+"
    r"(?P<deg>\d+)\s*°\s*"
    r"(?:(?P<min>\d+)\s*['\u2019]?\s*)?"
    r"(?:(?P<sec>\d+)\s*['\u2019\"\u201d]?\s*)?"
    r"(?P<ew>EAST|WEST).*?"
    r"(?P<dist>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
