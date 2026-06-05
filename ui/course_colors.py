"""Session-stable course colour + kind classification.

Single source of truth for how a parsed course maps to a colour and a draw
style.  Reused in three views so a technician sees one consistent colour per
course: COGO table row <-> source legal-text span <-> plotted parcel segment.

Deliberately Qt-free (returns hex strings + plain dataclasses) so the
association can be unit-tested without a running QApplication, and so any
view (embedded Parcel Preview or Large Preview dialog) can convert the hex
to its own colour type.
"""

from __future__ import annotations

from dataclasses import dataclass

KIND_LEGAL = "legal"
KIND_SUGGESTED = "suggested"
KIND_REFERENCE_TIE = "reference_tie"
KIND_UNRESOLVED = "unresolved"

_BOUNDARY_KINDS = frozenset({KIND_LEGAL, KIND_SUGGESTED})
_KNOWN_KINDS = frozenset(
    {KIND_LEGAL, KIND_SUGGESTED, KIND_REFERENCE_TIE, KIND_UNRESOLVED}
)

# 12-colour qualitative palette: high contrast on the #f7f9fc canvas,
# reasonable separation for common forms of colour-vision deficiency.
_PALETTE = (
    "#2563eb", "#dc2626", "#059669", "#d97706",
    "#7c3aed", "#0891b2", "#be185d", "#65a30d",
    "#ea580c", "#0d9488", "#4f46e5", "#b91c1c",
)

_REFERENCE_TIE_COLOR = "#94a3b8"
_UNRESOLVED_COLOR = "#f59e0b"

_SUGGESTED_TINT = "#fef9c3"
_REFERENCE_TIE_TINT = "#f1f5f9"
_UNRESOLVED_TINT = "#fffbeb"


@dataclass(frozen=True)
class CourseStyle:
    course_id: str
    kind: str
    color: str
    drawable: bool
    dashed: bool
    row_tint: str | None
    boundary_index: int


def palette_size() -> int:
    return len(_PALETTE)


def normalize_kind(kind):
    if kind is None:
        return KIND_LEGAL
    k = str(kind).strip().lower().replace("-", "_").replace(" ", "_")
    if k in _KNOWN_KINDS:
        return k
    if k in ("tie", "ref_tie", "referencetie", "reference"):
        return KIND_REFERENCE_TIE
    if k in ("unresolved_direction_only_call", "direction_only", "missing"):
        return KIND_UNRESOLVED
    if k in ("suggest", "suggestion", "proposed"):
        return KIND_SUGGESTED
    return KIND_LEGAL


def is_drawable_boundary(kind) -> bool:
    return normalize_kind(kind) in _BOUNDARY_KINDS


def boundary_color(index: int) -> str:
    if index < 0:
        raise ValueError(f"boundary index must be >= 0, got {index}")
    return _PALETTE[index % len(_PALETTE)]


def style_for(course_id, kind, boundary_index) -> CourseStyle:
    kind = normalize_kind(kind)
    if kind == KIND_REFERENCE_TIE:
        return CourseStyle(course_id, kind, _REFERENCE_TIE_COLOR,
                           drawable=False, dashed=False,
                           row_tint=_REFERENCE_TIE_TINT, boundary_index=-1)
    if kind == KIND_UNRESOLVED:
        return CourseStyle(course_id, kind, _UNRESOLVED_COLOR,
                           drawable=False, dashed=True,
                           row_tint=_UNRESOLVED_TINT, boundary_index=-1)
    color = boundary_color(boundary_index)
    if kind == KIND_SUGGESTED:
        return CourseStyle(course_id, kind, color,
                           drawable=True, dashed=True,
                           row_tint=_SUGGESTED_TINT, boundary_index=boundary_index)
    return CourseStyle(course_id, kind, color,
                       drawable=True, dashed=False,
                       row_tint=None, boundary_index=boundary_index)


def assign_styles(rows):
    """Assign a stable style to every row in order.

    The boundary colour index advances ONLY for drawable boundary courses,
    so inserting a reference tie between two boundaries does not shift the
    downstream boundary colours.
    """
    styles = []
    next_boundary = 0
    for course_id, kind in rows:
        kind = normalize_kind(kind)
        if is_drawable_boundary(kind):
            styles.append(style_for(course_id, kind, next_boundary))
            next_boundary += 1
        else:
            styles.append(style_for(course_id, kind, -1))
    return styles


def drawable_indices(styles):
    return [i for i, s in enumerate(styles) if s.drawable]
