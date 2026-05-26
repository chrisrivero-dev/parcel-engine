import math

import pytest

from geometry.builder import build_geometry
from models.schema import (
    LineCall,
    CurveCall,
    Bearing,
    BearingFormat,
    AzimuthBearing,
    DMS,
    DirectionBasis,
    CurveParams,
    CurveType,
    Handedness,
    Distance,
)


def azimuth(deg: float) -> AzimuthBearing:
    return AzimuthBearing(
        azimuth=DMS(
            deg=int(deg),
            minutes=0,
            seconds=0,
        )
    )


def dist(val: float) -> Distance:
    return Distance(raw_text=str(val), value=val)


def test_builder_lines_only_square():
    calls = [
        LineCall(
            id="L1",
            raw_text="E 100",
            bearing=Bearing(
                raw_text="E",
                format=BearingFormat.AZIMUTH,
                value=azimuth(90.0),
                basis=DirectionBasis.TRUE,
            ),
            distance=dist(100.0),
        ),
        LineCall(
            id="L2",
            raw_text="N 100",
            bearing=Bearing(
                raw_text="N",
                format=BearingFormat.AZIMUTH,
                value=azimuth(0.0),
                basis=DirectionBasis.TRUE,
            ),
            distance=dist(100.0),
        ),
        LineCall(
            id="L3",
            raw_text="W 100",
            bearing=Bearing(
                raw_text="W",
                format=BearingFormat.AZIMUTH,
                value=azimuth(270.0),
                basis=DirectionBasis.TRUE,
            ),
            distance=dist(100.0),
        ),
        LineCall(
            id="L4",
            raw_text="S 100",
            bearing=Bearing(
                raw_text="S",
                format=BearingFormat.AZIMUTH,
                value=azimuth(180.0),
                basis=DirectionBasis.TRUE,
            ),
            distance=dist(100.0),
        ),
    ]

    result = build_geometry(
        start_point=(0.0, 0.0),
        calls=calls,
    )

    pts = result["points"]

    assert pts[0] == (0.0, 0.0)
    assert pts[-1] == pytest.approx((0.0, 0.0))
    assert len(pts) == 5
    assert result["curves"] == []


def test_builder_line_then_curve():
    calls = [
        LineCall(
            id="L1",
            raw_text="N 100",
            bearing=Bearing(
                raw_text="N",
                format=BearingFormat.AZIMUTH,
                value=azimuth(0.0),
                basis=DirectionBasis.TRUE,
            ),
            distance=dist(100.0),
        ),
        CurveCall(
            id="C1",
            raw_text="Curve Right R50 Δ90",
            params=CurveParams(
                curve_type=CurveType.TANGENT,
                radius=50.0,
                handedness=Handedness.RIGHT,
                delta=DMS(deg=90, minutes=0, seconds=0),
            )
        ),
    ]

    result = build_geometry(
        start_point=(0.0, 0.0),
        calls=calls,
    )

    assert len(result["points"]) > 5
    assert len(result["curves"]) == 1

# ============================================================
# Minimal curve rendering (explicit handedness only)
# ============================================================

def _north_100() -> LineCall:
    return LineCall(
        id="L1",
        raw_text="N 100",
        bearing=Bearing(
            raw_text="N",
            format=BearingFormat.AZIMUTH,
            value=azimuth(0.0),
            basis=DirectionBasis.TRUE,
        ),
        distance=dist(100.0),
    )


def test_curve_renders_with_handedness_and_delta_endpoint():
    """Right quarter circle from (0,100) heading North -> endpoint (50,150)."""
    calls = [
        _north_100(),
        CurveCall(
            id="C1",
            raw_text="curve right R50 delta 90",
            params=CurveParams(
                curve_type=CurveType.TANGENT,
                radius=50.0,
                handedness=Handedness.RIGHT,
                delta=DMS(deg=90, minutes=0, seconds=0),
            ),
        ),
    ]

    result = build_geometry(start_point=(0.0, 0.0), calls=calls)

    assert len(result["curves"]) == 1
    assert result["points"][-1] == pytest.approx((50.0, 150.0), abs=1e-6)


def test_curve_renders_with_handedness_and_arc_length():
    """Arc length 50*(pi/2) over radius 50 == 90 degrees."""
    arc = 50.0 * (math.pi / 2.0)
    calls = [
        _north_100(),
        CurveCall(
            id="C1",
            raw_text="curve right R50 arc",
            params=CurveParams(
                curve_type=CurveType.NON_TANGENT,
                radius=50.0,
                handedness=Handedness.RIGHT,
                arc_length=arc,
            ),
        ),
    ]

    result = build_geometry(start_point=(0.0, 0.0), calls=calls)

    assert len(result["curves"]) == 1
    assert result["points"][-1] == pytest.approx((50.0, 150.0), abs=1e-6)


def test_curve_without_handedness_is_skipped():
    """No handedness -> curve must not render and must not fabricate geometry."""
    calls = [
        _north_100(),
        CurveCall(
            id="C1",
            raw_text="curve concave easterly R50 arc",
            params=CurveParams(
                curve_type=CurveType.NON_TANGENT,
                radius=50.0,
                handedness=None,
                arc_length=78.54,
            ),
        ),
    ]

    result = build_geometry(start_point=(0.0, 0.0), calls=calls)

    assert result["curves"] == []
    assert result["points"][-1] == pytest.approx((0.0, 100.0), abs=1e-6)

