import math
from typing import List

from models.schema import CurveParams
from models.errors import ErrorCode


def validate_curve_params(params: CurveParams) -> List[ErrorCode]:
    """
    Validate internal consistency of curve parameters.
    Does NOT compute geometry. Reports issues only.
    """
    errors: List[ErrorCode] = []

    # Radius checks
    if params.radius is not None and params.radius <= 0:
        errors.append(ErrorCode.CURVE_INCOMPLETE)

    # Delta checks
    if params.delta is not None:
        deg = (
            params.delta.deg
            + params.delta.minutes / 60.0
            + params.delta.seconds / 3600.0
        )
        if deg <= 0:
            errors.append(ErrorCode.CURVE_INCOMPLETE)

    # Arc length requires radius
    if params.arc_length is not None:
        if params.radius is None or params.radius <= 0:
            errors.append(ErrorCode.CURVE_INCOMPLETE)
        elif params.arc_length <= 0:
            errors.append(ErrorCode.CURVE_INCOMPLETE)

    # Chord length requires radius and compatibility
    if params.chord_length is not None:
        if params.radius is None or params.radius <= 0:
            errors.append(ErrorCode.CURVE_INCOMPLETE)
        else:
            if params.chord_length <= 0:
                errors.append(ErrorCode.CURVE_INCOMPLETE)
            elif params.chord_length > 2 * params.radius:
                errors.append(ErrorCode.CURVE_PARAM_MISMATCH)
                    # Tangent curves REQUIRE radius
    if params.curve_type.name == "TANGENT":
        if params.radius is None or params.radius <= 0:
            errors.append(ErrorCode.CURVE_INCOMPLETE)


    # Ensure we can derive delta deterministically
    can_derive_delta = (
        params.delta is not None
        or (params.arc_length is not None and params.radius is not None)
        or (params.chord_length is not None and params.radius is not None)
    )

    if not can_derive_delta:
        errors.append(ErrorCode.CURVE_INCOMPLETE)

    return errors
