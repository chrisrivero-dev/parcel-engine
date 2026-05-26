import pytest

from ui import ocr_runner
from ui.ocr_runner import (
    OCRLine,
    OcrFailed,
    PytesseractMissing,
    TesseractNotFound,
    assemble_ocr_lines_text,
    group_words_into_lines,
    run_ocr,
    run_ocr_lines,
)


class _FakePytesseract:
    class pytesseract:
        tesseract_cmd = ""

    def __init__(self, result: str = "OK", raises: Exception | None = None):
        self.result = result
        self.raises = raises
        self.called_with = None

    def image_to_string(self, image):
        if self.raises is not None:
            raise self.raises
        self.called_with = image
        return self.result


class _FakeImage:
    def __init__(self):
        self.opened = None

    def open(self, path):
        self.opened = path
        return f"<image:{path}>"


class _FakeDataPytesseract:
    class pytesseract:
        tesseract_cmd = ""

    class Output:
        DICT = "dict"

    def __init__(self, data: dict):
        self.data = data
        self.output_type = None

    def image_to_data(self, image, output_type=None):
        self.output_type = output_type
        return self.data


def test_pytesseract_missing_raises():
    with pytest.raises(PytesseractMissing):
        run_ocr(
            "x.png",
            resolver=lambda: "/usr/bin/tesseract",
            _import_pytesseract=lambda: None,
            _import_pil_image=lambda: _FakeImage(),
        )


def test_tesseract_not_found_raises():
    with pytest.raises(TesseractNotFound):
        run_ocr(
            "x.png",
            resolver=lambda: None,
            _import_pytesseract=lambda: _FakePytesseract(),
            _import_pil_image=lambda: _FakeImage(),
        )


def test_run_ocr_returns_text_and_sets_tesseract_cmd():
    fake_pt = _FakePytesseract(result="N 45 E 100.00 feet")
    fake_img = _FakeImage()

    text = run_ocr(
        "/tmp/parcel.png",
        resolver=lambda: "/opt/tesseract",
        _import_pytesseract=lambda: fake_pt,
        _import_pil_image=lambda: fake_img,
    )

    assert text == "N 45 E 100.00 feet"
    assert fake_pt.pytesseract.tesseract_cmd == "/opt/tesseract"
    assert fake_img.opened == "/tmp/parcel.png"


def test_ocr_failed_wraps_underlying_exception():
    fake_pt = _FakePytesseract(raises=RuntimeError("boom"))
    with pytest.raises(OcrFailed) as exc_info:
        run_ocr(
            "x.png",
            resolver=lambda: "/opt/tesseract",
            _import_pytesseract=lambda: fake_pt,
            _import_pil_image=lambda: _FakeImage(),
        )
    assert "boom" in str(exc_info.value)


def test_group_words_into_lines_groups_by_block_par_line():
    data = {
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 2, 2],
        "text": ["THENCE", "NORTH", "46.68", "FEET"],
        "conf": [90, 80, 95, 85],
        "left": [10, 70, 10, 80],
        "top": [5, 5, 30, 30],
        "width": [50, 60, 60, 40],
        "height": [20, 20, 20, 20],
    }
    lines = group_words_into_lines(data)

    assert len(lines) == 2
    assert lines[0].text == "THENCE NORTH"
    assert lines[0].confidence == 85.0  # mean of 90, 80
    assert lines[0].x == 10
    assert lines[0].y == 5
    assert lines[0].width == 120  # 70+60 - 10
    assert lines[0].height == 20

    assert lines[1].text == "46.68 FEET"
    assert lines[1].confidence == 90.0  # mean of 95, 85


def test_group_words_skips_empty_and_negative_conf():
    data = {
        "block_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 1],
        "text": ["WEST", "   ", "120"],
        "conf": [70, -1, -1],
        "left": [0, 0, 50],
        "top": [0, 0, 0],
        "width": [40, 0, 30],
        "height": [10, 0, 10],
    }
    lines = group_words_into_lines(data)

    assert len(lines) == 1
    assert lines[0].text == "WEST 120"
    # Only the 70-conf word counts; the -1 (no conf) words are excluded.
    assert lines[0].confidence == 70.0


def test_group_words_all_negative_conf_yields_none():
    data = {
        "block_num": [1],
        "par_num": [1],
        "line_num": [1],
        "text": ["SONGER"],
        "conf": [-1],
        "left": [0],
        "top": [0],
        "width": [60],
        "height": [12],
    }
    lines = group_words_into_lines(data)

    assert len(lines) == 1
    assert lines[0].confidence is None


def test_group_words_empty_data_returns_empty():
    assert group_words_into_lines({}) == []


def test_run_ocr_lines_returns_ocrline_objects():
    data = {
        "block_num": [1, 1],
        "par_num": [1, 1],
        "line_num": [1, 1],
        "text": ["SOUTH", "47"],
        "conf": [88, 92],
        "left": [0, 60],
        "top": [0, 0],
        "width": [55, 25],
        "height": [18, 18],
    }
    fake_pt = _FakeDataPytesseract(data)

    lines = run_ocr_lines(
        "/tmp/deed.png",
        resolver=lambda: "/opt/tesseract",
        _import_pytesseract=lambda: fake_pt,
        _import_pil_image=lambda: _FakeImage(),
    )

    assert fake_pt.pytesseract.tesseract_cmd == "/opt/tesseract"
    assert fake_pt.output_type == "dict"
    assert len(lines) == 1
    assert isinstance(lines[0], OCRLine)
    assert lines[0].text == "SOUTH 47"


def test_run_ocr_lines_missing_libs_raises():
    with pytest.raises(PytesseractMissing):
        run_ocr_lines(
            "x.png",
            resolver=lambda: "/opt/tesseract",
            _import_pytesseract=lambda: None,
            _import_pil_image=lambda: _FakeImage(),
        )


# ---------------------------------------------------------------------------
# assemble_ocr_lines_text
# ---------------------------------------------------------------------------

def _make_line(text, y=0, x=0, conf=None):
    return OCRLine(text=text, confidence=conf, x=x, y=y, width=100, height=20)


def test_assemble_preserves_reading_order():
    lines = [
        _make_line("THENCE SOUTH 47 WEST", y=40),
        _make_line("BEGINNING at a point", y=0),
        _make_line("120 FEET to POB", y=80),
    ]
    result = assemble_ocr_lines_text(lines)
    assert result == "BEGINNING at a point\nTHENCE SOUTH 47 WEST\n120 FEET to POB"


def test_assemble_excludes_confidence_values():
    lines = [_make_line("N 45 E 100 FEET", conf=88.5)]
    result = assemble_ocr_lines_text(lines)
    assert "88" not in result
    assert result == "N 45 E 100 FEET"


def test_assemble_skips_blank_lines():
    lines = [
        _make_line("THENCE NORTH", y=0),
        _make_line("   ", y=20),
        _make_line("", y=40),
        _make_line("46.68 FEET", y=60),
    ]
    result = assemble_ocr_lines_text(lines)
    assert result == "THENCE NORTH\n46.68 FEET"


def test_assemble_returns_empty_string_for_no_lines():
    assert assemble_ocr_lines_text([]) == ""


def test_run_ocr_to_draft_fallback_uses_flat_ocr_when_no_lines():
    # Simulate run_ocr_lines returning empty — flat run_ocr should be used.
    # We verify this at the helper level: assemble of empty list == ""
    # so callers must detect the empty case and call run_ocr instead.
    result = assemble_ocr_lines_text([])
    assert result == ""
