# FILE: parcel_engine/models/errors.py
# PURPOSE: Canonical error vocabulary and container models for the geometry engine
# STATUS: IMPLEMENTED (LOCKED)

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# Error codes (LOCKED)
# ============================================================

class ErrorCode(str, Enum):
    BAD_BEARING_FORMAT = "BAD_BEARING_FORMAT"
    MISSING_DISTANCE = "MISSING_DISTANCE"
    CURVE_INCOMPLETE = "CURVE_INCOMPLETE"
    CURVE_PARAM_MISMATCH = "CURVE_PARAM_MISMATCH"
    NON_TANGENT_AMBIGUITY = "NON_TANGENT_AMBIGUITY"
    NOT_CLOSED = "NOT_CLOSED"
    SELF_INTERSECTS = "SELF_INTERSECTS"
    NEEDS_REFERENCE_GEOMETRY = "NEEDS_REFERENCE_GEOMETRY"
    MONUMENT_CONFLICT = "MONUMENT_CONFLICT"
    COMMENCEMENT_GAP = "COMMENCEMENT_GAP"
    OCR_UNCLEAR = "OCR_UNCLEAR"
    UNKNOWN_ELEMENT = "UNKNOWN_ELEMENT"


# ============================================================
# Severity levels
# ============================================================

class ErrorSeverity(str, Enum):
    ERROR = "error"      # Geometry is invalid / cannot proceed
    WARNING = "warning"  # Geometry built but legally or technically suspect


# ============================================================
# Engine error container
# ============================================================

class EngineError(BaseModel):
    """
    Deterministic, survey-defensible error record.

    - code: machine-readable ErrorCode
    - severity: ERROR vs WARNING
    - message: human-readable explanation (no geometry logic here)
    - call_id: optional reference to the offending call
    """

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    severity: ErrorSeverity = ErrorSeverity.ERROR
    message: str = Field(..., min_length=1)
    call_id: Optional[str] = None
