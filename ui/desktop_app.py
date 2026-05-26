from __future__ import annotations

import os
import sys
from typing import List, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QPainter, QPen, QPolygonF, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

try:
    import pytesseract
    from PIL import Image
except Exception:
    pytesseract = None
    Image = None

from domain.project import ParcelProject
from exporters.dxf import export_dxf
from geometry.builder import build_geometry
from transcription.normalize import normalize
from transcription.parser_v2 import parse_legal_description
from ui.image_viewer import ReferenceImageViewer
from ui.manual_courses import build_manual_line
from ui.ocr_config import OCR_SETUP_MESSAGE, resolve_tesseract_path
from ui.ocr_runner import (
    OcrError,
    OcrFailed,
    PytesseractMissing,
    TesseractNotFound,
    assemble_ocr_lines_text,
    run_ocr,
    run_ocr_lines,
)

Point = Tuple[float, float]


class ParcelCanvas(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#f7f9fc"))
        self.setSceneRect(QRectF(0, 0, 1000, 700))

        self._transformed_points: List[QPointF] = []
        self._segments: List[Tuple[Point, Point, str]] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._draw_next_segment)
        self._draw_index = 0

    def clear_canvas(self) -> None:
        self._timer.stop()
        self._scene.clear()
        self._transformed_points = []
        self._segments = []
        self._draw_index = 0

    def _transform_points(self, points: List[Point]) -> List[QPointF]:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max(max_x - min_x, 1.0)
        height = max(max_y - min_y, 1.0)

        pad = 60.0
        view_w = 1000.0
        view_h = 700.0

        scale_x = (view_w - 2 * pad) / width
        scale_y = (view_h - 2 * pad) / height
        scale = min(scale_x, scale_y)

        transformed: List[QPointF] = []
        for pt in points:
            x = pad + (pt[0] - min_x) * scale
            y = view_h - pad - (pt[1] - min_y) * scale
            transformed.append(QPointF(x, y))

        return transformed

    def _add_north_arrow(self) -> None:
        arrow_pen = QPen(QColor("#0f172a"))
        arrow_pen.setWidth(2)

        base_x = 60
        base_y = 80
        top_y = 30

        self._scene.addLine(base_x, base_y, base_x, top_y, arrow_pen)

        triangle = QPolygonF(
            [
                QPointF(base_x, top_y - 8),
                QPointF(base_x - 8, top_y + 8),
                QPointF(base_x + 8, top_y + 8),
            ]
        )
        arrow_head = QGraphicsPolygonItem(triangle)
        arrow_head.setBrush(QColor("#0f172a"))
        arrow_head.setPen(arrow_pen)
        self._scene.addItem(arrow_head)

        label = self._scene.addSimpleText("N")
        label.setBrush(QColor("#0f172a"))
        label.setPos(base_x - 6, top_y - 28)

    def prepare_drawing(self, points: List[Point], labels: List[str]) -> None:
        self.clear_canvas()

        if len(points) < 2:
            return

        self._transformed_points = self._transform_points(points)
        self._segments = []

        for i in range(len(points) - 1):
            label = labels[i] if i < len(labels) else str(i + 1)
            self._segments.append((points[i], points[i + 1], label))

        self._add_north_arrow()

    def animate(self, points: List[Point], labels: List[str]) -> None:
        self.prepare_drawing(points, labels)
        if not self._segments:
            return
        self._draw_index = 0
        self._timer.start(220)

    def draw_static(self, points: List[Point], labels: List[str]) -> None:
        self.prepare_drawing(points, labels)
        while self._draw_index < len(self._segments):
            self._draw_next_segment()
        self.zoom_to_fit()

    def _draw_next_segment(self) -> None:
        if self._draw_index >= len(self._segments):
            self._timer.stop()
            self.zoom_to_fit()
            return

        i = self._draw_index
        p1 = self._transformed_points[i]
        p2 = self._transformed_points[i + 1]
        _, _, label_text = self._segments[i]

        line_pen = QPen(QColor("#1f2937"))
        line_pen.setWidth(2)
        self._scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), line_pen)

        vertex_pen = QPen(QColor("#2563eb"))
        vertex_pen.setWidth(1)
        self._scene.addEllipse(p1.x() - 3, p1.y() - 3, 6, 6, vertex_pen)
        if i == len(self._segments) - 1:
            self._scene.addEllipse(p2.x() - 3, p2.y() - 3, 6, 6, vertex_pen)

        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2
        label = self._scene.addSimpleText(label_text)
        label.setBrush(QColor("#b91c1c"))
        label.setPos(mid_x + 6, mid_y + 6)

        self._draw_index += 1

    def zoom_to_fit(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isValid():
            rect = rect.adjusted(-30, -30, 30, 30)
            self.fitInView(rect, Qt.KeepAspectRatio)


class ParcelDesktopApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("COGO Validator + DXF Export")
        self.resize(1500, 900)

        self.calls = []
        self.result = None
        self._last_errors_count = 0
        self._last_ties_count = 0
        self._ignored_chunks: list = []
        self._ocr_lines: list = []
        self.project: ParcelProject = ParcelProject()

        self._build_toolbar()
        self._build_ui()

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        parse_action = QAction("Parse", self)
        parse_action.triggered.connect(self.parse_legal_text)
        toolbar.addAction(parse_action)

        build_action = QAction("Build", self)
        build_action.triggered.connect(self.build_parcel)
        toolbar.addAction(build_action)

        animate_action = QAction("Animate", self)
        animate_action.triggered.connect(self.animate_parcel)
        toolbar.addAction(animate_action)

        export_action = QAction("Export DXF", self)
        export_action.triggered.connect(self.export_dxf_file)
        toolbar.addAction(export_action)

        zoom_action = QAction("Zoom To Fit", self)
        zoom_action.triggered.connect(self.zoom_to_fit)
        toolbar.addAction(zoom_action)

        ocr_action = QAction("Load Image OCR", self)
        ocr_action.triggered.connect(self.load_image_ocr)
        toolbar.addAction(ocr_action)

        ref_image_action = QAction("Load Reference Image", self)
        ref_image_action.triggered.connect(self.load_reference_image)
        toolbar.addAction(ref_image_action)

    def _build_ui(self) -> None:
        main = QWidget()
        self.setCentralWidget(main)

        # Three-pane COGO Reader layout, all panes resizable via splitters:
        #   Left   – read-only reference/deed image (with OCR line highlight)
        #   Middle – editable legal source + OCR Draft + OCR Lines review
        #   Right  – COGO grid, summary, ignored review, parcel preview, validation
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_image_pane())
        splitter.addWidget(self._build_review_pane())
        splitter.addWidget(self._build_output_pane())
        # ~40 % image | ~33 % text review | ~27 % COGO output at 1 500 px wide
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 3)
        splitter.setSizes([600, 500, 400])

        layout = QHBoxLayout(main)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

    # ── Left pane: reference image ─────────────────────────────────────
    def _build_image_pane(self) -> QWidget:
        pane = QWidget()
        pane_layout = QVBoxLayout(pane)

        title = QLabel("Reference / Deed Image")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        pane_layout.addWidget(title)

        load_image_btn = QPushButton("Load Reference Image")
        load_image_btn.clicked.connect(self.load_reference_image)
        pane_layout.addWidget(load_image_btn)

        self.reference_image_viewer = ReferenceImageViewer()
        pane_layout.addWidget(self.reference_image_viewer, stretch=1)

        return pane

    # ── Middle pane: OCR / legal source review ─────────────────────────
    def _build_review_pane(self) -> QWidget:
        pane = QWidget()
        pane_layout = QVBoxLayout(pane)

        title = QLabel("Legal Source Text")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        pane_layout.addWidget(title)

        coords_form = QFormLayout()
        self.start_x_input = QLineEdit("0.0")
        self.start_y_input = QLineEdit("0.0")
        self.basis_combo = QComboBox()
        self.basis_combo.addItems(["True North"])

        coords_form.addRow("Start X:", self.start_x_input)
        coords_form.addRow("Start Y:", self.start_y_input)
        coords_form.addRow("Basis:", self.basis_combo)
        pane_layout.addLayout(coords_form)

        # Vertical splitter so the legal text / OCR draft / OCR lines
        # sections can be resized independently.
        review_splitter = QSplitter(Qt.Vertical)

        legal_section = QWidget()
        legal_layout = QVBoxLayout(legal_section)
        legal_layout.setContentsMargins(0, 0, 0, 0)
        legal_label = QLabel("Legal Description (parsed on Parse Courses)")
        legal_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #6b7280;")
        legal_layout.addWidget(legal_label)
        self.legal_input = QPlainTextEdit()
        self.legal_input.setPlaceholderText(
            'Example:\n'
            'N 90°00\'00" E 100\n'
            'N 00°00\'00" E 100\n'
            'N 90°00\'00" W 100\n'
            'S 00°00\'00" W 100'
        )
        legal_layout.addWidget(self.legal_input, stretch=1)
        review_splitter.addWidget(legal_section)

        ocr_section = QWidget()
        ocr_layout = QVBoxLayout(ocr_section)
        ocr_layout.setContentsMargins(0, 0, 0, 0)
        ocr_draft_label = QLabel("OCR Draft (review, delete irrelevant text, then accept)")
        ocr_draft_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #6b7280;")
        ocr_layout.addWidget(ocr_draft_label)

        self.ocr_draft_input = QPlainTextEdit()
        self.ocr_draft_input.setPlaceholderText(
            "Run OCR to Draft after loading a reference image. "
            "Delete headers, exhibit labels, and other irrelevant text here, "
            "then click Accept OCR Text."
        )
        ocr_layout.addWidget(self.ocr_draft_input, stretch=1)

        ocr_draft_buttons = QHBoxLayout()
        run_ocr_draft_btn = QPushButton("Run OCR to Draft")
        run_ocr_draft_btn.clicked.connect(self.run_ocr_to_draft)
        ocr_draft_buttons.addWidget(run_ocr_draft_btn)

        accept_ocr_btn = QPushButton("Accept OCR Text")
        accept_ocr_btn.clicked.connect(self.accept_ocr_draft)
        ocr_draft_buttons.addWidget(accept_ocr_btn)
        ocr_draft_buttons.addStretch(1)
        ocr_layout.addLayout(ocr_draft_buttons)
        review_splitter.addWidget(ocr_section)

        lines_section = QWidget()
        lines_layout = QVBoxLayout(lines_section)
        lines_layout.setContentsMargins(0, 0, 0, 0)
        self.ocr_lines_label = QLabel("OCR Lines (select to locate on image)")
        self.ocr_lines_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #6b7280;"
        )
        self.ocr_lines_label.setVisible(False)
        lines_layout.addWidget(self.ocr_lines_label)

        self.ocr_lines_list = QListWidget()
        self.ocr_lines_list.setVisible(False)
        self.ocr_lines_list.setMinimumHeight(100)
        self.ocr_lines_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ocr_lines_list.itemSelectionChanged.connect(self._on_ocr_line_selected)
        lines_layout.addWidget(self.ocr_lines_list, stretch=1)
        review_splitter.addWidget(lines_section)

        # Legal tall, OCR Draft readable, OCR Lines enough to inspect
        review_splitter.setSizes([340, 260, 160])
        pane_layout.addWidget(review_splitter, stretch=1)

        button_row = QHBoxLayout()

        parse_btn = QPushButton("Parse Courses")
        parse_btn.clicked.connect(self.parse_legal_text)
        button_row.addWidget(parse_btn)

        build_btn = QPushButton("Build Parcel")
        build_btn.clicked.connect(self.build_parcel)
        button_row.addWidget(build_btn)

        animate_btn = QPushButton("Animate")
        animate_btn.clicked.connect(self.animate_parcel)
        button_row.addWidget(animate_btn)

        ocr_btn = QPushButton("Load Image OCR")
        ocr_btn.clicked.connect(self.load_image_ocr)
        button_row.addWidget(ocr_btn)

        export_btn = QPushButton("Export DXF")
        export_btn.clicked.connect(self.export_dxf_file)
        button_row.addWidget(export_btn)

        pane_layout.addLayout(button_row)

        return pane

    # ── Right pane: COGO grid / ignored review / preview+validation ───────────
    def _build_output_pane(self) -> QWidget:
        pane = QWidget()
        pane_layout = QVBoxLayout(pane)
        pane_layout.setContentsMargins(0, 0, 0, 0)

        # Three vertical sections so each gets its own resizable slice:
        #   top    – COGO grid + row/move buttons + summary
        #   middle – Ignored / Unparsed review
        #   bottom – Parcel Preview + Validation
        output_splitter = QSplitter(Qt.Vertical)

        # ── Section 1: COGO grid ────────────────────────────────────────
        grid_section = QWidget()
        grid_layout = QVBoxLayout(grid_section)
        grid_layout.setContentsMargins(4, 4, 4, 4)

        table_label = QLabel("Extracted COGO Courses")
        table_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        grid_layout.addWidget(table_label)

        self.course_table = QTableWidget(0, 6)
        self.course_table.setHorizontalHeaderLabels(
            ["ID", "Type", "Direction", "Distance", "Radius", "Delta"]
        )
        self.course_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.course_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.course_table.itemSelectionChanged.connect(self._on_course_row_selected)
        grid_layout.addWidget(self.course_table, stretch=1)

        row_button_row = QHBoxLayout()
        add_row_btn = QPushButton("Add Row")
        add_row_btn.clicked.connect(self.add_manual_row)
        row_button_row.addWidget(add_row_btn)

        del_row_btn = QPushButton("Delete Selected Row")
        del_row_btn.clicked.connect(self.delete_selected_row)
        row_button_row.addWidget(del_row_btn)
        grid_layout.addLayout(row_button_row)

        move_row_row = QHBoxLayout()
        up_btn = QPushButton("Move Row Up")
        up_btn.clicked.connect(self.move_row_up)
        move_row_row.addWidget(up_btn)

        down_btn = QPushButton("Move Row Down")
        down_btn.clicked.connect(self.move_row_down)
        move_row_row.addWidget(down_btn)

        clear_btn = QPushButton("Clear Rows")
        clear_btn.clicked.connect(self.clear_rows)
        move_row_row.addWidget(clear_btn)
        grid_layout.addLayout(move_row_row)

        summary_label = QLabel("Parse Summary")
        summary_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        grid_layout.addWidget(summary_label)

        summary_panel = QWidget()
        summary_layout = QFormLayout(summary_panel)
        self.summary_boundary_count = QLabel("0")
        self.summary_ties_count = QLabel("0")
        self.summary_errors_count = QLabel("0")
        self.summary_closure = QLabel("-")
        summary_layout.addRow("Boundary Calls:", self.summary_boundary_count)
        summary_layout.addRow("Connection / Reference Ties:", self.summary_ties_count)
        summary_layout.addRow("Parse Errors:", self.summary_errors_count)
        summary_layout.addRow("Closure Misclose:", self.summary_closure)
        grid_layout.addWidget(summary_panel)

        output_splitter.addWidget(grid_section)

        # ── Section 2: Ignored / Unparsed review ───────────────────────
        ignored_section = QWidget()
        ignored_layout = QVBoxLayout(ignored_section)
        ignored_layout.setContentsMargins(4, 4, 4, 4)

        ignored_label = QLabel("Ignored / Unparsed Text")
        ignored_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        ignored_layout.addWidget(ignored_label)

        ignored_note = QLabel(
            "Review skipped text. Correct OCR/source text in the middle pane, "
            "then click Parse Courses again."
        )
        ignored_note.setStyleSheet("font-size: 11px; color: #6b7280;")
        ignored_note.setWordWrap(True)
        ignored_layout.addWidget(ignored_note)

        self.ignored_table = QTableWidget(0, 2)
        self.ignored_table.setMinimumHeight(160)
        self.ignored_table.setHorizontalHeaderLabels(["Type", "Text"])
        self.ignored_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ignored_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ignored_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ignored_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ignored_table.setWordWrap(True)
        self.ignored_table.itemSelectionChanged.connect(self._on_ignored_row_selected)
        ignored_layout.addWidget(self.ignored_table, stretch=1)

        output_splitter.addWidget(ignored_section)

        # ── Section 3: Parcel Preview + Validation ─────────────────────
        preview_section = QWidget()
        preview_layout = QVBoxLayout(preview_section)
        preview_layout.setContentsMargins(4, 4, 4, 4)

        preview_label = QLabel("Parcel Preview")
        preview_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        preview_layout.addWidget(preview_label)

        self.canvas = ParcelCanvas()
        self.canvas.setMinimumHeight(260)
        preview_layout.addWidget(self.canvas, stretch=1)

        validation_label = QLabel("Validation")
        validation_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        preview_layout.addWidget(validation_label)

        self.validation_panel = QWidget()
        validation_layout = QFormLayout(self.validation_panel)

        self.closure_value = QLabel("-")
        self.intersections_value = QLabel("-")
        self.curve_errors_value = QLabel("-")

        validation_layout.addRow("Closure Misclose:", self.closure_value)
        validation_layout.addRow("Intersections:", self.intersections_value)
        validation_layout.addRow("Curve Error Groups:", self.curve_errors_value)

        preview_layout.addWidget(self.validation_panel)

        output_splitter.addWidget(preview_section)

        # grid ~40 % | ignored ~26 % | preview+validation ~34 %
        output_splitter.setSizes([360, 230, 310])

        pane_layout.addWidget(output_splitter)

        return pane

    def _get_start_point(self) -> Point:
        try:
            x = float(self.start_x_input.text().strip())
            y = float(self.start_y_input.text().strip())
        except ValueError as exc:
            raise ValueError("Start X and Start Y must be numeric.") from exc
        return (x, y)

    def _call_label_for_row(self, call) -> str:
        if hasattr(call, "bearing") and call.bearing is not None and hasattr(call, "distance"):
            direction = call.bearing.raw_text
            distance = call.distance.value if call.distance else ""
            return f"{direction} / {distance}"

        if hasattr(call, "params") and call.params is not None:
            radius = call.params.radius if call.params.radius is not None else ""
            delta = ""
            if call.params.delta is not None:
                d = call.params.delta
                delta = f'{d.deg}°{d.minutes:02d}\'{int(d.seconds):02d}"'
            hand = call.params.handedness.value.upper() if call.params.handedness else ""
            return f"{hand} R={radius} Δ={delta}"

        return getattr(call, "id", "?")

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Build Failed", message)

    def parse_legal_text(self) -> None:
        text = self.legal_input.toPlainText().strip()

        if not text:
            QMessageBox.warning(self, "No Text", "Paste a legal description first.")
            return

        calls, reference_ties, errors, ignored_chunks = parse_legal_description(text)
        self.calls = calls
        self._last_errors_count = len(errors)
        self._last_ties_count = len(reference_ties)
        self._ignored_chunks = ignored_chunks
        self.project = ParcelProject.from_parse_result(
            source_text=text,
            calls=calls,
            reference_ties=reference_ties,
            errors=errors,
            ignored_chunks=ignored_chunks,
        )

        self.ignored_table.setRowCount(len(ignored_chunks))
        self.ignored_table.verticalHeader().setDefaultSectionSize(48)
        for row, ic in enumerate(ignored_chunks):
            type_item = QTableWidgetItem(ic.get("type", ""))
            text_item = QTableWidgetItem(ic.get("text", ""))
            text_item.setToolTip(ic.get("text", ""))
            self.ignored_table.setItem(row, 0, type_item)
            self.ignored_table.setItem(row, 1, text_item)

        self.course_table.setRowCount(len(calls))

        for row, call in enumerate(calls):
            call_type = type(call).__name__.replace("Call", "")
            direction = ""
            distance = ""
            radius = ""
            delta = ""

            if hasattr(call, "bearing") and call.bearing is not None:
                direction = call.bearing.raw_text

            if hasattr(call, "distance") and call.distance is not None:
                distance = str(call.distance.value)

            if hasattr(call, "params") and call.params is not None:
                if call.params.radius is not None:
                    radius = str(call.params.radius)
                if call.params.delta is not None:
                    d = call.params.delta
                    delta = f'{d.deg}°{d.minutes:02d}\'{int(d.seconds):02d}"'
                if call.params.handedness is not None:
                    direction = call.params.handedness.value.upper()

            values = [
                getattr(call, "id", ""),
                call_type,
                direction,
                distance,
                radius,
                delta,
            ]

            for col, value in enumerate(values):
                self.course_table.setItem(row, col, QTableWidgetItem(str(value)))

        self._update_summary()

        # Replace displayed text with normalized form so span indices align for highlighting.
        self.legal_input.setPlainText(normalize(text))

        if errors:
            QMessageBox.warning(self, "Parse Issues", "\n".join(errors))

    def _highlight_source_span(self, span) -> None:
        if span is None:
            return
        cursor = self.legal_input.textCursor()
        cursor.setPosition(span.start)
        cursor.setPosition(span.end, QTextCursor.KeepAnchor)
        self.legal_input.setTextCursor(cursor)
        self.legal_input.ensureCursorVisible()

    def _on_course_row_selected(self) -> None:
        sel = self.course_table.selectionModel()
        if sel is None:
            return
        rows = sorted({i.row() for i in sel.selectedIndexes()})
        if not rows or rows[0] >= len(self.calls):
            return
        span = getattr(self.calls[rows[0]], "source_span", None)
        self._highlight_source_span(span)

    def _on_ignored_row_selected(self) -> None:
        sel = self.ignored_table.selectionModel()
        if sel is None:
            return
        rows = sorted({i.row() for i in sel.selectedIndexes()})
        if not rows or rows[0] >= len(self._ignored_chunks):
            return
        span = self._ignored_chunks[rows[0]].get("source_span")
        self._highlight_source_span(span)

    def add_manual_row(self) -> None:
        row = self.course_table.rowCount()
        self.course_table.insertRow(row)
        self.course_table.setItem(row, 0, QTableWidgetItem(f"L{row + 1}"))
        self.course_table.setItem(row, 1, QTableWidgetItem("Line"))
        for col in (2, 3, 4, 5):
            self.course_table.setItem(row, col, QTableWidgetItem(""))
        # Scroll the new row into view before opening the inline editor;
        # editItem silently no-ops when the target cell is outside the viewport.
        item = self.course_table.item(row, 2)
        self.course_table.scrollToItem(item)
        self.course_table.editItem(item)

    def delete_selected_row(self) -> None:
        selection = self.course_table.selectionModel()
        if selection is None:
            return
        rows = sorted({i.row() for i in selection.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.course_table.removeRow(row)
        self._renumber_course_ids()
        self._update_summary()

    def _selected_course_row(self) -> int:
        selection = self.course_table.selectionModel()
        if selection is None:
            return -1
        rows = sorted({i.row() for i in selection.selectedIndexes()})
        return rows[0] if rows else -1

    def _swap_course_rows(self, a: int, b: int) -> None:
        cols = self.course_table.columnCount()
        for col in range(cols):
            ia = self.course_table.takeItem(a, col)
            ib = self.course_table.takeItem(b, col)
            self.course_table.setItem(a, col, ib if ib is not None else QTableWidgetItem(""))
            self.course_table.setItem(b, col, ia if ia is not None else QTableWidgetItem(""))

    def move_row_up(self) -> None:
        row = self._selected_course_row()
        if row <= 0:
            QMessageBox.information(self, "Move Row Up", "Select a row below the first row to move it up.")
            return
        self._swap_course_rows(row, row - 1)
        self.course_table.selectRow(row - 1)
        self._renumber_course_ids()

    def move_row_down(self) -> None:
        row = self._selected_course_row()
        last = self.course_table.rowCount() - 1
        if row < 0 or row >= last:
            QMessageBox.information(self, "Move Row Down", "Select a row above the last row to move it down.")
            return
        self._swap_course_rows(row, row + 1)
        self.course_table.selectRow(row + 1)
        self._renumber_course_ids()

    def clear_rows(self) -> None:
        self.course_table.setRowCount(0)
        self.calls = []
        self.result = None
        self.summary_closure.setText("-")
        self._update_summary()

    def _renumber_course_ids(self) -> None:
        for row in range(self.course_table.rowCount()):
            self.course_table.setItem(row, 0, QTableWidgetItem(f"L{row + 1}"))

    def _update_summary(self) -> None:
        self.summary_boundary_count.setText(str(self.course_table.rowCount()))
        self.summary_ties_count.setText(str(self._last_ties_count))
        self.summary_errors_count.setText(str(self._last_errors_count))

    def _calls_from_table(self) -> list:
        calls = []
        errors = []
        for row in range(self.course_table.rowCount()):
            type_item = self.course_table.item(row, 1)
            dir_item = self.course_table.item(row, 2)
            dist_item = self.course_table.item(row, 3)

            row_type = (type_item.text() if type_item else "").strip().lower()
            direction = dir_item.text() if dir_item else ""
            distance = dist_item.text() if dist_item else ""

            if not direction.strip() and not distance.strip():
                continue

            if row_type and row_type not in ("line", ""):
                errors.append(
                    f"Row {row + 1}: type {row_type!r} not supported (line only)"
                )
                continue

            try:
                call = build_manual_line(direction, distance, len(calls) + 1)
            except ValueError as exc:
                errors.append(f"Row {row + 1}: {exc}")
                continue
            calls.append(call)

        if errors:
            raise ValueError("\n".join(errors))
        return calls

    def _build_result(self) -> None:
        try:
            calls = self._calls_from_table()
        except ValueError as exc:
            QMessageBox.warning(self, "Row Errors", str(exc))
            self.result = None
            return

        if not calls:
            # Table empty — fall back to parsing the text input once.
            self.parse_legal_text()
            try:
                calls = self._calls_from_table()
            except ValueError as exc:
                QMessageBox.warning(self, "Row Errors", str(exc))
                self.result = None
                return
            if not calls:
                self.result = None
                return

        self.calls = calls

        start_point = self._get_start_point()
        result = build_geometry(start_point=start_point, calls=self.calls)

        if not result or "points" not in result or not result["points"]:
            self.result = None
            return

        self.result = result

        validation = self.result.get("validation", {})
        closure = validation.get("closure", {})
        intersections = validation.get("intersections", [])
        curve_errors = validation.get("curve_errors", [])

        self.closure_value.setText(str(closure.get("misclosure", "-")))
        self.intersections_value.setText(str(len(intersections)))
        self.curve_errors_value.setText(str(len(curve_errors)))
        self.summary_closure.setText(str(closure.get("misclosure", "-")))
        self._update_summary()

    def build_parcel(self) -> None:
        try:
            self._build_result()
        except Exception as exc:
            QMessageBox.critical(self, "Build Failed", str(exc))
            return

        if not self.result or "points" not in self.result:
            self.show_error(
                "No valid courses parsed.\n\n"
                "This description may contain narrative text.\n"
                "Try simplifying or check parser support."
            )
            return

        points = self.result["points"]
        labels = [self._call_label_for_row(call) for call in self.calls]
        self.canvas.draw_static(points, labels)

    def animate_parcel(self) -> None:
        try:
            self._build_result()
        except Exception as exc:
            QMessageBox.critical(self, "Build Failed", str(exc))
            return

        if not self.result or "points" not in self.result:
            self.show_error(
                "No valid COGO courses parsed.\n\n"
                "This description may contain narrative text not yet supported."
            )
            return

        points = self.result["points"]
        labels = [self._call_label_for_row(call) for call in self.calls]
        self.canvas.animate(points, labels)

    def export_dxf_file(self) -> None:
        if not self.result:
            try:
                self._build_result()
            except Exception as exc:
                QMessageBox.critical(self, "Build Failed", str(exc))
                return

        if not self.result or "points" not in self.result:
            self.show_error(
                "No valid courses parsed.\n\n"
                "Build a parcel before exporting."
            )
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save DXF",
            os.path.join(os.getcwd(), "parcel.dxf"),
            "DXF Files (*.dxf)",
        )

        if not output_path:
            return

        try:
            export_dxf(self.result["points"], output_path)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc))
            return

        QMessageBox.information(self, "Export Complete", f"DXF written:\n{output_path}")

    def zoom_to_fit(self) -> None:
        self.canvas.zoom_to_fit()

    def load_reference_image(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Reference Image",
            "",
            ReferenceImageViewer.SUPPORTED_FILTER,
        )
        if not file_path:
            return

        if not self.reference_image_viewer.load(file_path):
            QMessageBox.warning(
                self,
                "Image Load Failed",
                f"Could not read image:\n{file_path}",
            )
            return

    def run_ocr_to_draft(self) -> None:
        image_path = self.reference_image_viewer.current_path
        if not image_path:
            QMessageBox.information(
                self,
                "No Reference Image",
                "Load a reference image first via Load Reference Image.",
            )
            return

        try:
            lines = run_ocr_lines(image_path)
        except PytesseractMissing as exc:
            QMessageBox.information(self, "OCR Not Installed", str(exc))
            return
        except TesseractNotFound:
            QMessageBox.information(self, "Tesseract Not Found", OCR_SETUP_MESSAGE)
            return
        except OcrFailed as exc:
            QMessageBox.critical(self, "OCR Failed", str(exc))
            return

        if lines:
            draft_text = assemble_ocr_lines_text(lines)
        else:
            # No structured lines returned — fall back to flat OCR text.
            try:
                draft_text = run_ocr(image_path)
            except OcrFailed as exc:
                QMessageBox.critical(self, "OCR Failed", str(exc))
                return

        self.ocr_draft_input.setPlainText(draft_text)
        self._populate_ocr_lines(lines)

    def _populate_ocr_lines(self, lines: list) -> None:
        self._ocr_lines = lines
        self.ocr_lines_list.clear()
        self.reference_image_viewer.clear_highlight()

        for line in lines:
            if line.confidence is not None:
                label = f"[{line.confidence:.0f}%] {line.text}"
            else:
                label = line.text
            self.ocr_lines_list.addItem(label)

        has_lines = bool(lines)
        self.ocr_lines_label.setVisible(has_lines)
        self.ocr_lines_list.setVisible(has_lines)

    def _on_ocr_line_selected(self) -> None:
        row = self.ocr_lines_list.currentRow()
        if row < 0 or row >= len(self._ocr_lines):
            return
        line = self._ocr_lines[row]
        self.reference_image_viewer.highlight_box(
            line.x, line.y, line.width, line.height
        )

    def accept_ocr_draft(self) -> None:
        draft = self.ocr_draft_input.toPlainText()
        if not draft.strip():
            QMessageBox.information(
                self,
                "Empty OCR Draft",
                "OCR Draft is empty. Run OCR to Draft first, or edit the draft text.",
            )
            return
        self.legal_input.setPlainText(draft)

    def load_image_ocr(self) -> None:
        if pytesseract is None or Image is None:
            QMessageBox.information(
                self,
                "OCR Not Installed",
                "OCR Python libraries are not installed.\n\n"
                "Install them with:\n    pip install pytesseract Pillow\n\n"
                "Manual paste/edit of legal descriptions still works without OCR.",
            )
            return

        tesseract_path = resolve_tesseract_path()
        if tesseract_path is None:
            QMessageBox.information(self, "Tesseract Not Found", OCR_SETUP_MESSAGE)
            return

        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Legal Description Image",
            "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp)",
        )

        if not file_path:
            return

        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
        except Exception as exc:
            QMessageBox.critical(self, "OCR Failed", str(exc))
            return

        self.legal_input.setPlainText(text)

        QMessageBox.information(
            self,
            "OCR Complete",
            "Image text loaded into legal description box.",
        )


def main() -> None:
    app = QApplication(sys.argv)
    window = ParcelDesktopApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()