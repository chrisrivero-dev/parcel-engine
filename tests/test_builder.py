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
