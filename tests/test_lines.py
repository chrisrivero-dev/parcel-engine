# FILE: tests/test_lines.py

import pytest

from geometry.lines import compute_line


def test_due_north():
    start = (0.0, 0.0)
    end = compute_line(start, azimuth_deg=0.0, distance=100.0)
    assert end[0] == pytest.approx(0.0)
    assert end[1] == pytest.approx(100.0)


def test_due_east():
    start = (0.0, 0.0)
    end = compute_line(start, azimuth_deg=90.0, distance=50.0)
    assert end[0] == pytest.approx(50.0)
    assert end[1] == pytest.approx(0.0)


def test_due_south():
    start = (10.0, 10.0)
    end = compute_line(start, azimuth_deg=180.0, distance=10.0)
    assert end[0] == pytest.approx(10.0)
    assert end[1] == pytest.approx(0.0)


def test_due_west():
    start = (5.0, 5.0)
    end = compute_line(start, azimuth_deg=270.0, distance=5.0)
    assert end[0] == pytest.approx(0.0)
    assert end[1] == pytest.approx(5.0)


def test_diagonal_NE_45():
    start = (0.0, 0.0)
    end = compute_line(start, azimuth_deg=45.0, distance=100.0)

    expected = 100.0 / (2 ** 0.5)
    assert end[0] == pytest.approx(expected)
    assert end[1] == pytest.approx(expected)


def test_zero_or_negative_distance_fails():
    start = (0.0, 0.0)

    with pytest.raises(ValueError):
        compute_line(start, azimuth_deg=0.0, distance=0.0)

    with pytest.raises(ValueError):
        compute_line(start, azimuth_deg=0.0, distance=-10.0)
