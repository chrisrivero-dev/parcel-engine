"""Pure helpers for the output-pane layout (no PySide6).

Kept import-clean so the title/count logic can be unit-tested headless.
"""

from __future__ import annotations

from typing import Mapping, Sequence


UNRESOLVED_TYPE = "Unresolved Direction-Only Call"


def count_unresolved(chunks: Sequence[Mapping]) -> int:
    """Number of ignored chunks that are unresolved direction-only calls."""
    return sum(1 for c in chunks if c.get("type") == UNRESOLVED_TYPE)


def format_ignored_title(total: int, unresolved: int = 0) -> str:
    """Section title for the collapsible Ignored / Unparsed group."""
    base = "Ignored / Unparsed Text"
    if total <= 0:
        return base
    if unresolved > 0:
        return f"{base} ({total}, {unresolved} unresolved)"
    return f"{base} ({total})"
