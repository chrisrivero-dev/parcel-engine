"""Tests for ui.project_io — no Qt required."""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from ui.audit_trail import RowAudit, RowAuditStore, SOURCE_LEGAL, SOURCE_MANUAL, SOURCE_SUGGESTED
from ui.project_io import (
    audit_from_dict,
    audit_store_from_list,
    audit_store_to_list,
    audit_to_dict,
    build_project_dict,
    ocr_lines_from_list,
    ocr_lines_to_list,
    read_project_file,
    table_rows_to_list,
    validate_project_dict,
    write_project_file,
)


# ---------------------------------------------------------------------------
# RowAudit round-trip
# ---------------------------------------------------------------------------

class TestAuditRoundTrip:
    def test_legal_audit_round_trips(self):
        a = RowAudit.legal()
        assert audit_from_dict(audit_to_dict(a)) == a

    def test_manual_audit_round_trips(self):
        a = RowAudit.manual()
        assert audit_from_dict(audit_to_dict(a)) == a

    def test_suggested_audit_preserves_fields(self):
        a = RowAudit(
            source=SOURCE_SUGGESTED,
            original_text="N 45 degrees E 100 ft",
            method="geometry_aware",
            confidence="high",
            reason="best fit",
            residual=0.001,
            bearing_text="N 45°00'00\" E",
            distance_text="100.00",
            direction_word="thence",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        assert audit_from_dict(audit_to_dict(a)) == a

    def test_unknown_source_defaults_to_legal(self):
        d = {"source": "Ghost", "original_text": ""}
        a = audit_from_dict(d)
        assert a.source == SOURCE_LEGAL

    def test_extra_keys_ignored(self):
        d = {"source": SOURCE_MANUAL, "extra_unknown_field": "value"}
        a = audit_from_dict(d)
        assert a.source == SOURCE_MANUAL


class TestAuditStoreRoundTrip:
    def _make_store(self):
        store = RowAuditStore()
        store.replace_all_legal(3)
        store._records[1] = RowAudit.manual()
        store._records[2] = RowAudit(
            source=SOURCE_SUGGESTED, original_text="raw", residual=0.5
        )
        return store

    def test_round_trips(self):
        store = self._make_store()
        data = audit_store_to_list(store)
        new_store = RowAuditStore()
        audit_store_from_list(new_store, data)
        assert new_store.to_list() == store.to_list()

    def test_empty_store_round_trips(self):
        store = RowAuditStore()
        data = audit_store_to_list(store)
        new_store = RowAuditStore()
        audit_store_from_list(new_store, data)
        assert len(new_store) == 0


# ---------------------------------------------------------------------------
# OCRLine round-trip
# ---------------------------------------------------------------------------

class TestOcrLinesRoundTrip:
    def _make_ocr_lines(self):
        from ui.ocr_runner import OCRLine
        return [
            OCRLine(text="N 45 degrees E 100 ft", confidence=95.0, x=10, y=20, width=200, height=18),
            OCRLine(text="Thence S 01 degrees W", confidence=None, x=10, y=40, width=180, height=18),
        ]

    def test_round_trips(self):
        lines = self._make_ocr_lines()
        data = ocr_lines_to_list(lines)
        restored = ocr_lines_from_list(data)
        assert len(restored) == 2
        assert restored[0].text == lines[0].text
        assert restored[0].confidence == lines[0].confidence
        assert restored[0].x == lines[0].x
        assert restored[1].confidence is None

    def test_empty_list_round_trips(self):
        assert ocr_lines_from_list([]) == []

    def test_missing_confidence_defaults_none(self):
        restored = ocr_lines_from_list([{"text": "hello", "x": 0, "y": 0, "width": 0, "height": 0}])
        assert restored[0].confidence is None


# ---------------------------------------------------------------------------
# Table rows serialisation
# ---------------------------------------------------------------------------

class TestTableRowsSerialization:
    def test_standard_row_preserved(self):
        rows = [{"id": "L1", "type": "Line", "direction": "N45E", "distance": "100",
                 "radius": "", "delta": "", "source": "Legal"}]
        result = table_rows_to_list(rows)
        assert result[0]["id"] == "L1"
        assert result[0]["source"] == "Legal"

    def test_missing_source_defaults_legal(self):
        rows = [{"id": "C1", "type": "Curve"}]
        result = table_rows_to_list(rows)
        assert result[0]["source"] == "Legal"

    def test_all_values_are_strings(self):
        rows = [{"id": 1, "type": "Line", "distance": 100.5}]
        result = table_rows_to_list(rows)
        assert all(isinstance(v, str) for v in result[0].values())


# ---------------------------------------------------------------------------
# Full project dict build / validate
# ---------------------------------------------------------------------------

class TestBuildProjectDict:
    def _make_store(self, n=2):
        store = RowAuditStore()
        store.replace_all_legal(n)
        return store

    def test_version_is_1(self):
        d = build_project_dict(
            legal_text="N 45 E 100",
            start_x="0.0", start_y="0.0",
            ocr_draft="",
            image_path=None,
            ocr_lines=[],
            table_rows=[],
            audit_store=self._make_store(0),
            closure_text="-",
        )
        assert d["version"] == 1

    def test_all_required_keys_present(self):
        d = build_project_dict(
            legal_text="text", start_x="1.0", start_y="2.0",
            ocr_draft="draft", image_path="/path/to/img.png",
            ocr_lines=[], table_rows=[],
            audit_store=self._make_store(0),
            closure_text="0.002",
        )
        for key in ("version", "legal_text", "start_x", "start_y", "ocr_draft",
                    "reference_image_path", "ocr_lines", "course_rows", "row_audits", "closure"):
            assert key in d, f"missing key: {key}"

    def test_none_image_path_saved_as_empty_string(self):
        d = build_project_dict(
            legal_text="", start_x="0", start_y="0",
            ocr_draft="", image_path=None,
            ocr_lines=[], table_rows=[],
            audit_store=self._make_store(0),
            closure_text="",
        )
        assert d["reference_image_path"] == ""


class TestValidateProjectDict:
    def test_valid_dict_passes(self):
        validate_project_dict({"version": 1, "course_rows": []})

    def test_not_a_dict_raises(self):
        with pytest.raises(ValueError, match="not a JSON object"):
            validate_project_dict([1, 2, 3])

    def test_missing_version_raises(self):
        with pytest.raises(ValueError, match="version"):
            validate_project_dict({"course_rows": []})

    def test_missing_course_rows_raises(self):
        with pytest.raises(ValueError, match="course_rows"):
            validate_project_dict({"version": 1})

    def test_future_version_raises(self):
        with pytest.raises(ValueError, match="newer"):
            validate_project_dict({"version": 99, "course_rows": []})


# ---------------------------------------------------------------------------
# File I/O round-trip
# ---------------------------------------------------------------------------

class TestFileIO:
    def test_write_and_read_round_trip(self):
        store = RowAuditStore()
        store.replace_all_legal(1)
        data = build_project_dict(
            legal_text="test legal text",
            start_x="0.0", start_y="0.0",
            ocr_draft="draft text",
            image_path=None,
            ocr_lines=[],
            table_rows=[{"id": "L1", "type": "Line", "direction": "N45E",
                          "distance": "100", "radius": "", "delta": "", "source": "Legal"}],
            audit_store=store,
            closure_text="0.005",
        )
        with tempfile.NamedTemporaryFile(suffix=".parcel", delete=False) as f:
            path = f.name
        try:
            write_project_file(path, data)
            loaded = read_project_file(path)
            assert loaded["legal_text"] == "test legal text"
            assert loaded["course_rows"][0]["id"] == "L1"
            assert loaded["closure"] == "0.005"
        finally:
            os.unlink(path)

    def test_file_is_valid_json(self):
        store = RowAuditStore()
        data = build_project_dict(
            legal_text="hello", start_x="0", start_y="0",
            ocr_draft="", image_path=None, ocr_lines=[],
            table_rows=[], audit_store=store, closure_text="",
        )
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            write_project_file(path, data)
            with open(path) as fh:
                parsed = json.load(fh)
            assert isinstance(parsed, dict)
        finally:
            os.unlink(path)
