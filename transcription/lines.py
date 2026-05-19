from __future__ import annotations

import re

from models.schema import (
    Bearing,
    BearingFormat,
    DirectionBasis,
    Distance,
    DMS,
    LineCall,
    QuadrantBearing,
)

_WORD_TO_CARDINAL = {
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
    "N": "N",
    "S": "S",
    "E": "E",
    "W": "W",
}

_BEARING = r"""
    (?P<ns>NORTH|SOUTH|N|S)
    \s*
    (?P<deg>\d{1,3})
    \s*°\s*
    (?P<min>\d{1,2})
    \s*'\s*
    (?:(?P<sec>\d{1,2}(?:\.\d+)?)\s*"?)?
    \s*,?\s*
    (?P<ew>EAST|WEST|E|W)
    \b
"""

LINE_CLEAN_RE = re.compile(
    _BEARING + r"""
    \s*,?\s*
    (?:a\s+distance\s+of\s+)?
    (?P<dist>\d+(?:\.\d+)?)
    \s*(?:feet|foot|ft)?\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

LINE_NARRATIVE_RE = re.compile(
    _BEARING + r"""
    \s+[A-Za-z][^,]{0,160}?,?\s+
    (?P<dist>\d+(?:\.\d+)?)
    \s+(?:feet|foot|ft)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _build_line_call(match: re.Match, idx: int) -> LineCall:
    ns = _WORD_TO_CARDINAL[match.group("ns").upper()]
    ew = _WORD_TO_CARDINAL[match.group("ew").upper()]
    deg = int(match.group("deg"))
    minutes = int(match.group("min") or 0)
    sec_raw = match.group("sec")
    seconds = float(sec_raw) if sec_raw not in (None, "") else 0.0

    raw_text = f'{ns} {deg}°{minutes}\'{int(seconds) if seconds == int(seconds) else seconds}" {ew}'

    bearing = Bearing(
        raw_text=raw_text,
        format=BearingFormat.QUADRANT,
        value=QuadrantBearing(
            quadrant_ns=ns,
            quadrant_ew=ew,
            angle=DMS(deg=deg, minutes=minutes, seconds=seconds),
        ),
        basis=DirectionBasis.TRUE,
        confidence=1.0,
    )

    dist_raw = match.group("dist")
    distance = Distance(raw_text=dist_raw, value=float(dist_raw))

    return LineCall(
        id=f"L{idx}",
        raw_text=match.group(0).strip(),
        bearing=bearing,
        distance=distance,
    )


def parse_line_chunk(text: str, idx: int) -> LineCall | None:
    match = LINE_CLEAN_RE.search(text)
    if match is None:
        match = LINE_NARRATIVE_RE.search(text)
    if match is None:
        return None
    return _build_line_call(match, idx)
