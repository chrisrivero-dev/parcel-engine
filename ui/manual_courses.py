from __future__ import annotations

from models.schema import (
    AzimuthBearing,
    Bearing,
    BearingFormat,
    DirectionBasis,
    Distance,
    DMS,
    LineCall,
)
from transcription.lines import parse_line_chunk
from transcription.normalize import normalize


_CARDINAL_AZIMUTH = {"N": 0, "S": 180, "E": 90, "W": 270}
_CARDINAL_WORDS = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W"}


def build_manual_line(direction: str, distance: str, idx: int) -> LineCall:
    """
    Build a LineCall from manually-entered direction text and distance text.

    Supported direction formats:
      - Quadrant DMS:  N 45°32'10" E,  N45°32'10"E,  NORTH 45°32'10" EAST
      - Pure cardinal: N, S, E, W
      - Cardinal word: NORTH, SOUTH, EAST, WEST

    Raises ValueError with a human-readable message on failure.
    """
    direction = (direction or "").strip()
    distance = (distance or "").strip()

    if not direction:
        raise ValueError("missing direction")
    if not distance:
        raise ValueError("missing distance")

    try:
        dist_value = float(distance)
    except ValueError as exc:
        raise ValueError(f"distance not numeric: {distance!r}") from exc

    if dist_value <= 0:
        raise ValueError(f"distance must be positive: {dist_value}")

    normalized_dir = normalize(direction).upper().strip()

    cardinal_letter = None
    if normalized_dir in _CARDINAL_AZIMUTH:
        cardinal_letter = normalized_dir
    elif normalized_dir in _CARDINAL_WORDS:
        cardinal_letter = _CARDINAL_WORDS[normalized_dir]

    if cardinal_letter is not None:
        az_deg = _CARDINAL_AZIMUTH[cardinal_letter]
        return LineCall(
            id=f"L{idx}",
            raw_text=f"{cardinal_letter} {dist_value}",
            bearing=Bearing(
                raw_text=cardinal_letter,
                format=BearingFormat.AZIMUTH,
                value=AzimuthBearing(
                    azimuth=DMS(deg=az_deg, minutes=0, seconds=0.0)
                ),
                basis=DirectionBasis.TRUE,
                confidence=1.0,
            ),
            distance=Distance(raw_text=str(dist_value), value=dist_value),
        )

    combined = f"{normalize(direction)} {dist_value}"
    parsed = parse_line_chunk(combined, idx)
    if parsed is None:
        raise ValueError(f"could not parse direction: {direction!r}")

    parsed.id = f"L{idx}"
    parsed.distance = Distance(raw_text=str(dist_value), value=dist_value)
    return parsed
