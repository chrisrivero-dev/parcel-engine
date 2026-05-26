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


# ---------------------------------------------------------------------------
# OCR-fragmented deed calls (bearing and distance split by a stray semicolon)
# ---------------------------------------------------------------------------

def test_fragmented_bearing_distance_split_by_ocr_semicolon():
    text = (
        "THENCE SOUTH 34°39'40\" WEST ALONG. 'THE SOUTHEASTERLY LINE OF "
        "SAID LOT; 113.31 FEET TO A POINT;"
    )
    calls, _, errors, _ = _parse_one(text)

    assert errors == []
    assert len(calls) == 1
    call = calls[0]
    assert call.bearing.value.quadrant_ns == "S"
    assert call.bearing.value.quadrant_ew == "W"
    assert call.bearing.value.angle.deg == 34
    assert call.bearing.value.angle.minutes == 39
    assert call.bearing.value.angle.seconds == 40
    assert call.distance.value == 113.31


def test_existing_comma_context_clause_still_parses():
    text = (
        "THENCE SOUTH 47°45'30\" WEST, ALONG THE SOUTHWESTERLY LINE OF "
        "SAID LAND CONVEYED TO SONGER, 120 FEET;"
    )
    calls, _, errors, _ = _parse_one(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].bearing.value.quadrant_ns == "S"
    assert calls[0].bearing.value.quadrant_ew == "W"
    assert calls[0].distance.value == 120.0


def test_ocr_typo_each_for_east_is_not_inferred():
    text = (
        "THENCE NORTH 1°02' EACH ALONG THE WESTERLY LINE OF SAID LOT, "
        "2.96 FEET;"
    )
    calls, _, _, ignored = _parse_one(text)

    assert calls == []
    assert len(ignored) >= 1


def test_qualitative_direction_not_parsed_as_geometry():
    text = "THENCE NORTHEASTERLY IN A DIRECT LINE, 140.48 FEET TO A POINT;"
    calls, _, _, ignored = _parse_one(text)

    assert calls == []
    assert len(ignored) >= 1


def test_mixed_ocr_sample_parses_only_safe_exact_bearings():
    text = (
        "THENCE SOUTH 34°39'40\" WEST ALONG. 'THE SOUTHEASTERLY LINE OF "
        "SAID LOT; 113.31 FEET TO A POINT IN THE SOUTHERLY LINE OF SAID LOT;\n"
        "THENCE NORTH 81°18'15\" WEST ALONG THE SOUTHERLY LINE OF SAID LOT "
        "67.65 FEET TO A POINT IN THE WESTERLY LINE OF SAID LOT;\n"
        "THENCE NORTH 1°02' EACH ALONG THE WESTERLY LINE OF SAID LOT, 2.96 FEET;\n"
        "THENCE NORTHEASTERLY IN A DIRECT LINE, 140.48 FEET TO A POINT;\n"
        "THENCE SOUTHEASTERLY ALONG THE NORTHEASTERLY LINE OF SAID LOT, "
        "50 FEET TO THE POINT OF BEGINNING."
    )
    calls, _, _, _ = _parse_one(text)

    parsed = [
        (
            c.bearing.value.quadrant_ns,
            c.bearing.value.angle.deg,
            c.bearing.value.angle.minutes,
            int(c.bearing.value.angle.seconds),
            c.bearing.value.quadrant_ew,
            c.distance.value,
        )
        for c in calls
    ]

    assert parsed == [
        ("S", 34, 39, 40, "W", 113.31),
        ("N", 81, 18, 15, "W", 67.65),
    ]
def test_true_point_boundary_phrase_switches_subsequent_calls_to_boundary():
    text = (
        "THAT PORTION OF LOT 2 OF FRACTIONAL SECTION 13, IN TOWNSHIP 7 SOUTH, "
        "RANGE 9 WEST, SAN BERNARDINO BASE AND MERIDIAN, IN THE CITY OF LAGUNA BEACH, "
        "COUNTY OF ORANGE, STATE OF CALIFORNIA, DESCRIBED AS FOLLOWS: "
        "COMMENCING AT STATION 453+00.85, A POINT ON THE CENTER LINE OF LAGUNA CANYON ROAD, "
        "AS SHOWN ON A MAP THEREOF APPROVED BY NAT NEFF, SUPERINTENDENT OF HIGHWAYS "
        "OF ORANGE COUNTY, CALIFORNIA, ON NOVEMBER 4, 1929, SAID POINT BEING THE "
        "NORTHWEST CORNER OF A PARCEL OF LAND DESCRIBED IN DEED TO ARCH CRAIG BY THE "
        "YOCH COMPANY, RECORDED MARCH 5, 1930 IN BOOK 366, PAGE 48, OF OFFICIAL RECORDS; "
        "THENCE SOUTHERLY FOLLOWING THE CENTERLINE OF LAGUNA CANYON ROAD, 1459.15 FEET "
        "TO THE MOST WESTERLY CORNER OF THE PARCEL OF LAND CONVEYED TO PATRICIA M. GOLDBAR, "
        "BY DEED DATED MAY 27, 1939 AND RECORDED IN BOOK 998, PAGE 253, OF OFFICIAL RECORDS, "
        "SAID CORNER BEING THE TRUE POINT OF BEGINNING OF THE BOUNDARY OF THE PROPERTY "
        "DESCRIBED HEREIN; "
        "THENCE SOUTH 58°49' WEST, ALONG THE SOUTHWESTERLY LINE OF SAID LAND OF GOLDBAR, "
        "197.18 FEET TO THE MOST SOUTHERLY CORNER OF SAID LAND; "
        "THENCE SOUTH 17°59'28\" WEST 109.90 FEET MORE OR LESS TO THE NORTHEASTERLY CORNER "
        "OF THE PARCEL OF LAND CONVEYED TO GEORGIA DAY ROBERTSON, AND OTHERS BY DEED "
        "DATED MAY 27, 1939 AND RECORDED IN BOOK 1001, PAGE 119, OF OFFICIAL RECORDS; "
        "THENCE NORTH 58°49' WEST, ALONG THE NORTHEASTERLY LINE OF SAID LAND OF ROBERTSON, "
        "222.26 FEET TO THE CENTER LINE OF LAGUNA CANYON ROAD; "
        "THENCE NORTH 31°11' EAST, ALONG SAID CENTER LINE 107 FEET TO THE TRUE POINT OF BEGINNING. "
        "PARCEL 2: THE NORTHEASTERLY 107.00 FEET OF THAT CERTAIN PARCEL OF LAND DESCRIBED "
        "IN A DEED TO ROBERT P. KELLOGG AND HAZEL A. KELLOGG, RECORDED OCTOBER 6, 1944 "
        "IN BOOK 1285, PAGE 357, OF OFFICIAL RECORDS, RECORDS OF ORANGE COUNTY, STATE OF CALIFORNIA."
    )

    calls, ties, errors, ignored = _parse_one(text)

    assert errors == []
    assert len(calls) == 4

    parsed = [
        (
            c.bearing.value.quadrant_ns,
            c.bearing.value.angle.deg,
            c.bearing.value.angle.minutes,
            int(c.bearing.value.angle.seconds),
            c.bearing.value.quadrant_ew,
            c.distance.value,
        )
        for c in calls
    ]

    assert parsed == [
        ("S", 58, 49, 0, "W", 197.18),
        ("S", 17, 59, 28, "W", 109.90),
        ("N", 58, 49, 0, "W", 222.26),
        ("N", 31, 11, 0, "E", 107.0),
    ]

    assert not any(
        getattr(t.get("parsed_line"), "distance", None)
        and t["parsed_line"].distance.value == 1459.15
        for t in ties
    )