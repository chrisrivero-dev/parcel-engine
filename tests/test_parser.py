from transcription.parser import parse_legal_description


def test_parse_quadrant_line():
    text = 'N 54°32\'10" E 100.23'
    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 100.23


def test_parse_curve_radius_delta():
    text = (
        'thence along a curve to the right having a radius of 50.00 feet '
        'through a central angle of 90°00\'00"'
    )

    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].params.radius == 50.0


def test_parse_unknown_line_fails():
    text = "this is junk"

    calls, errors = parse_legal_description(text)

    assert calls == []
    assert len(errors) == 1


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

    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) >= 5

    assert calls[0].bearing.raw_text == 'S 89°47\'10" E'
    assert calls[0].distance.value == 136.93

    assert calls[1].bearing.raw_text == 'N 06°20\'24" E'
    assert calls[1].distance.value == 49.96

    assert calls[2].bearing.raw_text == 'N 13°49\'21" E'
    assert calls[2].distance.value == 19.92

    assert calls[3].bearing.raw_text == 'N 60°29\'30" W'
    assert calls[3].distance.value == 46.68

    assert calls[4].bearing.raw_text == 'S 49°21\'40" W'
    assert calls[4].distance.value == 140.46

def test_parse_compact_quadrant_line():
    text = 'N45°32\'10"E 100.23'

    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 100.23


def test_parse_wordy_quadrant_line():
    text = 'North 45°32\'10" East 100.23 feet'

    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 100.23


def test_parse_optional_seconds_line():
    text = 'N 45°32\' E 100.23'

    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 1
    assert calls[0].distance.value == 100.23


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

    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) >= 5
    assert calls[0].distance.value == 150.25
    assert calls[1].distance.value == 220.50
    assert calls[2].distance.value == 140.00
    assert calls[3].distance.value == 215.75
    assert calls[4].distance.value == 130.10

def test_parse_target_mapping_from_narrative():
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
    

    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) >= 5

    assert calls[0].bearing.raw_text == 'S 89°47\'10" E'
    assert calls[0].distance.value == 136.93

    assert calls[1].bearing.raw_text == 'N 06°20\'24" E'
    assert calls[1].distance.value == 49.96

    assert calls[2].bearing.raw_text == 'N 13°49\'21" E'
    assert calls[2].distance.value == 19.92

    assert calls[3].bearing.raw_text == 'N 60°29\'30" W'
    assert calls[3].distance.value == 46.68

    assert calls[4].bearing.raw_text == 'S 49°21\'40" W'
    assert calls[4].distance.value == 140.46

def test_parse_long_form_prose_deed_courses():
    text = (
        "BEGINNING AT AN ANGLE POINT IN LOT 10, SAID ANGLE POINT BEING THE MOST "
        "WESTERLY CORNER OF SAID TRACT NO. 2609; THENCE SOUTH 50 DEGREES 00' 30\" "
        "EAST ALONG THE SOUTHWESTERLY LINE OF SAID LOT 10 AND LOT 11, 120.00 "
        "FEET TO A POINT; THENCE NORTH 63 DEGREES 31' 47\" EAST, 131.57 FEET "
        "TO A POINT; THENCE SOUTH 85 DEGREES 15' 17\" WEST, 174.28 FEET TO "
        "THE POINT OF BEGINNING."
    )

    calls, errors = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 3
    assert calls[0].bearing.raw_text == 'S 50°00\'30" E'
    assert calls[0].distance.value == 120.00
    assert calls[1].bearing.raw_text == 'N 63°31\'47" E'
    assert calls[1].distance.value == 131.57
    assert calls[2].bearing.raw_text == 'S 85°15\'17" W'
    assert calls[2].distance.value == 174.28