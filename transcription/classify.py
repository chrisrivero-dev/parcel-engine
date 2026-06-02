from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from domain.source import SourceSpan
from models.schema import CurveCall, LineCall

from transcription.curves import parse_curve_chunk
from transcription.lines import has_bearing, parse_line_chunk

KIND_BOUNDARY = "BOUNDARY"
KIND_COMMENCEMENT = "COMMENCEMENT"
KIND_REFERENCE_TIE = "REFERENCE_TIE"
KIND_NOTE = "NOTE"


@dataclass
class Chunk:
    raw: str
    kind: str
    parsed_line: Optional[LineCall | CurveCall]
    source_span: Optional[SourceSpan] = field(default=None)


_TIE_KEYWORDS = ("SAID POINT BEING", "AS MEASURED ALONG")
_POB_RE = re.compile(r"\bPOINT\s+OF\s+BEGINNING\b", re.IGNORECASE)
_COMMENCING_RE = re.compile(r"\bCOMMENCING\b", re.IGNORECASE)
_THENCE_RE = re.compile(r"\bTHENCE\b", re.IGNORECASE)
_DISTANCE_FEET_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:feet|foot|ft)\b", re.IGNORECASE)

# Reference / locating language: a measurement that *positions* the POB
# relative to a known monument, line, or corner — NOT a drawable boundary
# course.  Keys on a tail "FROM ..." anchor so generic verbs (BEING,
# DISTANT, MEASURED ALONG) cannot match unless paired with a true tie.
_FROM_CORNER_RE = re.compile(
    r"\bFROM\s+THE\s+[A-Z]+(?:\s+[A-Z]+)?\s+CORNER\b",
    re.IGNORECASE,
)
_FROM_POB_RE = re.compile(
    r"\bFROM\s+THE\s+POINT\s+OF\s+BEGINNING\b",
    re.IGNORECASE,
)
_DISTANT_FROM_RE = re.compile(
    r"\bDISTANT\b[^.;]{0,120}\bFROM\b",
    re.IGNORECASE,
)
_MEASURED_FROM_RE = re.compile(
    r"\bMEASURED\s+ALONG\b[^.;]{0,120}\bFROM\b",
    re.IGNORECASE,
)
_BEING_FROM_RE = re.compile(
    r"\bBEING\b[^.;]{0,120}\bFROM\b",
    re.IGNORECASE,
)
_REFERENCE_TIE_REGEXES = (
    _FROM_CORNER_RE,
    _FROM_POB_RE,
    _DISTANT_FROM_RE,
    _MEASURED_FROM_RE,
    _BEING_FROM_RE,
)


def _looks_like_reference_tie(clause: str) -> bool:
    """True when a clause is a pre-boundary locator, not a drawable course.

    A clause that begins with THENCE is always a boundary call — even when
    its descriptive context happens to mention "FROM THE POINT OF
    BEGINNING".  Otherwise, any of the reference-tie patterns marks it as
    a locator/tie.
    """
    stripped = clause.strip().upper()
    if stripped.startswith("THENCE"):
        return False
    return any(rx.search(clause) for rx in _REFERENCE_TIE_REGEXES)


def _initial_phase(text: str) -> str:
    """If text has a COMMENCING preamble before the first THENCE, start pre-POB."""
    first_thence = _THENCE_RE.search(text)
    preamble = text[: first_thence.start()] if first_thence else text
    if _COMMENCING_RE.search(preamble):
        return "pre_pob"
    return "boundary"


def _split_on_internal_thence(
    clause: str, abs_start: int
) -> List[Tuple[str, int, int]]:
    """Split a clause on any internal THENCE so each call has its own clause.

    Legal descriptions sometimes chain a POB setup with the first boundary
    course inside a single comma-separated sentence ("BEGINNING AT ..., S
    5° W 25 FT FROM THE NE CORNER, THENCE S 5° W 200 FT").  A leading
    THENCE is left intact; only THENCE occurrences strictly inside the
    clause cause a split, and the THENCE is preserved at the head of the
    new sub-clause so the existing boundary parser still sees it.
    """
    matches = list(re.finditer(r"\bTHENCE\b", clause, re.IGNORECASE))
    internal = [m.start() for m in matches if m.start() > 0]
    if not internal:
        return [(clause, abs_start, abs_start + len(clause))]
    cuts = [0] + internal + [len(clause)]
    pieces: List[Tuple[str, int, int]] = []
    for a, b in zip(cuts, cuts[1:]):
        raw = clause[a:b]
        stripped = raw.strip().rstrip(",").rstrip(".").rstrip(";").strip()
        if not stripped:
            continue
        offset = raw.find(stripped)
        s = abs_start + a + offset
        pieces.append((stripped, s, s + len(stripped)))
    return pieces


def _split_clauses_with_spans(text: str) -> List[Tuple[str, int, int]]:
    """
    Split on semicolons (and then on sentence-internal THENCE) and return
    (clause, start, end) triples.

    start/end are character offsets into the original `text` string (i.e.
    the normalized source text passed to classify()).
    """
    results: List[Tuple[str, int, int]] = []
    cursor = 0
    for segment in re.split(r";", text):
        stripped = segment.strip().rstrip(".").strip()
        if stripped:
            offset = segment.find(stripped)
            abs_start = cursor + offset
            results.extend(_split_on_internal_thence(stripped, abs_start))
        cursor += len(segment) + 1  # +1 for the ";" separator
    return results


def _rejoin_ocr_fragments(
    clauses: List[Tuple[str, int, int]]
) -> List[Tuple[str, int, int]]:
    """Rejoin a THENCE call that OCR split across a stray semicolon.

    When a clause carries a valid bearing but does not parse (because the
    distance was pushed into the following fragment), and the next fragment
    is a pure continuation -- no THENCE, no bearing of its own, but does
    contain a distance -- the two are merged with a space so the line
    parser can recover the full bearing+distance call. The merge is only
    accepted if the joined text actually parses, so context-only fragments
    are left untouched. Joining is bounded to a single following fragment.
    """
    merged: List[Tuple[str, int, int]] = []
    i = 0
    n = len(clauses)
    while i < n:
        text, start, end = clauses[i]
        if (
            i + 1 < n
            and has_bearing(text)
            and parse_line_chunk(text, 0) is None
        ):
            next_text, _, next_end = clauses[i + 1]
            if (
                not _THENCE_RE.search(next_text)
                and not has_bearing(next_text)
                and _DISTANCE_FEET_RE.search(next_text)
            ):
                joined = f"{text} {next_text}"
                if parse_line_chunk(joined, 0) is not None:
                    merged.append((joined, start, next_end))
                    i += 2
                    continue
        merged.append((text, start, end))
        i += 1
    return merged


def classify(text: str) -> List[Chunk]:
    phase = _initial_phase(text)
    chunks: List[Chunk] = []
    idx = 1

    for clause, span_start, span_end in _rejoin_ocr_fragments(
        _split_clauses_with_spans(text)
    ):
        span = SourceSpan(start=span_start, end=span_end, text=clause)
        upper = clause.upper()

        is_tie_keyword = any(k in upper for k in _TIE_KEYWORDS)
        is_reference_tie = _looks_like_reference_tie(clause)
        if is_tie_keyword or is_reference_tie:
            tie_parsed = parse_line_chunk(clause, idx)
            if tie_parsed is not None or _DISTANCE_FEET_RE.search(clause):
                chunks.append(
                    Chunk(
                        raw=clause,
                        kind=KIND_REFERENCE_TIE,
                        parsed_line=tie_parsed,
                        source_span=span,
                    )
                )
                continue
            # Tie phrase without measurement → just a monument description.
            chunks.append(Chunk(raw=clause, kind=KIND_NOTE, parsed_line=None, source_span=span))
            continue

        parsed = parse_line_chunk(clause, idx)
        if parsed is None:
            parsed = parse_curve_chunk(clause, idx)

        if parsed is None:
            chunks.append(Chunk(raw=clause, kind=KIND_NOTE, parsed_line=None, source_span=span))

            if phase == "pre_pob" and _POB_RE.search(clause):
                phase = "boundary"

            continue

        if phase == "pre_pob":
            chunks.append(
                Chunk(raw=clause, kind=KIND_COMMENCEMENT, parsed_line=parsed, source_span=span)
            )
            if _POB_RE.search(clause):
                phase = "boundary"
        else:
            chunks.append(Chunk(raw=clause, kind=KIND_BOUNDARY, parsed_line=parsed, source_span=span))
            idx += 1
            continue

        idx += 1

    return chunks
