"""Tests for bearing-punctuation normalisation.

Covers OCR / transcription errors that appear in real deed scans while
leaving clean DMS bearings unchanged.  Direction-word typos (Fast, Bast)
are explicitly excluded per the branch scope.
"""

import pytest

from transcription.lines import _normalize_bearing_punct, parse_line_chunk
from transcription.parser_v2 import parse_legal_description


# ---------------------------------------------------------------------------
# Unit: _normalize_bearing_punct
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dirty, clean", [
    # stray leading apostrophe before degree digits
    ("South '50°00°00\" East", "South 50°00'00\" East"),
    # double-degree used as minutes separator
    ("South 50°00°00\" East",  "South 50°00'00\" East"),
    # double-quote used as minutes marker (with seconds)
    ("North 44°05\" 00\" East", "North 44°05' 00\" East"),
    ("North 77°31\" 30\" East", "North 77°31' 30\" East"),
    # double-quote as minutes marker (no seconds)
    ("NORTH 31°11\" EAST",      "NORTH 31°11' EAST"),
    # clean bearings are untouched
    ("SOUTH 47°45'30\" WEST",   "SOUTH 47°45'30\" WEST"),
    ("NORTH 58°49' WEST",       "NORTH 58°49' WEST"),
    ("N 0°00'00\" E",           "N 0°00'00\" E"),
])
def test_normalize_punct(dirty, clean):
    assert _normalize_bearing_punct(dirty) == clean


def test_normalize_is_idempotent():
    """Running normalisation twice gives the same result as once."""
    dirty = "South '50°00°00\" East"
    once = _normalize_bearing_punct(dirty)
    twice = _normalize_bearing_punct(once)
    assert once == twice


# ---------------------------------------------------------------------------
# Integration: parse_legal_description with dirty bearing punctuation
# ---------------------------------------------------------------------------

def _assert_call(text, ns, ew, deg, mn, sec, dist):
    calls, _, errors, _ = parse_legal_description(text)
    assert errors == [], f"unexpected errors for {text!r}: {errors}"
    assert len(calls) == 1, f"expected 1 call, got {len(calls)} for {text!r}"
    b = calls[0].bearing.value
    assert b.quadrant_ns == ns
    assert b.quadrant_ew == ew
    assert b.angle.deg == deg
    assert b.angle.minutes == mn
    assert b.angle.seconds == pytest.approx(sec, abs=0.01)
    assert calls[0].distance.value == pytest.approx(dist, abs=0.01)


def test_south_58_49_no_seconds_west():
    """SOUTH 58°49' WEST — already clean, confirmed unchanged."""
    _assert_call("THENCE SOUTH 58°49' WEST, 197.18 FEET", "S", "W", 58, 49, 0.0, 197.18)


def test_north_31_11_no_seconds_east():
    """NORTH 31°11' EAST — already clean, confirmed unchanged."""
    _assert_call("THENCE NORTH 31°11' EAST, 107 FEET", "N", "E", 31, 11, 0.0, 107.0)


def test_south_50_double_degree_east():
    """South 50°00°00\" East — second ° is a transcription error for '."""
    _assert_call("thence South 50°00°00\" East 135.00 feet", "S", "E", 50, 0, 0.0, 135.0)


def test_north_44_quote_as_minutes():
    """North 44°05\" 00\" East — first \" stands in for the minutes mark."""
    _assert_call("thence North 44°05\" 00\" East 81.13 feet", "N", "E", 44, 5, 0.0, 81.13)


def test_north_77_quote_as_minutes_with_seconds():
    """North 77°31\" 30\" East — \" as minutes marker, 30 as seconds."""
    _assert_call("North 77°31\" 30\" East 158.19 feet", "N", "E", 77, 31, 30.0, 158.19)


def test_south_stray_leading_apostrophe():
    """South '50°00°00\" East — stray leading apostrophe before degrees."""
    _assert_call("THENCE South '50°00°00\" East 200.00 feet", "S", "E", 50, 0, 0.0, 200.0)


# ---------------------------------------------------------------------------
# Regression: clean existing bearings unchanged
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, ns, ew, deg, mn, sec, dist", [
    ("THENCE SOUTH 47°45'30\" WEST, 120 FEET",    "S", "W", 47, 45, 30.0, 120.0),
    ("THENCE NORTH 60°29'30\" WEST 46.68 FEET",   "N", "W", 60, 29, 30.0,  46.68),
    ("THENCE SOUTH 49°21'40\" WEST 140.46 FEET",  "S", "W", 49, 21, 40.0, 140.46),
    ("THENCE N 45°00'00\" E a distance of 100.00 feet", "N", "E", 45,  0,  0.0, 100.0),
])
def test_existing_clean_bearings_unaffected(text, ns, ew, deg, mn, sec, dist):
    _assert_call(text, ns, ew, deg, mn, sec, dist)


# ---------------------------------------------------------------------------
# Guard: direction-word OCR typos are NOT inferred in this branch
# ---------------------------------------------------------------------------

def test_fast_direction_word_not_corrected():
    """'Fast' must not be silently treated as 'East'."""
    text = "THENCE NORTH 45°00'00\" Fast 100.00 FEET;"
    calls, _, _, _ = parse_legal_description(text)
    assert calls == []


def test_bast_direction_word_not_corrected():
    """'Bast' must not be silently treated as 'East'."""
    text = "THENCE NORTH 45°00'00\" Bast 100.00 FEET;"
    calls, _, _, _ = parse_legal_description(text)
    assert calls == []
