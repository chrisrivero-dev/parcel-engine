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
    QGroupBox,
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
from models.schema import CurveCall, LineCall
from transcription.normalize import normalize
from transcription.parser_v2 import parse_legal_description
from transcription.sections import split_legal_text_sections
from transcription.suggestions import explain_unsuggestable, suggest_resolution
from geometry.resolution import suggest_geometry_aware
from ui.audit_trail import RowAudit, RowAuditStore, SOURCE_SUGGESTED
from ui.preview_panel import count_unresolved, format_ignored_title
from ui.section_select import FULL_TEXT_LABEL, resolve_parse_text
from ui.image_viewer import ReferenceImageViewer
from ui.manual_courses import build_manual_line
from ui.table_call_adapter import build_calls_from_table_rows
from ui.manual_courses import build_manual_curve
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
    LINE_WIDTH = 3
    HIGHLIGHT_WIDTH = 6
    LABEL_POINT_SIZE = 12
    PAD = 40.0
    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#f7f9fc"))
        self.setSceneRect(QRectF(0, 0, 1000, 700))

        self._transformed_points: List[QPointF] = []
        self._segments: List[Tuple[Point, Point, str]] = []
        self._segment_items: list = []  # QGraphicsLineItem per drawn segment
        self._highlighted: list = []
        # When the technician manually zooms we stop auto-fitting on
        # resize so their chosen zoom is preserved; Fit/Reset re-enable it.
        self._user_zoomed = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._draw_next_segment)
        self._draw_index = 0

    def clear_canvas(self) -> None:
        self._timer.stop()
        self._scene.clear()
        self._transformed_points = []
        self._segments = []
        self._segment_items = []
        self._highlighted = []
        self._draw_index = 0

    def _transform_points(self, points: List[Point]) -> List[QPointF]:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        width = max(max_x - min_x, 1.0)
        height = max(max_y - min_y, 1.0)

        pad = self.PAD
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

        self._user_zoomed = False  # fresh drawing -> auto-fit until user zooms
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
        line_pen.setWidth(self.LINE_WIDTH)
        line_item = self._scene.addLine(p1.x(), p1.y(), p2.x(), p2.y(), line_pen)
        self._segment_items.append(line_item)

        vertex_pen = QPen(QColor("#2563eb"))
        vertex_pen.setWidth(1)
        self._scene.addEllipse(p1.x() - 3, p1.y() - 3, 6, 6, vertex_pen)
        if i == len(self._segments) - 1:
            self._scene.addEllipse(p2.x() - 3, p2.y() - 3, 6, 6, vertex_pen)

        mid_x = (p1.x() + p2.x()) / 2
        mid_y = (p1.y() + p2.y()) / 2
        if label_text:
            label = self._scene.addSimpleText(label_text)
            label.setBrush(QColor("#b91c1c"))
            font = label.font()
            font.setPointSize(self.LABEL_POINT_SIZE)
            font.setBold(True)
            label.setFont(font)
            label.setPos(mid_x + 6, mid_y + 6)

        self._draw_index += 1

    def highlight_segments(self, indices) -> None:
        """Restore prior highlight, then thicken/recolor the given segments.

        ``indices`` is any iterable of segment positions (0-based) into the
        already-drawn line items.  Out-of-range indices are skipped safely.
        Pass an empty iterable to clear the current highlight.
        """
        default_pen = QPen(QColor("#1f2937"))
        default_pen.setWidth(self.LINE_WIDTH)
        for i in self._highlighted:
            if 0 <= i < len(self._segment_items):
                self._segment_items[i].setPen(default_pen)
        self._highlighted = []

        highlight_pen = QPen(QColor("#dc2626"))
        highlight_pen.setWidth(self.HIGHLIGHT_WIDTH)
        for i in indices:
            if 0 <= i < len(self._segment_items):
                self._segment_items[i].setPen(highlight_pen)
                self._highlighted.append(i)

    def zoom_to_fit(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isValid():
            margin = max(rect.width(), rect.height()) * 0.04 + 10.0
            rect = rect.adjusted(-margin, -margin, margin, margin)
            self.fitInView(rect, Qt.KeepAspectRatio)


    
    # ── Preview controls ──────────────────────────────────────────────────
    def resizeEvent(self, event) -> None:
        # Re-fit on every viewport size change (window show, splitter
        # drag) so the parcel is never left clipped by a stale
        # transform.  Skip when the user has manually zoomed.
        super().resizeEvent(event)
        if not self._user_zoomed and self._scene.items():
            self.zoom_to_fit()
    
    def zoom_in(self) -> None:
        self._user_zoomed = True
        self.scale(1.25, 1.25)
    
    def zoom_out(self) -> None:
        self._user_zoomed = True
        self.scale(0.8, 0.8)
    
    def fit_to_view(self) -> None:
        self._user_zoomed = False
        self.zoom_to_fit()
    
    def reset_view(self) -> None:
        self._user_zoomed = False
        self.resetTransform()
        self.zoom_to_fit()
class ParcelDesktopApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("COGO Validator + DXF Export")
        self.resize(1500, 900)
        self.setMinimumSize(900, 700)

        self.calls = []
        self._parsed_calls: list = []  # original parsed calls; always carry source_span
        self.result = None
        self._last_errors_count = 0
        self._last_ties_count = 0
        self._ignored_chunks: list = []
        self._row_audit = RowAuditStore()
        self._detected_sections: list = []
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
        self.ocr_lines_list.setMinimumHeight(60)
        self.ocr_lines_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.ocr_lines_list.itemSelectionChanged.connect(self._on_ocr_line_selected)
        lines_layout.addWidget(self.ocr_lines_list, stretch=1)
        review_splitter.addWidget(lines_section)

        # Legal tall, OCR Draft readable, OCR Lines enough to inspect
        review_splitter.setSizes([340, 260, 160])
        pane_layout.addWidget(review_splitter, stretch=1)

        # Optional section selector: lets the user parse the full text
        # (default) or one detected section of a multi-parcel deed.
        section_row = QHBoxLayout()
        section_row.addWidget(QLabel("Parse target:"))
        self.section_combo = QComboBox()
        self.section_combo.addItem(FULL_TEXT_LABEL)
        self.section_combo.setToolTip(
            "Choose which text Parse Courses uses. Full text is the default; "
            "click Detect Sections to list parcels / easements / exhibits."
        )
        section_row.addWidget(self.section_combo, stretch=1)

        detect_btn = QPushButton("Detect Sections")
        detect_btn.clicked.connect(self.detect_sections)
        section_row.addWidget(detect_btn)
        pane_layout.addLayout(section_row)

        # Changing the source text invalidates any detected sections so a
        # stale selection can never be applied to different text.
        self.legal_input.textChanged.connect(self._reset_detected_sections)

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

        # Four vertical sections so each gets its own resizable slice:
        #   top      – COGO grid + row/move buttons
        #   summary  – Parse Summary
        #   middle   – Ignored / Unparsed review
        #   bottom   – Parcel Preview + Validation
        output_splitter = QSplitter(Qt.Vertical)

        # ── Section 1: COGO grid ────────────────────────────────────────
        cogo_section = QWidget()
        cogo_layout = QVBoxLayout(cogo_section)
        cogo_layout.setContentsMargins(4, 4, 4, 4)

        table_label = QLabel("Extracted COGO Courses")
        table_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        cogo_layout.addWidget(table_label)

        self.course_table = QTableWidget(0, 7)
        self.course_table.setMinimumHeight(120)
        self.course_table.setHorizontalHeaderLabels(
            ["ID", "Type", "Direction", "Distance", "Radius", "Delta", "Source"]
        )
        self.course_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.course_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.course_table.itemSelectionChanged.connect(self._on_course_row_selected)
        self.course_table.cellDoubleClicked.connect(self._on_course_cell_double_clicked)
        cogo_layout.addWidget(self.course_table, stretch=1)

        row_button_row = QHBoxLayout()
        add_row_btn = QPushButton("Add Row")
        add_row_btn.clicked.connect(self.add_manual_row)
        row_button_row.addWidget(add_row_btn)

        del_row_btn = QPushButton("Delete Selected Row")
        del_row_btn.clicked.connect(self.delete_selected_row)
        row_button_row.addWidget(del_row_btn)
        
        audit_btn = QPushButton("Show Row Audit")
        audit_btn.clicked.connect(self._show_row_audit)
        row_button_row.addWidget(audit_btn)
        cogo_layout.addLayout(row_button_row)

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
        cogo_layout.addLayout(move_row_row)

        output_splitter.addWidget(cogo_section)

        # ── Section 2: Parse Summary ────────────────────────────────────
        self.summary_group = QGroupBox("Parse Summary")
        self.summary_group.setCheckable(True)
        self.summary_group.setChecked(False)

        summary_group_layout = QVBoxLayout(self.summary_group)
        summary_group_layout.setContentsMargins(6, 4, 6, 4)

        self._summary_body = QWidget()
        summary_layout = QFormLayout(self._summary_body)
        self.summary_boundary_count = QLabel("0")
        self.summary_ties_count = QLabel("0")
        self.summary_errors_count = QLabel("0")
        self.summary_closure = QLabel("-")
        summary_layout.addRow("Boundary Calls:", self.summary_boundary_count)
        summary_layout.addRow("Connection / Reference Ties:", self.summary_ties_count)
        summary_layout.addRow("Parse Errors:", self.summary_errors_count)
        summary_layout.addRow("Closure Misclose:", self.summary_closure)

        summary_group_layout.addWidget(self._summary_body)
        self._summary_body.setVisible(False)
        self.summary_group.toggled.connect(self._summary_body.setVisible)

        output_splitter.addWidget(self.summary_group)

        # ── Section 3: Ignored / Unparsed review (collapsible) ─────────
        self.ignored_group = QGroupBox(format_ignored_title(0))
        self.ignored_group.setCheckable(True)
        self.ignored_group.setChecked(False)
        self.ignored_group.setStyleSheet("QGroupBox { font-size: 14px; font-weight: 600; }")

        ignored_outer = QVBoxLayout(self.ignored_group)
        ignored_outer.setContentsMargins(6, 4, 6, 4)

        self._ignored_body = QWidget()
        ignored_layout = QVBoxLayout(self._ignored_body)
        ignored_layout.setContentsMargins(0, 0, 0, 0)

        ignored_note = QLabel(
            "Review skipped text. Correct OCR/source text in the middle pane, "
            "then click Parse Courses again. Double-click a row to see full text."
        )
        ignored_note.setStyleSheet("font-size: 11px; color: #6b7280;")
        ignored_note.setWordWrap(True)
        ignored_layout.addWidget(ignored_note)

        self.ignored_table = QTableWidget(0, 2)
        self.ignored_table.setMinimumHeight(60)
        self.ignored_table.setHorizontalHeaderLabels(["Type", "Text"])
        self.ignored_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ignored_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ignored_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ignored_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ignored_table.setWordWrap(True)
        self.ignored_table.itemSelectionChanged.connect(self._on_ignored_row_selected)
        self.ignored_table.cellDoubleClicked.connect(self._on_ignored_cell_double_clicked)
        ignored_layout.addWidget(self.ignored_table, stretch=1)

        self.suggest_btn = QPushButton("Suggest Resolution")
        self.suggest_btn.clicked.connect(self._suggest_resolution_for_selected)
        ignored_layout.addWidget(self.suggest_btn)

        ignored_outer.addWidget(self._ignored_body)
        self.ignored_group.toggled.connect(self._ignored_body.setVisible)
        self._ignored_body.setVisible(False)

        output_splitter.addWidget(self.ignored_group)
        # ── Section 4: Parcel Preview + Validation ─────────────────────
        preview_section = QWidget()
        preview_layout = QVBoxLayout(preview_section)
        preview_layout.setContentsMargins(4, 4, 4, 4)

        preview_label = QLabel("Parcel Preview")
        preview_label.setStyleSheet("font-size: 18px; font-weight: 700;")
        preview_layout.addWidget(preview_label)

        
        # Preview controls: zoom / fit / reset.
        preview_controls = QHBoxLayout()
        zoom_in_btn = QPushButton("Zoom In")
        zoom_out_btn = QPushButton("Zoom Out")
        fit_btn = QPushButton("Fit to View")
        reset_btn = QPushButton("Reset View")
        large_btn = QPushButton("Open Large Preview")
        for btn in (zoom_in_btn, zoom_out_btn, fit_btn, reset_btn, large_btn):
            preview_controls.addWidget(btn)
        preview_controls.addStretch(1)
        zoom_in_btn.clicked.connect(lambda: self.canvas.zoom_in())
        zoom_out_btn.clicked.connect(lambda: self.canvas.zoom_out())
        fit_btn.clicked.connect(lambda: self.canvas.fit_to_view())
        reset_btn.clicked.connect(lambda: self.canvas.reset_view())
        large_btn.clicked.connect(self.open_large_preview)
        preview_layout.addLayout(preview_controls)
        self.canvas = ParcelCanvas()
        self.canvas.setMinimumHeight(120)
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

        # COGO and Parcel Preview are the primary review areas.
        # Parse Summary starts collapsed; Ignored / Unparsed stays compact.
        output_splitter.setSizes([260, 36, 36, 840])
        output_splitter.setStretchFactor(0, 2)
        output_splitter.setStretchFactor(1, 0)
        output_splitter.setStretchFactor(2, 0)
        output_splitter.setStretchFactor(3, 9)
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


    def _segment_labels_for_points(self, points) -> list[str]:
        """Return one label per drawn segment.

        Line calls get one label on their single segment.
        Curve calls may expand into many chord segments; only the first chord
        receives the curve label and the remaining child chords are unlabeled.
        """
        segment_count = max(0, len(points) - 1)
        labels = [""] * segment_count

        for row, call in enumerate(getattr(self, "calls", [])):
            label = self._call_label_for_row(call)
            seg_range = self._segment_range_for_row(row)

            if seg_range:
                start, _end = seg_range
                if 0 <= start < segment_count:
                    labels[start] = label
                continue

            if row < segment_count:
                labels[row] = label

        return labels

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Build Failed", message)

    def _reset_detected_sections(self) -> None:
        """Drop detected sections and reset the selector to Full text.

        Called whenever the Legal Source Text changes so a previously
        detected section can never be parsed against different text.
        """
        if not self._detected_sections and self.section_combo.count() <= 1:
            return
        self._detected_sections = []
        self.section_combo.blockSignals(True)
        self.section_combo.clear()
        self.section_combo.addItem(FULL_TEXT_LABEL)
        self.section_combo.setCurrentIndex(0)
        self.section_combo.blockSignals(False)

    def detect_sections(self) -> None:
        """Populate the selector with sections found in the source text.

        The original Legal Source Text is never modified; this only fills
        the dropdown. Full text remains index 0 and stays selected.
        """
        full_text = self.legal_input.toPlainText()
        sections = split_legal_text_sections(full_text)
        self._detected_sections = sections

        self.section_combo.blockSignals(True)
        self.section_combo.clear()
        self.section_combo.addItem(FULL_TEXT_LABEL)
        for sec in sections:
            self.section_combo.addItem(f"{sec.label} ({sec.section_type})")
        self.section_combo.setCurrentIndex(0)
        self.section_combo.blockSignals(False)

        if not sections:
            QMessageBox.information(
                self,
                "No Sections Detected",
                "No parcel / easement / exhibit sections were found. "
                "Parse Courses will use the full text.",
            )

    def parse_legal_text(self) -> None:
        full_text = self.legal_input.toPlainText()
        text = resolve_parse_text(
            full_text, self._detected_sections, self.section_combo.currentIndex()
        ).strip()

        if not text:
            QMessageBox.warning(self, "No Text", "Paste a legal description first.")
            return

        calls, reference_ties, errors, ignored_chunks = parse_legal_description(text)
        self.calls = calls
        self._parsed_calls = calls  # preserve source_span for geometry-aware suggestions
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

            
            # Update the collapsible group's title with counts and
            # auto-expand it only when there is something to review.
            _total_ignored = len(ignored_chunks)
            _unresolved = count_unresolved(ignored_chunks)
            self.ignored_group.setTitle(
                format_ignored_title(_total_ignored, _unresolved)
            )
            self.ignored_group.setChecked(_total_ignored > 0)
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

        for _r in range(self.course_table.rowCount()):
            self.course_table.setItem(
                _r, self.course_table.columnCount() - 1,
                QTableWidgetItem("Legal"),
            )
        self._row_audit.replace_all_legal(self.course_table.rowCount())
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
        row = rows[0]
        span = getattr(self.calls[row], "source_span", None)
        self._highlight_source_span(span)

        seg_range = self._segment_range_for_row(row)
        if seg_range is None:
            self.canvas.highlight_segments([])
        else:
            start, end = seg_range
            self.canvas.highlight_segments(range(start, end))

    def _segment_range_for_row(self, row: int) -> Tuple[int, int] | None:
        """Map a COGO row to the (start, end) segment range in the canvas.

        Walks ``self.calls`` in order and accumulates vertex indices: a
        LineCall contributes one segment; a CurveCall contributes one polyline
        whose end vertex is matched against ``self.result['curves'][*]
        ['end_point']``.  Returns ``None`` when no segments exist for the row
        (e.g. a skipped curve) or when there is no built geometry.
        """
        if not self.result or row < 0 or row >= len(self.calls):
            return None
        points = self.result.get("points", [])
        if len(points) < 2:
            return None
        curves_by_id = {
            c.get("call_id"): c for c in self.result.get("curves", []) if c.get("call_id")
        }

        cursor = 0
        for i, call in enumerate(self.calls):
            if isinstance(call, LineCall):
                if cursor + 1 >= len(points):
                    return None
                start, end = cursor, cursor + 1
                cursor = end
            elif isinstance(call, CurveCall):
                meta = curves_by_id.get(call.id)
                if meta is None:
                    if i == row:
                        return None
                    continue
                end_pt = meta.get("end_point")
                end_idx = None
                for j in range(cursor + 1, len(points)):
                    if (
                        abs(points[j][0] - end_pt[0]) < 1e-6
                        and abs(points[j][1] - end_pt[1]) < 1e-6
                    ):
                        end_idx = j
                        break
                if end_idx is None:
                    if i == row:
                        return None
                    continue
                start, end = cursor, end_idx
                cursor = end_idx
            else:
                continue

            if i == row:
                return (start, end)
        return None

    def _on_ignored_row_selected(self) -> None:

        sel = self.ignored_table.selectionModel()
        if sel is None:
            return
        rows = sorted({i.row() for i in sel.selectedIndexes()})
        if not rows or rows[0] >= len(self._ignored_chunks):
            return
        span = self._ignored_chunks[rows[0]].get("source_span")
        self._highlight_source_span(span)

    def _on_ignored_cell_double_clicked(self, row, col):
        if row < 0 or row >= len(self._ignored_chunks):
            return
        chunk = self._ignored_chunks[row]
        kind = chunk.get("type", "Ignored")
        text = chunk.get("text", "") or "(no text)"
        QMessageBox.information(self, f"{kind}", text)

    def _suggest_resolution_for_selected(self) -> None:
        """Suggest a COGO resolution for the selected Ignored row.

        Only direction-only unresolved entries with a recognized direction
        word and a numeric distance produce a suggestion.  The technician
        confirms via dialog before a new row is appended to the COGO
        grid; the preview is not redrawn until they click Build Parcel.
        """
        sel = self.ignored_table.selectionModel()
        if sel is None:
            return
        rows = sorted({i.row() for i in sel.selectedIndexes()})
        if not rows or rows[0] >= len(self._ignored_chunks):
            QMessageBox.information(
                self,
                "Suggest Resolution",
                "Select an Ignored / Unparsed row first.",
            )
            return
        entry = self._ignored_chunks[rows[0]]
        if entry.get("type") != "Unresolved Direction-Only Call":
            QMessageBox.information(
                self,
                "Suggest Resolution",
                "Suggestions are only available for "
                "Unresolved Direction-Only Call entries.",
            )
            return

        # Use the originally-parsed calls (which carry source_span), not
        # self.calls which _build_result replaces with source-span-less
        # table calls after Build Parcel runs.
        sug = suggest_geometry_aware(
            entry,
            calls=self._parsed_calls,
            ignored_chunks=self._ignored_chunks,
        )
        if sug is None:
            QMessageBox.information(
                self,
                "Suggest Resolution",
                explain_unsuggestable(entry),
            )
            return

        bearing_text = sug.bearing_text()
        distance_text = (
            f"{sug.distance:.2f} ft" if sug.distance is not None else "(unknown)"
        )
        method_label = {
            "paired_bracket": "Paired bracket (geometry-aware)",
            "closure_bracket": "Closure bracket (geometry-aware)",
            "direction_distance": "Direction + distance (text)",
        }.get(sug.method, sug.method)
        residual_text = (
            f"\nFit residual: {sug.residual}°" if sug.residual is not None else ""
        )
        body = (
            f"Original: {sug.original_text}\n\n"
            f"Method: {method_label}\n"
            f"Suggested bearing: {bearing_text}\n"
            f"Suggested distance: {distance_text}\n"
            f"Confidence: {sug.confidence}{residual_text}\n\n"
            f"Reason: {sug.reason}\n\n"
            "Apply this suggestion as a new editable COGO row? "
            "The drawing will not update until you click Build Parcel."
        )
        choice = QMessageBox.question(
            self,
            "Suggested Resolution",
            body,
            QMessageBox.Apply | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if choice != QMessageBox.Apply:
            return

        self._append_suggested_row(sug, bearing_text, distance_text)

    def _append_suggested_row(self, sug, bearing_text: str, distance_text: str) -> None:
        """Append a Line row populated from a suggestion to the COGO grid."""
        row = self.course_table.rowCount()
        self.course_table.insertRow(row)
        values = [
            f"L{row + 1}",
            "Line",
            bearing_text,
            f"{sug.distance:.2f}",
            "",
            "",
        ]
        for col, val in enumerate(values):
            self.course_table.setItem(row, col, QTableWidgetItem(val))
        self.course_table.setItem(
            row, self.course_table.columnCount() - 1,
            QTableWidgetItem("Suggested"),
        )
        self._row_audit.append(
            RowAudit.from_suggestion(sug, bearing_text, distance_text)
        )
        self._tint_row(row, "#fef3c7")
        self._renumber_course_ids()
        self._update_summary()
        item = self.course_table.item(row, 2)
        if item is not None:
            self.course_table.scrollToItem(item)
            self.course_table.setCurrentItem(item)

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
        self.course_table.setItem(
            row, self.course_table.columnCount() - 1,
            QTableWidgetItem("Manual"),
        )
        self._row_audit.append(RowAudit.manual())

    def delete_selected_row(self) -> None:
        selection = self.course_table.selectionModel()
        if selection is None:
            return
        rows = sorted({i.row() for i in selection.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            self.course_table.removeRow(row)
            self._row_audit.remove_at(row)
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
        self._row_audit.swap(a, b)
        self._reapply_row_tints()

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
        self._parsed_calls = []
        self.result = None
        self.summary_closure.setText("-")
        self._update_summary()
        self._row_audit.clear()

    def _renumber_course_ids(self) -> None:
        for row in range(self.course_table.rowCount()):
            self.course_table.setItem(row, 0, QTableWidgetItem(f"L{row + 1}"))
        self._reapply_row_tints()

    def _update_summary(self) -> None:
        self.summary_boundary_count.setText(str(self.course_table.rowCount()))
        self.summary_ties_count.setText(str(self._last_ties_count))
        self.summary_errors_count.setText(str(self._last_errors_count))

    def _calls_from_table(self) -> list:
        rows = []

        def cell_text(row: int, col: int) -> str:
            item = self.course_table.item(row, col)
            return item.text().strip() if item else ""

        for row in range(self.course_table.rowCount()):
            rows.append(
                {
                    "id": cell_text(row, 0),
                    "type": cell_text(row, 1),
                    "direction": cell_text(row, 2),
                    "distance": cell_text(row, 3),
                    "radius": cell_text(row, 4),
                    "delta": cell_text(row, 5),
                    "row_number": row + 1,
                }
            )

        calls, errors = build_calls_from_table_rows(rows)

        if errors:
            QMessageBox.warning(self, "Row Errors", "\n".join(errors))

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
        labels = self._segment_labels_for_points(points)
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
        labels = self._segment_labels_for_points(points)
        self.canvas.animate(points, labels)


    def open_large_preview(self) -> None:
            # Build if not built yet so the technician can launch the large
            # preview directly without manually clicking Build first.
            if not self.result or "points" not in self.result:
                try:
                    self._build_result()
                except Exception as exc:
                    QMessageBox.critical(self, "Build Failed", str(exc))
                    return
            if not self.result or "points" not in self.result:
                QMessageBox.information(
                    self,
                    "Large Parcel Preview",
                    "Nothing to preview yet — parse a description and click "
                    "Build Parcel first.",
                )
                return

            # Local import to avoid a top-of-module cycle (ui.large_preview
            # imports ParcelCanvas from this module).
            from ui.large_preview import LargePreviewDialog

            points = self.result["points"]
            labels = self._segment_labels_for_points(points)
            dlg = LargePreviewDialog(self, points, labels)
            dlg.show()
            self._large_preview = dlg
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



# Runtime attachment for audit handlers. This fixes cases where the direct-apply
# script inserted audit helper methods outside the ParcelDesktopApp class.
def _audit_show_row_audit(self):
    row = self.course_table.currentRow()
    if row < 0:
        QMessageBox.information(self, "Row Audit", "Select a COGO row first.")
        return

    source_col = self.course_table.columnCount() - 1
    source_item = self.course_table.item(row, source_col)
    source = source_item.text() if source_item is not None else "Unknown"

    store = getattr(self, "_row_audit_store", None)
    audit = None

    if store is not None:
        for getter_name in ("get", "get_audit", "audit_for_row", "get_row_audit"):
            getter = getattr(store, getter_name, None)
            if getter is None:
                continue

            for row_key in (row, row + 1):
                try:
                    audit = getter(row_key)
                except Exception:
                    audit = None

                if audit is not None:
                    break

            if audit is not None:
                break

    if audit is None:
        QMessageBox.information(
            self,
            "Row Audit",
            f"Row: {row + 1}\nSource: {source}\n\nNo detailed audit metadata found for this row.",
        )
        return

    def field(name, default=""):
        if isinstance(audit, dict):
            return audit.get(name, default)
        return getattr(audit, name, default)

    details = [
        f"Row: {row + 1}",
        f"Source: {source}",
        f"Original unresolved text: {field('original_text', field('unresolved_text', ''))}",
        f"Method: {field('method', '')}",
        f"Confidence: {field('confidence', '')}",
        f"Reason: {field('reason', '')}",
        f"Residual: {field('residual', '')}",
        f"Suggested bearing: {field('bearing', field('suggested_bearing', ''))}",
        f"Suggested distance: {field('distance', field('suggested_distance', ''))}",
    ]

    QMessageBox.information(
        self,
        "Row Audit",
        "\n".join(str(item) for item in details if str(item).strip()),
    )


def _audit_on_course_cell_double_clicked(self, row, col):
    source_col = self.course_table.columnCount() - 1
    if col == source_col:
        self.course_table.selectRow(row)
        self._show_row_audit()


ParcelDesktopApp._show_row_audit = _audit_show_row_audit
ParcelDesktopApp._on_course_cell_double_clicked = _audit_on_course_cell_double_clicked

def main() -> None:
    app = QApplication(sys.argv)
    window = ParcelDesktopApp()
    window.show()
    sys.exit(app.exec())


    # ── Row audit ─────────────────────────────────────────────────────────
    def _tint_row(self, row, hex_color):
        bg = QColor(hex_color)
        for col in range(self.course_table.columnCount()):
            item = self.course_table.item(row, col)
            if item is not None:
                item.setBackground(bg)

    def _reapply_row_tints(self):
        for row in range(self.course_table.rowCount()):
            audit = self._row_audit.get(row)
            if audit.source == SOURCE_SUGGESTED:
                self._tint_row(row, "#fef3c7")
            else:
                for col in range(self.course_table.columnCount()):
                    item = self.course_table.item(row, col)
                    if item is not None:
                        item.setBackground(QColor("white"))

    def _show_row_audit(self):
        row = self._selected_course_row()
        if row < 0:
            QMessageBox.information(
                self,
                "Row Audit",
                "Select a COGO row first to view its audit detail.",
            )
            return
        audit = self._row_audit.get(row)
        QMessageBox.information(self, f"Row Audit — L{row + 1}", audit.detail_text())

    def _on_course_cell_double_clicked(self, row, col):
        if col == self.course_table.columnCount() - 1:
            audit = self._row_audit.get(row)
            QMessageBox.information(self, f"Row Audit — L{row + 1}", audit.detail_text())

if __name__ == "__main__":
    main()


# ===========================================================================
# Synchronized course review
# Appended by apply_course_source_sync_and_playback.py
# Adds per-course colour, row<->source<->plot sync, and Prev/Next/Play.
# Idempotent: presence of __COURSE_SYNC_APPLIED__ blocks re-application.
# ===========================================================================
__COURSE_SYNC_APPLIED__ = True

from PySide6.QtCore import Qt as _CC_Qt, QTimer as _CC_QTimer
from PySide6.QtGui import (
    QAction as _CC_QAction,
    QColor as _CC_QColor,
    QPen as _CC_QPen,
    QTextCharFormat as _CC_TCF,
    QTextCursor as _CC_TC,
)
from PySide6.QtWidgets import (
    QGraphicsLineItem as _CC_QGLI,
    QTableWidgetItem as _CC_QTWI,
    QTextEdit as _CC_QTE,
    QToolBar as _CC_QTB,
)

from ui.course_colors import KIND_LEGAL as _CC_KIND_LEGAL, assign_styles as _cc_assign_styles


# ----- ParcelCanvas augmentation ------------------------------------------

_cc_orig_clear = ParcelCanvas.clear_canvas
_cc_orig_draw_next = ParcelCanvas._draw_next_segment


def _cc_clear_canvas(self):
    _cc_orig_clear(self)
    self._cc_segment_items = []
    self._cc_segment_colors = []
    self._cc_segment_dashed = []
    self._cc_highlight_index = -1


def _cc_draw_next_segment(self):
    i = getattr(self, "_draw_index", 0)
    segs = getattr(self, "_segments", [])
    has_segment_to_draw = i < len(segs)
    before = set(self._scene.items()) if has_segment_to_draw else None
    _cc_orig_draw_next(self)
    if before is None:
        return
    if not hasattr(self, "_cc_segment_items"):
        self._cc_segment_items = []
        self._cc_segment_colors = []
        self._cc_segment_dashed = []
        self._cc_highlight_index = -1
    after = self._scene.items()
    for it in after:
        if it in before:
            continue
        if isinstance(it, _CC_QGLI):
            self._cc_segment_items.append(it)
            break


def _cc_pen(color, width, dashed):
    pen = _CC_QPen(_CC_QColor(color))
    pen.setWidth(width)
    pen.setCosmetic(True)
    if dashed:
        pen.setStyle(_CC_Qt.DashLine)
    return pen


def _cc_apply_pen_at(self, idx, width):
    items = getattr(self, "_cc_segment_items", [])
    if idx < 0 or idx >= len(items):
        return
    color = self._cc_segment_colors[idx] if idx < len(self._cc_segment_colors) else "#1f2937"
    dashed = self._cc_segment_dashed[idx] if idx < len(self._cc_segment_dashed) else False
    items[idx].setPen(_cc_pen(color, width, dashed))


def _cc_set_course_colors(self, colors, dashed=None):
    """Recolour every drawn segment to the per-course palette."""
    items = getattr(self, "_cc_segment_items", [])
    if not items:
        # Geometry not drawn yet; remember colours for the next draw cycle.
        self._cc_segment_colors = list(colors)
        self._cc_segment_dashed = list(dashed) if dashed else [False] * len(colors)
        return
    self._cc_segment_colors = list(colors)
    self._cc_segment_dashed = list(dashed) if dashed else [False] * len(colors)
    for i in range(len(items)):
        _cc_apply_pen_at(self, i, 2)
    hi = getattr(self, "_cc_highlight_index", -1)
    if 0 <= hi < len(items):
        _cc_apply_pen_at(self, hi, 5)


def _cc_highlight_segment(self, index):
    items = getattr(self, "_cc_segment_items", [])
    if not items:
        return
    prev = getattr(self, "_cc_highlight_index", -1)
    if 0 <= prev < len(items) and prev != index:
        _cc_apply_pen_at(self, prev, 2)
        items[prev].setZValue(0)
    self._cc_highlight_index = index
    if 0 <= index < len(items):
        _cc_apply_pen_at(self, index, 5)
        items[index].setZValue(10)


def _cc_clear_highlight(self):
    items = getattr(self, "_cc_segment_items", [])
    if not items:
        return
    self._cc_highlight_index = -1
    for i in range(len(items)):
        _cc_apply_pen_at(self, i, 2)
        items[i].setZValue(0)


ParcelCanvas.clear_canvas = _cc_clear_canvas
ParcelCanvas._draw_next_segment = _cc_draw_next_segment
ParcelCanvas.set_course_colors = _cc_set_course_colors
ParcelCanvas.highlight_segment = _cc_highlight_segment
ParcelCanvas.clear_highlight = _cc_clear_highlight


# ----- ParcelDesktopApp augmentation --------------------------------------

_cc_orig_init = ParcelDesktopApp.__init__
_cc_orig_parse = ParcelDesktopApp.parse_legal_text
_cc_orig_build = ParcelDesktopApp.build_parcel
_cc_orig_animate = getattr(ParcelDesktopApp, "animate_parcel", None)
_cc_orig_clear_rows = ParcelDesktopApp.clear_rows
_cc_orig_row_sel = ParcelDesktopApp._on_course_row_selected
_cc_orig_renumber = getattr(ParcelDesktopApp, "_renumber_course_ids", None)
_cc_orig_add_row = getattr(ParcelDesktopApp, "add_manual_row", None)


def _cc_selected_row(self):
    sel = self.course_table.selectionModel()
    if sel is None:
        return -1
    rows = sorted({i.row() for i in sel.selectedIndexes()})
    return rows[0] if rows else -1


def _cc_select_row(self, row):
    n = self.course_table.rowCount()
    if n == 0:
        return
    row = max(0, min(row, n - 1))
    self.course_table.selectRow(row)
    item = self.course_table.item(row, 0)
    if item is not None:
        self.course_table.scrollToItem(item)


def _cc_prev_course(self):
    n = self.course_table.rowCount()
    if n == 0:
        return
    cur = _cc_selected_row(self)
    self._cc_select_row(n - 1 if cur <= 0 else cur - 1)


def _cc_next_course(self):
    n = self.course_table.rowCount()
    if n == 0:
        return
    cur = _cc_selected_row(self)
    nxt = 0 if (cur < 0 or cur >= n - 1) else cur + 1
    self._cc_select_row(nxt)


def _cc_toggle_play(self):
    if self._cc_play_timer.isActive():
        self._cc_play_timer.stop()
        self._cc_play_action.setText("Play")
        return
    if self.course_table.rowCount() == 0:
        return
    if _cc_selected_row(self) < 0:
        self._cc_select_row(0)
    self._cc_play_timer.start(900)
    self._cc_play_action.setText("Stop")


def _cc_play_step(self):
    n = self.course_table.rowCount()
    if n == 0:
        self._cc_play_timer.stop()
        self._cc_play_action.setText("Play")
        return
    cur = _cc_selected_row(self)
    if cur < 0 or cur >= n - 1:
        self._cc_play_timer.stop()
        self._cc_play_action.setText("Play")
        return
    self._cc_select_row(cur + 1)


def _cc_build_review_toolbar(self):
    tb = _CC_QTB("Course Review")
    tb.setObjectName("CourseReviewToolBar")
    self.addToolBar(tb)
    prev_act = _CC_QAction("◀ Prev Course", self)
    prev_act.triggered.connect(self._cc_prev_course)
    tb.addAction(prev_act)
    next_act = _CC_QAction("Next Course ▶", self)
    next_act.triggered.connect(self._cc_next_course)
    tb.addAction(next_act)
    self._cc_play_action = _CC_QAction("Play", self)
    self._cc_play_action.triggered.connect(self._cc_toggle_play)
    tb.addAction(self._cc_play_action)


def _cc_apply_row_swatches(self):
    for r, style in enumerate(self._cc_course_styles):
        id_item = self.course_table.item(r, 0)
        if id_item is None:
            id_item = _CC_QTWI("")
            self.course_table.setItem(r, 0, id_item)
        id_item.setBackground(_CC_QColor(style.color))
        id_item.setForeground(_CC_QColor("#ffffff"))


def _cc_refresh_styles(self):
    rows = []
    for r in range(self.course_table.rowCount()):
        id_item = self.course_table.item(r, 0)
        course_id = id_item.text() if id_item else f"L{r + 1}"
        rows.append((course_id, _CC_KIND_LEGAL))
    self._cc_course_styles = _cc_assign_styles(rows)
    _cc_apply_row_swatches(self)
    colors = [s.color for s in self._cc_course_styles]
    dashed = [s.dashed for s in self._cc_course_styles]
    try:
        self.canvas.set_course_colors(colors, dashed)
    except Exception:
        pass


def _cc_span_for_row(self, row):
    spans = getattr(self, "_cc_row_spans", [])
    if 0 <= row < len(spans) and spans[row] is not None:
        return spans[row]
    calls = getattr(self, "calls", [])
    if 0 <= row < len(calls):
        return getattr(calls[row], "source_span", None)
    return None


def _cc_color_for_row(self, row):
    styles = getattr(self, "_cc_course_styles", [])
    if 0 <= row < len(styles):
        return styles[row].color
    return None


def _cc_highlight_source(self, span, color_hex=None):
    if span is None:
        try:
            self.legal_input.setExtraSelections([])
        except Exception:
            pass
        return
    sel = _CC_QTE.ExtraSelection()
    cursor = self.legal_input.textCursor()
    cursor.setPosition(span.start)
    cursor.setPosition(span.end, _CC_TC.KeepAnchor)
    sel.cursor = cursor
    fmt = _CC_TCF()
    tint = _CC_QColor(color_hex) if color_hex else _CC_QColor("#fde68a")
    tint.setAlpha(90)
    fmt.setBackground(tint)
    sel.format = fmt
    self.legal_input.setExtraSelections([sel])
    sc = self.legal_input.textCursor()
    sc.setPosition(span.start)
    self.legal_input.setTextCursor(sc)
    self.legal_input.ensureCursorVisible()


# Wrapped methods -----------------------------------------------------------

def _cc_init(self):
    _cc_orig_init(self)
    self._cc_course_styles = []
    self._cc_row_spans = []
    self._cc_play_timer = _CC_QTimer(self)
    self._cc_play_timer.timeout.connect(self._cc_play_step)
    self._cc_build_review_toolbar()


def _cc_parse(self):
    _cc_orig_parse(self)
    calls = getattr(self, "calls", []) or []
    self._cc_row_spans = [getattr(c, "source_span", None) for c in calls]
    self._cc_refresh_styles()


def _cc_build(self):
    _cc_orig_build(self)
    self._cc_refresh_styles()


def _cc_animate(self):
    _cc_orig_animate(self)
    _CC_QTimer.singleShot(50, self._cc_refresh_styles)


def _cc_clear_rows(self):
    if hasattr(self, "_cc_play_timer"):
        self._cc_play_timer.stop()
        try:
            self._cc_play_action.setText("Play")
        except Exception:
            pass
    _cc_orig_clear_rows(self)
    self._cc_course_styles = []
    self._cc_row_spans = []
    try:
        self.canvas.clear_highlight()
    except Exception:
        pass
    try:
        self.legal_input.setExtraSelections([])
    except Exception:
        pass


def _cc_row_selected(self):
    _cc_orig_row_sel(self)
    row = _cc_selected_row(self)
    if row < 0:
        return
    _cc_highlight_source(self, _cc_span_for_row(self, row), _cc_color_for_row(self, row))
    try:
        self.canvas.highlight_segment(row)
    except Exception:
        pass


def _cc_renumber(self):
    _cc_orig_renumber(self)
    self._cc_refresh_styles()


def _cc_add_row(self):
    _cc_orig_add_row(self)
    self._cc_refresh_styles()


ParcelDesktopApp.__init__ = _cc_init
ParcelDesktopApp.parse_legal_text = _cc_parse
ParcelDesktopApp.build_parcel = _cc_build
if _cc_orig_animate is not None:
    ParcelDesktopApp.animate_parcel = _cc_animate
ParcelDesktopApp.clear_rows = _cc_clear_rows
ParcelDesktopApp._on_course_row_selected = _cc_row_selected
if _cc_orig_renumber is not None:
    ParcelDesktopApp._renumber_course_ids = _cc_renumber
if _cc_orig_add_row is not None:
    ParcelDesktopApp.add_manual_row = _cc_add_row

ParcelDesktopApp._cc_build_review_toolbar = _cc_build_review_toolbar
ParcelDesktopApp._cc_select_row = _cc_select_row
ParcelDesktopApp._cc_prev_course = _cc_prev_course
ParcelDesktopApp._cc_next_course = _cc_next_course
ParcelDesktopApp._cc_toggle_play = _cc_toggle_play
ParcelDesktopApp._cc_play_step = _cc_play_step
ParcelDesktopApp._cc_refresh_styles = _cc_refresh_styles


# ===========================================================================
# Curve row support in Build Parcel
# Appended by apply_curve_table_build_support.py.
# Idempotent: presence of __CURVE_TABLE_BUILD_APPLIED__ blocks re-application.
# ===========================================================================
__CURVE_TABLE_BUILD_APPLIED__ = True

from ui.manual_courses import (
    build_manual_curve as _cv_build_curve,
    build_manual_line as _cv_build_line,
)


def _cv_calls_from_table(self):
    """Curve-aware replacement for ParcelDesktopApp._calls_from_table.

    Dispatch on the row Type cell:
      - 'curve'           -> build_manual_curve (handedness/radius/delta/arc)
      - 'line' or blank   -> build_manual_line  (existing behaviour)
      - anything else     -> clear row error, no silent coercion
    """
    calls = []
    errors = []
    for row in range(self.course_table.rowCount()):
        type_item = self.course_table.item(row, 1)
        dir_item = self.course_table.item(row, 2)
        dist_item = self.course_table.item(row, 3)
        radius_item = self.course_table.item(row, 4)
        delta_item = self.course_table.item(row, 5)

        row_type = (type_item.text() if type_item else "").strip().lower()
        direction = dir_item.text() if dir_item else ""
        distance = dist_item.text() if dist_item else ""
        radius = radius_item.text() if radius_item else ""
        delta = delta_item.text() if delta_item else ""

        if not any(s.strip() for s in (direction, distance, radius, delta)):
            continue

        if row_type == "curve":
            try:
                call = _cv_build_curve(
                    direction=direction,
                    radius=radius,
                    delta=delta,
                    arc=distance,
                    idx=len(calls) + 1,
                )
            except ValueError as exc:
                errors.append(f"Row {row + 1}: {exc}")
                continue
            calls.append(call)
            continue

        if row_type and row_type not in ("line", ""):
            errors.append(
                f"Row {row + 1}: type {row_type!r} not supported "
                f"(use 'Line' or 'Curve')"
            )
            continue

        try:
            call = _cv_build_line(direction, distance, len(calls) + 1)
        except ValueError as exc:
            errors.append(f"Row {row + 1}: {exc}")
            continue
        calls.append(call)

    if errors:
        raise ValueError("\n".join(errors))
    return calls


ParcelDesktopApp._calls_from_table = _cv_calls_from_table
