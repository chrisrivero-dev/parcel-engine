"""Tests for the pure RowAuditStore."""

from types import SimpleNamespace

from ui.audit_trail import (
    RowAudit,
    RowAuditStore,
    SOURCE_LEGAL,
    SOURCE_MANUAL,
    SOURCE_SUGGESTED,
)


def _suggestion(**kw):
    defaults = dict(
        original_text="THENCE WESTERLY TO A POINT",
        method="paired_bracket",
        confidence="medium",
        reason="solved from bracket",
        residual=4.23,
        direction="WESTERLY",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_from_suggestion_populates_all_fields():
    a = RowAudit.from_suggestion(_suggestion(), bearing_text="N 85d W", distance_text="119.90 ft")
    assert a.source == SOURCE_SUGGESTED
    assert a.method == "paired_bracket"
    assert a.confidence == "medium"
    assert a.residual == 4.23
    assert a.direction_word == "WESTERLY"
    assert a.timestamp != ""


def test_detail_text_legal_vs_manual_vs_suggested():
    assert "Legal" in RowAudit.legal().detail_text()
    assert "Manual" in RowAudit.manual().detail_text()
    txt = RowAudit.from_suggestion(_suggestion(), "N", "10").detail_text()
    assert "Suggested" in txt and "paired_bracket" in txt and "WESTERLY" in txt


def test_replace_all_legal_sets_n_legal_rows():
    s = RowAuditStore()
    s.replace_all_legal(3)
    assert len(s) == 3
    assert all(r.source == SOURCE_LEGAL for r in s)


def test_append_returns_new_index():
    s = RowAuditStore()
    s.replace_all_legal(2)
    assert s.append(RowAudit.manual()) == 2
    assert s.get(2).source == SOURCE_MANUAL


def test_remove_at_compacts_indices():
    s = RowAuditStore()
    s.replace_all_legal(1)
    s.append(RowAudit.manual())
    s.append(RowAudit.from_suggestion(_suggestion(), "N", "1"))
    s.remove_at(1)
    assert [r.source for r in s] == [SOURCE_LEGAL, SOURCE_SUGGESTED]


def test_swap_exchanges_audit_records():
    s = RowAuditStore()
    s.replace_all_legal(1)
    s.append(RowAudit.manual())
    s.swap(0, 1)
    assert s.get(0).source == SOURCE_MANUAL
    assert s.get(1).source == SOURCE_LEGAL


def test_insert_at_shifts_subsequent_rows():
    s = RowAuditStore()
    s.replace_all_legal(2)
    s.insert_at(1, RowAudit.from_suggestion(_suggestion(), "N", "1"))
    assert [r.source for r in s] == [SOURCE_LEGAL, SOURCE_SUGGESTED, SOURCE_LEGAL]


def test_clear_empties_the_store():
    s = RowAuditStore()
    s.replace_all_legal(3)
    s.clear()
    assert len(s) == 0


def test_get_out_of_range_returns_legal_default():
    s = RowAuditStore()
    s.replace_all_legal(1)
    assert s.get(99).source == SOURCE_LEGAL


def test_remove_unknown_index_is_noop():
    s = RowAuditStore()
    s.replace_all_legal(2)
    s.remove_at(42)
    assert len(s) == 2


def test_audit_metadata_survives_move_sequence():
    s = RowAuditStore()
    s.replace_all_legal(2)
    sugg = RowAudit.from_suggestion(_suggestion(), "N 85 W", "119.9")
    s.append(sugg)
    s.swap(2, 1)
    s.swap(1, 0)
    assert s.get(0).source == SOURCE_SUGGESTED
    assert s.get(0).bearing_text == "N 85 W"
    assert s.get(0).method == "paired_bracket"
    s.remove_at(1)
    assert s.get(0).source == SOURCE_SUGGESTED
