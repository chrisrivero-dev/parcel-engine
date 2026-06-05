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


# ===========================================================================
# Curve row support tests  (appended by apply_curve_table_build_support.py)
# ===========================================================================
__CURVE_TABLE_BUILD_TESTS_APPLIED__ = True

import pytest as _cv_pytest

from geometry.builder import build_geometry as _cv_build_geometry
from models.schema import CurveCall as _CV_T_CurveCall, Handedness as _CV_T_Handedness
from ui.manual_courses import build_manual_curve as _cv_build_manual_curve
from ui.manual_courses import build_manual_line as _cv_build_manual_line


def test_curve_with_handedness_radius_delta():
    call = _cv_build_manual_curve(
        direction="RIGHT", radius="100", delta="45°00'00\"", idx=2
    )
    assert isinstance(call, _CV_T_CurveCall)
    assert call.id == "C2"
    assert call.params.handedness == _CV_T_Handedness.RIGHT
    assert call.params.radius == 100.0
    assert call.params.delta.deg == 45
    assert call.params.delta.minutes == 0
    assert call.params.delta.seconds == 0.0


def test_curve_handedness_left_word():
    call = _cv_build_manual_curve("LEFT", "50", "30°15'45\"")
    assert call.params.handedness == _CV_T_Handedness.LEFT
    assert call.params.delta.minutes == 15


@_cv_pytest.mark.parametrize("token", ["L", "l", "left", "LH", "ccw", "CCW"])
def test_curve_handedness_left_aliases(token):
    call = _cv_build_manual_curve(token, "50", "30")
    assert call.params.handedness == _CV_T_Handedness.LEFT


@_cv_pytest.mark.parametrize("token", ["R", "r", "Right", "RH", "cw", "CW"])
def test_curve_handedness_right_aliases(token):
    call = _cv_build_manual_curve(token, "50", "30")
    assert call.params.handedness == _CV_T_Handedness.RIGHT


def test_curve_with_arc_length_only():
    call = _cv_build_manual_curve("RIGHT", "100", "", arc="78.5398")
    assert call.params.delta is None
    assert call.params.arc_length == _cv_pytest.approx(78.5398)
    result = _cv_build_geometry(start_point=(0.0, 0.0), calls=[call])
    assert "points" in result and len(result["points"]) >= 2


def test_curve_with_both_delta_and_arc():
    call = _cv_build_manual_curve("LEFT", "100", "45°00'00\"", arc="78.5398")
    assert call.params.delta is not None
    assert call.params.arc_length is not None


def test_curve_decimal_degrees_delta():
    call = _cv_build_manual_curve("RIGHT", "100", "45.5")
    assert call.params.delta.deg == 45
    assert call.params.delta.minutes == 30


def test_curve_delta_dms_no_seconds():
    call = _cv_build_manual_curve("RIGHT", "100", "45°30'")
    assert call.params.delta.deg == 45
    assert call.params.delta.minutes == 30
    assert call.params.delta.seconds == 0.0


def test_curve_missing_radius_raises():
    with _cv_pytest.raises(ValueError, match="missing radius"):
        _cv_build_manual_curve("RIGHT", "", "45°00'00\"")


def test_curve_missing_delta_and_arc_raises():
    with _cv_pytest.raises(ValueError, match="missing delta or arc"):
        _cv_build_manual_curve("RIGHT", "100", "")


def test_curve_missing_handedness_raises():
    with _cv_pytest.raises(ValueError, match="missing handedness"):
        _cv_build_manual_curve("", "100", "45")


def test_curve_unknown_handedness_raises():
    with _cv_pytest.raises(ValueError, match="unknown handedness"):
        _cv_build_manual_curve("sideways", "100", "45")


def test_curve_zero_radius_raises():
    with _cv_pytest.raises(ValueError, match="radius must be positive"):
        _cv_build_manual_curve("RIGHT", "0", "45")


def test_curve_negative_radius_raises():
    with _cv_pytest.raises(ValueError, match="radius must be positive"):
        _cv_build_manual_curve("RIGHT", "-10", "45")


def test_curve_non_numeric_radius_raises():
    with _cv_pytest.raises(ValueError, match="radius not numeric"):
        _cv_build_manual_curve("RIGHT", "abc", "45")


def test_curve_bad_delta_raises():
    with _cv_pytest.raises(ValueError, match="could not parse delta"):
        _cv_build_manual_curve("RIGHT", "100", "not-an-angle")


def test_curve_zero_arc_raises():
    with _cv_pytest.raises(ValueError, match="arc length must be positive"):
        _cv_build_manual_curve("RIGHT", "100", "", arc="0")


def test_curve_90deg_right_ends_at_R_minus_R():
    """90 degree right-hand curve from due-north tangent at (0,0)
    must finish at (+R, -R) - concrete proof the builder accepted it."""
    call = _cv_build_manual_curve("RIGHT", "100", "90°00'00\"")
    result = _cv_build_geometry(start_point=(0.0, 0.0), calls=[call])
    end = result["points"][-1]
    assert end[0] == _cv_pytest.approx(100.0, abs=1e-6)
    assert end[1] == _cv_pytest.approx(100.0, abs=1e-6)


def test_line_path_still_rejects_curve_words():
    """A line entry with 'LEFT' must still fail at the line parser -
    never silently coerce a curve into a line."""
    with _cv_pytest.raises(ValueError, match="could not parse direction"):
        _cv_build_manual_line("LEFT", "100", 1)
