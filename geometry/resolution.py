"""Geometry-aware resolution candidates for unresolved direction-only calls.

This is a *pure* helper (no PySide6, no I/O).  Where ``transcription.suggestions``
maps a single direction word to a default cardinal bearing using text alone,
this module uses the surrounding *known* geometry to propose a better
candidate when an unresolved call sits inside a closed traverse.

Phase 1 scope — one method beyond the simple fallback:

    closure_bracket
        When exactly one unresolved direction-only call lacks a distance and
        it is bracketed by known LineCalls (at least one resolved call before
        and after it in source order), and the parcel is assumed to close,
        the call's full vector is *solved* from the closure gap:

            sum(all vectors) = 0   (closed polygon)
            target_vector = -(sum(resolved) + sum(other unresolved defaults))

        The solved bearing/distance are returned together with a residual:
        the angular deviation between the solved bearing and the nominal
        azimuth of the stated direction word ("WESTERLY" → 270°).  A small
        residual corroborates the call; a large one is surfaced as a warning.

Nothing here draws geometry or mutates input.  The caller shows the candidate
and requires technician approval before anything is applied.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from models.schema import CurveCall, LineCall
from geometry.builder import bearing_to_azimuth
from transcription.suggestions import (
    ResolutionSuggestion,
    suggest_resolution,
)


# Legal direction word → survey azimuth (degrees, 0 = North, clockwise).
# Mirrors the concavity table in geometry.builder; owned here because this
# module's responsibility is "legal direction word → azimuth for resolution".
_DIRECTION_AZIMUTH = {
    "NORTH":          0.0,
    "NORTHERLY":      0.0,
    "NORTHEAST":     45.0,
    "NORTHEASTERLY": 45.0,
    "EAST":          90.0,
    "EASTERLY":      90.0,
    "SOUTHEAST":    135.0,
    "SOUTHEASTERLY":135.0,
    "SOUTH":        180.0,
    "SOUTHERLY":    180.0,
    "SOUTHWEST":    225.0,
    "SOUTHWESTERLY":225.0,
    "WEST":         270.0,
    "WESTERLY":     270.0,
    "NORTHWEST":    315.0,
    "NORTHWESTERLY":315.0,
}

_UNRESOLVED_TYPE = "Unresolved Direction-Only Call"

# A distance token: "<num> FEET|FOOT|FT".
_DIST_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:FEET|FOOT|FT)\b")


def _effective_distance(entry: Mapping) -> Optional[float]:
    """Return the call-*length* distance, or None when it is an offset/target.

    The direction-only detector captures any "<n> FEET" in the clause, but
    in a target-defined call the stated distance is often an *offset tie*,
    not the leg length, e.g.:

        "WESTERLY TO A POINT … DISTANT SOUTHERLY 52 FEET FROM THE NW CORNER"

    Here 52 ft is the offset of the target point, not the WESTERLY leg.  We
    treat the captured distance as the call length only when nothing between
    the direction word and the distance token marks it as a target/offset
    ("TO A", "TO THE", "DISTANT").  "DIR ALONG <line> <n> FEET" stays a
    length-stated call.
    """
    dist = entry.get("distance")
    if dist is None:
        return None
    text = (entry.get("text") or "").upper()
    direction = (entry.get("direction") or "").upper()
    di = text.find(direction)
    m = _DIST_TOKEN_RE.search(text)
    if di == -1 or m is None:
        return float(dist)  # cannot analyze → trust the captured value
    between = text[di + len(direction): m.start()]
    if "DISTANT" in between or "TO A " in between or "TO THE " in between:
        return None
    return float(dist)


@dataclass(frozen=True)
class ResolutionCandidate:
    """A reviewable candidate carrying its resolution method and fit info.

    Mirrors the display surface of ``ResolutionSuggestion`` (bearing parts,
    distance, confidence, reason, original_text, direction) and adds
    ``method`` and ``residual`` so the UI can explain *how* it was derived.
    """

    quadrant_ns: str
    quadrant_ew: str
    deg: int
    minutes: int
    seconds: float
    distance: Optional[float]
    confidence: str          # "medium" | "low"
    reason: str
    method: str              # "closure_bracket" | "direction_distance"
    residual: Optional[float]  # angular deviation in degrees, when available
    original_text: str
    direction: str

    def bearing_text(self) -> str:
        return (
            f"{self.quadrant_ns} {self.deg}°"
            f"{self.minutes:02d}'{int(self.seconds):02d}\" "
            f"{self.quadrant_ew}"
        )


def _from_simple(sug: ResolutionSuggestion) -> ResolutionCandidate:
    """Wrap a text-only :class:`ResolutionSuggestion` as a candidate."""
    return ResolutionCandidate(
        quadrant_ns=sug.quadrant_ns,
        quadrant_ew=sug.quadrant_ew,
        deg=sug.deg,
        minutes=sug.minutes,
        seconds=sug.seconds,
        distance=sug.distance,
        confidence=sug.confidence,
        reason=sug.reason,
        method="direction_distance",
        residual=None,
        original_text=sug.original_text,
        direction=sug.direction,
    )


def _az_to_dxdy(az_deg: float, dist: float) -> tuple[float, float]:
    """Survey convention: dx (East) = d·sin(az), dy (North) = d·cos(az)."""
    az = math.radians(az_deg)
    return dist * math.sin(az), dist * math.cos(az)


def _dxdy_to_quadrant(dx: float, dy: float) -> tuple[str, str, int, int, float, float]:
    """Return (ns, ew, deg, minutes, seconds, azimuth) for a vector."""
    az = math.degrees(math.atan2(dx, dy)) % 360.0
    if dy >= 0 and dx >= 0:
        ns, ew, theta = "N", "E", az
    elif dy < 0 and dx >= 0:
        ns, ew, theta = "S", "E", 180.0 - az
    elif dy < 0 and dx < 0:
        ns, ew, theta = "S", "W", az - 180.0
    else:  # dy >= 0, dx < 0
        ns, ew, theta = "N", "W", 360.0 - az
    theta = abs(theta)
    deg = int(theta)
    rem = (theta - deg) * 60.0
    minutes = int(rem)
    seconds = (rem - minutes) * 60.0
    return ns, ew, deg, minutes, seconds, az


def _angular_diff(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return 360.0 - d if d > 180.0 else d


def _span_start(obj) -> Optional[int]:
    span = obj.get("source_span") if isinstance(obj, Mapping) else getattr(obj, "source_span", None)
    return getattr(span, "start", None)


def _try_closure_bracket(
    entry: Mapping,
    calls: Sequence,
    ignored_chunks: Sequence[Mapping],
) -> Optional[ResolutionCandidate]:
    """Solve ``entry``'s vector from the closure gap, or return None.

    Only fires when *entry* is the single distance-less unresolved
    direction-only call, it is bracketed by known LineCalls, and no curve
    appears in the boundary (curves would leave the closure sum incomplete).
    """
    direction = (entry.get("direction") or "").upper()
    if _effective_distance(entry) is not None:
        return None  # has a call-length distance → not the closure target
    if direction not in _DIRECTION_AZIMUTH:
        return None

    target_start = _span_start(entry)
    if target_start is None:
        return None

    # No curve solving in Phase 1: a curve leaves the closure sum incomplete.
    if any(isinstance(c, CurveCall) for c in calls):
        return None

    resolved = [
        c for c in calls
        if isinstance(c, LineCall) and _span_start(c) is not None
    ]
    if len(resolved) < 2:
        return None

    before = [c for c in resolved if _span_start(c) < target_start]
    after = [c for c in resolved if _span_start(c) > target_start]
    if not before or not after:
        return None  # not bracketed

    unresolved = [
        ic for ic in ignored_chunks
        if ic.get("type") == _UNRESOLVED_TYPE and _span_start(ic) is not None
    ]
    no_distance = [ic for ic in unresolved if _effective_distance(ic) is None]
    if len(no_distance) != 1 or _span_start(no_distance[0]) != target_start:
        return None  # not the single unknown

    # Sum the known boundary vectors.
    sum_dx = sum_dy = 0.0
    for c in resolved:
        az = bearing_to_azimuth(c.bearing)
        ddx, ddy = _az_to_dxdy(az, c.distance.value)
        sum_dx += ddx
        sum_dy += ddy

    # Sum the *other* unresolved calls using their direction-default vectors.
    for ic in unresolved:
        if _span_start(ic) == target_start:
            continue
        other_dir = (ic.get("direction") or "").upper()
        other_az = _DIRECTION_AZIMUTH.get(other_dir)
        other_dist = _effective_distance(ic)
        if other_az is None or other_dist is None:
            return None  # can't form a vector for a sibling → bail safely
        ddx, ddy = _az_to_dxdy(other_az, other_dist)
        sum_dx += ddx
        sum_dy += ddy

    # Closure: all vectors sum to zero.  The target fills the remaining gap.
    tx, ty = -sum_dx, -sum_dy
    dist = math.hypot(tx, ty)
    if dist < 1e-6:
        return None  # degenerate

    ns, ew, deg, minutes, seconds, az_t = _dxdy_to_quadrant(tx, ty)
    nominal = _DIRECTION_AZIMUTH[direction]
    residual = round(_angular_diff(az_t, nominal), 2)

    if residual <= 10.0:
        confidence = "medium"
        fit = "consistent with"
    elif residual <= 30.0:
        confidence = "low"
        fit = "roughly consistent with"
    else:
        confidence = "low"
        fit = "DEVIATES SUBSTANTIALLY from"

    bearing_disp = (
        f"{ns} {deg}°{minutes:02d}'{int(seconds):02d}\" {ew}"
    )

    # Identify the canonical "paired bracket" shape explicitly so the
    # technician sees *which* sibling and closing call were used to solve
    # this leg.  The shape: one resolved before, one distance-bearing
    # sibling unresolved (e.g. NORTHERLY 52 FEET), and at least one
    # resolved after (typically the back-to-POB call).
    sibling_unresolved = [
        ic for ic in unresolved if _span_start(ic) != target_start
    ]
    closing_call = after[-1]
    is_back_to_pob = "POINT OF BEGINNING" in (
        getattr(closing_call.source_span, "text", "") or ""
    ).upper()
    if (
        len(before) >= 1
        and len(after) >= 1
        and len(sibling_unresolved) == 1
        and _effective_distance(sibling_unresolved[0]) is not None
    ):
        method = "paired_bracket"
        sib = sibling_unresolved[0]
        sib_dir = (sib.get("direction") or "").upper()
        sib_dist = _effective_distance(sib)
        closing_desc = (
            "the closing call back to the point of beginning"
            if is_back_to_pob else "the closing known call"
        )
        reason = (
            f"Paired-bracket solve. The unresolved call sits between known "
            f"{before[-1].id} (bearing {before[-1].bearing.raw_text}, "
            f"{before[-1].distance.value:g} ft) and {closing_desc} "
            f"{closing_call.id} (bearing {closing_call.bearing.raw_text}, "
            f"{closing_call.distance.value:g} ft). Sibling unresolved call "
            f"{sib_dir} {sib_dist:g} ft was taken at its stated cardinal "
            f"direction. Assuming the parcel closes, the remaining gap solves "
            f"to bearing {bearing_disp}, distance {dist:.2f} ft, "
            f"{fit} the stated direction {direction!r} "
            f"(residual {residual}° from due "
            f"{direction.rstrip('LY').rstrip('ER') or direction}). "
            f"Technician must confirm before drawing."
        )
    else:
        method = "closure_bracket"
        reason = (
            f"Solved from closure bracket: {len(before)} known call(s) before "
            f"and {len(after)} after, assuming the parcel closes and any sibling "
            f"direction-only calls follow their stated cardinal directions. "
            f"Solved bearing {bearing_disp}, distance {dist:.2f} ft "
            f"{fit} the stated direction {direction!r} "
            f"(residual {residual}° from due "
            f"{direction.rstrip('LY').rstrip('ER') or direction}). "
            f"Technician must confirm before drawing."
        )

    return ResolutionCandidate(
        quadrant_ns=ns,
        quadrant_ew=ew,
        deg=deg,
        minutes=minutes,
        seconds=seconds,
        distance=round(dist, 2),
        confidence=confidence,
        reason=reason,
        method=method,
        residual=residual,
        original_text=entry.get("text") or "",
        direction=direction,
    )


def suggest_geometry_aware(
    entry: Mapping,
    *,
    calls: Sequence = (),
    ignored_chunks: Sequence[Mapping] = (),
) -> Optional[ResolutionCandidate]:
    """Best candidate for an unresolved direction-only ``entry``.

    Tries the geometry-aware closure-bracket solve first; if it cannot be
    applied safely, falls back to the simple text-only direction+distance
    suggestion.  Returns ``None`` when neither can produce a safe candidate
    (caller should surface "manual resolution required").
    """
    bracket = _try_closure_bracket(entry, calls, ignored_chunks)
    if bracket is not None:
        return bracket

    # Fall back to the simple text-only suggestion, but using the *effective*
    # distance so an offset tie ("DISTANT … 52 FEET") is not mistaken for a
    # leg length when no bracket is available to solve it.
    fallback_entry = dict(entry)
    fallback_entry["distance"] = _effective_distance(entry)
    simple = suggest_resolution(fallback_entry)
    if simple is not None:
        return _from_simple(simple)

    return None
