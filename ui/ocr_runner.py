"""Pure (non-Qt) wrapper around Tesseract OCR.

Resolves the Tesseract executable via ``ui.ocr_config`` and runs OCR
through ``pytesseract``. Raises typed errors so callers can decide how
to surface each failure mode (install hint, setup dialog, generic
error). Imports of ``pytesseract`` / ``PIL.Image`` are deferred so the
app starts without those libraries installed.
"""

from __future__ import annotations

from typing import Callable, Optional

from ui.ocr_config import resolve_tesseract_path


class OcrError(Exception):
    """Base class for OCR runner errors."""


class PytesseractMissing(OcrError):
    """pytesseract or Pillow is not importable."""


class TesseractNotFound(OcrError):
    """Tesseract executable could not be located."""


class OcrFailed(OcrError):
    """OCR ran but pytesseract raised."""


def run_ocr(
    image_path: str,
    *,
    resolver: Callable[[], Optional[str]] = resolve_tesseract_path,
    _import_pytesseract: Optional[Callable] = None,
    _import_pil_image: Optional[Callable] = None,
) -> str:
    """Run OCR on ``image_path`` and return the extracted text.

    Dependencies are injected via the underscore-prefixed kwargs so the
    helper is unit-testable without pytesseract / Pillow / Tesseract
    actually being installed.
    """

    pytesseract = _load(_import_pytesseract, "pytesseract")
    pil_image = _load(_import_pil_image, "PIL.Image")
    if pytesseract is None or pil_image is None:
        raise PytesseractMissing(
            "pytesseract and Pillow are required. Install with:\n"
            "    pip install pytesseract Pillow"
        )

    tesseract_path = resolver()
    if tesseract_path is None:
        raise TesseractNotFound("Tesseract executable not found.")

    pytesseract.pytesseract.tesseract_cmd = tesseract_path

    try:
        image = pil_image.open(image_path)
        return pytesseract.image_to_string(image)
    except Exception as exc:
        raise OcrFailed(str(exc)) from exc


def _load(injected: Optional[Callable], module_name: str):
    if injected is not None:
        return injected()
    try:
        if module_name == "pytesseract":
            import pytesseract  # type: ignore

            return pytesseract
        if module_name == "PIL.Image":
            from PIL import Image  # type: ignore

            return Image
    except Exception:
        return None
    return None
