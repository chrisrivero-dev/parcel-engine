import pytest

from validation.intersections import find_self_intersections


def test_no_self_intersection_square():
    pts = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
    ]
    hits = find_self_intersections(pts)
    assert hits == []


def test_bowtie_self_intersects():
    # bowtie polygon: (0,0)->(10,10)->(0,10)->(10,0)->(0,0)
    pts = [
        (0.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (10.0, 0.0),
        (0.0, 0.0),
    ]
    hits = find_self_intersections(pts)
    assert len(hits) >= 1

    # Each hit should report segment index pairs
    a, b = hits[0]
    assert isinstance(a, tuple) and isinstance(b, tuple)
    assert a[0] != b[0]


def test_adjacent_segments_not_flagged():
    # Shared endpoint is normal and must not be flagged
    pts = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 0.0),
    ]
    hits = find_self_intersections(pts)
    assert hits == []
