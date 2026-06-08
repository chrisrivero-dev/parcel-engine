from ui.table_call_adapter import build_calls_from_table_rows


def test_blank_rows_are_ignored():
    calls, errors = build_calls_from_table_rows(
        [
            {"id": "", "type": "", "direction": "", "distance": "", "radius": "", "delta": ""},
        ]
    )

    assert calls == []
    assert errors == []


def test_line_row_builds_call():
    calls, errors = build_calls_from_table_rows(
        [
            {
                "id": "L1",
                "type": "Line",
                "direction": "N 00°00'00\" E",
                "distance": "100.00",
                "radius": "",
                "delta": "",
            }
        ]
    )

    assert errors == []
    assert len(calls) == 1
    assert calls[0].id == "L1"


def test_curve_row_builds_call():
    calls, errors = build_calls_from_table_rows(
        [
            {
                "id": "C1",
                "type": "Curve",
                "direction": "RIGHT",
                "distance": "78.54",
                "radius": "50.00",
                "delta": "90°00'00\"",
            }
        ]
    )

    assert errors == []
    assert len(calls) == 1
    assert calls[0].id == "C1"


def test_unsupported_row_type_returns_row_error():
    calls, errors = build_calls_from_table_rows(
        [
            {
                "id": "X1",
                "type": "Spiral",
                "direction": "RIGHT",
                "distance": "10",
                "radius": "",
                "delta": "",
            }
        ]
    )

    assert calls == []
    assert errors == ["Row 1: type 'spiral' not supported (use 'Line' or 'Curve')"]


def test_line_validation_error_has_row_number():
    calls, errors = build_calls_from_table_rows(
        [
            {
                "id": "L1",
                "type": "Line",
                "direction": "N 00°00'00\" E",
                "distance": "",
                "radius": "",
                "delta": "",
                "row_number": 7,
            }
        ]
    )

    assert calls == []
    assert errors
    assert errors[0].startswith("Row 7:")


def test_curve_validation_error_has_row_number():
    calls, errors = build_calls_from_table_rows(
        [
            {
                "id": "C1",
                "type": "Curve",
                "direction": "RIGHT",
                "distance": "",
                "radius": "",
                "delta": "90°00'00\"",
                "row_number": 4,
            }
        ]
    )

    assert calls == []
    assert errors
    assert errors[0].startswith("Row 4:")
