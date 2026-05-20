from pathlib import Path

from transcription.normalize import normalize
from transcription.parser_v2 import parse_legal_description

FIXTURES = Path(__file__).parent / "fixtures"


def _load_reddleshire() -> str:
    return (FIXTURES / "reddleshire_synthetic.txt").read_text(encoding="utf-8")


def test_each_boundary_call_has_source_span():
    calls, _, _, _ = parse_legal_description(_load_reddleshire())
    assert len(calls) == 8
    for call in calls:
        assert call.source_span is not None
        assert call.source_span.text != ""


def test_reference_tie_has_source_span():
    _, ties, _, _ = parse_legal_description(_load_reddleshire())
    commencement_ties = [t for t in ties if t["kind"] == "commencement"]
    assert len(commencement_ties) == 1
    span = commencement_ties[0]["source_span"]
    assert span is not None
    assert span.text != ""


def test_ignored_chunk_has_source_span():
    text = "COMMENCING AT THE NORTHWEST CORNER OF LOT 5; THENCE N 45°00'00\" E 100.00 FEET"
    _, _, _, ignored = parse_legal_description(text)
    for chunk in ignored:
        assert "source_span" in chunk
        assert chunk["source_span"] is not None
        assert chunk["source_span"].text != ""


def test_source_span_text_round_trips():
    """span.text must equal the normalized text slice at [start:end]."""
    text = _load_reddleshire()
    normalized = normalize(text)
    calls, ties, _, ignored = parse_legal_description(text)

    for call in calls:
        span = call.source_span
        assert span is not None
        assert normalized[span.start : span.end] == span.text

    for tie in ties:
        span = tie["source_span"]
        assert span is not None
        assert normalized[span.start : span.end] == span.text

    for chunk in ignored:
        span = chunk["source_span"]
        assert span is not None
        assert normalized[span.start : span.end] == span.text


def test_existing_parser_behavior_unchanged():
    calls, ties, errors, ignored = parse_legal_description(_load_reddleshire())
    assert errors == []
    assert len(calls) == 8
    assert len(ties) == 1
    assert calls[0].distance.value == 3.17
    assert calls[-1].distance.value == 56.74
