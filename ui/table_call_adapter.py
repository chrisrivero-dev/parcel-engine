"""COGO table row to builder-call adapter.

This module intentionally has no Qt imports. The desktop UI should collect plain
row dictionaries from the QTableWidget, then call build_calls_from_table_rows().
"""

from __future__ import annotations

from typing import Any

from ui.manual_courses import build_manual_curve, build_manual_line


def _text(row: dict[str, Any], key: str) -> str:
    value = row.get(key, "")
    return "" if value is None else str(value).strip()


def _row_number(row: dict[str, Any], fallback: int) -> int:
    try:
        return int(row.get("row_number") or fallback)
    except (TypeError, ValueError):
        return fallback


def _normalize_helper_result(result: Any) -> tuple[Any, list[str]]:
    """Accept helper results in either call-only or (call, errors) form."""
    if isinstance(result, tuple):
        call = result[0] if len(result) >= 1 else None
        raw_errors = result[1] if len(result) >= 2 else []
    else:
        call = result
        raw_errors = []

    if raw_errors is None:
        errors: list[str] = []
    elif isinstance(raw_errors, str):
        errors = [raw_errors]
    else:
        errors = [str(err) for err in raw_errors]

    return call, errors


def _with_row_prefix(row_number: int, error: str) -> str:
    error = str(error).strip()
    if not error:
        return f"Row {row_number}: unknown error"
    if error.lower().startswith("row "):
        return error
    return f"Row {row_number}: {error}"


def _is_blank_row(row: dict[str, Any]) -> bool:
    return not any(
        _text(row, key)
        for key in ("id", "type", "direction", "distance", "radius", "delta")
    )


def build_calls_from_table_rows(rows: list[dict[str, Any]]) -> tuple[list[Any], list[str]]:
    """Convert plain COGO table row dictionaries into builder call objects.

    Supported row types:
    - blank / Line
    - Curve

    The adapter owns validation and row-numbered error reporting. It does not
    import Qt and it does not know about QTableWidget.
    """
    calls: list[Any] = []
    errors: list[str] = []

    for index, row in enumerate(rows, start=1):
        row_number = _row_number(row, index)

        if _is_blank_row(row):
            continue

        row_type = _text(row, "type").lower()
        direction = _text(row, "direction")
        distance = _text(row, "distance")
        radius = _text(row, "radius")
        delta = _text(row, "delta")

        try:
            if row_type in ("", "line"):
                result = build_manual_line(direction, distance, row_number)
            elif row_type == "curve":
                result = build_manual_curve(
                    direction=direction,
                    radius=radius,
                    delta=delta,
                    arc=distance,
                    idx=row_number,
                )
            else:
                errors.append(
                    f"Row {row_number}: type {row_type!r} not supported "
                    "(use 'Line' or 'Curve')"
                )
                continue

            call, row_errors = _normalize_helper_result(result)

        except Exception as exc:
            call = None
            row_errors = [str(exc)]

        errors.extend(_with_row_prefix(row_number, err) for err in row_errors)

        if call is not None:
            calls.append(call)

    return calls, errors
