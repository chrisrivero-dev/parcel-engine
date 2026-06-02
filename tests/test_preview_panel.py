"""Tests for the pure preview-panel title/count helpers."""

from ui.preview_panel import count_unresolved, format_ignored_title


def _chunk(t):
    return {"type": t, "text": "x"}


def test_count_unresolved_only_counts_direction_only():
    chunks = [
        _chunk("Boilerplate"),
        _chunk("Unresolved Direction-Only Call"),
        _chunk("Reference / Context"),
        _chunk("Unresolved Direction-Only Call"),
        _chunk("Unknown / Unparsed"),
    ]
    assert count_unresolved(chunks) == 2


def test_count_unresolved_empty():
    assert count_unresolved([]) == 0


def test_title_no_items():
    assert format_ignored_title(0, 0) == "Ignored / Unparsed Text"


def test_title_items_no_unresolved():
    assert format_ignored_title(3, 0) == "Ignored / Unparsed Text (3)"


def test_title_items_with_unresolved():
    assert format_ignored_title(3, 2) == "Ignored / Unparsed Text (3, 2 unresolved)"


def test_title_negative_total_treated_as_empty():
    assert format_ignored_title(-1, 0) == "Ignored / Unparsed Text"
