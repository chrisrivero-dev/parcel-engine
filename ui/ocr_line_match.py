"""Qt-free helper for matching a SourceSpan's text to an OCR line.

Exports
-------
best_ocr_line_for_text(span_text, ocr_lines, *, threshold, min_tokens)
    Return the index of the best-matching OCRLine, or None.
"""

from __future__ import annotations

import re
from typing import List, Optional

# ---------------------------------------------------------------------------
# Internal normalisation
# ---------------------------------------------------------------------------

_DEGREE_WORDS = re.compile(
    r"\b(degrees?|deg)\b", re.IGNORECASE
)
_MINUTE_WORDS = re.compile(
    r"\b(minutes?|min)\b", re.IGNORECASE
)
_SECOND_WORDS = re.compile(
    r"\b(seconds?|sec)\b", re.IGNORECASE
)
_FEET_WORDS = re.compile(
    r"\b(feet|foot|ft)\b", re.IGNORECASE
)
_LINKS_WORDS = re.compile(
    r"\b(links?|lks?)\b", re.IGNORECASE
)
_CHAINS_WORDS = re.compile(
    r"\b(chains?|chs?)\b", re.IGNORECASE
)
_THENCE = re.compile(r"\bthence\b", re.IGNORECASE)
_NONWORD = re.compile(r"[^\w]+")

# Curly / typographic substitutions that OCR may or may not apply.
_CHAR_MAP = {
    "’": "'",  # right single quotation mark → '
    "‘": "'",  # left single quotation mark → '
    "“": '"',  # left double quotation mark → "
    "”": '"',  # right double quotation mark → "
    "º": "°",  # masculine ordinal indicator → °
    "˚": "°",  # ring above → °
    "–": "-",  # en dash → -
    "—": "-",  # em dash → -
}


def _normalise(text: str) -> str:
    """Lower, substitute degree-words and typographic chars, strip noise."""
    for bad, good in _CHAR_MAP.items():
        text = text.replace(bad, good)
    text = _DEGREE_WORDS.sub("°", text)
    text = _MINUTE_WORDS.sub("'", text)
    text = _SECOND_WORDS.sub('"', text)
    text = _FEET_WORDS.sub("ft", text)
    text = _LINKS_WORDS.sub("lk", text)
    text = _CHAINS_WORDS.sub("ch", text)
    text = _THENCE.sub("", text)
    text = text.lower()
    # collapse all non-word runs to space, trim
    text = _NONWORD.sub(" ", text).strip()
    return text


def _tokenise(text: str) -> List[str]:
    """Return non-empty word tokens from normalised text."""
    return [t for t in text.split() if t]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _token_recall(span_tokens: List[str], line_tokens: List[str]) -> float:
    """Fraction of span tokens present in line_tokens (order-independent)."""
    if not span_tokens:
        return 0.0
    line_set = set(line_tokens)
    hits = sum(1 for t in span_tokens if t in line_set)
    return hits / len(span_tokens)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def best_ocr_line_for_text(
    span_text: Optional[str],
    ocr_lines: list,
    *,
    threshold: float = 0.45,
    min_tokens: int = 4,
) -> Optional[int]:
    """Return the index of the OCRLine that best matches *span_text*, or None.

    Parameters
    ----------
    span_text:
        The ``SourceSpan.text`` extracted from the parsed legal description.
    ocr_lines:
        List of ``OCRLine`` objects (must have a ``.text`` attribute).
    threshold:
        Minimum token-recall score to accept a match.  0.45 was chosen to
        tolerate OCR noise while avoiding false positives on short fragments.
    min_tokens:
        Minimum number of tokens the *span* must produce before attempting a
        match.  Spans shorter than this (e.g. "N", "45°") nearly always false-
        match, so we return None immediately.

    Returns
    -------
    int or None
        Index into *ocr_lines* of the best match, or None if no confident
        match exists.
    """
    if not span_text or not ocr_lines:
        return None

    norm_span = _normalise(span_text)
    span_tokens = _tokenise(norm_span)

    if len(span_tokens) < min_tokens:
        return None

    best_idx: Optional[int] = None
    best_score: float = 0.0

    for i, ln in enumerate(ocr_lines):
        line_text = getattr(ln, "text", None) or ""
        if not line_text.strip():
            continue
        norm_line = _normalise(line_text)
        line_tokens = _tokenise(norm_line)
        score = _token_recall(span_tokens, line_tokens)
        if score > best_score:
            best_score = score
            best_idx = i

    if best_score >= threshold and best_idx is not None:
        return best_idx
    return None
