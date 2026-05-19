from __future__ import annotations

from typing import List, Tuple, Optional

Point = Tuple[float, float]
Seg = Tuple[Point, Point]
Hit = Tuple[Tuple[int, int], Tuple[int, int]]  # ((i,i+1),(j,j+1))


def _orient(a: Point, b: Point, c: Point) -> float:
    # cross product (b-a) x (c-a)
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a: Point, b: Point, p: Point, eps: float = 1e-12) -> bool:
    # p collinear with a-b and within bbox
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
    )


def _segments_intersect(s1: Seg, s2: Seg, eps: float = 1e-12) -> bool:
    a, b = s1
    c, d = s2

    o1 = _orient(a, b, c)
    o2 = _orient(a, b, d)
    o3 = _orient(c, d, a)
    o4 = _orient(c, d, b)

    # General case
    if (o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and (o3 > eps and o4 < -eps or o3 < -eps and o4 > eps):
        return True

    # Collinear / touching cases (do NOT treat shared endpoints as intersection here)
    if abs(o1) <= eps and _on_segment(a, b, c, eps):
        return True
    if abs(o2) <= eps and _on_segment(a, b, d, eps):
        return True
    if abs(o3) <= eps and _on_segment(c, d, a, eps):
        return True
    if abs(o4) <= eps and _on_segment(c, d, b, eps):
        return True

    return False


def _is_adjacent(i: int, j: int, nsegs: int) -> bool:
    # Adjacent segments share a vertex and should not count as self-intersection.
    # Segment k is (k, k+1). Adjacent if indices differ by 1, or first/last in closed ring.
    if abs(i - j) == 1:
        return True
    if i == 0 and j == nsegs - 1:
        return True
    if j == 0 and i == nsegs - 1:
        return True
    return False


def find_self_intersections(points: List[Point]) -> List[Hit]:
    """
    Given a polyline/polygon vertex list, find all non-adjacent segment intersections.

    - Treats consecutive points as segments.
    - Ignores intersections between adjacent segments (shared endpoints).
    - Works for closed rings (first == last) and open polylines.

    Returns: list of hits as segment index pairs.
    """
    if len(points) < 4:
        return []

    segs: List[Seg] = []
    for i in range(len(points) - 1):
        segs.append((points[i], points[i + 1]))

    hits: List[Hit] = []
    nsegs = len(segs)

    for i in range(nsegs):
        for j in range(i + 1, nsegs):
            if _is_adjacent(i, j, nsegs):
                continue

            s1 = segs[i]
            s2 = segs[j]

            # skip if they share an endpoint exactly (common in closed rings)
            if s1[0] == s2[0] or s1[0] == s2[1] or s1[1] == s2[0] or s1[1] == s2[1]:
                continue

            if _segments_intersect(s1, s2):
                hits.append(((i, i + 1), (j, j + 1)))

    return hits
