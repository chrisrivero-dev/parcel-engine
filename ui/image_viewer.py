from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget


class ReferenceImageViewer(QWidget):
    """Read-only viewer for a reference image of a legal description.

    Displays the image scaled to fit the panel while preserving aspect
    ratio. The original pixmap is retained so resize events can rescale
    without quality loss from repeated scaling. Does not perform OCR or
    expose the image to the parser.
    """

    SUPPORTED_FILTER = "Images (*.png *.jpg *.jpeg *.tif *.tiff)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._pixmap: QPixmap | None = None
        self._current_path: str | None = None
        self._highlight: tuple[int, int, int, int] | None = None

        self._label = QLabel("No reference image loaded.")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("color: #6b7280;")
        self._label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self._label.setMinimumSize(1, 1)

        self._scroll = QScrollArea()
        self._scroll.setWidget(self._label)
        self._scroll.setWidgetResizable(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll)

    def load(self, file_path: str) -> bool:
        pixmap = QPixmap(file_path)
        if pixmap.isNull():
            return False
        self._pixmap = pixmap
        self._current_path = file_path
        self._highlight = None
        self._label.setStyleSheet("")
        self._rescale()
        return True

    def clear(self) -> None:
        self._pixmap = None
        self._current_path = None
        self._highlight = None
        self._label.setStyleSheet("color: #6b7280;")
        self._label.setText("No reference image loaded.")

    @property
    def current_path(self) -> str | None:
        return self._current_path

    def highlight_box(self, x: int, y: int, width: int, height: int) -> None:
        """Highlight one rectangle, given in original-image pixel coords."""
        self._highlight = (x, y, width, height)
        self._rescale()

    def clear_highlight(self) -> None:
        self._highlight = None
        self._rescale()

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        target = self._scroll.viewport().size()
        if target.width() <= 0 or target.height() <= 0:
            return
        scaled = self._pixmap.scaled(
            target, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        if self._highlight is not None:
            scaled = self._draw_highlight(scaled)
        self._label.setPixmap(scaled)

    def _draw_highlight(self, scaled: QPixmap) -> QPixmap:
        if self._pixmap is None or self._pixmap.width() == 0:
            return scaled
        sx = scaled.width() / self._pixmap.width()
        sy = scaled.height() / self._pixmap.height()
        x, y, w, h = self._highlight

        canvas = QPixmap(scaled)
        painter = QPainter(canvas)
        pen = QPen(QColor(220, 38, 38))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(int(x * sx), int(y * sy), int(w * sx), int(h * sy))
        painter.end()
        return canvas
