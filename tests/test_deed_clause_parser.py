"""Tolerance tests for deed-style THENCE clauses with long context phrases."""

from transcription.parser_v2 import parse_legal_description


def _parse_one(text: str):
    calls, ties, errors, ignored = parse_legal_description(text)
    return calls, ties, errors, ignored


def test_deed_clause_bearing_distance_with_along_context():
    text = (
        "THENCE SOUTH 47°45'30\" WEST, ALONG THE SOUTHWESTERLY LINE OF "
        "SAID LAND CONVEYED TO SONGER, 120 FEET;"
    )
    calls, _, errors, _ = _parse_one(text)

    assert errors == []
    assert len(calls) == 1
    call = calls[0]
    assert call.bearing.value.quadrant_ns == "S"
    assert call.bearing.value.quadrant_ew == "W"
    assert call.bearing.value.angle.deg == 47
    assert call.bearing.value.angle.minutes == 45
    assert call.bearing.value.angle.seconds == 30
    assert call.distance.value == 120.0


def test_deed_clause_distance_without_distance_of_phrase():
    text = "THENCE NORTH 60°29'30\" WEST 46.68 FEET;"
    calls, _, errors, _ = _parse_one(text)

    assert errors == []
    assert len(calls) == 1
    call = calls[0]
    assert call.bearing.value.quadrant_ns == "N"
    assert call.bearing.value.quadrant_ew == "W"
    assert call.distance.value == 46.68


def test_decimal_distance_preserved_from_ocr_text():
    text = "THENCE SOUTH 49°21'40\" WEST 140.46 FEET;"
    calls, _, errors, _ = _parse_one(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 140.46
    assert calls[0].distance.raw_text == "140.46"


def test_context_without_bearing_distance_remains_unparsed():
    text = (
        "THENCE ALONG THE SOUTHERLY LINE OF SAID PARCEL, MORE OR LESS, "
        "TO THE POINT OF BEGINNING;"
    )
    calls, _, _, ignored = _parse_one(text)

    assert calls == []
    assert len(ignored) >= 1


def test_existing_clean_calls_unchanged():
    text = (
        "BEGINNING at a point; "
        "thence N 45°00'00\" E a distance of 100.00 feet; "
        "thence S 45°00'00\" E 50 feet to the POINT OF BEGINNING."
    )
    calls, _, errors, _ = _parse_one(text)

    assert errors == []
    assert len(calls) == 2
    assert calls[0].bearing.value.quadrant_ns == "N"
    assert calls[0].distance.value == 100.0
    assert calls[1].bearing.value.quadrant_ns == "S"
    assert calls[1].distance.value == 50.0
