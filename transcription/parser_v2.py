from __future__ import annotations

from typing import Dict, List, Tuple

from models.schema import LineCall

from transcription.classify import (
    KIND_BOUNDARY,
    KIND_COMMENCEMENT,
    KIND_NOTE,
    KIND_REFERENCE_TIE,
    classify,
)
from transcription.normalize import normalize


def parse_legal_description(
    text: str,
) -> Tuple[List[LineCall], List[Dict], List[str]]:
    """
    Parse a metes-and-bounds legal description into:
      - calls: boundary LineCall list (in order, ready for build_geometry)
      - ties:  informational dicts (commencement legs and reference ties)
      - errors: unparsed clauses

    Curves, OCR images, and closure synthesis are out of scope.
    """
    normalized = normalize(text)
    chunks = classify(normalized)

    calls: List[LineCall] = []
    ties: List[Dict] = []
    errors: List[str] = []

    tie_idx = 1
    line_idx = 1

    for chunk in chunks:
        if chunk.kind == KIND_BOUNDARY:
            assert chunk.parsed_line is not None
            chunk.parsed_line.id = f"L{line_idx}"
            calls.append(chunk.parsed_line)
            line_idx += 1
        elif chunk.kind == KIND_COMMENCEMENT:
            if chunk.parsed_line is not None:
                chunk.parsed_line.id = f"RT{tie_idx}"
            ties.append(
                {
                    "id": f"RT{tie_idx}",
                    "kind": "commencement",
                    "raw_text": chunk.raw,
                    "parsed_line": chunk.parsed_line,
                }
            )
            tie_idx += 1
        elif chunk.kind == KIND_REFERENCE_TIE:
            ties.append(
                {
                    "id": f"RT{tie_idx}",
                    "kind": "reference_tie",
                    "raw_text": chunk.raw,
                    "parsed_line": None,
                }
            )
            tie_idx += 1
        elif chunk.kind == KIND_NOTE:
            upper = chunk.raw.upper()
            if any(
                k in upper
                for k in (
                    "COMMENCING",
                    "BEGINNING AT",
                    "POINT OF BEGINNING",
                    "TRACT",
                    "RECORDED",
                    "OFFICIAL RECORDS",
                    "MAP",
                    "COUNTY",
                    "LOT",
                    "SECTION",
                    "BLOCK",
                    "RIGHT-OF-WAY",
                    "RIGHT OF WAY",
                )
            ):
                continue
            errors.append(f"UNKNOWN_ELEMENT: '{chunk.raw}'")

    return calls, ties, errors
