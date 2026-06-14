"""Persistence layer for TradeGumi.

Postgres is the single source of truth for evaluated opportunities, criterion
results, and the signal journal.  There is no SQLite fallback — the app
requires a reachable Postgres configured via ``TRADEGUMI_DATABASE_URL``.

Connection management
---------------------
A single persistent connection per backend instance, sufficient for the
threaded API server model.  Switch to ``psycopg_pool.ConnectionPool`` if
multi-process usage is needed.
"""

from __future__ import annotations

import logging
import os
import threading
from contextlib import contextmanager
from typing import Any, Generator, Optional

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("TRADEGUMI_DATABASE_URL", "")


class PostgresBackend:
    """Postgres backend using psycopg3.

    Uses a single persistent connection per backend instance.  Standalone
    writes (``execute``/``executemany``) commit immediately; a ``transaction()``
    block defers the commit so a multi-statement unit of work stays atomic.
    """

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or DATABASE_URL or ""
        if not self.dsn:
            raise ValueError("Postgres backend requires TRADEGUMI_DATABASE_URL to be set")
        self._conn: Optional[Any] = None
        # RLock so transaction() can hold the lock while execute()/fetch run.
        self._lock = threading.RLock()
        self._txn_depth = 0
        try:
            import psycopg
            self._psycopg = psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for the Postgres backend") from exc

    def _get_conn(self) -> Any:
        with self._lock:
            if self._conn is None or self._conn.closed:
                self._conn = self._psycopg.connect(self.dsn)
            return self._conn

    def connect(self) -> Any:
        return self._get_conn()

    @staticmethod
    def _translate(sql: str) -> str:
        """Translate ?-style placeholders to psycopg %s.

        Literal ``%`` (e.g. in ``LIKE '%pullback%'``) is first escaped to ``%%``
        so psycopg does not mistake it for a placeholder, then ``?`` becomes
        ``%s``.  Keep SQL strings free of literal ``?`` inside string literals.
        """
        return sql.replace("%", "%%").replace("?", "%s")

    def init_schema(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluated_opportunities (
                    id TEXT NOT NULL,
                    evaluated_at TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    signal_type TEXT NOT NULL DEFAULT 'pullback',
                    direction TEXT NOT NULL,
                    trend TEXT NOT NULL,
                    final_decision TEXT NOT NULL,
                    decision_reason TEXT NOT NULL,
                    confidence REAL,
                    failed_criteria_count INTEGER NOT NULL,
                    near_miss INTEGER NOT NULL,
                    data_complete INTEGER NOT NULL,
                    data_quality_notes TEXT NOT NULL,
                    threshold_version TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    first_blocker TEXT,
                    all_blockers TEXT NOT NULL DEFAULT '[]',
                    blocking_layer TEXT,
                    trend_decision TEXT,
                    pipeline_state TEXT,
                    near_miss_reason TEXT,
                    threshold_version_unknown_reason TEXT,
                    usable_for_strategy_stats INTEGER,
                    stats_exclusion_reason TEXT,
                    volatility_shock_detected INTEGER NOT NULL DEFAULT 0,
                    shock_timeframe TEXT,
                    shock_candle_time TIMESTAMPTZ,
                    shock_true_range REAL,
                    shock_atr REAL,
                    shock_atr_multiple REAL,
                    shock_lookback_bars INTEGER NOT NULL DEFAULT 0,
                    shock_direction TEXT NOT NULL DEFAULT 'none',
                    shock_suppression_until TIMESTAMPTZ,
                    shock_suppression_candles_remaining INTEGER NOT NULL DEFAULT 0,
                    raw_lr_1h REAL,
                    raw_lr_15m REAL,
                    raw_lr_5m REAL,
                    filtered_lr_1h REAL,
                    filtered_lr_15m REAL,
                    filtered_lr_5m REAL,
                    trend_changed_after_filter INTEGER NOT NULL DEFAULT 0,
                    market_validity_state TEXT NOT NULL DEFAULT 'valid',
                    market_validity_reason TEXT,
                    PRIMARY KEY (id, evaluated_at)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS criterion_results (
                    id SERIAL PRIMARY KEY,
                    opportunity_id TEXT NOT NULL,
                    evaluated_at TIMESTAMPTZ NOT NULL,
                    criterion_name TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    measured_value TEXT,
                    threshold_value TEXT,
                    threshold_operator TEXT NOT NULL,
                    passed INTEGER,
                    expected_pass INTEGER,
                    pass_mismatch INTEGER NOT NULL DEFAULT 0,
                    margin REAL,
                    normalized_margin REAL,
                    required INTEGER NOT NULL,
                    blocked_signal INTEGER NOT NULL,
                    data_quality TEXT NOT NULL,
                    diagnostic_state TEXT NOT NULL DEFAULT 'evaluated',
                    reason TEXT,
                    context TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(opportunity_id, evaluated_at) REFERENCES evaluated_opportunities(id, evaluated_at) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_at ON evaluated_opportunities(evaluated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_symbol ON evaluated_opportunities(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_decision ON evaluated_opportunities(final_decision)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_symbol ON evaluated_opportunities(evaluated_at, symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_decision ON evaluated_opportunities(evaluated_at, final_decision)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_signal_type ON evaluated_opportunities(signal_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_first_blocker ON evaluated_opportunities(first_blocker)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_opp ON criterion_results(opportunity_id, evaluated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_name_opp ON criterion_results(criterion_name, opportunity_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id SERIAL PRIMARY KEY,
                    signal_id TEXT,
                    signal_timestamp TIMESTAMPTZ,
                    symbol TEXT,
                    direction TEXT,
                    strategy TEXT,
                    signal_type TEXT,
                    lifecycle_role TEXT,
                    grade TEXT,
                    grade_timestamp TIMESTAMPTZ,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    lot_size REAL,
                    atr REAL,
                    rr REAL,
                    confidence REAL,
                    notes TEXT,
                    discord_msg_id TEXT,
                    data JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_timestamp ON journal_entries(signal_timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_symbol ON journal_entries(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_grade ON journal_entries(grade)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_lifecycle ON journal_entries(lifecycle_role)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_direction ON journal_entries(direction)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_strategy ON journal_entries(strategy)")
            conn.commit()

    def execute(self, sql: str, params: Optional[tuple] = None):
        """Execute a write/DDL statement.  Commits unless inside a transaction()."""
        translated = self._translate(sql)
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(translated, params or ())
            if self._txn_depth == 0:
                conn.commit()
            return cur

    def executemany(self, sql: str, params: list[tuple]):
        translated = self._translate(sql)
        with self._lock:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.executemany(translated, params)
            if self._txn_depth == 0:
                conn.commit()

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> list[dict[str, Any]]:
        translated = self._translate(sql)
        with self._lock:
            conn = self._get_conn()
            with conn.cursor() as cur:
                cur.execute(translated, params or ())
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            # Close out the implicit read transaction so the shared connection
            # does not sit "idle in transaction" between requests.
            if self._txn_depth == 0:
                conn.commit()
            return rows

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[dict[str, Any]]:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    @contextmanager
    def transaction(self) -> Generator[Any, None, None]:
        with self._lock:
            conn = self._get_conn()
            self._txn_depth += 1
            try:
                yield conn
            except Exception:
                self._txn_depth -= 1
                if self._txn_depth == 0:
                    conn.rollback()
                raise
            else:
                self._txn_depth -= 1
                if self._txn_depth == 0:
                    conn.commit()

    def close(self) -> None:
        with self._lock:
            if self._conn and not self._conn.closed:
                self._conn.close()
                self._conn = None


# Backwards-compatible alias used in type hints across the codebase.
DBBackend = PostgresBackend


# ── Singleton factory ─────────────────────────────────────────────────────────

_backend_instance: Optional[PostgresBackend] = None
_backend_lock = threading.Lock()


def get_db(database_url: Optional[str] = None) -> PostgresBackend:
    """Return the Postgres persistence backend (singleton).

    Parameters
    ----------
    database_url:
        Override the connection DSN.  Used in tests.

    Raises
    ------
    ValueError / RuntimeError / psycopg errors if Postgres is not configured or
    not reachable.  There is no SQLite fallback.
    """
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance

    with _backend_lock:
        if _backend_instance is not None:
            return _backend_instance

        dsn = database_url or os.getenv("TRADEGUMI_DATABASE_URL", DATABASE_URL)
        backend = PostgresBackend(dsn=dsn)
        backend.init_schema()
        _backend_instance = backend
        try:
            log.info("Persistence backend: postgres (%s)", dsn.split("@")[-1].split("/")[0])
        except Exception:
            log.info("Persistence backend: postgres")
        return _backend_instance


def close_db() -> None:
    global _backend_instance
    with _backend_lock:
        if _backend_instance is not None:
            _backend_instance.close()
            _backend_instance = None
