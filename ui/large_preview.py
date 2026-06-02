"""Large detached Parcel Preview dialog.

Reuses :class:`ui.desktop_app.ParcelCanvas` by subclassing it.  Adds two
transient interaction modes used only here: rubber-band Box Zoom and
hand-drag Pan.
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsView,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
)

from ui.desktop_app import ParcelCanvas

Point = Tuple[float, float]


class LargeParcelCanvas(ParcelCanvas):
    def __init__(self) -> None:
        super().__init__()
        self._box_zoom_active = False
        self._pan_active = False
        self.setSceneRect(QRectF(0, 0, 1600, 1100))

    def set_box_zoom(self, active: bool) -> None:
        self._box_zoom_active = active
        if active:
            self._pan_active = False
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setCursor(Qt.CrossCursor)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.unsetCursor()

    def set_pan(self, active: bool) -> None:
        self._pan_active = active
        if active:
            self._box_zoom_active = False
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        else:
            self.setDragMode(QGraphicsView.NoDrag)
            self.unsetCursor()

    def mousePressEvent(self, event):
        if self._box_zoom_active and event.button() == Qt.LeftButton:
            self._box_zoom_press = self.mapToScene(event.pos())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if not self._box_zoom_active or event.button() != Qt.LeftButton:
            return
        press = getattr(self, "_box_zoom_press", None)
        if press is None:
            return
        release = self.mapToScene(event.pos())
        rect = QRectF(press, release).normalized()
        if rect.width() < 4 or rect.height() < 4:
            return
        self._user_zoomed = True
        self.fitInView(rect, Qt.KeepAspectRatio)
        self._box_zoom_press = None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape and (self._box_zoom_active or self._pan_active):
            self.set_box_zoom(False)
            self.set_pan(False)
            return
        super().keyPressEvent(event)


class LargePreviewDialog(QDialog):
    def __init__(self, parent, points: List[Point], labels: List[str]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Large Parcel Preview")
        self.resize(1100, 800)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.fit_btn = QPushButton("Fit to View")
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_out_btn = QPushButton("Zoom Out")
        self.reset_btn = QPushButton("Reset View")
        self.box_zoom_btn = QPushButton("Box Zoom")
        self.box_zoom_btn.setCheckable(True)
        self.pan_btn = QPushButton("Pan")
        self.pan_btn.setCheckable(True)
        self.close_btn = QPushButton("Close")
        for btn in (
            self.fit_btn, self.zoom_in_btn, self.zoom_out_btn,
            self.reset_btn, self.box_zoom_btn, self.pan_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch(1)
        toolbar.addWidget(self.close_btn)
        layout.addLayout(toolbar)

        self.canvas = LargeParcelCanvas()
        layout.addWidget(self.canvas, stretch=1)

        self.fit_btn.clicked.connect(self._fit)
        self.zoom_in_btn.clicked.connect(self.canvas.zoom_in)
        self.zoom_out_btn.clicked.connect(self.canvas.zoom_out)
        self.reset_btn.clicked.connect(self.canvas.reset_view)
        self.box_zoom_btn.toggled.connect(self._on_box_zoom_toggled)
        self.pan_btn.toggled.connect(self._on_pan_toggled)
        self.close_btn.clicked.connect(self.close)

        if points and len(points) >= 2:
            self.canvas.draw_static(points, labels)

    def _fit(self) -> None:
        self.box_zoom_btn.setChecked(False)
        self.pan_btn.setChecked(False)
        self.canvas.fit_to_view()

    def _on_box_zoom_toggled(self, active: bool) -> None:
        if active:
            self.pan_btn.setChecked(False)
        self.canvas.set_box_zoom(active)

    def _on_pan_toggled(self, active: bool) -> None:
        if active:
            self.box_zoom_btn.setChecked(False)
        self.canvas.set_pan(active)

    def highlight_segments(self, indices) -> None:
        self.canvas.highlight_segments(indices)
