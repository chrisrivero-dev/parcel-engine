from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpan:
    """Immutable character span into the normalized source text."""

    start: int
    end: int
    text: str
