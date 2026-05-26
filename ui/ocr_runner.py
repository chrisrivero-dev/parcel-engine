"""Pure (non-Qt) wrapper around Tesseract OCR.

Resolves the Tesseract executable via ``ui.ocr_config`` and runs OCR
through ``pytesseract``. Raises typed errors so callers can decide how
to surface each failure mode (install hint, setup dialog, generic
error). Imports of ``pytesseract`` / ``PIL.Image`` are deferred so the
app starts without those libraries installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from ui.ocr_config import resolve_tesseract_path


@dataclass
class OCRLine:
    """One OCR-detected text line with its bounding box on the image.

    ``confidence`` is the mean word confidence (0-100) when available, or
    None. ``x``/``y``/``width``/``height`` are pixel coordinates in the
    original image's coordinate space.
    """

    text: str
    confidence: Optional[float]
    x: int
    y: int
    width: int
    height: int


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


def group_words_into_lines(data: dict) -> List[OCRLine]:
    """Group pytesseract ``image_to_data`` word rows into text lines.

    ``data`` is the dict produced with ``output_type=Output.DICT``: parallel
    lists keyed by ``text``, ``conf``, ``left``, ``top``, ``width``,
    ``height``, and ``block_num``/``par_num``/``line_num``. Words sharing a
    (block, paragraph, line) key are concatenated in order; the line bbox is
    the union of its word boxes and confidence is the mean of non-negative
    word confidences. Empty/whitespace-only words are skipped, and lines with
    no remaining text are dropped.
    """

    texts = data.get("text", [])
    n = len(texts)

    def col(name: str):
        values = data.get(name, [])
        return values if len(values) == n else [0] * n

    blocks = col("block_num")
    pars = col("par_num")
    lines = col("line_num")
    confs = col("conf")
    lefts = col("left")
    tops = col("top")
    widths = col("width")
    heights = col("height")

    grouped: "dict[tuple, dict]" = {}
    order: List[tuple] = []

    for i in range(n):
        word = (texts[i] or "").strip()
        if not word:
            continue
        key = (blocks[i], pars[i], lines[i])
        if key not in grouped:
            grouped[key] = {
                "words": [],
                "confs": [],
                "x0": lefts[i],
                "y0": tops[i],
                "x1": lefts[i] + widths[i],
                "y1": tops[i] + heights[i],
            }
            order.append(key)
        g = grouped[key]
        g["words"].append(word)
        try:
            c = float(confs[i])
        except (TypeError, ValueError):
            c = -1.0
        if c >= 0:
            g["confs"].append(c)
        g["x0"] = min(g["x0"], lefts[i])
        g["y0"] = min(g["y0"], tops[i])
        g["x1"] = max(g["x1"], lefts[i] + widths[i])
        g["y1"] = max(g["y1"], tops[i] + heights[i])

    result: List[OCRLine] = []
    for key in order:
        g = grouped[key]
        text = " ".join(g["words"])
        if not text:
            continue
        confidence = sum(g["confs"]) / len(g["confs"]) if g["confs"] else None
        result.append(
            OCRLine(
                text=text,
                confidence=confidence,
                x=int(g["x0"]),
                y=int(g["y0"]),
                width=int(g["x1"] - g["x0"]),
                height=int(g["y1"] - g["y0"]),
            )
        )
    return result


def run_ocr_lines(
    image_path: str,
    *,
    resolver: Callable[[], Optional[str]] = resolve_tesseract_path,
    _import_pytesseract: Optional[Callable] = None,
    _import_pil_image: Optional[Callable] = None,
) -> List[OCRLine]:
    """Run OCR and return structured line-level results.

    Backward-compatible companion to ``run_ocr``: same error semantics and
    same injectable dependencies, but returns a list of ``OCRLine`` built
    from ``image_to_data`` rather than the flat text string.
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
        data = pytesseract.image_to_data(
            image, output_type=pytesseract.Output.DICT
        )
    except Exception as exc:
        raise OcrFailed(str(exc)) from exc

    return group_words_into_lines(data)


def assemble_ocr_lines_text(lines: List[OCRLine]) -> str:
    """Assemble OCRLine objects into plain editable text for the OCR Draft box.

    Sorts by reading order (top-to-bottom, then left-to-right), skips
    blank lines, and joins with newlines. Confidence values are excluded
    so the result is clean legal description text ready for editing.
    """
    sorted_lines = sorted(lines, key=lambda ln: (ln.y, ln.x))
    return "\n".join(ln.text for ln in sorted_lines if ln.text.strip())


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
