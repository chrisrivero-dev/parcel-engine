# FILE: parcel_engine/models/schema.py
# PURPOSE: Canonical, locked Pydantic contract for transcription → deterministic geometry
# STATUS: IMPLEMENTED (no geometry, no heuristics)

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


# ============================================================
# Core enums
# ============================================================

class Units(str, Enum):
    FEET = "feet"
    METERS = "meters"


class DirectionBasis(str, Enum):
    TRUE = "true"
    GRID = "grid"
    RECORD = "record"
    ASSUMED = "assumed"
    UNKNOWN = "unknown"


class CallType(str, Enum):
    COMMENCEMENT = "commencement"
    LINE = "line"
    CURVE = "curve"
    CLOSE = "close"
    NOTE = "note"


class CurveType(str, Enum):
    TANGENT = "tangent"
    NON_TANGENT = "non_tangent"


class Handedness(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class BearingFormat(str, Enum):
    QUADRANT = "quadrant"
    AZIMUTH = "azimuth"
    UNKNOWN = "unknown"


# ============================================================
# Primitive measurement models
# ============================================================

class DMS(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deg: int = Field(..., ge=0, le=360)
    minutes: int = Field(..., ge=0, lt=60)
    seconds: float = Field(..., ge=0.0, lt=60.0)

    @field_validator("deg")
    @classmethod
    def _deg_int(cls, v: int) -> int:
        return int(v)


class QuadrantBearing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quadrant_ns: Literal["N", "S"]
    angle: DMS
    quadrant_ew: Literal["E", "W"]


class AzimuthBearing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    azimuth: DMS


BearingValue = Union[QuadrantBearing, AzimuthBearing]


class Bearing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    format: BearingFormat = BearingFormat.UNKNOWN
    value: Optional[BearingValue] = None
    basis: DirectionBasis = DirectionBasis.UNKNOWN
    confidence: float = Field(0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _require_value_if_known(self) -> "Bearing":
        if self.format != BearingFormat.UNKNOWN and self.value is None:
            raise ValueError("Bearing.value required when format is not UNKNOWN")
        return self


class Distance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    value: Optional[float] = Field(default=None, gt=0.0)
    units: Units = Units.FEET
    confidence: float = Field(0.0, ge=0.0, le=1.0)


# ============================================================
# Monument references
# ============================================================

class MonumentType(str, Enum):
    FOUND = "found"
    SET = "set"
    RECORD = "record"
    CALCULATED = "calculated"
    UNKNOWN = "unknown"


class MonumentRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: Optional[str] = None
    monument_type: MonumentType = MonumentType.UNKNOWN
    x: Optional[float] = None
    y: Optional[float] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


# ============================================================
# Curve parameters (deterministic contract)
# ============================================================

class CurveParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curve_type: CurveType

    radius: Optional[float] = Field(default=None, gt=0.0)
    delta: Optional[DMS] = None
    arc_length: Optional[float] = Field(default=None, gt=0.0)
    chord_length: Optional[float] = Field(default=None, gt=0.0)
    chord_bearing: Optional[Bearing] = None

    handedness: Optional[Handedness] = None

    # Non-tangent anchors (NO assumptions allowed)
    radial_bearing_to_pc: Optional[Bearing] = None
    radial_bearing_to_pt: Optional[Bearing] = None
    bearing_in: Optional[Bearing] = None
    bearing_out: Optional[Bearing] = None

    confidence: float = Field(0.0, ge=0.0, le=1.0)


# ============================================================
# Call hierarchy
# ============================================================

class BaseCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    call_type: CallType
    raw_text: str
    confidence: float = Field(0.0, ge=0.0, le=1.0)

    to_monument: Optional[str] = None
    along_feature: Optional[str] = None
    more_or_less: bool = False


class CommencementCall(BaseCall):
    call_type: Literal[CallType.COMMENCEMENT] = CallType.COMMENCEMENT

    bearing: Optional[Bearing] = None
    distance: Optional[Distance] = None
    from_monument: Optional[str] = None
    to_point_description: Optional[str] = None


class LineCall(BaseCall):
    call_type: Literal[CallType.LINE] = CallType.LINE

    bearing: Bearing
    distance: Distance


class CurveCall(BaseCall):
    call_type: Literal[CallType.CURVE] = CallType.CURVE

    params: CurveParams


class CloseCall(BaseCall):
    call_type: Literal[CallType.CLOSE] = CallType.CLOSE
    to_pob: bool = True


class NoteCall(BaseCall):
    call_type: Literal[CallType.NOTE] = CallType.NOTE
    tags: List[str] = Field(default_factory=list)


AnyCall = Union[
    CommencementCall,
    LineCall,
    CurveCall,
    CloseCall,
    NoteCall,
]



# ============================================================
# Reference ties (non-traverse, informational geometry only)
# ============================================================

class RefTieKind(str, Enum):
    BEARING_FROM_MONUMENT = "bearing_from_monument"   # SAID POINT BEING brg dist FROM mon
    LINEAR_ALONG_LINE     = "linear_along_line"       # dist dir AS MEASURED ALONG feat FROM mon


class ReferenceTie(BaseModel):
    """
    A survey reference tie extracted from a legal description.

    These describe WHERE a traverse point sits relative to a known monument
    or line feature.  They are NOT traverse legs — exclude from closure
    calculations and build_geometry.  Render as dashed/informational lines.
    """
    model_config = ConfigDict(extra="forbid")

    id: str
    raw_text: str
    kind: RefTieKind

    # Populated for BEARING_FROM_MONUMENT
    bearing: Optional[Bearing] = None

    # Populated for both kinds
    distance: Optional[Distance] = None
    direction_word: Optional[str] = None   # e.g. "SOUTHEASTERLY"

    # The feature / line being measured along (LINEAR_ALONG_LINE)
    along_feature: Optional[str] = None

    # The monument this tie originates from
    from_monument: Optional[str] = None

    # The traverse call this tie is attached to (parent endpoint)
    parent_call_id: Optional[str] = None

    confidence: float = Field(0.0, ge=0.0, le=1.0)

# ============================================================
# Easements
# ============================================================

class EasementRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    raw_text: str
    related_call_ids: List[str] = Field(default_factory=list)
    width: Optional[float] = Field(default=None, gt=0.0)
    units: Units = Units.FEET
    confidence: float = Field(0.0, ge=0.0, le=1.0)


# ============================================================
# Root legal description
# ============================================================

class LegalDescription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    doc_id: str
    source_text: str

    units: Units = Units.FEET
    direction_basis: DirectionBasis = DirectionBasis.UNKNOWN

    monuments: List[MonumentRef] = Field(default_factory=list)

    commencement_calls: List[CommencementCall] = Field(default_factory=list)
    boundary_calls: List[AnyCall] = Field(default_factory=list)

    easements: List[EasementRef] = Field(default_factory=list)
    reference_ties: List[ReferenceTie] = Field(default_factory=list)

    meta: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _unique_call_ids(self) -> "LegalDescription":
        ids = [c.id for c in self.commencement_calls] + [
            c.id for c in self.boundary_calls
        ]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate call IDs detected")
        return self
