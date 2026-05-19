from pathlib import Path

import pytest

from geometry.builder import build_geometry
from transcription.parser_v2 import parse_legal_description


FIXTURES = Path(__file__).parent / "fixtures"


# ============================================================
# Core line parsing
# ============================================================

def test_parse_quadrant_line():
    text = 'N 54°32\'10" E 100.23'
    calls, ties, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 100.23


def test_parse_compact_quadrant_line():
    text = 'N45°32\'10"E 100.23'

    calls, ties, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 100.23


def test_parse_wordy_quadrant_line():
    text = 'North 45°32\'10" East 100.23 feet'

    calls, ties, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 100.23


def test_parse_optional_seconds_line():
    text = 'N 45°32\' E 100.23'

    calls, ties, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 100.23


def test_a_distance_of_phrasing():
    text = 'THENCE S 03°25\'14" E, a distance of 3.17 feet to a point for corner'
    calls, ties, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 3.17


def test_curly_quote_ocr():
    text = 'THENCE S 03°25’14” E, a distance of 3.17 feet to a point for corner'
    calls, ties, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 3.17


def test_degrees_word_form():
    text = 'THENCE NORTH 03 DEGREES 25 MINUTES 14 SECONDS EAST 3.17 FEET'
    calls, ties, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 3.17


def test_parse_unknown_line_fails():
    text = "this is junk"

    calls, ties, errors = parse_legal_description(text)

    assert calls == []
    assert ties == []
    assert len(errors) == 1


# ============================================================
# Reference-tie classification
# ============================================================

def test_said_point_being_is_tie_not_boundary():
    text = (
        'BEGINNING AT A POINT, SAID POINT BEING N 50° 00\' 00" E, 100.00 FEET '
        'FROM A FOUND IRON ROD; THENCE N 89° 00\' 00" E 50.00 feet to a point.'
    )
    calls, ties, errors = parse_legal_description(text)

    assert len(calls) == 1
    assert calls[0].distance.value == 50.00
    assert any(t["kind"] == "reference_tie" for t in ties)


# ============================================================
# Gold standard: Reddleshire synthetic
# ============================================================

def _load_reddleshire() -> str:
    return (FIXTURES / "reddleshire_synthetic.txt").read_text(encoding="utf-8")


def test_reddleshire_gold_standard():
    text = _load_reddleshire()
    calls, ties, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 8
    assert len(ties) == 1

    # First boundary call is the FIRST call after POINT OF BEGINNING,
    # NOT the commencement leg.
    assert calls[0].distance.value == 3.17
    assert calls[0].bearing.value.quadrant_ns == "S"
    assert calls[0].bearing.value.quadrant_ew == "E"

    # Last boundary call closes back to POB.
    assert calls[-1].distance.value == 56.74
    assert calls[-1].bearing.value.quadrant_ns == "N"
    assert calls[-1].bearing.value.quadrant_ew == "E"


def test_commencement_classified_separately():
    text = _load_reddleshire()
    calls, ties, errors = parse_legal_description(text)

    commencement_ties = [t for t in ties if t["kind"] == "commencement"]
    assert len(commencement_ties) == 1

    leg = commencement_ties[0]["parsed_line"]
    assert leg is not None
    assert leg.distance.value == 14.60
    assert leg.bearing.value.quadrant_ns == "S"
    assert leg.bearing.value.quadrant_ew == "W"

    # And the commencement leg's distance must NOT appear in calls.
    assert not any(c.distance.value == 14.60 for c in calls)


def test_e2e_reddleshire_closes():
    text = _load_reddleshire()
    calls, ties, errors = parse_legal_description(text)

    result = build_geometry(start_point=(0.0, 0.0), calls=calls)
    assert result["curves"] == []
    assert result["validation"]["closure"]["misclosure"] < 0.05


# ============================================================
# Narrative samples (carried over from legacy intent)
# ============================================================

def test_parse_precise_narrative_courses():
    text = (
        'BEGINNING AT A POINT IN THE SOUTH LINE OF SAID SECTION 24, SAID POINT BEING THE MOST '
        'EASTERLY CORNER OF LOT 144, IN TRACT NO. 858, AS SHOWN ON A MAP RECORDED IN BOOK '
        '28, PAGES 25, 26 AND 27, OF MISCELLANEOUS MAPS, IN THE OFFICE OF THE COUNTY RECORDER '
        'OF SAID COUNTY; THENCE ALONG SAID SOUTH LINE SOUTH 89° 47\' 10" EAST 136.93 FEET TO THE '
        'SOUTHWESTERLY CORNER OF THE LAND DESCRIBED IN A DEED TO DARRELL J. SATTERFIELD '
        'AND WIFE, RECORDED IN BOOK 1358, PAGE 168 OF OFFICIAL RECORDS OF SAID ORANGE '
        'COUNTY; THENCE ALONG THE WESTERLY LINE OF SAID SATTERFIELD PROPERTY NORTH 06° 20\' '
        '24" EAST 49.96 FEET; THENCE NORTH 13° 49\' 21" EAST 19.92 FEET TO THE MOST SOUTHERLY '
        'CORNER OF THE LAND DESCRIBED IN A DEED TO HUBERT J. THOMPSON AND WIFE, RECORDED '
        'IN BOOK 2817, PAGE 640 OF OFFICIAL RECORDS OF SAID ORANGE COUNTY; THENCE NORTH 60° '
        '29\' 30" WEST 46.68 FEET TO THE POINT OF BEGINNING; SOUTH 49° 21\' 40" WEST 140.46 FEET.'
    )

    calls, ties, errors = parse_legal_description(text)

    # No COMMENCING preamble → all bearing-bearing clauses are boundary.
    assert len(calls) == 5

    assert calls[0].distance.value == 136.93
    assert calls[1].distance.value == 49.96
    assert calls[2].distance.value == 19.92
    assert calls[3].distance.value == 46.68
    assert calls[4].distance.value == 140.46


def test_parse_complex_narrative_description():
    text = (
        "COMMENCING AT THE SOUTHWEST CORNER OF LOT 12 OF TRACT NO. 4321, AS SHOWN "
        "ON A MAP RECORDED IN BOOK 100, PAGES 10 THROUGH 12 OF MISCELLANEOUS MAPS, "
        "IN THE OFFICE OF THE COUNTY RECORDER OF SAID COUNTY; "
        "THENCE ALONG THE WESTERLY LINE OF SAID LOT NORTH 00° 15' 30\" WEST 150.25 FEET "
        "TO THE TRUE POINT OF BEGINNING; "
        "THENCE NORTH 89° 45' 10\" EAST 220.50 FEET; "
        "THENCE ALONG THE EASTERLY LINE OF SAID PROPERTY SOUTH 00° 10' 20\" EAST 140.00 FEET; "
        "THENCE SOUTH 89° 50' 40\" WEST 215.75 FEET TO A POINT ON THE WESTERLY LINE OF SAID LOT; "
        "THENCE NORTH 00° 12' 10\" WEST 130.10 FEET TO THE TRUE POINT OF BEGINNING."
    )

    calls, ties, errors = parse_legal_description(text)

    # COMMENCING preamble → first THENCE-to-POB is commencement, not boundary.
    assert len(calls) == 4
    assert calls[0].distance.value == 220.50
    assert calls[1].distance.value == 140.00
    assert calls[2].distance.value == 215.75
    assert calls[3].distance.value == 130.10

    commencement = [t for t in ties if t["kind"] == "commencement"]
    assert len(commencement) == 1
    assert commencement[0]["parsed_line"].distance.value == 150.25


def test_parse_long_form_prose_deed_courses():
    text = (
        "BEGINNING AT AN ANGLE POINT IN LOT 10, SAID ANGLE POINT BEING THE MOST "
        "WESTERLY CORNER OF SAID TRACT NO. 2609; THENCE SOUTH 50 DEGREES 00' 30\" "
        "EAST ALONG THE SOUTHWESTERLY LINE OF SAID LOT 10 AND LOT 11, 120.00 "
        "FEET TO A POINT; THENCE NORTH 63 DEGREES 31' 47\" EAST, 131.57 FEET "
        "TO A POINT; THENCE SOUTH 85 DEGREES 15' 17\" WEST, 174.28 FEET TO "
        "THE POINT OF BEGINNING."
    )

    calls, ties, errors = parse_legal_description(text)

    # No closure synthesis: exactly 3 boundary calls.
    assert len(calls) == 3
    assert calls[0].distance.value == 120.00
    assert calls[1].distance.value == 131.57
    assert calls[2].distance.value == 174.28


# ============================================================
# Curve parsing — frozen until lines are stable
# ============================================================

@pytest.mark.skip(reason="Curves frozen until line-only parser is stable")
def test_parse_curve_radius_delta():
    pass
