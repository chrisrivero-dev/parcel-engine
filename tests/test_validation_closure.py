import pytest
import math

from validation.closure import compute_closure


def test_perfect_closure():
    """
    Square that closes perfectly.
    """
    pts = [
        (0.0, 0.0),
        (100.0, 0.0),
        (100.0, 100.0),
        (0.0, 100.0),
        (0.0, 0.0),
    ]

    result = compute_closure(pts)

    assert result["dx"] == pytest.approx(0.0)
    assert result["dy"] == pytest.approx(0.0)
    assert result["misclosure"] == pytest.approx(0.0)
    assert result["precision"] is None


def test_small_misclosure():
    """
    Slight gap at closure.
    """
    pts = [
        (0.0, 0.0),
        (100.0, 0.0),
        (100.0, 100.0),
        (0.0, 100.0),
        (0.1, 0.0),  # gap
    ]

    result = compute_closure(pts)

    assert result["misclosure"] > 0.0
    assert result["precision"] > 0.0
    assert result["precision"] < 10_000  # sanity bound


def test_invalid_input_fails():
    """
    Need at least 2 points.
    """
    with pytest.raises(ValueError):
        compute_closure([(0.0, 0.0)])
