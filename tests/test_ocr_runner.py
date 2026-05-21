import pytest

from ui import ocr_runner
from ui.ocr_runner import (
    OcrFailed,
    PytesseractMissing,
    TesseractNotFound,
    run_ocr,
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
