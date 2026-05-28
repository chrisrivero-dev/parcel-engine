"""Tests for ``transcription.suggestions``.

Suggestions are reviewable candidates only — these tests confirm the
helper produces the documented bearing/confidence/reason for each
supported shape, and refuses to fabricate geometry for unsupported
shapes.
"""

import pytest

from transcription.parser_v2 import parse_legal_description
from transcription.suggestions import (
    ResolutionSuggestion,
    explain_unsuggestable,
    suggest_resolution,
)


def _unresolved(text):
    _, _, _, ignored = parse_legal_description(text)
    return [c for c in ignored if c["type"] == "Unresolved Direction-Only Call"]


# ---------------------------------------------------------------------------
# Cardinal direction + distance → medium-confidence suggestion
# ---------------------------------------------------------------------------

def test_northerly_with_distance_suggests_due_north():
    entry = _unresolved("THENCE NORTHERLY 52 FEET ALONG THE CURVE")[0]
    sug = suggest_resolution(entry)
    assert sug is not None
    assert sug.quadrant_ns == "N" and sug.quadrant_ew == "E"
    assert (sug.deg, sug.minutes, sug.seconds) == (0, 0, 0.0)
    assert sug.distance == pytest.approx(52.0)
    assert sug.confidence == "medium"
    assert sug.direction == "NORTHERLY"
    assert "NORTHERLY" in sug.reason
    assert sug.original_text


def test_southerly_with_distance_suggests_due_south():
    entry = _unresolved("THENCE SOUTHERLY 20 FEET TO A POINT")[0]
    sug = suggest_resolution(entry)
    assert sug is not None
    assert sug.quadrant_ns == "S" and sug.quadrant_ew == "W"
    assert (sug.deg, sug.minutes, sug.seconds) == (0, 0, 0.0)
    assert sug.distance == pytest.approx(20.0)
    assert sug.confidence == "medium"


def test_easterly_with_distance_suggests_due_east():
    entry = _unresolved("THENCE EASTERLY 120 FEET")[0]
    sug = suggest_resolution(entry)
    assert sug is not None
    assert sug.quadrant_ns == "N" and sug.quadrant_ew == "E"
    assert sug.deg == 90 and sug.minutes == 0 and sug.seconds == 0.0
    assert sug.distance == pytest.approx(120.0)
    assert sug.confidence == "medium"


def test_westerly_with_distance_suggests_due_west():
    entry = _unresolved("THENCE WESTERLY 75 FEET")[0]
    sug = suggest_resolution(entry)
    assert sug is not None
    assert sug.quadrant_ns == "N" and sug.quadrant_ew == "W"
    assert sug.deg == 90
    assert sug.distance == pytest.approx(75.0)
    assert sug.confidence == "medium"


def test_plain_north_word_also_suggests():
    """NORTH (not NORTHERLY) gets the same cardinal suggestion."""
    entry = _unresolved("THENCE NORTH 40 FEET")[0]
    sug = suggest_resolution(entry)
    assert sug is not None
    assert sug.quadrant_ns == "N"
    assert sug.confidence == "medium"


# ---------------------------------------------------------------------------
# Intercardinal direction + distance → low-confidence 45° suggestion
# ---------------------------------------------------------------------------

def test_northeasterly_with_distance_suggests_low_confidence_45():
    entry = _unresolved("THENCE NORTHEASTERLY 80 FEET")[0]
    sug = suggest_resolution(entry)
    assert sug is not None
    assert sug.quadrant_ns == "N" and sug.quadrant_ew == "E"
    assert sug.deg == 45 and sug.minutes == 0
    assert sug.confidence == "low"
    assert "45" in sug.reason


def test_southwesterly_with_distance_suggests_low_confidence_45():
    entry = _unresolved("THENCE SOUTHWESTERLY 65 FEET")[0]
    sug = suggest_resolution(entry)
    assert sug is not None
    assert sug.quadrant_ns == "S" and sug.quadrant_ew == "W"
    assert sug.deg == 45
    assert sug.confidence == "low"


def test_northwest_plain_intercardinal():
    entry = _unresolved("THENCE NORTHWEST 100 FEET")[0]
    sug = suggest_resolution(entry)
    assert sug is not None
    assert sug.quadrant_ns == "N" and sug.quadrant_ew == "W"
    assert sug.deg == 45
    assert sug.confidence == "low"


# ---------------------------------------------------------------------------
# Refusals — no fabricated geometry
# ---------------------------------------------------------------------------

def test_no_distance_returns_none():
    entry = _unresolved("THENCE WESTERLY TO A POINT ON THE EAST LINE")[0]
    assert suggest_resolution(entry) is None
    msg = explain_unsuggestable(entry)
    assert "Manual resolution required" in msg


def test_unknown_direction_returns_none():
    """A made-up direction word never produces a suggestion."""
    entry = {
        "type": "Unresolved Direction-Only Call",
        "text": "THENCE INWARDLY 30 FEET",
        "direction": "INWARDLY",
        "distance": 30.0,
        "source_span": None,
    }
    assert suggest_resolution(entry) is None
    assert "INWARDLY" in explain_unsuggestable(entry)


def test_empty_entry_returns_none():
    assert suggest_resolution({}) is None


# ---------------------------------------------------------------------------
# Bearing text rendering
# ---------------------------------------------------------------------------

def test_bearing_text_for_cardinal():
    entry = _unresolved("THENCE EASTERLY 10 FEET")[0]
    sug = suggest_resolution(entry)
    assert isinstance(sug, ResolutionSuggestion)
    assert sug.bearing_text() == "N 90°00'00\" E"


def test_bearing_text_for_intercardinal():
    entry = _unresolved("THENCE SOUTHEASTERLY 10 FEET")[0]
    sug = suggest_resolution(entry)
    assert sug.bearing_text() == "S 45°00'00\" E"


# ---------------------------------------------------------------------------
# Suggestion is pure — does not mutate input
# ---------------------------------------------------------------------------

def test_suggest_does_not_mutate_entry():
    entry = dict(_unresolved("THENCE EASTERLY 50 FEET")[0])
    snapshot = dict(entry)
    suggest_resolution(entry)
    assert entry == snapshot
