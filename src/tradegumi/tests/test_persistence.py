"""Tests for the Postgres persistence backend and get_db() factory.

These require a live Postgres — set ``TRADEGUMI_TEST_DATABASE_URL`` to run them;
otherwise they skip.
"""

import pytest

from tradegumi.persistence import PostgresBackend, get_db, close_db
from tradegumi.tests._pg import TEST_DSN, requires_postgres, get_test_backend


@pytest.fixture
def db():
    yield get_test_backend()


@requires_postgres
class TestPostgresBackend:
    def test_init_schema_creates_tables(self, db: PostgresBackend):
        rows = db.fetchall(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name IN ('evaluated_opportunities', 'criterion_results', 'journal_entries')
            """
        )
        tables = {r["table_name"] for r in rows}
        assert tables == {"evaluated_opportunities", "criterion_results", "journal_entries"}

    def test_evaluated_opportunities_is_append_only(self, db: PostgresBackend):
        """Composite PK (id, evaluated_at): same id at a new evaluated_at inserts."""
        for ts, decision in (("2026-01-01T00:00:00+00:00", "emitted"), ("2026-01-01T01:00:00+00:00", "rejected")):
            db.execute(
                """
                INSERT INTO evaluated_opportunities (id, evaluated_at, symbol, timeframe, mode, strategy,
                    signal_type, direction, trend, final_decision, decision_reason, failed_criteria_count,
                    near_miss, data_complete, data_quality_notes, threshold_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("opp-1", ts, "EURUSD", "M15", "alert_only", "cti",
                 "pullback", "BUY", "uptrend", decision, "x", 0, 0, 1, "[]", "v1", ts),
            )
        rows = db.fetchall("SELECT * FROM evaluated_opportunities WHERE id = ?", ("opp-1",))
        assert len(rows) == 2
        assert {r["final_decision"] for r in rows} == {"emitted", "rejected"}

    def test_criterion_results_foreign_key(self, db: PostgresBackend):
        db.execute(
            """
            INSERT INTO evaluated_opportunities (id, evaluated_at, symbol, timeframe, mode, strategy,
                signal_type, direction, trend, final_decision, decision_reason, failed_criteria_count,
                near_miss, data_complete, data_quality_notes, threshold_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("opp-2", "2026-01-01T00:00:00+00:00", "GBPUSD", "M15", "alert_only", "cti",
             "pullback", "SELL", "downtrend", "emitted", "passed", 0, 0, 1, "[]", "v1", "2026-01-01T00:00:00+00:00"),
        )
        db.execute(
            """
            INSERT INTO criterion_results (opportunity_id, evaluated_at, criterion_name, layer,
                threshold_operator, required, blocked_signal, data_quality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("opp-2", "2026-01-01T00:00:00+00:00", "trend_aligned", "layer_1", "gte", 1, 0, "complete"),
        )
        rows = db.fetchall("SELECT * FROM criterion_results WHERE opportunity_id = ?", ("opp-2",))
        assert len(rows) == 1
        assert rows[0]["criterion_name"] == "trend_aligned"

    def test_fetchone_returns_none_when_empty(self, db: PostgresBackend):
        assert db.fetchone("SELECT * FROM evaluated_opportunities WHERE id = ?", ("nope",)) is None

    def test_execute_commits_standalone_write(self, db: PostgresBackend):
        """A bare execute() persists immediately (committed, not left in a txn)."""
        db.execute(
            """
            INSERT INTO evaluated_opportunities (id, evaluated_at, symbol, timeframe, mode, strategy,
                signal_type, direction, trend, final_decision, decision_reason, failed_criteria_count,
                near_miss, data_complete, data_quality_notes, threshold_version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("opp-commit", "2026-01-01T00:00:00+00:00", "EURUSD", "M15", "alert_only", "cti",
             "pullback", "BUY", "uptrend", "emitted", "passed", 0, 0, 1, "[]", "v1", "2026-01-01T00:00:00+00:00"),
        )
        # A separate connection only sees committed data.
        import psycopg
        other = psycopg.connect(TEST_DSN)
        try:
            with other.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM evaluated_opportunities WHERE id = %s", ("opp-commit",))
                count = cur.fetchone()[0]
        finally:
            other.close()
        assert count == 1

    def test_transaction_rollback_on_error(self, db: PostgresBackend):
        with pytest.raises(RuntimeError):
            with db.transaction():
                db.execute(
                    """
                    INSERT INTO evaluated_opportunities (id, evaluated_at, symbol, timeframe, mode, strategy,
                        signal_type, direction, trend, final_decision, decision_reason, failed_criteria_count,
                        near_miss, data_complete, data_quality_notes, threshold_version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("opp-rb", "2026-01-01T00:00:00+00:00", "USDJPY", "M15", "alert_only", "cti",
                     "pullback", "BUY", "uptrend", "emitted", "passed", 0, 0, 1, "[]", "v1", "2026-01-01T00:00:00+00:00"),
                )
                raise RuntimeError("rollback")
        assert db.fetchall("SELECT * FROM evaluated_opportunities WHERE id = ?", ("opp-rb",)) == []


class TestGetDbFactory:
    def test_get_db_requires_database_url(self, monkeypatch):
        """With no DSN, get_db() raises (no SQLite fallback)."""
        monkeypatch.setenv("TRADEGUMI_DATABASE_URL", "")
        close_db()
        with pytest.raises(Exception):
            get_db(database_url="")
        close_db()

    @requires_postgres
    def test_factory_returns_singleton(self):
        close_db()
        try:
            db1 = get_db(database_url=TEST_DSN)
            db2 = get_db(database_url=TEST_DSN)
            assert db1 is db2
            assert isinstance(db1, PostgresBackend)
        finally:
            close_db()
