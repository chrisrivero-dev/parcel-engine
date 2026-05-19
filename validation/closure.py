import math
from typing import List, Tuple, Dict

Point = Tuple[float, float]


def compute_closure(points: List[Point]) -> Dict[str, float | None]:
    """
    Compute closure statistics for a polygon or traverse.

    Returns:
      {
        "dx": float,
        "dy": float,
        "misclosure": float,
        "precision": float | None
      }
    """
    if len(points) < 2:
        raise ValueError("Need at least two points to compute closure")

    x0, y0 = points[0]
    xn, yn = points[-1]

    dx = xn - x0
    dy = yn - y0

    misclosure = math.hypot(dx, dy)

    # Compute perimeter
    perimeter = 0.0
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        perimeter += math.hypot(x2 - x1, y2 - y1)

    precision = None
    if misclosure > 0.0:
        precision = perimeter / misclosure

    return {
        "dx": dx,
        "dy": dy,
        "misclosure": misclosure,
        "precision": precision,
    }
