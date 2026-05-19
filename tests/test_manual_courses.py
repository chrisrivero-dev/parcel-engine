import pytest

from ui.manual_courses import build_manual_line


def test_quadrant_with_dms():
    call = build_manual_line('N 45°32\'10" E', "100.23", 1)
    assert call.distance.value == 100.23
    assert call.bearing.value.quadrant_ns == "N"
    assert call.bearing.value.quadrant_ew == "E"


def test_compact_quadrant():
    call = build_manual_line('N45°32\'10"E', "100", 1)
    assert call.distance.value == 100.0
    assert call.bearing.value.quadrant_ns == "N"


def test_wordy_quadrant():
    call = build_manual_line('NORTH 45°32\'10" EAST', "100", 1)
    assert call.distance.value == 100.0
    assert call.bearing.value.quadrant_ns == "N"
    assert call.bearing.value.quadrant_ew == "E"


def test_cardinal_letter_east():
    call = build_manual_line("E", "50", 1)
    assert call.distance.value == 50.0
    assert call.bearing.value.azimuth.deg == 90


def test_cardinal_letter_west():
    call = build_manual_line("W", "50", 1)
    assert call.bearing.value.azimuth.deg == 270


def test_cardinal_word_west():
    call = build_manual_line("WEST", "50", 1)
    assert call.bearing.value.azimuth.deg == 270


def test_missing_direction_raises():
    with pytest.raises(ValueError, match="missing direction"):
        build_manual_line("", "100", 1)


def test_missing_distance_raises():
    with pytest.raises(ValueError, match="missing distance"):
        build_manual_line("E", "", 1)


def test_bad_distance_raises():
    with pytest.raises(ValueError, match="distance not numeric"):
        build_manual_line("E", "abc", 1)


def test_zero_distance_raises():
    with pytest.raises(ValueError, match="distance must be positive"):
        build_manual_line("E", "0", 1)


def test_unknown_direction_raises():
    with pytest.raises(ValueError, match="could not parse direction"):
        build_manual_line("northeast-ish", "100", 1)
