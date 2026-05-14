import csv
import json
from io import StringIO

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


def test_build_journal_export_includes_attachment_metadata(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "symbol": "EURUSD", "signal_timestamp": "2026-05-10T10:00:00Z"}])

    result = journal.build_journal_export(journal.SignalJournalExportSelection(start="2026-05-01", end="2026-05-14"))

    assert result.record_count == 1
    assert result.filename == "signal-journal-2026-05-01-to-2026-05-14.csv"
    assert result.content_type == "text/csv; charset=utf-8"
    assert result.content_disposition == 'attachment; filename="signal-journal-2026-05-01-to-2026-05-14.csv"'
    assert "sig-1" in result.csv_text


def test_export_journal_csv_filters_by_evaluated_created_and_legacy_timestamps(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-old", "evaluated_at": "2026-04-30T23:59:00Z"},
            {"signal_id": "sig-evaluated", "evaluated_at": "2026-05-10T12:00:00Z"},
            {"signal_id": "sig-created", "created_at": "2026-05-11T12:00:00Z"},
            {"signal_id": "sig-legacy", "signal_timestamp": "2026-05-12T12:00:00Z"},
            {"signal_id": "sig-new", "created_at": "2026-05-15T00:01:00Z"},
        ],
    )

    csv_text = journal.export_journal_csv(start="2026-05-10T00:00:00Z", end="2026-05-14T23:59:59Z")

    assert "sig-evaluated" in csv_text
    assert "sig-created" in csv_text
    assert "sig-legacy" in csv_text
    assert "sig-old" not in csv_text
    assert "sig-new" not in csv_text


def test_build_journal_export_rejects_invalid_range(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "created_at": "2026-05-10T12:00:00Z"}])

    with pytest.raises(ValueError, match="start must be before end"):
        journal.build_journal_export(journal.SignalJournalExportSelection(start="2026-05-14", end="2026-05-10"))


def test_build_journal_export_reports_empty_selection(journal_file):
    write_entries(journal_file, [{"signal_id": "sig-1", "created_at": "2026-05-10T12:00:00Z"}])

    result = journal.build_journal_export(journal.SignalJournalExportSelection(start="2026-05-11"))

    assert result.record_count == 0
    assert "signal_id,symbol,direction,strategy" in result.csv_text


def test_export_journal_csv_combines_grade_and_range(journal_file):
    write_entries(
        journal_file,
        [
            {"signal_id": "sig-1", "grade": "PENDING", "created_at": "2026-05-10T12:00:00Z"},
            {"signal_id": "sig-2", "grade": "TP_HIT", "created_at": "2026-05-10T12:00:00Z"},
            {"signal_id": "sig-3", "grade": "TP_HIT", "created_at": "2026-04-01T12:00:00Z"},
        ],
    )

    csv_text = journal.export_journal_csv("TP_HIT", start="2026-05-01", end="2026-05-14")

    assert "sig-2" in csv_text
    assert "sig-1" not in csv_text
    assert "sig-3" not in csv_text


def test_export_journal_csv_has_required_columns_and_json_nested_values(journal_file):
    write_entries(
        journal_file,
        [
            {
                "signal_id": "sig-1",
                "symbol": "EURUSD",
                "all_blockers": ["trend", "risk"],
                "criteria": {"trend": False, "risk": True},
            }
        ],
    )

    rows = list(csv.DictReader(StringIO(journal.export_journal_csv())))

    assert rows[0]["signal_id"] == "sig-1"
    assert "opportunity_id" in rows[0]
    assert "timeframe" in rows[0]
    assert "final_decision" in rows[0]
    assert "evaluated_at" in rows[0]
    assert "created_at" in rows[0]
    assert rows[0]["all_blockers"] == '["trend","risk"]'
    assert rows[0]["criteria"] == '{"risk":true,"trend":false}'


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
