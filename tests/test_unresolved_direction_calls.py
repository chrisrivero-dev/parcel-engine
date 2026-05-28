"""Tests for unresolved direction-only call detection.

Clauses such as "THENCE WESTERLY TO A POINT" or
"THENCE NORTHERLY 52 FEET ALONG THE CURVE" carry a direction word
but no numeric DMS bearing.  They must appear in ignored_chunks as
"Unresolved Direction-Only Call" and must NOT appear in calls, ties,
or errors.
"""

import pytest

from transcription.parser_v2 import parse_legal_description


def _unresolved(ignored):
    return [c for c in ignored if c["type"] == "Unresolved Direction-Only Call"]


# ---------------------------------------------------------------------------
# Basic detection
# ---------------------------------------------------------------------------

def test_thence_westerly_no_distance():
    """Bare direction word without distance → unresolved, no error emitted."""
    calls, _, errors, ignored = parse_legal_description(
        "THENCE WESTERLY TO A POINT ON THE EAST LINE"
    )
    assert calls == []
    assert errors == []
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    assert unresolved[0]["direction"] == "WESTERLY"
    assert unresolved[0]["distance"] is None


def test_thence_northerly_with_distance():
    """Direction word plus distance → distance captured, not in errors."""
    calls, _, errors, ignored = parse_legal_description(
        "THENCE NORTHERLY 52 FEET ALONG THE CURVE"
    )
    assert calls == []
    assert errors == []
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    assert unresolved[0]["direction"] == "NORTHERLY"
    assert unresolved[0]["distance"] == pytest.approx(52.0)


def test_thence_southeasterly():
    """Compound intercardinal direction word is detected."""
    calls, _, errors, ignored = parse_legal_description(
        "THENCE SOUTHEASTERLY TO THE TRUE POINT OF BEGINNING"
    )
    assert errors == []
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    assert unresolved[0]["direction"] == "SOUTHEASTERLY"


def test_thence_northwest_plain():
    """Plain intercardinal without -ERLY suffix is detected."""
    calls, _, errors, ignored = parse_legal_description(
        "THENCE NORTHWEST 100 FEET"
    )
    assert errors == []
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    assert unresolved[0]["direction"] == "NORTHWEST"
    assert unresolved[0]["distance"] == pytest.approx(100.0)


def test_thence_southerly_with_distance():
    """SOUTHERLY + distance captured correctly."""
    calls, _, errors, ignored = parse_legal_description(
        "THENCE SOUTHERLY 30 FEET TO A POINT"
    )
    assert errors == []
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    assert unresolved[0]["direction"] == "SOUTHERLY"
    assert unresolved[0]["distance"] == pytest.approx(30.0)


def test_thence_northwesterly():
    """NORTHWESTERLY (longest compound) matched, not just NORTH."""
    calls, _, errors, ignored = parse_legal_description(
        "THENCE NORTHWESTERLY TO A MONUMENT"
    )
    assert errors == []
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    assert unresolved[0]["direction"] == "NORTHWESTERLY"


# ---------------------------------------------------------------------------
# Does NOT fire on a well-formed DMS call
# ---------------------------------------------------------------------------

def test_full_dms_bearing_not_unresolved():
    """A call with a full DMS bearing parses normally; no unresolved entry."""
    calls, _, errors, ignored = parse_legal_description(
        "THENCE SOUTH 45°30'00\" EAST 100.00 FEET"
    )
    assert len(calls) == 1
    assert errors == []
    assert _unresolved(ignored) == []


def test_north_in_full_dms_call_not_unresolved():
    """'NORTH' that begins a full DMS call does not trigger direction-only."""
    calls, _, errors, ignored = parse_legal_description(
        "THENCE NORTH 30°15'00\" EAST 200.00 FEET"
    )
    assert len(calls) == 1
    assert _unresolved(ignored) == []


# ---------------------------------------------------------------------------
# Multiple clauses — only direction-only ones are flagged
# ---------------------------------------------------------------------------

def test_mixed_description_flags_only_direction_only():
    """One real call + one direction-only → one parsed call, one unresolved."""
    text = (
        "THENCE SOUTH 45°30'00\" EAST 100.00 FEET; "
        "THENCE NORTHWESTERLY TO A MONUMENT"
    )
    calls, _, errors, ignored = parse_legal_description(text)
    assert len(calls) == 1
    assert errors == []
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    assert unresolved[0]["direction"] == "NORTHWESTERLY"


def test_two_direction_only_clauses():
    """Two consecutive direction-only clauses each produce an entry."""
    text = (
        "THENCE EASTERLY TO THE CENTERLINE; "
        "THENCE NORTHERLY ALONG SAID CENTERLINE 75 FEET"
    )
    calls, _, errors, ignored = parse_legal_description(text)
    assert calls == []
    assert errors == []
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 2
    directions = {e["direction"] for e in unresolved}
    assert "EASTERLY" in directions
    assert "NORTHERLY" in directions


# ---------------------------------------------------------------------------
# Metadata fields
# ---------------------------------------------------------------------------

def test_unresolved_dict_has_required_fields():
    """Every unresolved direction-only entry carries all expected keys."""
    _, _, _, ignored = parse_legal_description(
        "THENCE EASTERLY ALONG THE SOUTHERLY LINE 75 FEET"
    )
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    entry = unresolved[0]
    assert entry["type"] == "Unresolved Direction-Only Call"
    assert "text" in entry
    assert "direction" in entry
    assert "distance" in entry
    assert "source_span" in entry


def test_distance_none_when_no_feet_token():
    """distance is None when no feet/foot/ft token appears."""
    _, _, _, ignored = parse_legal_description(
        "THENCE WESTERLY TO THE NORTHEAST CORNER"
    )
    unresolved = _unresolved(ignored)
    assert len(unresolved) == 1
    assert unresolved[0]["distance"] is None


# ---------------------------------------------------------------------------
# Not added to errors
# ---------------------------------------------------------------------------

def test_direction_only_not_in_errors():
    """Direction-only calls are recognized, not unknown; no error string."""
    _, _, errors, ignored = parse_legal_description(
        "THENCE SOUTHERLY 30 FEET TO A POINT"
    )
    assert errors == []
    assert len(_unresolved(ignored)) == 1
