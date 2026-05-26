"""Tests for the pure legal-text section splitter.

These exercise only ``transcription.sections``; they do not touch
``parse_legal_description`` (whose behaviour must remain unchanged).
"""

import pytest

from transcription.sections import (
    LegalTextSection,
    split_legal_text_sections,
    TYPE_BOILERPLATE,
    TYPE_COMMENCEMENT,
    TYPE_PARCEL,
    TYPE_EASEMENT,
    TYPE_EXHIBIT,
    TYPE_UNKNOWN,
)


def _concat(sections):
    return "".join(s.text for s in sections)


def test_empty_and_whitespace_returns_empty():
    assert split_legal_text_sections("") == []
    assert split_legal_text_sections("   \n\t ") == []
    assert split_legal_text_sections(None) == []


def test_two_parcels_yield_two_parcel_sections():
    text = (
        "PARCEL 1:\nTHENCE NORTH 100 FEET;\n"
        "PARCEL 2:\nTHENCE EAST 50 FEET;"
    )
    sections = split_legal_text_sections(text)

    parcels = [s for s in sections if s.section_type == TYPE_PARCEL]
    assert len(parcels) == 2
    assert parcels[0].label == "PARCEL 1"
    assert parcels[1].label == "PARCEL 2"
    assert _concat(sections) == text


def test_text_before_first_parcel_is_preserved():
    text = (
        "THE FOLLOWING DESCRIBED LAND IN ORANGE COUNTY:\n"
        "PARCEL 1:\nTHENCE NORTH 100 FEET;"
    )
    sections = split_legal_text_sections(text)

    assert sections[0].section_type in (TYPE_BOILERPLATE, TYPE_COMMENCEMENT)
    assert "ORANGE COUNTY" in sections[0].text
    assert _concat(sections) == text


def test_true_point_of_beginning_marks_commencement_transition():
    text = (
        "COMMENCING AT THE NORTHEAST CORNER OF SECTION 5; "
        "THENCE WEST 200 FEET TO THE TRUE POINT OF BEGINNING; "
        "THENCE NORTH 100 FEET;"
    )
    sections = split_legal_text_sections(text)

    assert sections[0].section_type == TYPE_COMMENCEMENT
    assert "TRUE POINT OF BEGINNING" in sections[0].text.upper()
    # Everything after the POB phrase becomes a boundary (unknown) section.
    assert sections[1].section_type == TYPE_UNKNOWN
    assert _concat(sections) == text


def test_easement_parcel_classified_as_easement():
    text = (
        "PARCEL 1:\nTHENCE NORTH 100 FEET;\n"
        "EASEMENT PARCEL 2:\nAN EASEMENT FOR INGRESS AND EGRESS."
    )
    sections = split_legal_text_sections(text)

    easements = [s for s in sections if s.section_type == TYPE_EASEMENT]
    assert len(easements) == 1
    assert easements[0].label == "EASEMENT PARCEL 2"
    # The inner word "PARCEL" must not spawn a separate parcel section.
    parcels = [s for s in sections if s.section_type == TYPE_PARCEL]
    assert len(parcels) == 1
    assert _concat(sections) == text


def test_access_and_nonexclusive_easements_detected():
    text = (
        "PARCEL A:\nTHENCE NORTH 100 FEET;\n"
        "ACCESS EASEMENT:\nOVER THE WESTERLY 20 FEET.\n"
        "NON-EXCLUSIVE EASEMENT:\nFOR UTILITIES."
    )
    sections = split_legal_text_sections(text)
    types = [s.section_type for s in sections]
    assert types.count(TYPE_EASEMENT) == 2
    assert _concat(sections) == text


def test_exhibit_classified_as_exhibit():
    text = (
        "EXHIBIT A\nLEGAL DESCRIPTION\n"
        "PARCEL 1:\nTHENCE NORTH 100 FEET;"
    )
    sections = split_legal_text_sections(text)

    exhibits = [s for s in sections if s.section_type == TYPE_EXHIBIT]
    assert len(exhibits) == 1
    assert exhibits[0].label == "EXHIBIT A"
    assert _concat(sections) == text


def test_no_text_is_lost_on_complex_input():
    text = (
        "EXHIBIT A\n"
        "THAT PORTION OF LOT 7 DESCRIBED AS:\n"
        "PARCEL ONE:\n"
        "COMMENCING AT A POINT; THENCE TO THE TRUE POINT OF BEGINNING; "
        "THENCE NORTH 100 FEET;\n"
        "PARCEL B:\nTHENCE EAST 50 FEET;\n"
        "EASEMENT PARCEL:\nFOR DRAINAGE."
    )
    sections = split_legal_text_sections(text)

    assert _concat(sections) == text
    # Sections must be contiguous and offset-consistent.
    assert sections[0].start == 0
    assert sections[-1].end == len(text)
    for prev, nxt in zip(sections, sections[1:]):
        assert prev.end == nxt.start
        assert text[nxt.start:nxt.end] == nxt.text


def test_plain_boundary_without_headers_is_single_section():
    text = "THENCE NORTH 100 FEET; THENCE EAST 50 FEET;"
    sections = split_legal_text_sections(text)

    assert len(sections) == 1
    assert _concat(sections) == text


def test_sections_are_frozen_dataclasses():
    text = "PARCEL 1:\nTHENCE NORTH 100 FEET;"
    section = split_legal_text_sections(text)[0]
    assert isinstance(section, LegalTextSection)
    with pytest.raises(Exception):
        section.label = "X"  # frozen → immutable
