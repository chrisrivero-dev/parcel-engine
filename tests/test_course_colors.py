"""Tests for ui.course_colors.  Qt-free on purpose."""

import pytest

from ui.course_colors import (
    KIND_LEGAL,
    KIND_REFERENCE_TIE,
    KIND_SUGGESTED,
    KIND_UNRESOLVED,
    CourseStyle,
    assign_styles,
    boundary_color,
    drawable_indices,
    is_drawable_boundary,
    normalize_kind,
    palette_size,
    style_for,
)


def test_boundary_color_is_stable_for_same_index():
    assert boundary_color(0) == boundary_color(0)
    assert boundary_color(3) == boundary_color(3)


def test_boundary_colors_differ_within_palette():
    colors = [boundary_color(i) for i in range(palette_size())]
    assert len(set(colors)) == palette_size()


def test_boundary_color_cycles_after_palette_exhausted():
    n = palette_size()
    assert boundary_color(0) == boundary_color(n)
    assert boundary_color(1) == boundary_color(n + 1)


def test_boundary_color_rejects_negative():
    with pytest.raises(ValueError):
        boundary_color(-1)


def test_boundary_color_returns_hex():
    c = boundary_color(0)
    assert c.startswith("#") and len(c) == 7


@pytest.mark.parametrize("raw, expected", [
    ("legal", KIND_LEGAL),
    ("LEGAL", KIND_LEGAL),
    (None, KIND_LEGAL),
    ("", KIND_LEGAL),
    ("garbage", KIND_LEGAL),
    ("suggested", KIND_SUGGESTED),
    ("Suggestion", KIND_SUGGESTED),
    ("proposed", KIND_SUGGESTED),
    ("reference_tie", KIND_REFERENCE_TIE),
    ("reference-tie", KIND_REFERENCE_TIE),
    ("tie", KIND_REFERENCE_TIE),
    ("unresolved", KIND_UNRESOLVED),
    ("direction_only", KIND_UNRESOLVED),
])
def test_normalize_kind(raw, expected):
    assert normalize_kind(raw) == expected


@pytest.mark.parametrize("kind, drawable", [
    (KIND_LEGAL, True),
    (KIND_SUGGESTED, True),
    (KIND_REFERENCE_TIE, False),
    (KIND_UNRESOLVED, False),
    ("tie", False),
    (None, True),
])
def test_is_drawable_boundary(kind, drawable):
    assert is_drawable_boundary(kind) is drawable


def test_legal_style_is_solid_drawable_no_tint():
    s = style_for("L1", KIND_LEGAL, 0)
    assert isinstance(s, CourseStyle)
    assert s.drawable is True
    assert s.dashed is False
    assert s.row_tint is None
    assert s.color == boundary_color(0)
    assert s.boundary_index == 0


def test_suggested_style_shares_palette_but_dashed_and_tinted():
    legal = style_for("L2", KIND_LEGAL, 1)
    suggested = style_for("S2", KIND_SUGGESTED, 1)
    assert suggested.color == legal.color
    assert suggested.dashed is True
    assert suggested.drawable is True
    assert suggested.row_tint is not None


def test_reference_tie_style_not_drawable():
    s = style_for("RT1", KIND_REFERENCE_TIE, -1)
    assert s.drawable is False
    assert s.boundary_index == -1
    assert s.row_tint is not None


def test_unresolved_style_not_drawable_but_dashed():
    s = style_for("U1", KIND_UNRESOLVED, -1)
    assert s.drawable is False
    assert s.dashed is True
    assert s.boundary_index == -1


def test_assign_styles_all_legal_get_sequential_palette():
    styles = assign_styles([("L1", "legal"), ("L2", "legal"), ("L3", "legal")])
    assert [s.color for s in styles] == [
        boundary_color(0), boundary_color(1), boundary_color(2),
    ]
    assert [s.boundary_index for s in styles] == [0, 1, 2]


def test_assign_styles_tie_does_not_shift_boundary_colors():
    rows = [
        ("L1", "legal"),
        ("RT1", "reference_tie"),
        ("L2", "legal"),
    ]
    styles = assign_styles(rows)
    assert styles[0].color == boundary_color(0)
    assert styles[2].color == boundary_color(1)
    assert styles[1].drawable is False


def test_assign_styles_mixed_kinds_drawable_flags():
    rows = [
        ("L1", "legal"),
        ("S1", "suggested"),
        ("RT1", "reference_tie"),
        ("U1", "unresolved"),
    ]
    styles = assign_styles(rows)
    assert [s.drawable for s in styles] == [True, True, False, False]


def test_drawable_indices_bridges_rows_to_segments():
    rows = [
        ("L1", "legal"),
        ("RT1", "reference_tie"),
        ("L2", "legal"),
        ("U1", "unresolved"),
        ("S1", "suggested"),
    ]
    styles = assign_styles(rows)
    assert drawable_indices(styles) == [0, 2, 4]


def test_assign_styles_empty():
    assert assign_styles([]) == []
