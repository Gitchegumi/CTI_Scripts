import json

import pytest

from tradegumi import journal


def write_entries(path, entries):
    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")


@pytest.fixture
def journal_file(tmp_path, monkeypatch):
    path = tmp_path / "signal_journal.jsonl"
    monkeypatch.setattr(journal, "JOURNAL_FILE", path)
    return path


def test_export_journal_csv_empty_has_analysis_header(journal_file):
    csv_text = journal.export_journal_csv()

    assert "signal_id,symbol,direction,strategy" in csv_text
    assert csv_text.count("\n") == 1


def test_export_journal_csv_filters_and_preserves_legacy_fields(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-1", "symbol": "EURUSD", "grade": "PENDING", "legacy_score": 0.7},
            {"signal_id": "sig-2", "symbol": "USDJPY", "grade": "TP_HIT", "legacy_score": 0.9},
        ],
    )

    csv_text = journal.export_journal_csv("TP_HIT")

    assert "legacy_score" in csv_text
    assert "sig-2" in csv_text
    assert "sig-1" not in csv_text


def test_purge_journal_entries_scopes_to_filter(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-1", "grade": "PENDING"},
            {"signal_id": "sig-2", "grade": "TP_HIT"},
            {"signal_id": "sig-3", "grade": "TP_HIT"},
        ],
    )

    result = journal.purge_journal_entries("TP_HIT")

    assert result == {"removed_count": 2, "remaining_count": 1}
    remaining = journal.read_journal()
    assert [entry["signal_id"] for entry in remaining] == ["sig-1"]
    assert journal.purge_journal_entries("TP_HIT") == {"removed_count": 0, "remaining_count": 1}


def test_reset_signal_to_pending_preserves_signal_data_and_notes(journal_file):
    write_entries(
        journal_file,
        [
            {
                "signal_id": "sig-1",
                "symbol": "EURUSD",
                "grade": "SL_HIT",
                "grade_timestamp": "2026-05-05T10:00:00Z",
                "notes": "keep this",
                "outcome": "loss",
                "score": 0.1,
                "lr_1h": 0.003,
            }
        ],
    )

    assert journal.reset_signal_to_pending("sig-1") is True
    entry = journal.read_journal()[0]
    assert entry["grade"] == "PENDING"
    assert entry["grade_timestamp"] is None
    assert entry["notes"] == "keep this"
    assert entry["lr_1h"] == 0.003
    assert "outcome" not in entry
    assert "score" not in entry


def test_reset_pending_or_missing_signal_is_safe(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "grade": "PENDING", "notes": "ok"}])

    assert journal.reset_signal_to_pending("sig-1") is True
    assert journal.reset_signal_to_pending("missing") is False
    assert journal.read_journal()[0]["notes"] == "ok"
