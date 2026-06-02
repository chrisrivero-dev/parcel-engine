"""Per-row audit trail for the Extracted COGO Courses table.

Pure helper (no PySide6) so it can be unit-tested headless.  Tracks
per-row metadata (Legal / Manual / Suggested) and exposes mutations
that mirror the QTableWidget operations the COGO grid performs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterator, List, Optional


SOURCE_LEGAL = "Legal"
SOURCE_MANUAL = "Manual"
SOURCE_SUGGESTED = "Suggested"


@dataclass(frozen=True)
class RowAudit:
    source: str
    original_text: str = ""
    method: str = ""
    confidence: str = ""
    reason: str = ""
    residual: Optional[float] = None
    bearing_text: str = ""
    distance_text: str = ""
    direction_word: str = ""
    timestamp: str = ""

    @classmethod
    def legal(cls) -> "RowAudit":
        return cls(source=SOURCE_LEGAL)

    @classmethod
    def manual(cls) -> "RowAudit":
        return cls(source=SOURCE_MANUAL)

    @classmethod
    def from_suggestion(cls, suggestion, bearing_text: str, distance_text: str) -> "RowAudit":
        return cls(
            source=SOURCE_SUGGESTED,
            original_text=getattr(suggestion, "original_text", "") or "",
            method=getattr(suggestion, "method", "") or "",
            confidence=getattr(suggestion, "confidence", "") or "",
            reason=getattr(suggestion, "reason", "") or "",
            residual=getattr(suggestion, "residual", None),
            bearing_text=bearing_text,
            distance_text=distance_text,
            direction_word=getattr(suggestion, "direction", "") or "",
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    def detail_text(self) -> str:
        if self.source == SOURCE_LEGAL:
            return "Source: Legal\nRow was parsed directly from the legal description."
        if self.source == SOURCE_MANUAL:
            return "Source: Manual\nRow was added by the technician via Add Row."
        residual_text = f"Fit residual: {self.residual}\u00b0\n" if self.residual is not None else ""
        ts_text = f"Applied at: {self.timestamp}\n" if self.timestamp else ""
        return (
            "Source: Suggested (technician-approved)\n"
            f"Method: {self.method or '(unknown)'}\n"
            f"Confidence: {self.confidence or '(unknown)'}\n"
            f"Suggested bearing: {self.bearing_text}\n"
            f"Suggested distance: {self.distance_text}\n"
            f"Direction word: {self.direction_word or '-'}\n"
            f"{residual_text}"
            f"{ts_text}"
            f"\nOriginal unresolved text:\n{self.original_text or '(none recorded)'}\n"
            f"\nReason:\n{self.reason or '(none recorded)'}"
        )


@dataclass
class RowAuditStore:
    _records: Dict[int, RowAudit] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[RowAudit]:
        for i in sorted(self._records):
            yield self._records[i]

    def get(self, index: int) -> RowAudit:
        return self._records.get(index, RowAudit.legal())

    def clear(self) -> None:
        self._records.clear()

    def replace_all_legal(self, count: int) -> None:
        self._records = {i: RowAudit.legal() for i in range(count)}

    def append(self, audit: RowAudit) -> int:
        idx = max(self._records.keys(), default=-1) + 1
        self._records[idx] = audit
        return idx

    def insert_at(self, index: int, audit: RowAudit) -> None:
        shifted = {(k + 1 if k >= index else k): v for k, v in self._records.items()}
        shifted[index] = audit
        self._records = shifted

    def remove_at(self, index: int) -> None:
        if index not in self._records:
            return
        del self._records[index]
        self._records = {(k - 1 if k > index else k): v for k, v in self._records.items()}

    def swap(self, a: int, b: int) -> None:
        ra = self._records.get(a, RowAudit.legal())
        rb = self._records.get(b, RowAudit.legal())
        self._records[a] = rb
        self._records[b] = ra

    def to_list(self) -> List[RowAudit]:
        return [self._records[i] for i in sorted(self._records)]
