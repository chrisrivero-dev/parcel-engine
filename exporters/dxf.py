from __future__ import annotations

from typing import Iterable, Tuple

import ezdxf

Point = Tuple[float, float]


def export_dxf(points: Iterable[Point], output_path: str) -> str:
    """
    Export a parcel boundary as a lightweight polyline to DXF.

    Parameters:
    - points: ordered boundary points
    - output_path: target .dxf path

    Returns:
    - output_path
    """
    point_list = [(float(x), float(y)) for x, y in points]
    if len(point_list) < 2:
        raise ValueError("At least two points are required for DXF export")

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    is_closed = point_list[0] == point_list[-1]
    lwpoly_points = [(x, y) for x, y in point_list[:-1]] if is_closed else point_list

    msp.add_lwpolyline(
        lwpoly_points,
        close=is_closed,
        dxfattribs={"layer": "PARCEL"},
    )

    doc.saveas(output_path)
    return output_path