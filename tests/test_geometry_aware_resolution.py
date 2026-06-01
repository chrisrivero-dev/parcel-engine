"""Tests for the geometry-aware resolution helper.

Covers the closure-bracket solve, fallback to the simple text-only
suggestion, and the no-fabrication guards.  All inputs are produced by
``parse_legal_description`` so source spans and call objects are realistic.
"""

import math

import pytest

from geometry.resolution import (
    ResolutionCandidate,
    suggest_geometry_aware,
)
from transcription.parser_v2 import parse_legal_description


LOT_11 = (
    "BEGINNING AT THE NORTHEAST CORNER OF SAID LOT 11; "
    "THENCE SOUTH 00°24'19\" WEST 60 FEET ALONG THE EASTERLY LINE AND ITS "
    "SOUTHERLY EXTENSION OF SAID LOT 11; "
    "THENCE WESTERLY TO A POINT ON THE SOUTHERLY EXTENSION OF THE WESTERLY "
    "LINE THAT IS DISTANT SOUTHERLY 52 FEET FROM THE NORTHWEST CORNER OF "
    "SAID LOT 11; "
    "THENCE NORTHERLY 52 FEET ALONG SAID SOUTHERLY EXTENSION AND THE WESTERLY "
    "LINE OF LOT 11 TO THE NORTHWEST CORNER THEREOF; "
    "THENCE SOUTH 89°35'41\" EAST 120 FEET ALONG THE NORTHERLY LINE OF SAID "
    "LOT 11 TO THE POINT OF BEGINNING."
)


def _unresolved(ignored):
    return [c for c in ignored if c["type"] == "Unresolved Direction-Only Call"]


def _find(ignored, direction):
    for c in _unresolved(ignored):
        if c["direction"] == direction:
            return c
    raise AssertionError(f"no unresolved {direction} call")


# ---------------------------------------------------------------------------
# Closure-bracket solve on a clean synthetic rectangle (deterministic)
# ---------------------------------------------------------------------------

def test_closure_bracket_solves_missing_west_side_of_rectangle():
    """E 100, S 50, WESTERLY (?), N 50 → WESTERLY solved to due-west 100 ft.

    No sibling unresolved → method label is the generic closure_bracket.
    """
    text = (
        "THENCE NORTH 90°00'00\" EAST 100 FEET; "
        "THENCE SOUTH 0°00'00\" EAST 50 FEET; "
        "THENCE WESTERLY TO A POINT; "
        "THENCE NORTH 0°00'00\" EAST 50 FEET;"
    )
    calls, _, _, ignored = parse_legal_description(text)
    entry = _find(ignored, "WESTERLY")

    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert cand is not None
    assert cand.method == "closure_bracket"
    assert cand.quadrant_ew == "W"
    assert cand.distance == pytest.approx(100.0, abs=0.05)
    assert cand.residual == pytest.approx(0.0, abs=0.1)
    assert cand.confidence == "medium"


# ---------------------------------------------------------------------------
# Lot 11 — the motivating real example
# ---------------------------------------------------------------------------

def test_lot11_westerly_gets_paired_bracket_candidate():
    """The distance-less WESTERLY call is solved from the paired bracket.

    Pattern: known L1 before + sibling unresolved NORTHERLY 52' (with
    distance) + closing known L2 back to POB.  Method label must be the
    explicit ``paired_bracket`` form so the technician sees which sibling
    and closing call were used.
    """
    calls, _, _, ignored = parse_legal_description(LOT_11)
    entry = _find(ignored, "WESTERLY")

    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert cand is not None
    assert cand.method == "paired_bracket"
    # The solved distance is the bracket gap, ~119.9 ft — NOT the offset 52'.
    assert cand.distance == pytest.approx(119.9, abs=0.5)
    assert cand.distance > 100.0
    # Predominantly westerly, consistent with the stated direction word.
    assert cand.quadrant_ew == "W"
    assert cand.residual is not None and cand.residual < 10.0
    assert cand.confidence == "medium"
    # Reason must explicitly mention the NORTHERLY sibling and the closing
    # back-to-POB call so the technician understands the inference chain.
    lower = cand.reason.lower()
    assert "northerly" in lower
    assert "point of beginning" in lower


def test_lot11_westerly_distance_not_taken_from_offset_phrase():
    """The 52' in 'DISTANT SOUTHERLY 52 FEET' must not become the leg length."""
    calls, _, _, ignored = parse_legal_description(LOT_11)
    entry = _find(ignored, "WESTERLY")
    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert cand is not None
    # 52 ft would be the wrong (offset-tie) value; solved value must differ.
    assert abs(cand.distance - 52.0) > 10.0


def test_lot11_northerly_falls_back_to_direction_distance():
    """NORTHERLY 52 has a distance and is not the sole unknown → simple."""
    calls, _, _, ignored = parse_legal_description(LOT_11)
    entry = _find(ignored, "NORTHERLY")

    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert cand is not None
    assert cand.method == "direction_distance"
    assert cand.quadrant_ns == "N"
    assert cand.distance == pytest.approx(52.0)


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------

def test_isolated_direction_distance_uses_simple():
    """A lone direction+distance call (no bracket) → simple suggestion."""
    calls, _, _, ignored = parse_legal_description("THENCE NORTHERLY 52 FEET")
    entry = _find(ignored, "NORTHERLY")
    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert cand is not None
    assert cand.method == "direction_distance"
    assert cand.quadrant_ns == "N"


def test_isolated_no_distance_returns_none():
    """A lone distance-less call with no bracketing geometry → None."""
    calls, _, _, ignored = parse_legal_description(
        "THENCE WESTERLY TO A POINT ON THE EAST LINE"
    )
    entry = _find(ignored, "WESTERLY")
    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert cand is None


# ---------------------------------------------------------------------------
# No-fabrication guards
# ---------------------------------------------------------------------------

def test_two_distance_less_calls_not_solved():
    """Two unknowns (both no distance) → cannot solve → no closure candidate."""
    text = (
        "THENCE NORTH 90°00'00\" EAST 100 FEET; "
        "THENCE WESTERLY TO A POINT; "
        "THENCE SOUTHERLY TO ANOTHER POINT; "
        "THENCE NORTH 0°00'00\" EAST 50 FEET;"
    )
    calls, _, _, ignored = parse_legal_description(text)
    entry = _find(ignored, "WESTERLY")
    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    # WESTERLY has no distance and is not the *sole* unknown → no closure
    # solve, and simple cannot help a distance-less call → None.
    assert cand is None


def test_no_resolved_calls_no_bracket():
    """No known boundary calls → cannot bracket; distance-less → None."""
    text = "THENCE WESTERLY TO A POINT; THENCE NORTHERLY TO ANOTHER;"
    calls, _, _, ignored = parse_legal_description(text)
    assert calls == []
    entry = _find(ignored, "WESTERLY")
    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert cand is None


def test_candidate_is_resolution_candidate_type():
    text = (
        "THENCE NORTH 90°00'00\" EAST 100 FEET; "
        "THENCE SOUTH 0°00'00\" EAST 50 FEET; "
        "THENCE WESTERLY TO A POINT; "
        "THENCE NORTH 0°00'00\" EAST 50 FEET;"
    )
    calls, _, _, ignored = parse_legal_description(text)
    entry = _find(ignored, "WESTERLY")
    cand = suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert isinstance(cand, ResolutionCandidate)
    # bearing_text renders cleanly
    assert cand.bearing_text().endswith("W")


# ---------------------------------------------------------------------------
# Purity — helper does not mutate inputs
# ---------------------------------------------------------------------------

def test_helper_does_not_mutate_inputs():
    text = (
        "THENCE NORTH 90°00'00\" EAST 100 FEET; "
        "THENCE SOUTH 0°00'00\" EAST 50 FEET; "
        "THENCE WESTERLY TO A POINT; "
        "THENCE NORTH 0°00'00\" EAST 50 FEET;"
    )
    calls, _, _, ignored = parse_legal_description(text)
    entry = _find(ignored, "WESTERLY")
    snapshot = dict(entry)
    suggest_geometry_aware(entry, calls=calls, ignored_chunks=ignored)
    assert entry == snapshot


# ---------------------------------------------------------------------------
# Regression: source-span-less calls (post-Build-Parcel) must not break solve
# ---------------------------------------------------------------------------

def test_calls_without_source_span_do_not_produce_bracket_candidate():
    """Calls built from the COGO table (no source_span) must not fool the
    bracket solver into fabricating a candidate from mis-ordered spans.
    The solver should safely return None rather than produce garbage.
    """
    from models.schema import (
        Bearing, BearingFormat, DirectionBasis, Distance, DMS,
        LineCall, QuadrantBearing,
    )
    # Build two LineCall objects as _calls_from_table() / build_manual_line()
    # would — no source_span set.
    def _make_line(idx, ns, deg, mn, sc, ew, dist):
        return LineCall(
            id=f"L{idx}",
            raw_text=f"{ns} {deg}°{mn}'{sc}\" {ew}",
            bearing=Bearing(
                raw_text=f"{ns} {deg}°{mn}'{sc}\" {ew}",
                format=BearingFormat.QUADRANT,
                value=QuadrantBearing(
                    quadrant_ns=ns,
                    angle=DMS(deg=deg, minutes=mn, seconds=float(sc)),
                    quadrant_ew=ew,
                ),
                basis=DirectionBasis.TRUE,
                confidence=1.0,
            ),
            distance=Distance(raw_text=str(dist), value=float(dist)),
            # source_span intentionally absent (None by default)
        )

    table_calls = [
        _make_line(1, "S", 0, 24, 19, "W", 60),
        _make_line(2, "S", 89, 35, 41, "E", 120),
    ]
    _, _, _, ignored = parse_legal_description(LOT_11)
    westerly = _find(ignored, "WESTERLY")
    # Without source spans the bracket solver cannot order calls vs the
    # unresolved entry; it must return None, not a random result.
    cand = suggest_geometry_aware(westerly, calls=table_calls, ignored_chunks=ignored)
    assert cand is None


def test_parsed_calls_with_source_span_still_solve_after_build_parcel_simulation():
    """Storing _parsed_calls separately from self.calls means the suggestion
    helper always receives span-bearing calls even after Build Parcel rewrites
    self.calls with source-span-less table calls.
    """
    calls, _, _, ignored = parse_legal_description(LOT_11)
    # parsed_calls has source_span; this is what _parsed_calls holds.
    westerly = _find(ignored, "WESTERLY")
    cand = suggest_geometry_aware(westerly, calls=calls, ignored_chunks=ignored)
    assert cand is not None
    assert cand.method == "paired_bracket"
    assert cand.distance == pytest.approx(119.9, abs=0.5)
