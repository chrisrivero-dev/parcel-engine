from __future__ import annotations

import os
import shutil
from typing import Optional

ENV_VAR = "PARCEL_ENGINE_TESSERACT"

_COMMON_WINDOWS_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
)

OCR_SETUP_MESSAGE = (
    "Tesseract OCR was not found on this machine.\n\n"
    "Image OCR requires the Tesseract executable. You can still paste or "
    "type legal descriptions into the source box manually without OCR.\n\n"
    "To enable Load Image OCR:\n"
    "  1. Install Tesseract:\n"
    "       Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
    "       macOS:   brew install tesseract\n"
    "       Linux:   sudo apt install tesseract-ocr\n"
    "  2. Either add the Tesseract install folder to your PATH,\n"
    "     or set the PARCEL_ENGINE_TESSERACT environment variable\n"
    "     to the full path of tesseract.exe (or tesseract).\n\n"
    "Then restart the app and try Load Image OCR again."
)


def resolve_tesseract_path(
    env: Optional[dict] = None,
    path_exists=os.path.isfile,
    path_which=shutil.which,
) -> Optional[str]:
    """
    Return a resolved path to the Tesseract executable, or None if not found.

    Resolution order:
      1. PARCEL_ENGINE_TESSERACT env var (if it points to an existing file)
      2. Common Windows system-wide install locations (Program Files)
      3. Per-user Windows install: %LOCALAPPDATA%\\Programs\\Tesseract-OCR\\tesseract.exe
      4. `tesseract` on PATH

    All filesystem and PATH lookups are injectable for testing.
    """
    env = env if env is not None else os.environ

    env_path = env.get(ENV_VAR)
    if env_path and path_exists(env_path):
        return env_path

    for candidate in _COMMON_WINDOWS_PATHS:
        if path_exists(candidate):
            return candidate

    localappdata = env.get("LOCALAPPDATA")
    if localappdata:
        candidate = os.path.join(
            localappdata, "Programs", "Tesseract-OCR", "tesseract.exe"
        )
        if path_exists(candidate):
            return candidate

    found = path_which("tesseract")
    if found:
        return found

    return None
