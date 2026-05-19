import pytest

from validation.curve_checks import validate_curve_params
from models.schema import CurveParams, CurveType, Handedness, DMS
from models.errors import ErrorCode


def test_valid_delta_only_passes():
    params = CurveParams(
        curve_type=CurveType.TANGENT,
        radius=100.0,
        handedness=Handedness.LEFT,
        delta=DMS(deg=45, minutes=0, seconds=0),
    )

    errors = validate_curve_params(params)
    assert errors == []


def test_arc_length_requires_radius_fails():
    params = CurveParams(
        curve_type=CurveType.TANGENT,
        radius=None,
        handedness=Handedness.LEFT,
        arc_length=50.0,
    )

    errors = validate_curve_params(params)
    assert ErrorCode.CURVE_INCOMPLETE in errors


def test_chord_length_requires_radius_fails():
    params = CurveParams(
        curve_type=CurveType.TANGENT,
        radius=None,
        handedness=Handedness.RIGHT,
        chord_length=30.0,
    )

    errors = validate_curve_params(params)
    assert ErrorCode.CURVE_INCOMPLETE in errors


def test_invalid_chord_radius_combo_fails():
    params = CurveParams(
        curve_type=CurveType.TANGENT,
        radius=10.0,
        handedness=Handedness.LEFT,
        chord_length=50.0,  # impossible: chord > 2r
    )

    errors = validate_curve_params(params)
    assert ErrorCode.CURVE_PARAM_MISMATCH in errors
