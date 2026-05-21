from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParcelProject:
    """In-memory project/session state for a parcel under review.

    Foundation for future save/load, audit logging, and export provenance.
    Stores parsed artifacts alongside the source text they came from; does
    not own widgets, geometry results, or persistence concerns yet.
    """

    source_text: str = ""
    calls: list = field(default_factory=list)
    reference_ties: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    ignored_chunks: list = field(default_factory=list)
    closure_misclose: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_parse_result(
        cls,
        source_text: str,
        calls: list,
        reference_ties: list,
        errors: list,
        ignored_chunks: list,
    ) -> "ParcelProject":
        return cls(
            source_text=source_text,
            calls=list(calls),
            reference_ties=list(reference_ties),
            errors=list(errors),
            ignored_chunks=list(ignored_chunks),
        )

    def boundary_count(self) -> int:
        return len(self.calls)

    def reference_tie_count(self) -> int:
        return len(self.reference_ties)

    def error_count(self) -> int:
        return len(self.errors)

    def ignored_count(self) -> int:
        return len(self.ignored_chunks)
