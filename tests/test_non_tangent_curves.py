import pytest

from geometry.curves import compute_curve
from models.schema import (
    CurveParams,
    CurveType,
    Handedness,
    DMS,
    Bearing,
    BearingFormat,
    QuadrantBearing,
    DirectionBasis,
)
from models.errors import ErrorCode


# ------------------------------------------------------------
# 1) Missing radial bearing → HARD FAIL
# ------------------------------------------------------------

def test_non_tangent_missing_radial_bearing_fails():
    """
    Non-tangent curves MUST have an explicit radial bearing
    from CENTER → PC. No inference allowed.
    """
    start = (0.0, 0.0)

    params = CurveParams(
        curve_type=CurveType.NON_TANGENT,
        radius=100.0,
        handedness=Handedness.LEFT,
        delta=DMS(deg=60, minutes=0, seconds=0),
        radial_bearing_to_pc=None,  # ❌ missing
    )

    with pytest.raises(ValueError) as exc:
        compute_curve(start, params)

    assert ErrorCode.NON_TANGENT_AMBIGUITY.value in str(exc.value)


# ------------------------------------------------------------
# 2) Partial parameters → HARD FAIL
# ------------------------------------------------------------

def test_non_tangent_incomplete_params_fail():
    """
    Radius alone is not sufficient.
    Delta alone is not sufficient.
    No fallback assumptions permitted.
    """
    start = (0.0, 0.0)

    params = CurveParams(
        curve_type=CurveType.NON_TANGENT,
        radius=100.0,
        handedness=Handedness.RIGHT,
        delta=None,  # ❌ cannot derive delta
        radial_bearing_to_pc=None,
    )

    with pytest.raises(ValueError) as exc:
        compute_curve(start, params)

    # Could be CURVE_INCOMPLETE or NON_TANGENT_AMBIGUITY — both are valid hard stops
    msg = str(exc.value)
    assert (
        ErrorCode.CURVE_INCOMPLETE.value in msg
        or ErrorCode.NON_TANGENT_AMBIGUITY.value in msg
    )


# ------------------------------------------------------------
# 3) Fully specified non-tangent curve → PASS
# ------------------------------------------------------------

def test_non_tangent_with_explicit_radial_bearing_passes():
    """
    Explicit non-tangent curve with:
    - radius
    - handedness
    - delta
    - radial bearing from CENTER → PC

    This MUST compute deterministically.
    """
    start = (0.0, 0.0)

    radial_bearing = Bearing(
        raw_text="S 90°00'00\" W",
        format=BearingFormat.QUADRANT,
        value=QuadrantBearing(
            quadrant_ns="S",
            quadrant_ew="W",
            angle=DMS(deg=90, minutes=0, seconds=0),
        ),
        basis=DirectionBasis.TRUE,
    )

    params = CurveParams(
        curve_type=CurveType.NON_TANGENT,
        radius=50.0,
        handedness=Handedness.LEFT,
        delta=DMS(deg=90, minutes=0, seconds=0),
        radial_bearing_to_pc=radial_bearing,
    )

    end_pt, arc_pts = compute_curve(
        start,
        params,
        segments_per_curve=32,
    )

    # Deterministic geometry checks
    assert isinstance(end_pt, tuple)
    assert len(end_pt) == 2
    assert len(arc_pts) > 5
