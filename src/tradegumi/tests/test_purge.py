"""Tests for tradegumi.purge module.
"""

import json
from pathlib import Path

import pytest

from tradegumi import purge


class _FakeDB:
    """Records executed SQL so tests can assert TRUNCATE behaviour."""

    def __init__(self):
        self.executed: list[str] = []

    def execute(self, sql, params=None):
        self.executed.append(sql)
        return None


@pytest.fixture(autouse=True)
def _reset_data_dir(monkeypatch, tmp_path):
    """Redirect all data paths to a temp directory for isolation."""
    monkeypatch.setattr(purge, "DATA_DIR", tmp_path)
    monkeypatch.setattr(purge, "JOURNAL_FILE", tmp_path / "signal_journal.jsonl")
    monkeypatch.setattr(purge, "STRATEGY_METRICS_DB", tmp_path / "strategy_metrics.db")
    monkeypatch.setattr(purge, "STRATEGY_METRICS_STATE", tmp_path / "strategy_metrics.json")
    monkeypatch.setattr(purge, "MANUAL_TRADES_DB", tmp_path / "manual_trades.db")
    monkeypatch.setattr(purge, "SIGNALS_FILE", tmp_path / "signals.json")
    monkeypatch.setattr(purge, "LOOP_STATE_FILE", tmp_path / "loop_state.json")
    monkeypatch.setattr(purge, "SESSION_STATE_FILE", tmp_path / "session_state.json")
    monkeypatch.setattr(purge, "TRADE_CORRELATIONS_FILE", tmp_path / "trade_correlations.json")


@pytest.fixture(autouse=True)
def _fake_pg(monkeypatch):
    """Stub out the Postgres backend so purge tests run without a database."""
    fake = _FakeDB()
    monkeypatch.setattr(purge, "get_db", lambda: fake)
    return fake


class TestTruncatePostgres:
    def test_truncate_runs_expected_sql(self, _fake_pg):
        assert purge._truncate_postgres("journal_entries") is True
        assert _fake_pg.executed == ["TRUNCATE journal_entries RESTART IDENTITY CASCADE"]

    def test_truncate_reports_failure_when_unavailable(self, monkeypatch):
        def boom():
            raise RuntimeError("postgres unavailable")

        monkeypatch.setattr(purge, "get_db", boom)
        assert purge._truncate_postgres("journal_entries") is False


class TestPurgeJournal:
    def test_purge_empty_journal_truncates_postgres(self, _fake_pg):
        assert purge.purge_journal() is True
        assert not purge.JOURNAL_FILE.exists()
        assert any("journal_entries" in sql for sql in _fake_pg.executed)

    def test_purge_removes_entries(self, _fake_pg):
        purge.JOURNAL_FILE.write_text(json.dumps({"signal_id": "TEST:1"}) + "\n", encoding="utf-8")
        assert purge.purge_journal() is True
        assert purge.JOURNAL_FILE.exists()
        assert purge.JOURNAL_FILE.read_text() == ""
        assert any("journal_entries" in sql for sql in _fake_pg.executed)

    def test_purge_creates_backup_when_requested(self, tmp_path):
        purge.JOURNAL_FILE.write_text(json.dumps({"signal_id": "TEST:2"}) + "\n", encoding="utf-8")
        backup_dir = tmp_path / "backups"
        purge.purge_journal(backup_dir=backup_dir)
        backups = list(backup_dir.glob("signal_journal.jsonl.*"))
        assert len(backups) == 1
        assert "TEST:2" in backups[0].read_text()

    def test_jsonl_cleared_even_if_postgres_fails(self, monkeypatch):
        def boom():
            raise RuntimeError("postgres unavailable")

        monkeypatch.setattr(purge, "get_db", boom)
        purge.JOURNAL_FILE.write_text(json.dumps({"signal_id": "TEST:3"}) + "\n", encoding="utf-8")
        assert purge.purge_journal() is False
        assert purge.JOURNAL_FILE.read_text() == ""


class TestPurgeStrategyMetrics:
    def test_purge_truncates_postgres_tables(self, _fake_pg):
        assert purge.purge_strategy_metrics() is True
        assert any(
            "evaluated_opportunities" in sql and "criterion_results" in sql
            for sql in _fake_pg.executed
        )

    def test_purge_deletes_legacy_file_and_state(self, _fake_pg):
        # A pre-migration install may still have the SQLite file + state snapshot.
        purge.STRATEGY_METRICS_DB.write_text("sqlite", encoding="utf-8")
        purge.STRATEGY_METRICS_STATE.write_text(json.dumps({"total": 42}), encoding="utf-8")
        assert purge.purge_strategy_metrics() is True
        assert not purge.STRATEGY_METRICS_DB.exists()
        assert not purge.STRATEGY_METRICS_STATE.exists()
        assert any("evaluated_opportunities" in sql for sql in _fake_pg.executed)

    def test_purge_creates_backup_when_requested(self, tmp_path):
        purge.STRATEGY_METRICS_DB.write_text("sqlite", encoding="utf-8")
        purge.STRATEGY_METRICS_STATE.write_text(json.dumps({"total": 42}), encoding="utf-8")
        backup_dir = tmp_path / "backups"
        purge.purge_strategy_metrics(backup_dir=backup_dir)
        assert len(list(backup_dir.glob("strategy_metrics.db.*"))) == 1
        assert len(list(backup_dir.glob("strategy_metrics.json.*"))) == 1

    def test_purge_reports_failure_when_postgres_unavailable(self, monkeypatch):
        def boom():
            raise RuntimeError("postgres unavailable")

        monkeypatch.setattr(purge, "get_db", boom)
        assert purge.purge_strategy_metrics() is False


class TestPurgeManualTrades:
    def test_purge_nonexistent_db_is_safe(self):
        assert purge.purge_manual_trades() is True

    def test_purge_deletes_manual_trades_db(self):
        purge.MANUAL_TRADES_DB.write_text("sqlite", encoding="utf-8")
        assert purge.purge_manual_trades() is True
        assert not purge.MANUAL_TRADES_DB.exists()


class TestPurgeSignalsState:
    def test_purge_resets_signals_to_empty_list(self):
        purge.SIGNALS_FILE.write_text(json.dumps([{"id": "s1"}]), encoding="utf-8")
        assert purge.purge_signals_state() is True
        assert json.loads(purge.SIGNALS_FILE.read_text()) == []


class TestPurgeLoopState:
    def test_purge_resets_loop_state(self):
        purge.LOOP_STATE_FILE.write_text(json.dumps({"last_run": "2024-01-01"}), encoding="utf-8")
        assert purge.purge_loop_state() is True
        data = json.loads(purge.LOOP_STATE_FILE.read_text())
        assert data["last_run"] is None
        assert data["symbols_processed"] == []


class TestPurgeSessionState:
    def test_purge_resets_session_state(self):
        purge.SESSION_STATE_FILE.write_text(json.dumps({"session_id": "abc"}), encoding="utf-8")
        assert purge.purge_session_state() is True
        data = json.loads(purge.SESSION_STATE_FILE.read_text())
        assert data["session_id"] is None


class TestPurgeTradeCorrelations:
    def test_purge_nonexistent_file_is_safe(self):
        assert purge.purge_trade_correlations() is False

    def test_purge_deletes_file(self):
        purge.TRADE_CORRELATIONS_FILE.write_text(json.dumps({}), encoding="utf-8")
        assert purge.purge_trade_correlations() is True
        assert not purge.TRADE_CORRELATIONS_FILE.exists()


class TestPurgeAll:
    def test_purge_all_clears_everything(self):
        # Seed all targets
        purge.JOURNAL_FILE.write_text(json.dumps({"id": 1}) + "\n", encoding="utf-8")
        purge.STRATEGY_METRICS_DB.write_text("sqlite", encoding="utf-8")
        purge.STRATEGY_METRICS_STATE.write_text("{}", encoding="utf-8")
        purge.MANUAL_TRADES_DB.write_text("sqlite", encoding="utf-8")
        purge.SIGNALS_FILE.write_text(json.dumps([{"id": "s1"}]), encoding="utf-8")
        purge.LOOP_STATE_FILE.write_text(json.dumps({"last_run": "x"}), encoding="utf-8")
        purge.SESSION_STATE_FILE.write_text(json.dumps({"session_id": "x"}), encoding="utf-8")
        purge.TRADE_CORRELATIONS_FILE.write_text("{}", encoding="utf-8")

        results = purge.purge_all()
        assert all(results.values())
        assert purge.JOURNAL_FILE.read_text() == ""
        assert not purge.STRATEGY_METRICS_DB.exists()
        assert not purge.MANUAL_TRADES_DB.exists()
        assert json.loads(purge.SIGNALS_FILE.read_text()) == []

    def test_purge_all_with_backup(self, tmp_path):
        backup_dir = tmp_path / "backups"
        purge.JOURNAL_FILE.write_text(json.dumps({"id": 1}) + "\n", encoding="utf-8")
        purge.STRATEGY_METRICS_DB.write_text("sqlite", encoding="utf-8")

        results = purge.purge_all(backup_dir=backup_dir)
        # trade_correlations may return False if file didn't exist, which is fine
        assert all(v for k, v in results.items() if k != "trade_correlations")
        assert len(list(backup_dir.glob("*"))) > 0

    def test_purge_selected_targets_only(self):
        purge.JOURNAL_FILE.write_text(json.dumps({"id": 1}) + "\n", encoding="utf-8")
        purge.SIGNALS_FILE.write_text(json.dumps([{"id": "s1"}]), encoding="utf-8")

        results = purge.purge_all(targets=["journal"])
        assert results["journal"] is True
        assert "signals" not in results
        assert purge.JOURNAL_FILE.read_text() == ""
        assert json.loads(purge.SIGNALS_FILE.read_text()) == [{"id": "s1"}]


class TestMainCLI:
    def test_list_targets(self, capsys):
        assert purge.main(["--list-targets"]) == 0
        captured = capsys.readouterr()
        assert "journal" in captured.out
        assert "strategy_metrics" in captured.out

    def test_purge_with_force_no_confirm(self, tmp_path, capsys):
        purge.JOURNAL_FILE.write_text(json.dumps({"id": 1}) + "\n", encoding="utf-8")
        backup_dir = tmp_path / "backups"
        assert purge.main(["--force", "--targets", "journal", "--backup-dir", str(backup_dir)]) == 0
        captured = capsys.readouterr()
        assert "✅ journal" in captured.out
        assert purge.JOURNAL_FILE.read_text() == ""

    def test_purge_no_backup(self, capsys):
        purge.JOURNAL_FILE.write_text(json.dumps({"id": 1}) + "\n", encoding="utf-8")
        assert purge.main(["--force", "--no-backup", "--targets", "journal"]) == 0
        captured = capsys.readouterr()
        assert "WARNING: No backup" in captured.out

    def test_purge_without_force_aborts_on_no(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        assert purge.main(["--targets", "journal"]) == 1
        captured = capsys.readouterr()
        assert "Aborted" in captured.out
