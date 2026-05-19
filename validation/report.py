from typing import Dict, List, Any

from validation.closure import compute_closure
from validation.intersections import find_self_intersections
from validation.curve_checks import validate_curve_params
from models.schema import CurveParams
from models.errors import ErrorCode


def build_validation_report(
    *,
    points: List[tuple],
    curves: List[CurveParams],
) -> Dict[str, Any]:
    """
    Aggregate validation results into a single report.
    This function NEVER modifies geometry.
    """

    closure = compute_closure(points)
    intersections = find_self_intersections(points)

    curve_errors: Dict[int, List[ErrorCode]] = {}
    for idx, curve in enumerate(curves):
        errs = validate_curve_params(curve)
        if errs:
            curve_errors[idx] = errs

    return {
        "closure": closure,
        "intersections": intersections,
        "curve_errors": curve_errors,
    }
