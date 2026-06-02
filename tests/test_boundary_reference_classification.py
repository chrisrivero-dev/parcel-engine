"""Boundary vs reference/tie classification.

A pre-boundary locator phrase like "S 5° W 25 FEET FROM THE NE CORNER"
must not be drawn as a boundary course.  These tests pin that behaviour
on a real legal description and confirm normal THENCE calls still parse.
"""

import pytest

from transcription.parser_v2 import parse_legal_description


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


def _distances(calls):
    return [round(c.distance.value, 2) for c in calls]


# ---------------------------------------------------------------------------
# Parcel 1 acceptance criteria
# ---------------------------------------------------------------------------

def test_parcel1_produces_exactly_four_boundary_calls():
    calls, _, _, _ = parse_legal_description(PARCEL_1)
    assert len(calls) == 4, (
        f"expected 4 boundary calls, got {len(calls)} "
        f"with distances {_distances(calls)}"
    )


def test_parcel1_first_boundary_is_200_not_25():
    calls, _, _, _ = parse_legal_description(PARCEL_1)
    assert calls[0].distance.value == pytest.approx(200.0, abs=0.01)


def test_parcel1_boundary_distances_in_order():
    calls, _, _, _ = parse_legal_description(PARCEL_1)
    assert _distances(calls) == [200.0, 244.61, 203.15, 236.77]


def test_parcel1_no_25ft_in_boundary_calls():
    calls, _, _, _ = parse_legal_description(PARCEL_1)
    for c in calls:
        assert c.distance.value != pytest.approx(25.0, abs=0.01)


def test_parcel1_25ft_phrase_preserved_as_reference_tie():
    """The locator must not be silently lost — it lands in ties or notes."""
    _, ties, _, ignored = parse_legal_description(PARCEL_1)
    tie_distances = []
    for t in ties:
        parsed = t.get("parsed_line")
        if parsed is not None and getattr(parsed, "distance", None) is not None:
            tie_distances.append(round(parsed.distance.value, 2))
    text_haystack = " ".join(t.get("raw_text", "") for t in ties)
    text_haystack += " " + " ".join(ic.get("text", "") for ic in ignored)
    assert (
        25.0 in tie_distances
        or "25" in text_haystack
    ), "the 25 ft locator phrase must survive somewhere (tie or note)"


def test_parcel1_no_errors():
    _, _, errors, _ = parse_legal_description(PARCEL_1)
    assert errors == [], f"unexpected parse errors: {errors}"


# ---------------------------------------------------------------------------
# Control cases — normal boundary calls must still parse
# ---------------------------------------------------------------------------

def test_plain_thence_25ft_still_a_boundary_call():
    """A real THENCE call with the same numbers is still a boundary."""
    calls, _, _, _ = parse_legal_description(
        "THENCE SOUTH 5°18' WEST 25 FEET"
    )
    assert len(calls) == 1
    assert calls[0].distance.value == pytest.approx(25.0)


def test_thence_clause_with_pob_phrase_in_context_stays_boundary():
    """A THENCE that mentions 'FROM THE POINT OF BEGINNING' inside its
    descriptive context is still a boundary call — the THENCE prefix wins.
    """
    text = (
        "THENCE NORTH 7°33'20\" EAST 203.15 FEET TO A POINT IN A LINE "
        "WHICH BEARS SOUTH 74°48'55\" WEST FROM THE POINT OF BEGINNING"
    )
    calls, _, _, _ = parse_legal_description(text)
    assert len(calls) == 1
    assert calls[0].distance.value == pytest.approx(203.15)


def test_commencing_preamble_still_creates_a_tie():
    """Existing COMMENCING → commencement tie behaviour is unchanged."""
    text = (
        "COMMENCING AT THE NE CORNER, THENCE SOUTH 5°18' WEST 25 FEET "
        "TO THE POINT OF BEGINNING; THENCE NORTH 90°00'00\" EAST 100 FEET"
    )
    calls, ties, _, _ = parse_legal_description(text)
    assert len(calls) == 1
    assert calls[0].distance.value == pytest.approx(100.0)
    # The commencement leg should appear in ties.
    assert any(
        t.get("parsed_line") is not None
        and t["parsed_line"].distance.value == pytest.approx(25.0)
        for t in ties
    )


# ---------------------------------------------------------------------------
# Tie-phrase detector unit tests
# ---------------------------------------------------------------------------

from transcription.classify import _looks_like_reference_tie


@pytest.mark.parametrize("clause", [
    "BEGINNING AT A POINT, S 5° W 25 FEET FROM THE NORTHEASTERLY CORNER OF SAID LOT 24",
    "BEGINNING AT A POINT, S 5° W 25 FEET FROM THE NORTHEAST CORNER",
    "SAID POINT DISTANT 50 FEET FROM SAID CORNER",
    "BEING 30 FEET FROM THE NORTHWEST CORNER",
    "S 0° W 10 FEET FROM THE POINT OF BEGINNING",
])
def test_reference_tie_phrases_detected(clause):
    assert _looks_like_reference_tie(clause)


@pytest.mark.parametrize("clause", [
    "THENCE SOUTH 5°18' WEST 25 FEET",
    "THENCE NORTH 7°33'20\" EAST 203.15 FEET TO A POINT IN A LINE "
    "WHICH BEARS WEST FROM THE POINT OF BEGINNING",
    "THENCE SOUTH 5° WEST 200 FEET FROM POINT A",  # THENCE-led wins
    "BEING 80 FEET WIDE",  # no FROM tail → not a tie
])
def test_non_tie_clauses_not_flagged(clause):
    assert not _looks_like_reference_tie(clause)
