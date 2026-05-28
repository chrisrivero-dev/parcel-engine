"""Tests for OCR-grade DMS punctuation cleanup.

Covers corruption modes seen in real deed scans: stray glyphs sitting where
', " or ° belong, and decimal comma in distances.  Direction-word typos
(Eagt, Fast, Bast) remain explicitly out of scope for this branch.
"""

import pytest

from transcription.lines import _normalize_bearing_punct, parse_line_chunk
from transcription.parser_v2 import parse_legal_description


def _assert_call(text, ns, ew, deg, mn, sec, dist):
    calls, _, errors, _ = parse_legal_description(text)
    assert errors == [], f"unexpected errors for {text!r}: {errors}"
    assert len(calls) == 1, f"expected 1 call for {text!r}, got {len(calls)}"
    b = calls[0].bearing.value
    assert b.quadrant_ns == ns
    assert b.quadrant_ew == ew
    assert b.angle.deg == deg
    assert b.angle.minutes == mn
    assert b.angle.seconds == pytest.approx(sec, abs=0.01)
    assert calls[0].distance.value == pytest.approx(dist, abs=0.01)


# ---------------------------------------------------------------------------
# Required dirty-OCR examples → parse cleanly
# ---------------------------------------------------------------------------

def test_double_quote_degree_and_paren_minutes_and_decimal_comma():
    _assert_call(
        "THENCE SOUTH 65\" 36) 12\" EAST 20,00 FEET",
        "S", "E", 65, 36, 12.0, 20.00,
    )


def test_cent_glyph_minutes_and_percent_seconds():
    _assert_call(
        "THENCE SOUTH 16°35¢ 20% WEST 20.00 FEET",
        "S", "W", 16, 35, 20.0, 20.00,
    )


def test_bang_glyph_minutes_and_decimal_comma_distance():
    _assert_call(
        "THENCE SOUTH 53°38! 00\" WEST 90,43 FEET",
        "S", "W", 53, 38, 0.0, 90.43,
    )


def test_asterisk_glyph_minutes():
    _assert_call(
        "THENCE NORTH 56°22* 00\" WEST 169.53 FEET",
        "N", "W", 56, 22, 0.0, 169.53,
    )


def test_bang_glyph_minutes_clean_distance():
    _assert_call(
        "THENCE SOUTH 81°15! 00\" EAST 92.34 FEET",
        "S", "E", 81, 15, 0.0, 92.34,
    )


# ---------------------------------------------------------------------------
# Unit tests for _normalize_bearing_punct directly
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dirty, clean", [
    ("65\" 36) 12\"",  "65° 36' 12\""),
    ("16°35¢ 20%",     "16°35' 20\""),
    ("53°38! 00\"",    "53°38' 00\""),
    ("56°22* 00\"",    "56°22' 00\""),
    ("81°15! 00\"",    "81°15' 00\""),
    # distance comma
    ("20,00 feet",     "20.00 feet"),
    ("90,43 FEET",     "90.43 FEET"),
    # clean text untouched
    ("S 45°30'10\" E", "S 45°30'10\" E"),
    ("NORTH 31°11' EAST", "NORTH 31°11' EAST"),
])
def test_normalize_punct(dirty, clean):
    assert _normalize_bearing_punct(dirty) == clean


def test_normalize_is_idempotent():
    dirty = "SOUTH 65\" 36) 12\" EAST 20,00"
    once = _normalize_bearing_punct(dirty)
    assert _normalize_bearing_punct(once) == once


def test_thousands_separator_in_distance_is_not_decimalised():
    """A 3-digit fractional part is treated as thousands, never as decimals."""
    assert _normalize_bearing_punct("1,234 feet") == "1,234 feet"


def test_real_seconds_quote_is_not_treated_as_degree_marker():
    """A genuine seconds " followed by digits must not be rewritten to °."""
    src = "SOUTH 45°30'10\" EAST 100.00 FEET"
    assert _normalize_bearing_punct(src) == src


# ---------------------------------------------------------------------------
# Explicit unsafe cases — must remain unparsed in this branch
# ---------------------------------------------------------------------------

def test_eagt_typo_not_corrected_to_east():
    text = "THENCE SOUTH 81°15! 00\" Eagt 92.34 feet"
    calls, _, _, _ = parse_legal_description(text)
    assert calls == []


def test_fast_typo_not_corrected_to_east():
    text = "THENCE NORTH 45°00'00\" Fast 100.00 FEET;"
    calls, _, _, _ = parse_legal_description(text)
    assert calls == []


def test_bast_typo_not_corrected_to_east():
    text = "THENCE NORTH 45°00'00\" Bast 100.00 FEET;"
    calls, _, _, _ = parse_legal_description(text)
    assert calls == []


def test_currency_glyph_and_garbled_unit_remains_unparsed():
    """'$2018 reets' is too corrupted — no fabricated distance."""
    text = "THENCE SOUTH 57°19°06) $2018 reets"
    calls, _, _, _ = parse_legal_description(text)
    assert calls == []
