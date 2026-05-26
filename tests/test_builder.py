import math

import pytest

from geometry.builder import build_geometry, _resolve_handedness
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

# ============================================================
# Concavity-to-handedness resolution
# ============================================================

@pytest.mark.parametrize("concavity,incoming_az,expected", [
    ("CONCAVE EAST", 0.0, Handedness.RIGHT),
    ("CONCAVE WEST", 0.0, Handedness.LEFT),
    ("CONCAVE SOUTH", 90.0, Handedness.RIGHT),
    ("CONCAVE NORTH", 90.0, Handedness.LEFT),
    ("CONCAVE WEST", 180.0, Handedness.RIGHT),
    ("CONCAVE EAST", 180.0, Handedness.LEFT),
    ("CONCAVE NORTH", 270.0, Handedness.RIGHT),
    ("CONCAVE SOUTH", 270.0, Handedness.LEFT),
    ("CONCAVE EASTERLY", 0.0, Handedness.RIGHT),
    ("CONCAVE WESTERLY", 0.0, Handedness.LEFT),
    ("CONCAVE NORTHEASTERLY", 270.0, Handedness.RIGHT),
    ("CONCAVE SOUTHWESTERLY", 90.0, Handedness.RIGHT),
])
def test_resolve_handedness_deterministic(concavity, incoming_az, expected):
    assert _resolve_handedness(concavity, incoming_az) == expected


@pytest.mark.parametrize("concavity,incoming_az", [
    ("CONCAVE NORTH", 0.0),
    ("CONCAVE SOUTH", 0.0),
    ("CONCAVE EAST", 90.0),
    ("CONCAVE WEST", 270.0),
    (None, 0.0),
    ("", 0.0),
    ("ALONG SOMETHING", 0.0),
    ("CONCAVE DIAGONAL", 0.0),
])
def test_resolve_handedness_ambiguous_returns_none(concavity, incoming_az):
    assert _resolve_handedness(concavity, incoming_az) is None


def test_concavity_curve_resolves_and_renders():
    arc = 50.0 * (math.pi / 2.0)
    calls = [
        _north_100(),
        CurveCall(
            id="C1",
            raw_text="concave easterly curve",
            along_feature="CONCAVE EASTERLY",
            params=CurveParams(
                curve_type=CurveType.NON_TANGENT,
                radius=50.0,
                handedness=None,
                arc_length=arc,
            ),
        ),
    ]

    result = build_geometry(start_point=(0.0, 0.0), calls=calls)

    assert len(result["curves"]) == 1
    assert result["curves"][0]["handedness"] == "right"
    assert result["points"][-1] == pytest.approx((50.0, 150.0), abs=1e-6)


def test_concavity_curve_west_resolves_left():
    arc = 50.0 * (math.pi / 2.0)
    calls = [
        _north_100(),
        CurveCall(
            id="C1",
            raw_text="concave westerly curve",
            along_feature="CONCAVE WESTERLY",
            params=CurveParams(
                curve_type=CurveType.NON_TANGENT,
                radius=50.0,
                handedness=None,
                arc_length=arc,
            ),
        ),
    ]

    result = build_geometry(start_point=(0.0, 0.0), calls=calls)

    assert len(result["curves"]) == 1
    assert result["curves"][0]["handedness"] == "left"
    assert result["points"][-1] == pytest.approx((-50.0, 150.0), abs=1e-6)


def test_ambiguous_concavity_still_skips():
    arc = 50.0 * (math.pi / 2.0)
    calls = [
        _north_100(),
        CurveCall(
            id="C1",
            raw_text="concave north curve",
            along_feature="CONCAVE NORTH",
            params=CurveParams(
                curve_type=CurveType.NON_TANGENT,
                radius=50.0,
                handedness=None,
                arc_length=arc,
            ),
        ),
    ]

    result = build_geometry(start_point=(0.0, 0.0), calls=calls)

    assert result["curves"] == []
    assert result["points"][-1] == pytest.approx((0.0, 100.0), abs=1e-6)

