from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from domain.source import SourceSpan
from models.schema import LineCall

from transcription.lines import parse_line_chunk

KIND_BOUNDARY = "BOUNDARY"
KIND_COMMENCEMENT = "COMMENCEMENT"
KIND_REFERENCE_TIE = "REFERENCE_TIE"
KIND_NOTE = "NOTE"


@dataclass
class Chunk:
    raw: str
    kind: str
    parsed_line: Optional[LineCall]
    source_span: Optional[SourceSpan] = field(default=None)


_TIE_KEYWORDS = ("SAID POINT BEING", "AS MEASURED ALONG")
_POB_RE = re.compile(r"\bPOINT\s+OF\s+BEGINNING\b", re.IGNORECASE)
_COMMENCING_RE = re.compile(r"\bCOMMENCING\b", re.IGNORECASE)
_THENCE_RE = re.compile(r"\bTHENCE\b", re.IGNORECASE)
_DISTANCE_FEET_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:feet|foot|ft)\b", re.IGNORECASE)


def _initial_phase(text: str) -> str:
    """If text has a COMMENCING preamble before the first THENCE, start pre-POB."""
    first_thence = _THENCE_RE.search(text)
    preamble = text[: first_thence.start()] if first_thence else text
    if _COMMENCING_RE.search(preamble):
        return "pre_pob"
    return "boundary"


def _split_clauses_with_spans(text: str) -> List[Tuple[str, int, int]]:
    """
    Split on semicolons and return (clause, start, end) triples.

    start/end are character offsets into the original `text` string
    (i.e. the normalized source text passed to classify()).
    """
    results: List[Tuple[str, int, int]] = []
    cursor = 0
    for segment in re.split(r";", text):
        stripped = segment.strip().rstrip(".").strip()
        if stripped:
            offset = segment.find(stripped)
            abs_start = cursor + offset
            abs_end = abs_start + len(stripped)
            results.append((stripped, abs_start, abs_end))
        cursor += len(segment) + 1  # +1 for the ";" separator
    return results


def classify(text: str) -> List[Chunk]:
    phase = _initial_phase(text)
    chunks: List[Chunk] = []
    idx = 1

    for clause, span_start, span_end in _split_clauses_with_spans(text):
        span = SourceSpan(start=span_start, end=span_end, text=clause)
        upper = clause.upper()

        is_tie_keyword = any(k in upper for k in _TIE_KEYWORDS)
        if is_tie_keyword:
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
            # Tie keyword without measurement → just a monument description.
            chunks.append(Chunk(raw=clause, kind=KIND_NOTE, parsed_line=None, source_span=span))
            continue

        parsed = parse_line_chunk(clause, idx)

        if parsed is None:
            chunks.append(Chunk(raw=clause, kind=KIND_NOTE, parsed_line=None, source_span=span))
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
