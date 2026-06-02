"""Parser tolerance for bearing + intervening descriptive context + distance.

These pin the behaviour where a deed clause carries a long descriptive
phrase between the bearing and the distance — and that phrase may
contain *commas* and *embedded numbered references* like ``LOT 24``.
The line parser must still recover the call's real distance.

Regressions covered:
- A real-world Parcel 1 clause where ``LOT 24`` digits would otherwise
  veto the deed-style regex.
- Comma-laden variants ("WEST, PARALLEL TO ... LOT 24, 244.61 FEET").
- The "POB locator" classification fix must not be undone — a clause
  matching a reference-tie phrase still routes to ties, not boundaries.
- Direction-only calls without a numeric distance still surface as
  Unresolved Direction-Only Call (existing behaviour preserved).
"""

import pytest

from transcription.lines import parse_line_chunk
from transcription.parser_v2 import parse_legal_description


# ---------------------------------------------------------------------------
# Comma + LOT-24 variants — the gap closed by this fix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clause, expect_dist", [
    # No commas, embedded LOT 24 — works pre-fix via NARRATIVE
    (
        "THENCE SOUTH 74°48'55\" WEST PARALLEL TO THE NORTHERLY LINE OF "
        "SAID LOT 24 244.61 FEET",
        244.61,
    ),
    # Commas around the descriptive body — pre-fix failed
    (
        "THENCE SOUTH 74°48'55\" WEST, PARALLEL TO THE NORTHERLY LINE OF "
        "SAID LOT 24, 244.61 FEET",
        244.61,
    ),
    # Comma + ALONG variant
    (
        "THENCE NORTH 7°33'20\" EAST, ALONG THE WESTERLY LINE OF LOT 24, "
        "203.15 FEET",
        203.15,
    ),
    # "ALONG" without leading comma but with mid-clause comma
    (
        "THENCE SOUTH 74°48'55\" WEST ALONG LOT 24, 244.61 FEET",
        244.61,
    ),
    # "WHICH BEARS ... FROM" descriptive context (no FROM the corner trigger)
    (
        "THENCE NORTH 7°33'20\" EAST 203.15 FEET TO A POINT IN A LINE "
        "WHICH BEARS SOUTH 74°48'55\" WEST FROM POINT A",
        203.15,
    ),
])
def test_bearing_then_descriptive_context_then_distance_parses(clause, expect_dist):
    line = parse_line_chunk(clause, 1)
    assert line is not None, f"failed to parse: {clause!r}"
    assert line.distance.value == pytest.approx(expect_dist, abs=0.01)


# ---------------------------------------------------------------------------
# Simple cases still parse to the correct distance (no over-greediness)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clause, expect_dist", [
    ("THENCE SOUTH 5°18' WEST 200 FEET", 200.0),
    ("THENCE SOUTH 5°18' WEST 25 FEET", 25.0),
    ("THENCE NORTH 90°00'00\" EAST 100 FEET", 100.0),
    ("THENCE SOUTH 0°00'00\" EAST 50 FEET", 50.0),
])
def test_simple_bearing_distance_still_parses_first(clause, expect_dist):
    line = parse_line_chunk(clause, 1)
    assert line is not None
    assert line.distance.value == pytest.approx(expect_dist)


# ---------------------------------------------------------------------------
# Reference-tie classification still wins — the relaxation does NOT undo
# patch 0028's POB-locator routing.
# ---------------------------------------------------------------------------

def test_pob_locator_still_routed_to_reference_tie_not_boundary():
    """The 25-foot FROM-CORNER locator must remain a tie, not a boundary."""
    text = (
        "BEGINNING AT A POINT IN THE EASTERLY LINE OF SAID LOT 24, "
        "SOUTH 5°18' WEST 25 FEET FROM THE NORTHEASTERLY CORNER OF "
        "SAID LOT 24, THENCE SOUTH 5°18' WEST ALONG SAID EASTERLY LINE "
        "200 FEET"
    )
    calls, ties, _, _ = parse_legal_description(text)
    assert len(calls) == 1
    assert calls[0].distance.value == pytest.approx(200.0)
    # The 25 ft locator must show up among ties (not silently lost).
    tie_dists = [
        t["parsed_line"].distance.value
        for t in ties
        if t.get("parsed_line") is not None
        and getattr(t["parsed_line"], "distance", None) is not None
    ]
    assert 25.0 in tie_dists


# ---------------------------------------------------------------------------
# Direction-only-without-distance still becomes an Unresolved call
# ---------------------------------------------------------------------------

def test_direction_only_no_distance_still_unresolved():
    calls, _, _, ignored = parse_legal_description(
        "THENCE WESTERLY TO A POINT ON THE EAST LINE"
    )
    assert calls == []
    assert any(c["type"] == "Unresolved Direction-Only Call" for c in ignored)


# ---------------------------------------------------------------------------
# End-to-end Parcel 1 — must still produce four boundary calls in order
# ---------------------------------------------------------------------------

PARCEL_1 = (
    "PARCEL 1: THE SOUTHERLY 80 FEET, SAID 80 FEET BEING MEASURED ALONG "
    "THE EASTERLY LINE OF THAT PORTION OF LOT 24, TRACT NO. 440, IN THE "
    "COUNTY OF ORANGE, STATE OF CALIFORNIA, AS PER MAP RECORDED IN BOOK "
    "16 PAGE(S) 21 AND 22 OF MISCELLANEOUS MAPS, RECORDS OF ORANGE "
    "COUNTY, DESCRIBED AS FOLLOWS: BEGINNING AT A POINT IN THE EASTERLY "
    "LINE OF SAID LOT 24, SOUTH 5°18' WEST 25 FEET FROM THE "
    "NORTHEASTERLY CORNER OF SAID LOT 24, THENCE SOUTH 5°18' WEST "
    "ALONG SAID EASTERLY LINE 200 FEET; THENCE SOUTH 74°48'55\" "
    "WEST PARALLEL TO THE NORTHERLY LINE OF SAID LOT 24 244.61 FEET; "
    "THENCE NORTH 7°33'20\" EAST 203.15 FEET TO A POINT IN A LINE "
    "WHICH BEARS SOUTH 74°48'55\" WEST PARALLEL TO THE NORTHERLY "
    "LINE OF SAID LOT 24 FROM THE POINT OF BEGINNING; THENCE NORTH "
    "74°48'55\" EAST 236.77 FEET TO THE POINT OF BEGINNING."
)


def test_parcel1_four_boundary_calls_in_correct_order():
    calls, _, _, _ = parse_legal_description(PARCEL_1)
    dists = [round(c.distance.value, 2) for c in calls]
    assert dists == [200.0, 244.61, 203.15, 236.77]


def test_parcel1_244_61_not_ignored():
    _, _, _, ignored = parse_legal_description(PARCEL_1)
    for ic in ignored:
        assert "244.61" not in ic.get("text", "")
