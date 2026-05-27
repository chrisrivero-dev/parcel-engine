"""Pure source-text section splitter for legal descriptions.

This module is a *pre-parse* foundation: it slices a raw legal-description
string into structured sections (parcels, easements, exhibits, commencement,
boilerplate) so that future workflows can route each section independently.

It deliberately does NOT parse geometry, infer calls, or alter the original
text beyond slicing.  ``parse_legal_description`` is untouched by this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class LegalTextSection:
    label: str
    section_type: str
    text: str
    start: int
    end: int


# Section types (simple string constants).
TYPE_BOILERPLATE = "boilerplate"
TYPE_COMMENCEMENT = "commencement"
TYPE_PARCEL = "parcel"
TYPE_EASEMENT = "easement"
TYPE_EXHIBIT = "exhibit"
TYPE_UNKNOWN = "unknown"


# Major section headers.  Easement alternatives are listed first so that a
# phrase like "EASEMENT PARCEL 1" is consumed as a single easement header
# rather than being split by the generic PARCEL pattern.
_HEADER_RE = re.compile(
    r"""
    (?P<easement>
        (?:NON[-\s]?EXCLUSIVE\s+EASEMENT)
      | (?:ACCESS\s+EASEMENT)
      | (?:EASEMENT\s+PARCEL(?:\s+(?:NO\.?\s+)?(?:\d+|[A-Z]\b))?)
    )
  | (?P<exhibit>
        EXHIBIT\s+[A-Z0-9]+\b
    )
  | (?P<parcel>
        PARCEL\s+
        (?:NO\.?\s+)?
        (?:\d+|[A-Z]\b|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)
        \b
        \s*:?
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# True-point-of-beginning transition phrases (greedy → longest form wins).
_POB_RE = re.compile(
    r"(?:THE\s+)?TRUE\s+POINT\s+OF\s+BEGINNING(?:\s+OF\s+THE\s+BOUNDARY)?"
    r"|POINT\s+OF\s+BEGINNING\s+OF\s+THE\s+BOUNDARY",
    re.IGNORECASE,
)


def _clean_label(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip().rstrip(":").strip().upper()


def _header_type(match: re.Match) -> str:
    if match.group("easement"):
        return TYPE_EASEMENT
    if match.group("exhibit"):
        return TYPE_EXHIBIT
    return TYPE_PARCEL


def _at_section_boundary(text: str, pos: int) -> bool:
    """Return True when *pos* is a safe place to start a section header.

    Safe positions: start of text, after a newline/tab, or after sentence-
    ending punctuation (. ; : ! ?) optionally followed by horizontal
    whitespace.  This prevents mid-sentence "PARCEL" occurrences without
    boundary punctuation from being treated as headers.
    """
    if pos == 0:
        return True
    look = pos - 1
    while look >= 0 and text[look] in " \t":
        look -= 1
    return look < 0 or text[look] in ".\n;:!?"


def _absorb_punctuation_bridges(
    sections: List[LegalTextSection],
) -> List[LegalTextSection]:
    """Fold punctuation-only UNKNOWN sections into the preceding section.

    When the POB phrase ends just before a section header (e.g. "…BEGINNING.
    PARCEL 1:"), the period-space between them becomes a tiny BOUNDARY slice.
    Absorbing it backward into the commencement/boilerplate keeps the list
    clean while preserving the concatenation invariant.
    """
    _PUNCT_ONLY = re.compile(r"^[\s.;,:!?]+$")
    result: List[LegalTextSection] = []
    for sec in sections:
        if (
            result
            and sec.section_type == TYPE_UNKNOWN
            and _PUNCT_ONLY.match(sec.text)
        ):
            prev = result[-1]
            result[-1] = LegalTextSection(
                label=prev.label,
                section_type=prev.section_type,
                text=prev.text + sec.text,
                start=prev.start,
                end=sec.end,
            )
        else:
            result.append(sec)
    return result


def split_legal_text_sections(text: str) -> List[LegalTextSection]:
    """Split ``text`` into ordered :class:`LegalTextSection` slices.

    Sections are contiguous: concatenating ``section.text`` in returned order
    reproduces the original input exactly.  Whitespace-only or empty input
    returns an empty list.
    """
    if not text or not text.strip():
        return []

    headers = [
        h for h in _HEADER_RE.finditer(text)
        if _at_section_boundary(text, h.start())
    ]
    header_starts = {h.start(): h for h in headers}

    lead_end = headers[0].start() if headers else len(text)
    pob = _POB_RE.search(text, 0, lead_end)
    pob_end = pob.end() if pob else None

    cuts = {0, len(text)}
    if pob_end is not None:
        cuts.add(pob_end)
    for h in headers:
        cuts.add(h.start())
    ordered_cuts = sorted(c for c in cuts if 0 <= c <= len(text))

    sections: List[LegalTextSection] = []
    for a, b in zip(ordered_cuts, ordered_cuts[1:]):
        if a == b:
            continue
        label, stype = _classify(a, header_starts, pob_end)
        sections.append(LegalTextSection(label, stype, text[a:b], a, b))

    return _absorb_punctuation_bridges(_merge_leading_whitespace(sections))


def _classify(
    start: int,
    header_starts: dict,
    pob_end: Optional[int],
) -> tuple[str, str]:
    header = header_starts.get(start)
    if header is not None:
        return _clean_label(header.group()), _header_type(header)
    if pob_end is not None:
        if start == 0:
            return "COMMENCEMENT", TYPE_COMMENCEMENT
        if start == pob_end:
            return "BOUNDARY", TYPE_UNKNOWN
    if start == 0:
        return "BOILERPLATE", TYPE_BOILERPLATE
    return "BOUNDARY", TYPE_UNKNOWN


def _merge_leading_whitespace(
    sections: List[LegalTextSection],
) -> List[LegalTextSection]:
    """Fold a whitespace-only leading slice into the next section.

    Keeps concatenation exact while avoiding an empty-looking first section
    when the source begins with stray newlines before a header.
    """
    if len(sections) >= 2 and not sections[0].text.strip():
        head, nxt = sections[0], sections[1]
        merged = LegalTextSection(
            label=nxt.label,
            section_type=nxt.section_type,
            text=head.text + nxt.text,
            start=head.start,
            end=nxt.end,
        )
        return [merged] + sections[2:]
    return sections
