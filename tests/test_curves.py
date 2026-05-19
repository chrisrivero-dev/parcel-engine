import pytest

from geometry.curves import compute_curve
from models.schema import (
    CurveParams,
    CurveType,
    Handedness,
    DMS,
)


def test_tangent_curve_left_quarter_circle():
    """
    Start at (0,0), heading EAST (azimuth 90).
    Left curve, radius 100, delta 90 degrees.

    Geometry:
    - Center = (0, 100)
    - Endpoint = (-100, 100)
    """
    start = (0.0, 0.0)
    incoming_tangent = 90.0  # east

    params = CurveParams(
        curve_type=CurveType.TANGENT,
        radius=100.0,
        handedness=Handedness.LEFT,
        delta=DMS(deg=90, minutes=0, seconds=0),
    )

    end_pt, arc_pts = compute_curve(
        start,
        params,
        incoming_tangent_azimuth_deg=incoming_tangent,
        segments_per_curve=32,
    )

    assert end_pt[0] == pytest.approx(100.0, abs=1e-6)
    assert end_pt[1] == pytest.approx(100.0, abs=1e-6)


    # arc should have multiple sampled points
    assert len(arc_pts) > 5


def test_tangent_curve_right_quarter_circle():
    """
    Start at (0,0), heading NORTH (azimuth 0).
    Right curve, radius 50, delta 90 degrees.

    Geometry:
    - Center = (50, 0)
    - Endpoint = (50, 50)
    """
    start = (0.0, 0.0)
    incoming_tangent = 0.0  # north

    params = CurveParams(
        curve_type=CurveType.TANGENT,
        radius=50.0,
        handedness=Handedness.RIGHT,
        delta=DMS(deg=90, minutes=0, seconds=0),
    )

    end_pt, arc_pts = compute_curve(
        start,
        params,
        incoming_tangent_azimuth_deg=incoming_tangent,
        segments_per_curve=32,
    )

    assert end_pt[0] == pytest.approx(50.0, abs=1e-6)
    assert end_pt[1] == pytest.approx(50.0, abs=1e-6)

    assert len(arc_pts) > 5


def test_tangent_curve_requires_incoming_tangent():
    """
    Tangent curves MUST have an incoming tangent azimuth.
    """
    start = (0.0, 0.0)

    params = CurveParams(
        curve_type=CurveType.TANGENT,
        radius=100.0,
        handedness=Handedness.LEFT,
        delta=DMS(deg=45, minutes=0, seconds=0),
    )

    with pytest.raises(ValueError):
        compute_curve(
            start,
            params,
            incoming_tangent_azimuth_deg=None,
        )
