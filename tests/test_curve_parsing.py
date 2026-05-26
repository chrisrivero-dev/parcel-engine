from geometry.builder import build_geometry
from models.schema import CurveCall, CurveType, Handedness
from transcription.curves import parse_curve_chunk
import pytest

from transcription.parser_v2 import parse_legal_description


def test_parse_tangent_curve_with_radius_arc_and_delta():
    curve = parse_curve_chunk(
        "THENCE ALONG A TANGENT CURVE TO THE RIGHT, HAVING A RADIUS OF "
        "150.00 FEET, THROUGH A CENTRAL ANGLE OF 29°39', AN ARC DISTANCE "
        "OF 77.62 FEET",
        1,
    )

    assert curve is not None
    assert curve.params.curve_type == CurveType.TANGENT
    assert curve.params.handedness == Handedness.RIGHT
    assert curve.params.radius == 150.0
    assert curve.params.arc_length == 77.62
    assert curve.params.delta.deg == 29
    assert curve.params.delta.minutes == 39
    assert curve.params.delta.seconds == 0.0


def test_parse_curve_with_radius_and_arc_only():
    curve = parse_curve_chunk(
        "THENCE SOUTHWESTERLY ALONG SAID CURVE, HAVING A RADIUS OF "
        "150.00 FEET, AN ARC LENGTH OF 77.62 FEET",
        1,
    )

    assert curve is not None
    assert curve.params.curve_type == CurveType.NON_TANGENT
    assert curve.params.radius == 150.0
    assert curve.params.arc_length == 77.62
    assert curve.params.delta is None
    assert curve.params.handedness is None


def test_concavity_direction_is_preserved():
    curve = parse_curve_chunk(
        "THENCE ALONG A CURVE CONCAVE EASTERLY, HAVING A RADIUS OF "
        "100.00 FEET, AN ARC DISTANCE OF 25.00 FEET",
        1,
    )

    assert curve is not None
    assert curve.along_feature == "CONCAVE EASTERLY"


def test_curve_without_numeric_geometry_is_not_parsed():
    curve = parse_curve_chunk(
        "THENCE ALONG A CURVE CONCAVE EASTERLY TO A POINT",
        1,
    )

    assert curve is None


def test_mixed_line_and_curve_description_parses_both():
    text = (
        "THENCE NORTH 00°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A TANGENT CURVE TO THE LEFT, HAVING A RADIUS OF "
        "50.00 FEET, AN ARC LENGTH OF 25.00 FEET;"
    )

    calls, ties, errors, ignored = parse_legal_description(text)

    assert errors == []
    assert len(calls) == 2
    assert calls[0].id == "L1"
    assert isinstance(calls[1], CurveCall)
    assert calls[1].id == "C1"
    assert calls[1].params.handedness == Handedness.LEFT


def test_curve_with_deterministic_concavity_renders_without_explicit_handedness():
    text = (
        "THENCE NORTH 00°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A CURVE CONCAVE EASTERLY, HAVING A RADIUS OF "
        "100.00 FEET, AN ARC DISTANCE OF 25.00 FEET;"
    )

    calls, ties, errors, ignored = parse_legal_description(text)
    result = build_geometry(start_point=(0.0, 0.0), calls=calls)

    assert len(calls) == 2
    assert isinstance(calls[1], CurveCall)
    assert calls[1].params.handedness is None
    assert len(result["curves"]) == 1
    assert result["curves"][0]["handedness"] == "right"

# ============================================================
# Realistic legal-description sample cases (parse → build)
# ============================================================

_QUARTER_ARC_R50 = 78.5398  # 50 * pi/2, a 90-degree arc on a 50 ft radius


def _parse_and_build(text: str):
    calls, _, _, _ = parse_legal_description(text)
    result = build_geometry(start_point=(0.0, 0.0), calls=calls)
    return calls, result


def test_sample_north_then_concave_east_renders_right():
    text = (
        "THENCE NORTH 0°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A CURVE CONCAVE EASTERLY, HAVING A RADIUS OF 50.00 FEET, "
        f"AN ARC DISTANCE OF {_QUARTER_ARC_R50} FEET;"
    )
    _, result = _parse_and_build(text)

    assert len(result["curves"]) == 1
    assert result["curves"][0]["handedness"] == "right"
    assert result["points"][-1] == pytest.approx((50.0, 150.0), abs=1e-3)


def test_sample_north_then_concave_west_renders_left():
    text = (
        "THENCE NORTH 0°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A CURVE CONCAVE WESTERLY, HAVING A RADIUS OF 50.00 FEET, "
        f"AN ARC DISTANCE OF {_QUARTER_ARC_R50} FEET;"
    )
    _, result = _parse_and_build(text)

    assert len(result["curves"]) == 1
    assert result["curves"][0]["handedness"] == "left"
    assert result["points"][-1] == pytest.approx((-50.0, 150.0), abs=1e-3)


def test_sample_east_then_concave_south_with_delta_renders_right():
    text = (
        "THENCE NORTH 90°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A CURVE CONCAVE SOUTHERLY, HAVING A RADIUS OF 50.00 FEET, "
        "THROUGH A CENTRAL ANGLE OF 90°00';"
    )
    _, result = _parse_and_build(text)

    assert len(result["curves"]) == 1
    assert result["curves"][0]["handedness"] == "right"
    assert result["points"][-1] == pytest.approx((150.0, -50.0), abs=1e-3)


def test_sample_east_then_concave_north_with_delta_renders_left():
    text = (
        "THENCE NORTH 90°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A CURVE CONCAVE NORTHERLY, HAVING A RADIUS OF 50.00 FEET, "
        "THROUGH A CENTRAL ANGLE OF 90°00';"
    )
    _, result = _parse_and_build(text)

    assert len(result["curves"]) == 1
    assert result["curves"][0]["handedness"] == "left"
    assert result["points"][-1] == pytest.approx((150.0, 50.0), abs=1e-3)


def test_sample_collinear_concavity_is_parsed_but_skipped():
    text = (
        "THENCE NORTH 0°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A CURVE CONCAVE NORTHERLY, HAVING A RADIUS OF 50.00 FEET, "
        f"AN ARC DISTANCE OF {_QUARTER_ARC_R50} FEET;"
    )
    calls, result = _parse_and_build(text)

    assert any(isinstance(call, CurveCall) for call in calls)
    assert result["curves"] == []
    assert result["points"][-1] == pytest.approx((0.0, 100.0), abs=1e-6)


def test_sample_curve_missing_radius_is_not_curvecall_and_skips():
    text = (
        "THENCE NORTH 0°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A CURVE CONCAVE EASTERLY, "
        f"AN ARC DISTANCE OF {_QUARTER_ARC_R50} FEET;"
    )
    calls, result = _parse_and_build(text)

    assert not any(isinstance(call, CurveCall) for call in calls)
    assert result["curves"] == []
    assert result["points"][-1] == pytest.approx((0.0, 100.0), abs=1e-6)


def test_sample_curve_missing_arc_and_delta_is_not_curvecall_and_skips():
    text = (
        "THENCE NORTH 0°00'00\" EAST 100.00 FEET; "
        "THENCE ALONG A CURVE CONCAVE EASTERLY, HAVING A RADIUS OF 50.00 FEET;"
    )
    calls, result = _parse_and_build(text)

    assert not any(isinstance(call, CurveCall) for call in calls)
    assert result["curves"] == []
    assert result["points"][-1] == pytest.approx((0.0, 100.0), abs=1e-6)

