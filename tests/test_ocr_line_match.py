"""Tests for ui.ocr_line_match — no Qt, no Tesseract required."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from ui.ocr_line_match import (
    _normalise,
    _token_recall,
    _tokenise,
    best_ocr_line_for_text,
)


# ---------------------------------------------------------------------------
# Minimal OCRLine stub
# ---------------------------------------------------------------------------

@dataclass
class _Line:
    text: str
    confidence: Optional[float] = None
    x: int = 0
    y: int = 0
    width: int = 100
    height: int = 20


# ---------------------------------------------------------------------------
# Unit tests: _normalise
# ---------------------------------------------------------------------------

class TestNormalise:
    def test_degree_word_same_as_symbol(self):
        # "DEGREES" → ° → stripped by _NONWORD; same token set as bare 45° 30
        assert _normalise("45 DEGREES 30") == _normalise("45° 30")

    def test_minutes_word_same_as_symbol(self):
        assert _normalise("30 minutes 15") == _normalise("30' 15")

    def test_seconds_word_same_as_symbol(self):
        assert _normalise('15 seconds') == _normalise('15"')

    def test_feet_word_replaced(self):
        assert "ft" in _normalise("125.50 FEET")

    def test_thence_stripped(self):
        result = _normalise("Thence N 45° E 100 ft")
        assert "thence" not in result

    def test_curly_quote_same_as_straight(self):
        # Right single quotation mark (U+2019) should normalise identically to '
        assert _normalise("N 45° 30' E") == _normalise("N 45° 30' E")

    def test_lowercased(self):
        assert _normalise("NORTH") == "north"

    def test_em_dash_same_as_hyphen(self):
        # Both em-dash and hyphen are stripped by _NONWORD — same token set
        assert _normalise("N 45—E") == _normalise("N 45-E")


# ---------------------------------------------------------------------------
# Unit tests: _tokenise
# ---------------------------------------------------------------------------

class TestTokenise:
    def test_basic_split(self):
        assert _tokenise("n 45 e 100") == ["n", "45", "e", "100"]

    def test_empty_string(self):
        assert _tokenise("") == []

    def test_multiple_spaces(self):
        assert _tokenise("a  b   c") == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# Unit tests: _token_recall
# ---------------------------------------------------------------------------

class TestTokenRecall:
    def test_perfect_match(self):
        assert _token_recall(["n", "45", "e"], ["n", "45", "e"]) == pytest.approx(1.0)

    def test_partial_match(self):
        assert _token_recall(["a", "b", "c", "d"], ["a", "b", "x", "y"]) == pytest.approx(0.5)

    def test_empty_span(self):
        assert _token_recall([], ["a", "b"]) == pytest.approx(0.0)

    def test_no_overlap(self):
        assert _token_recall(["x", "y"], ["a", "b"]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Integration tests: best_ocr_line_for_text
# ---------------------------------------------------------------------------

class TestBestOcrLineForText:
    def _lines(self, *texts):
        return [_Line(t) for t in texts]

    def test_exact_match_returned(self):
        lines = self._lines(
            "Begin at the iron pin on the north line",
            "Thence N 45°30' E a distance of 125.50 feet",
        )
        idx = best_ocr_line_for_text(
            "Thence N 45°30' E a distance of 125.50 feet", lines
        )
        assert idx == 1

    def test_degree_word_normalisation(self):
        lines = self._lines(
            "N 45 DEGREES 30 MINUTES E 100 feet",
            "Some unrelated text on this line here",
        )
        idx = best_ocr_line_for_text("N 45° 30' E 100 ft", lines)
        assert idx == 0

    def test_none_on_empty_span(self):
        lines = self._lines("N 45°30' E 100 feet to the point of beginning")
        assert best_ocr_line_for_text("", lines) is None

    def test_none_on_none_span(self):
        lines = self._lines("N 45°30' E 100 feet to the point of beginning")
        assert best_ocr_line_for_text(None, lines) is None

    def test_none_on_empty_ocr_lines(self):
        assert best_ocr_line_for_text("N 45°30' E 100 feet along the road", []) is None

    def test_short_span_below_min_tokens_returns_none(self):
        # Span with < 4 tokens — too short to match reliably.
        lines = self._lines("N 45 E")
        assert best_ocr_line_for_text("N 45", lines) is None

    def test_low_score_below_threshold_returns_none(self):
        lines = self._lines("completely different gibberish xyz abc def ghi")
        assert best_ocr_line_for_text("N 45°30' E 125.50 feet along the road", lines) is None

    def test_best_of_multiple_candidates(self):
        lines = self._lines(
            "S 89°45' W 200.00 feet along the south line of Lot 5",
            "Thence N 01°15' E 150.00 feet to the northwest corner",
            "some noise that does not match anything at all",
        )
        idx = best_ocr_line_for_text(
            "N 01°15' E 150.00 feet to the northwest corner", lines
        )
        assert idx == 1

    def test_thence_prefix_stripped_from_span(self):
        # "Thence" in the span should be stripped and not confuse matching.
        lines = self._lines(
            "N 45°30' E 100.00 feet to the iron pin set",
        )
        idx = best_ocr_line_for_text(
            "Thence N 45°30' E 100.00 feet to the iron pin set", lines
        )
        assert idx == 0

    def test_custom_threshold(self):
        lines = self._lines("N 45 degrees E 100 feet along said road")
        # With a very high threshold the weak match should be rejected.
        result_strict = best_ocr_line_for_text(
            "N 45° E 100 ft along said road edge boundary", lines, threshold=0.90
        )
        # With the default threshold the match should be accepted.
        result_default = best_ocr_line_for_text(
            "N 45° E 100 ft along said road edge boundary", lines
        )
        assert result_strict is None
        assert result_default == 0

    def test_custom_min_tokens(self):
        lines = self._lines("N 45 E")
        # Override min_tokens so a 2-token span can match.
        idx = best_ocr_line_for_text("N 45", lines, min_tokens=1)
        assert idx == 0

    def test_blank_ocr_lines_skipped(self):
        lines = self._lines("", "   ", "N 45°30' E 100.00 feet to the pin here")
        idx = best_ocr_line_for_text(
            "N 45°30' E 100.00 feet to the pin", lines
        )
        assert idx == 2
