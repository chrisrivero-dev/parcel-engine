from __future__ import annotations

import re

from models.schema import CurveCall, CurveParams, CurveType, DMS, Handedness

_CURVE_KEYWORD_RE = re.compile(
    r"\b(curve|radius|arc|central\s+angle|delta|tangent|concave)\b",
    re.IGNORECASE,
)

_RADIUS_RE = re.compile(
    r"\bRADIUS(?:\s+OF)?\s+(?P<radius>\d+(?:\.\d+)?)\s*(?:FEET|FOOT|FT)\b",
    re.IGNORECASE,
)

_ARC_RE = re.compile(
    r"\b(?:AN\s+)?ARC(?:\s+DISTANCE|\s+LENGTH)?(?:\s+OF)?\s+"
    r"(?P<arc>\d+(?:\.\d+)?)\s*(?:FEET|FOOT|FT)\b",
    re.IGNORECASE,
)

_DELTA_RE = re.compile(
    r"\b(?:CENTRAL\s+ANGLE|DELTA)(?:\s+OF)?\s+"
    r"(?P<deg>\d{1,3})\s*(?:°|DEGREES?)\s*"
    r"(?P<min>\d{1,2})?\s*(?:'|MINUTES?)?\s*"
    r"(?P<sec>\d{1,2}(?:\.\d+)?)?\s*(?:\"|SECONDS?)?",
    re.IGNORECASE,
)

_HAND_RE = re.compile(r"\b(?:TO\s+THE\s+)?(?P<hand>RIGHT|LEFT)\b", re.IGNORECASE)

_CONCAVE_RE = re.compile(
    r"\bCONCAVE\s+(?P<dir>NORTHERLY|SOUTHERLY|EASTERLY|WESTERLY|"
    r"NORTHEASTERLY|NORTHWESTERLY|SOUTHEASTERLY|SOUTHWESTERLY)\b",
    re.IGNORECASE,
)


def is_curve_clause(text: str) -> bool:
    return _CURVE_KEYWORD_RE.search(text) is not None


def _dms(deg: str, minutes: str | None, seconds: str | None) -> DMS:
    return DMS(
        deg=int(deg),
        minutes=int(minutes) if minutes not in (None, "") else 0,
        seconds=float(seconds) if seconds not in (None, "") else 0.0,
    )


def parse_curve_chunk(text: str, idx: int) -> CurveCall | None:
    if not is_curve_clause(text):
        return None

    radius_match = _RADIUS_RE.search(text)
    if radius_match is None:
        return None

    arc_match = _ARC_RE.search(text)
    delta_match = _DELTA_RE.search(text)

    if arc_match is None and delta_match is None:
        return None

    handedness = None
    hand_match = _HAND_RE.search(text)
    if hand_match is not None:
        hand = hand_match.group("hand").upper()
        handedness = Handedness.RIGHT if hand == "RIGHT" else Handedness.LEFT

    along_feature = None
    concave_match = _CONCAVE_RE.search(text)
    if concave_match is not None:
        along_feature = f"CONCAVE {concave_match.group('dir').upper()}"

    return CurveCall(
        id=f"C{idx}",
        raw_text=text.strip(),
        params=CurveParams(
            curve_type=CurveType.TANGENT
            if re.search(r"\bTANGENT\b", text, re.IGNORECASE)
            else CurveType.NON_TANGENT,
            radius=float(radius_match.group("radius")),
            arc_length=float(arc_match.group("arc")) if arc_match is not None else None,
            delta=_dms(
                delta_match.group("deg"),
                delta_match.group("min"),
                delta_match.group("sec"),
            )
            if delta_match is not None
            else None,
            handedness=handedness,
            confidence=0.8,
        ),
        along_feature=along_feature,
        confidence=0.8,
    )
