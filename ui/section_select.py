"""UI-state helper for the optional section-selection workflow.

Kept free of any PySide6 import so the selection logic can be unit-tested
without a display server.
"""

from __future__ import annotations

from typing import Sequence

FULL_TEXT_LABEL = "Full text"


def resolve_parse_text(
    full_text: str,
    sections: Sequence,
    selected_index: int,
) -> str:
    """Return the text Parse Courses should consume.

    ``selected_index`` 0 means "Full text"; indices 1..N map to
    ``sections[index - 1]``.  Any out-of-range index (e.g. a stale
    selection after the source changed) falls back to the full text.
    """
    if selected_index <= 0:
        return full_text
    sec_idx = selected_index - 1
    if 0 <= sec_idx < len(sections):
        return sections[sec_idx].text
    return full_text
