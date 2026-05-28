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

# ---------------------------------------------------------------------------
# OCR / punctuation normalisation for DMS bearings
# ---------------------------------------------------------------------------
#
# Each substitution is idempotent on clean text so normalised == original for
# well-formed input.  These run only as a fallback after the primary parser
# regexes have already failed.
#
# 1. Stray apostrophe before the degree digits: "South '50°…" → "South 50°…"
_STRAY_APOSTROPHE_RE = re.compile(r"(?<!\d)'(?=\d{1,3}°)")

# 2. OCR replaced the degree mark ° with a double-quote.  Only treat the
#    quote as a degree marker when an obvious DMS structure follows (digits
#    plus another marker).  A lookbehind guards against rewriting a real
#    seconds-mark by requiring the digits aren't preceded by ° or ' .
_DEGREE_QUOTE_FIX_RE = re.compile(
    r"(?<![\d°'])(\d{1,3})\"(?=\s*\d{1,2}\s*[°'\"!)¢*%])"
)

# 3. Second °-symbol used as minutes separator: 50°00°00" → 50°00'00"
_DOUBLE_DEGREE_RE = re.compile(r"(\d{1,3}°\s*\d{1,2})\s*°")

# 4. First "-symbol used as minutes marker when no ' precedes it: 31°11" → 31°11'
_QUOTE_AS_MINUTES_RE = re.compile(r'(\d{1,3}°\s*\d{1,2})\s*"')

# 5. Stray minute marker — OCR glyphs ! ) ¢ * sitting where ' belongs.
_STRAY_MINUTE_MARKER_RE = re.compile(r"(\d{1,3}°\s*\d{1,2})\s*[!)¢*]")

# 6. Stray seconds marker — % sitting where " belongs, only after a minutes ' .
_STRAY_SECONDS_MARKER_RE = re.compile(r"(\d{1,3}°\s*\d{1,2}\s*'\s*\d{1,2})\s*%")

# 7. Decimal comma in distance values: "20,00 feet" → "20.00 feet".  Strictly
#    bounded so a thousands separator (e.g. "1,234 feet") never matches.
_DISTANCE_DECIMAL_COMMA_RE = re.compile(
    r"(\d{1,4}),(\d{1,2})(?=\s*(?:feet|foot|ft)\b)",
    re.IGNORECASE,
)


def _normalize_bearing_punct(text: str) -> str:
    """Fix common OCR/transcription errors in DMS bearing punctuation.

    Order matters: degree-quote fix runs before the minute-marker fixes so a
    misread degree mark is restored before downstream patterns try to match
    around it.  Idempotent on clean text.  Direction-word typos (Fast, Bast,
    Eagt, etc.) are deliberately NOT corrected — those require a separate
    OCR-correction pass with explicit warnings.
    """
    text = _STRAY_APOSTROPHE_RE.sub("", text)
    text = _DEGREE_QUOTE_FIX_RE.sub(r"\1°", text)
    text = _DOUBLE_DEGREE_RE.sub(r"\1'", text)
    text = _QUOTE_AS_MINUTES_RE.sub(r"\1'", text)
    text = _STRAY_MINUTE_MARKER_RE.sub(r"\1'", text)
    text = _STRAY_SECONDS_MARKER_RE.sub(r'\1"', text)
    text = _DISTANCE_DECIMAL_COMMA_RE.sub(r"\1.\2", text)
    return text


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

# Standalone bearing detector: matches a complete quadrant bearing anywhere
# in the text. Used to decide whether a clause already carries its own
# bearing (so the OCR-fragment rejoin pass does not merge two real calls).
BEARING_RE = re.compile(_BEARING, re.IGNORECASE | re.VERBOSE)


def has_bearing(text: str) -> bool:
    if BEARING_RE.search(text) is not None:
        return True
    normalized = _normalize_bearing_punct(text)
    return normalized != text and BEARING_RE.search(normalized) is not None

LINE_NARRATIVE_RE = re.compile(
    _BEARING + r"""
    \s+[A-Za-z][^,]{0,160}?,?\s+
    (?P<dist>\d+(?:\.\d+)?)
    \s+(?:feet|foot|ft)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Deed-style clauses where the bearing and distance are separated by a
# longer context phrase that may itself contain commas, e.g.
#   SOUTH 47°45'30" WEST, ALONG THE SOUTHERLY LINE OF SAID LAND, 120 FEET
# The context body forbids digits and semicolons so we cannot accidentally
# skip past the real distance or cross a clause boundary, and the
# mandatory feet/foot/ft anchor prevents grabbing area or count tokens
# (e.g. "10 ACRES") that happen to appear in the context.
LINE_DEED_RE = re.compile(
    _BEARING + r"""
    \s*,?\s*
    (?P<context>[^\d;]{1,250}?)
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


def _match_bearing(text: str) -> re.Match | None:
    m = LINE_CLEAN_RE.search(text)
    if m is None:
        m = LINE_NARRATIVE_RE.search(text)
    if m is None:
        m = LINE_DEED_RE.search(text)
    return m


def parse_line_chunk(text: str, idx: int) -> LineCall | None:
    match = _match_bearing(text)
    if match is None:
        normalized = _normalize_bearing_punct(text)
        if normalized != text:
            match = _match_bearing(normalized)
    if match is None:
        return None
    return _build_line_call(match, idx)
