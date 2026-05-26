import os

from ui.ocr_config import ENV_VAR, OCR_SETUP_MESSAGE, resolve_tesseract_path


def _no_files(_):
    return False


def _no_which(_):
    return None


def test_env_var_wins_when_file_exists():
    result = resolve_tesseract_path(
        env={ENV_VAR: "/custom/tesseract"},
        path_exists=lambda p: p == "/custom/tesseract",
        path_which=_no_which,
    )
    assert result == "/custom/tesseract"


def test_env_var_ignored_when_file_missing():
    result = resolve_tesseract_path(
        env={ENV_VAR: "/does/not/exist"},
        path_exists=_no_files,
        path_which=_no_which,
    )
    assert result is None


def test_common_windows_path_used_when_present():
    win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    result = resolve_tesseract_path(
        env={},
        path_exists=lambda p: p == win_path,
        path_which=_no_which,
    )
    assert result == win_path


def test_path_lookup_used_as_fallback():
    result = resolve_tesseract_path(
        env={},
        path_exists=_no_files,
        path_which=lambda name: "/usr/bin/tesseract" if name == "tesseract" else None,
    )
    assert result == "/usr/bin/tesseract"


def test_returns_none_when_nothing_found():
    result = resolve_tesseract_path(
        env={},
        path_exists=_no_files,
        path_which=_no_which,
    )
    assert result is None


def test_env_var_takes_priority_over_windows_paths():
    win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    result = resolve_tesseract_path(
        env={ENV_VAR: "/custom/tesseract"},
        path_exists=lambda p: True,
        path_which=lambda name: "/usr/bin/tesseract",
    )
    assert result == "/custom/tesseract"


def test_setup_message_mentions_env_var_and_manual_workflow():
    assert ENV_VAR in OCR_SETUP_MESSAGE
    assert "manual" in OCR_SETUP_MESSAGE.lower()


def test_localappdata_per_user_install_found():
    localappdata = r"C:\Users\testuser\AppData\Local"
    expected = os.path.join(localappdata, "Programs", "Tesseract-OCR", "tesseract.exe")
    result = resolve_tesseract_path(
        env={"LOCALAPPDATA": localappdata},
        path_exists=lambda p: p == expected,
        path_which=_no_which,
    )
    assert result == expected


def test_env_var_takes_priority_over_localappdata():
    localappdata = r"C:\Users\testuser\AppData\Local"
    result = resolve_tesseract_path(
        env={ENV_VAR: "/custom/tesseract", "LOCALAPPDATA": localappdata},
        path_exists=lambda p: True,
        path_which=_no_which,
    )
    assert result == "/custom/tesseract"


def test_invalid_localappdata_path_ignored_safely():
    localappdata = r"C:\Users\testuser\AppData\Local"
    result = resolve_tesseract_path(
        env={"LOCALAPPDATA": localappdata},
        path_exists=_no_files,
        path_which=_no_which,
    )
    assert result is None


def test_path_fallback_used_when_localappdata_missing():
    result = resolve_tesseract_path(
        env={},
        path_exists=_no_files,
        path_which=lambda name: "/usr/local/bin/tesseract" if name == "tesseract" else None,
    )
    assert result == "/usr/local/bin/tesseract"
