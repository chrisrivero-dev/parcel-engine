"""Pure (non-Qt) helpers for serialising / deserialising a Parcel Engine
project to and from a JSON-compatible dict.

Designed to be imported both from desktop_app.py and from headless tests.
No PySide6 imports — callers extract widget values before calling these.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional

from ui.audit_trail import RowAudit, RowAuditStore, SOURCE_LEGAL, SOURCE_MANUAL, SOURCE_SUGGESTED

_CURRENT_VERSION = 1


# ---------------------------------------------------------------------------
# RowAudit serialisation
# ---------------------------------------------------------------------------

def audit_to_dict(audit: RowAudit) -> Dict[str, Any]:
    d = asdict(audit)
    return d


def audit_from_dict(d: Dict[str, Any]) -> RowAudit:
    known = {
        "source", "original_text", "method", "confidence",
        "reason", "residual", "bearing_text", "distance_text",
        "direction_word", "timestamp",
    }
    filtered = {k: v for k, v in d.items() if k in known}
    source = filtered.get("source", SOURCE_LEGAL)
    if source not in (SOURCE_LEGAL, SOURCE_MANUAL, SOURCE_SUGGESTED):
        source = SOURCE_LEGAL
    filtered["source"] = source
    return RowAudit(**filtered)


def audit_store_to_list(store: RowAuditStore) -> List[Dict[str, Any]]:
    return [audit_to_dict(store.get(i)) for i in range(len(store))]


def audit_store_from_list(store: RowAuditStore, data: List[Dict[str, Any]]) -> None:
    store.clear()
    for i, d in enumerate(data):
        store._records[i] = audit_from_dict(d)


# ---------------------------------------------------------------------------
# OCRLine serialisation
# ---------------------------------------------------------------------------

def ocr_lines_to_list(ocr_lines: list) -> List[Dict[str, Any]]:
    result = []
    for ln in ocr_lines:
        result.append({
            "text": getattr(ln, "text", ""),
            "confidence": getattr(ln, "confidence", None),
            "x": int(getattr(ln, "x", 0)),
            "y": int(getattr(ln, "y", 0)),
            "width": int(getattr(ln, "width", 0)),
            "height": int(getattr(ln, "height", 0)),
        })
    return result


def ocr_lines_from_list(data: List[Dict[str, Any]]) -> list:
    from ui.ocr_runner import OCRLine
    result = []
    for d in data:
        result.append(OCRLine(
            text=d.get("text", ""),
            confidence=d.get("confidence"),
            x=int(d.get("x", 0)),
            y=int(d.get("y", 0)),
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
        ))
    return result


# ---------------------------------------------------------------------------
# Course-table row serialisation
# ---------------------------------------------------------------------------

def table_rows_to_list(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Accept row dicts keyed by column name and return a JSON-safe copy."""
    safe = []
    for row in rows:
        safe.append({
            "id":        str(row.get("id", "")),
            "type":      str(row.get("type", "")),
            "direction": str(row.get("direction", "")),
            "distance":  str(row.get("distance", "")),
            "radius":    str(row.get("radius", "")),
            "delta":     str(row.get("delta", "")),
            "source":    str(row.get("source", "Legal")),
        })
    return safe


# ---------------------------------------------------------------------------
# Full project dict
# ---------------------------------------------------------------------------

def build_project_dict(
    *,
    legal_text: str,
    start_x: str,
    start_y: str,
    ocr_draft: str,
    image_path: Optional[str],
    ocr_lines: list,
    table_rows: List[Dict[str, str]],
    audit_store: RowAuditStore,
    closure_text: str,
) -> Dict[str, Any]:
    return {
        "version": _CURRENT_VERSION,
        "legal_text": legal_text,
        "start_x": start_x,
        "start_y": start_y,
        "ocr_draft": ocr_draft,
        "reference_image_path": image_path or "",
        "ocr_lines": ocr_lines_to_list(ocr_lines),
        "course_rows": table_rows_to_list(table_rows),
        "row_audits": audit_store_to_list(audit_store),
        "closure": closure_text,
    }


def write_project_file(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def read_project_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate_project_dict(data: Dict[str, Any]) -> None:
    """Raise ValueError with a human-readable message if the dict is unusable."""
    if not isinstance(data, dict):
        raise ValueError("Project file is not a JSON object.")
    version = data.get("version")
    if version is None:
        raise ValueError("Project file has no 'version' field.")
    if int(version) > _CURRENT_VERSION:
        raise ValueError(
            f"Project file version {version} is newer than this app supports "
            f"(max {_CURRENT_VERSION}). Please upgrade."
        )
    if "course_rows" not in data:
        raise ValueError("Project file is missing 'course_rows'.")
