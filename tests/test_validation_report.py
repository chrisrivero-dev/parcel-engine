import pytest

from validation.report import build_validation_report
from models.schema import CurveParams, CurveType, Handedness, DMS
from models.errors import ErrorCode


def test_empty_report_passes():
    pts = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
    ]

    curves = []

    report = build_validation_report(
        points=pts,
        curves=curves,
    )

    assert report["closure"]["misclosure"] == pytest.approx(0.0)
    assert report["intersections"] == []
    assert report["curve_errors"] == {}


def test_report_collects_curve_errors():
    pts = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
    ]

    curves = [
        CurveParams(
            curve_type=CurveType.TANGENT,
            radius=None,  # ❌ invalid
            handedness=Handedness.LEFT,
            delta=DMS(deg=45, minutes=0, seconds=0),
        )
    ]

    report = build_validation_report(
        points=pts,
        curves=curves,
    )

    assert 0 in report["curve_errors"]
    assert ErrorCode.CURVE_INCOMPLETE in report["curve_errors"][0]
