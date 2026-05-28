"""Pure suggestion helper for unresolved direction-only calls.

Given an unresolved direction-only call (an entry in ``ignored_chunks``
with ``type == "Unresolved Direction-Only Call"``), produce a candidate
COGO line resolution that a technician may review and approve.

Hard rules
----------
* This module never mutates state and never produces drawing geometry.
* A suggestion is only emitted when both a direction word *and* a numeric
  distance are present in the unresolved entry.
* Cardinal directions (N, S, E, W and their -ERLY variants) yield a
  ``"medium"`` confidence cardinal-bearing suggestion.
* Intercardinal directions (NE, SE, NW, SW and their -ERLY variants)
  yield a ``"low"`` confidence 45° suggestion.
* All other shapes (no distance, unknown direction word) return ``None``
  with a human-readable reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


# ---------------------------------------------------------------------------
# Direction → cardinal bearing tables.
# ---------------------------------------------------------------------------
#
# Bearing tuples are (ns, ew, deg, minutes, seconds) matching the
# QuadrantBearing convention used elsewhere in the codebase.  Pure
# cardinal directions live on the quadrant boundary; we encode them in
# the canonical form used by the rest of the parser ("N 0°0'0" E" for
# due north, "N 90°0'0" E" for due east, etc.).

_CARDINAL_BEARINGS = {
    "N":          ("N", "E",  0, 0, 0.0),
    "NORTH":      ("N", "E",  0, 0, 0.0),
    "NORTHERLY":  ("N", "E",  0, 0, 0.0),
    "S":          ("S", "W",  0, 0, 0.0),
    "SOUTH":      ("S", "W",  0, 0, 0.0),
    "SOUTHERLY":  ("S", "W",  0, 0, 0.0),
    "E":          ("N", "E", 90, 0, 0.0),
    "EAST":       ("N", "E", 90, 0, 0.0),
    "EASTERLY":   ("N", "E", 90, 0, 0.0),
    "W":          ("N", "W", 90, 0, 0.0),
    "WEST":       ("N", "W", 90, 0, 0.0),
    "WESTERLY":   ("N", "W", 90, 0, 0.0),
}

_INTERCARDINAL_BEARINGS = {
    "NORTHEAST":      ("N", "E", 45, 0, 0.0),
    "NORTHEASTERLY":  ("N", "E", 45, 0, 0.0),
    "NORTHWEST":      ("N", "W", 45, 0, 0.0),
    "NORTHWESTERLY":  ("N", "W", 45, 0, 0.0),
    "SOUTHEAST":      ("S", "E", 45, 0, 0.0),
    "SOUTHEASTERLY":  ("S", "E", 45, 0, 0.0),
    "SOUTHWEST":      ("S", "W", 45, 0, 0.0),
    "SOUTHWESTERLY":  ("S", "W", 45, 0, 0.0),
}


@dataclass(frozen=True)
class ResolutionSuggestion:
    """A reviewable candidate line resolution for an unresolved call.

    Carries enough information for the UI to render a confirmation
    dialog and, on approval, build a normal ``LineCall``-style row.
    """

    quadrant_ns: str
    quadrant_ew: str
    deg: int
    minutes: int
    seconds: float
    distance: float
    confidence: str  # "medium" | "low"
    reason: str
    original_text: str
    direction: str

    def bearing_text(self) -> str:
        """Human-readable bearing string for UI display."""
        return (
            f"{self.quadrant_ns} {self.deg}°"
            f"{self.minutes:02d}'{int(self.seconds):02d}\" "
            f"{self.quadrant_ew}"
        )


def _no_distance(entry: Mapping) -> str:
    return (
        "No safe automatic suggestion. Manual resolution required: "
        "the unresolved call has no numeric distance."
    )


def _unknown_direction(direction: str) -> str:
    return (
        "No safe automatic suggestion. Manual resolution required: "
        f"direction word {direction!r} is not in the cardinal or "
        "intercardinal table."
    )


def suggest_resolution(entry: Mapping) -> Optional[ResolutionSuggestion]:
    """Suggest a COGO line resolution for an unresolved direction-only call.

    Returns ``None`` when no safe suggestion can be made — caller should
    surface a "Manual resolution required" message and let the technician
    type the bearing/distance by hand.
    """
    direction = (entry.get("direction") or "").upper()
    distance = entry.get("distance")
    text = entry.get("text") or ""

    if distance is None:
        return None
    if not direction:
        return None

    if direction in _CARDINAL_BEARINGS:
        ns, ew, deg, minutes, seconds = _CARDINAL_BEARINGS[direction]
        return ResolutionSuggestion(
            quadrant_ns=ns,
            quadrant_ew=ew,
            deg=deg,
            minutes=minutes,
            seconds=seconds,
            distance=float(distance),
            confidence="medium",
            reason=(
                f"Cardinal direction word {direction!r} mapped to "
                "due-cardinal bearing. Distance taken verbatim. "
                "Technician must confirm before drawing."
            ),
            original_text=text,
            direction=direction,
        )

    if direction in _INTERCARDINAL_BEARINGS:
        ns, ew, deg, minutes, seconds = _INTERCARDINAL_BEARINGS[direction]
        return ResolutionSuggestion(
            quadrant_ns=ns,
            quadrant_ew=ew,
            deg=deg,
            minutes=minutes,
            seconds=seconds,
            distance=float(distance),
            confidence="low",
            reason=(
                f"Intercardinal direction word {direction!r} mapped to "
                "a 45° default. Likely needs adjustment based on "
                "adjoining course context. Technician must confirm."
            ),
            original_text=text,
            direction=direction,
        )

    return None


def explain_unsuggestable(entry: Mapping) -> str:
    """Return a UI-ready reason string when ``suggest_resolution`` is None."""
    direction = (entry.get("direction") or "").upper()
    if entry.get("distance") is None:
        return _no_distance(entry)
    if direction and direction not in _CARDINAL_BEARINGS \
            and direction not in _INTERCARDINAL_BEARINGS:
        return _unknown_direction(direction)
    return (
        "No safe automatic suggestion. Manual resolution required."
    )
