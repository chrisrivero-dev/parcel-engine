from pathlib import Path

from domain.project import ParcelProject
from transcription.parser_v2 import parse_legal_description

FIXTURES = Path(__file__).parent / "fixtures"


def _load_reddleshire() -> str:
    return (FIXTURES / "reddleshire_synthetic.txt").read_text(encoding="utf-8")


def test_project_from_parse_result_counts():
    text = _load_reddleshire()
    calls, ties, errors, ignored = parse_legal_description(text)

    project = ParcelProject.from_parse_result(text, calls, ties, errors, ignored)

    assert project.boundary_count() == 8
    assert project.reference_tie_count() == 1
    assert project.error_count() == 0


def test_project_stores_ignored_chunks():
    text = (
        "BEGINNING at an iron pin; "
        "TOGETHER WITH all riparian rights and appurtenances thereto; "
        "thence North 45 degrees East 100.00 feet; "
        "thence South 45 degrees East 100.00 feet to the POINT OF BEGINNING."
    )
    calls, ties, errors, ignored = parse_legal_description(text)

    project = ParcelProject.from_parse_result(text, calls, ties, errors, ignored)

    assert project.ignored_count() == len(ignored)
    assert project.ignored_chunks == ignored


def test_project_closure_misclose_can_be_updated():
    project = ParcelProject()
    assert project.closure_misclose is None

    project.closure_misclose = 0.042
    assert project.closure_misclose == 0.042


def test_project_does_not_mutate_calls():
    text = _load_reddleshire()
    calls, ties, errors, ignored = parse_legal_description(text)

    first_bearing_raw = calls[0].bearing.raw_text
    first_distance_value = calls[0].distance.value

    project = ParcelProject.from_parse_result(text, calls, ties, errors, ignored)

    assert project.calls[0] is calls[0]
    assert project.calls[0].bearing.raw_text == first_bearing_raw
    assert project.calls[0].distance.value == first_distance_value
