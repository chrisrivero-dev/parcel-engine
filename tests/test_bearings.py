# FILE: tests/test_bearings.py

import pytest
from geometry.bearings import bearing_to_azimuth_degrees
from models.schema import (
    Bearing,
    BearingFormat,
    QuadrantBearing,
    AzimuthBearing,
    DMS,
    DirectionBasis,
)
from models.errors import ErrorCode


def test_quadrant_NE():
    b = Bearing(
        raw_text="N 30°00'00\" E",
        format=BearingFormat.QUADRANT,
        value=QuadrantBearing(
            quadrant_ns="N",
            quadrant_ew="E",
            angle=DMS(deg=30, minutes=0, seconds=0),
        ),
        basis=DirectionBasis.TRUE,
    )

    az = bearing_to_azimuth_degrees(b)
    assert az == pytest.approx(30.0)


def test_quadrant_NW():
    b = Bearing(
        raw_text="N 45°00'00\" W",
        format=BearingFormat.QUADRANT,
        value=QuadrantBearing(
            quadrant_ns="N",
            quadrant_ew="W",
            angle=DMS(deg=45, minutes=0, seconds=0),
        ),
        basis=DirectionBasis.TRUE,
    )

    az = bearing_to_azimuth_degrees(b)
    assert az == pytest.approx(315.0)


def test_quadrant_SE():
    b = Bearing(
        raw_text="S 10°00'00\" E",
        format=BearingFormat.QUADRANT,
        value=QuadrantBearing(
            quadrant_ns="S",
            quadrant_ew="E",
            angle=DMS(deg=10, minutes=0, seconds=0),
        ),
        basis=DirectionBasis.TRUE,
    )

    az = bearing_to_azimuth_degrees(b)
    assert az == pytest.approx(170.0)


def test_azimuth_dms():
    b = Bearing(
        raw_text="123°30'00\"",
        format=BearingFormat.AZIMUTH,
        value=AzimuthBearing(
            azimuth=DMS(deg=123, minutes=30, seconds=0)
        ),
        basis=DirectionBasis.TRUE,
    )

    az = bearing_to_azimuth_degrees(b)
    assert az == pytest.approx(123.5)


def test_unknown_bearing_fails():
    b = Bearing(
        raw_text="unknown",
        format=BearingFormat.UNKNOWN,
        value=None,
        basis=DirectionBasis.TRUE,
    )

    with pytest.raises(ValueError) as exc:
        bearing_to_azimuth_degrees(b)

    assert ErrorCode.BAD_BEARING_FORMAT.value in str(exc.value)
