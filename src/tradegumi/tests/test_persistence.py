"""Tests for the persistence abstraction layer.

Covers SQLiteBackend and get_db() factory.  PostgresBackend is tested
separately (requires a live Postgres container) in CI.
"""

import os
import tempfile
from pathlib import Path

import pytest

from tradegumi.persistence import DBBackend, SQLiteBackend, get_db, close_db


@pytest.fixture
def tmp_sqlite():
    """Yield a fresh SQLiteBackend pointing at a temp file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    db = SQLiteBackend(db_path=path)
    yield db
    db.close()
    path.unlink(missing_ok=True)


class TestSQLiteBackend:
    def test_init_schema_creates_tables(self, tmp_sqlite: SQLiteBackend):
        tmp_sqlite.init_schema()
        conn = tmp_sqlite.connect()
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('evaluated_opportunities', 'criterion_results', 'journal_entries')"
        )
        tables = {r[0] for r in cur.fetchall()}
        assert tables == {"evaluated_opportunities", "criterion_results", "journal_entries"}

    def test_evaluated_opportunities_is_append_only(self, tmp_sqlite: SQLiteBackend):
        """The PK is composite (id, evaluated_at) — inserting the same id with a
        different evaluated_at should succeed (append-only)."""
        tmp_sqlite.init_schema()
        tmp_sqlite.execute(
            """
            INSERT INTO evaluated_opportunities (id, evaluated_at, symbol, timeframe, mode, strategy,
                signal_type, direction, trend, final_decision, decision_reason, failed_criteria_count,
                near_miss, data_complete, data_quality_notes, threshold_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("opp-1", "2026-01-01T00:00:00", "EURUSD", "M15", "alert_only", "cti",
             "pullback", "BUY", "uptrend", "emitted", "passed", 0, 0, 1, "[]", "v1", "2026-01-01T00:00:00"),
        )
        tmp_sqlite.execute(
            """
            INSERT INTO evaluated_opportunities (id, evaluated_at, symbol, timeframe, mode, strategy,
                signal_type, direction, trend, final_decision, decision_reason, failed_criteria_count,
                near_miss, data_complete, data_quality_notes, threshold_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("opp-1", "2026-01-01T01:00:00", "EURUSD", "M15", "alert_only", "cti",
             "pullback", "BUY", "uptrend", "rejected", "failed", 1, 0, 1, "[]", "v1", "2026-01-01T01:00:00"),
        )
        rows = tmp_sqlite.fetchall("SELECT * FROM evaluated_opportunities WHERE id = ?", ("opp-1",))
        assert len(rows) == 2
        decisions = {r["final_decision"] for r in rows}
        assert decisions == {"emitted", "rejected"}

    def test_criterion_results_foreign_key(self, tmp_sqlite: SQLiteBackend):
        """Criterion rows reference (id, evaluated_at)."""
        tmp_sqlite.init_schema()
        tmp_sqlite.execute(
            """
            INSERT INTO evaluated_opportunities (id, evaluated_at, symbol, timeframe, mode, strategy,
                signal_type, direction, trend, final_decision, decision_reason, failed_criteria_count,
                near_miss, data_complete, data_quality_notes, threshold_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("opp-2", "2026-01-01T00:00:00", "GBPUSD", "M15", "alert_only", "cti",
             "pullback", "SELL", "downtrend", "emitted", "passed", 0, 0, 1, "[]", "v1", "2026-01-01T00:00:00"),
        )
        tmp_sqlite.execute(
            """
            INSERT INTO criterion_results (opportunity_id, evaluated_at, criterion_name, layer,
                threshold_operator, required, blocked_signal, data_quality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("opp-2", "2026-01-01T00:00:00", "trend_aligned", "layer_1", "gte", 1, 0, "complete"),
        )
        rows = tmp_sqlite.fetchall("SELECT * FROM criterion_results WHERE opportunity_id = ?", ("opp-2",))
        assert len(rows) == 1
        assert rows[0]["criterion_name"] == "trend_aligned"

    def test_fetchone_returns_none_when_empty(self, tmp_sqlite: SQLiteBackend):
        tmp_sqlite.init_schema()
        result = tmp_sqlite.fetchone("SELECT * FROM evaluated_opportunities WHERE id = ?", ("nope",))
        assert result is None

    def test_transaction_rollback_on_error(self, tmp_sqlite: SQLiteBackend):
        tmp_sqlite.init_schema()
        with pytest.raises(Exception):
            with tmp_sqlite.transaction():
                tmp_sqlite.execute(
                    """
                    INSERT INTO evaluated_opportunities (id, evaluated_at, symbol, timeframe, mode, strategy,
                        signal_type, direction, trend, final_decision, decision_reason, failed_criteria_count,
                        near_miss, data_complete, data_quality_notes, threshold_version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("opp-3", "2026-01-01T00:00:00", "USDJPY", "M15", "alert_only", "cti",
                     "pullback", "BUY", "uptrend", "emitted", "passed", 0, 0, 1, "[]", "v1", "2026-01-01T00:00:00"),
                )
                raise RuntimeError("rollback")
        rows = tmp_sqlite.fetchall("SELECT * FROM evaluated_opportunities WHERE id = ?", ("opp-3",))
        assert len(rows) == 0

    def test_close_releases_connection(self, tmp_sqlite: SQLiteBackend):
        tmp_sqlite.init_schema()
        assert tmp_sqlite._conn is not None
        tmp_sqlite.close()
        assert tmp_sqlite._conn is None


class TestGetDbFactory:
    def test_factory_returns_singleton(self):
        os.environ["TRADEGUMI_DB_BACKEND"] = "sqlite"
        close_db()
        db1 = get_db()
        db2 = get_db()
        assert db1 is db2
        close_db()

    def test_factory_override_backend(self):
        """get_db accepts override params for testing."""
        close_db()
        db = get_db(backend="sqlite")
        assert isinstance(db, SQLiteBackend)
        close_db()

    def test_init_schema_called_on_first_use(self, tmp_sqlite: SQLiteBackend):
        """Schema is initialised automatically by get_db()."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = Path(f.name)
        try:
            db = get_db(backend="sqlite", database_url=str(path))
            conn = db.connect()
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {r[0] for r in cur.fetchall()}
            assert "evaluated_opportunities" in tables
        finally:
            close_db()
            path.unlink(missing_ok=True)

    def test_get_db_fallback_to_sqlite(self, monkeypatch):
        """If postgres backend fails and fallback is enabled, returns SQLite."""
        monkeypatch.setenv("TRADEGUMI_DB_BACKEND", "postgres")
        monkeypatch.setenv("TRADEGUMI_DATABASE_URL", "postgresql://invalid")
        close_db()
        db = get_db()
        assert isinstance(db, SQLiteBackend)
        close_db()

    def test_get_db_no_fallback_raises(self, monkeypatch):
        """If fallback is disabled and postgres fails, raises."""
        monkeypatch.setenv("TRADEGUMI_DB_BACKEND", "postgres")
        monkeypatch.setenv("TRADEGUMI_DATABASE_URL", "postgresql://invalid")
        monkeypatch.setenv("TRADEGUMI_SQLITE_FALLBACK", "false")
        close_db()
        with pytest.raises(Exception):
            get_db()
        close_db()
