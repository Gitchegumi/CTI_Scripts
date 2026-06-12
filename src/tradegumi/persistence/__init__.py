"""Persistence abstraction layer for TradeGumi.

Provides a unified interface over SQLite (fallback) and Postgres (primary)
with minimal overhead.  The factory returns a concrete backend based on
TRADEGUMI_DB_BACKEND env var.

Connection management
---------------------
- SQLite: single persistent connection per backend instance
- Postgres: single persistent connection per backend instance (sufficient
  for the threaded API server model; add psycopg_pool if multi-process)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

log = logging.getLogger(__name__)

BACKEND = os.getenv("TRADEGUMI_DB_BACKEND", "sqlite").lower()
DATABASE_URL = os.getenv("TRADEGUMI_DATABASE_URL", "")
SQLITE_FALLBACK = os.getenv("TRADEGUMI_SQLITE_FALLBACK", "true").lower() in ("true", "1", "yes")

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class DBBackend(ABC):
    """Abstract database backend."""

    @abstractmethod
    def init_schema(self) -> None:
        """Ensure all tables and indexes exist."""

    @abstractmethod
    def connect(self) -> Any:
        """Return a raw connection object for direct use."""

    @abstractmethod
    def execute(self, sql: str, params: Optional[tuple] = None) -> Any:
        """Execute a single statement.  Returns the rowcount (or None)."""

    @abstractmethod
    def executemany(self, sql: str, params: list[tuple]) -> Any:
        """Execute a statement multiple times."""

    @abstractmethod
    def fetchall(self, sql: str, params: Optional[tuple] = None) -> list[dict[str, Any]]:
        """Run SELECT and return rows as dicts."""

    @abstractmethod
    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[dict[str, Any]]:
        """Run SELECT and return a single row as dict, or None."""

    @abstractmethod
    def transaction(self) -> Any:
        """Context manager for a transaction block."""

    @abstractmethod
    def close(self) -> None:
        """Release any pooled or persistent connections."""


class SQLiteBackend(DBBackend):
    """SQLite backend — thin wrapper over sqlite3 with dict rows."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (DATA_DIR / "tradegumi.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def connect(self):
        return self._get_conn()

    def init_schema(self) -> None:
        with self._lock:
            conn = self._get_conn()
            # Strategy metrics tables
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluated_opportunities (
                    id TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
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
                    created_at TEXT NOT NULL,
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
                    shock_candle_time TEXT,
                    shock_true_range REAL,
                    shock_atr REAL,
                    shock_atr_multiple REAL,
                    shock_lookback_bars INTEGER NOT NULL DEFAULT 0,
                    shock_direction TEXT NOT NULL DEFAULT 'none',
                    shock_suppression_until TEXT,
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
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    opportunity_id TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
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
                    FOREIGN KEY(opportunity_id, evaluated_at) REFERENCES evaluated_opportunities(id, evaluated_at)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_at ON evaluated_opportunities(evaluated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_symbol ON evaluated_opportunities(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_decision ON evaluated_opportunities(final_decision)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_symbol ON evaluated_opportunities(evaluated_at, symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_decision ON evaluated_opportunities(evaluated_at, final_decision)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_opp ON criterion_results(opportunity_id, evaluated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_name_opp ON criterion_results(criterion_name, opportunity_id)")
            # Journal table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_id TEXT UNIQUE NOT NULL,
                    signal_timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    strategy TEXT,
                    signal_type TEXT,
                    lifecycle_role TEXT,
                    grade TEXT,
                    grade_timestamp TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    lot_size REAL,
                    atr REAL,
                    rr REAL,
                    confidence REAL,
                    notes TEXT,
                    discord_msg_id TEXT,
                    data TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_timestamp ON journal_entries(signal_timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_symbol ON journal_entries(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_grade ON journal_entries(grade)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_lifecycle ON journal_entries(lifecycle_role)")
            conn.commit()

    def execute(self, sql: str, params: Optional[tuple] = None):
        with self._lock:
            conn = self._get_conn()
            return conn.execute(sql, params or ())

    def executemany(self, sql: str, params: list[tuple]):
        with self._lock:
            conn = self._get_conn()
            return conn.executemany(sql, params)

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> list[dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(sql, params or ())
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        with self._lock:
            conn = self._get_conn()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None


class PostgresBackend(DBBackend):
    """Postgres backend using psycopg3.

    Uses a single persistent connection per backend instance.
    If multi-process usage is needed, switch to psycopg_pool.ConnectionPool.
    """

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or DATABASE_URL or ""
        if not self.dsn:
            raise ValueError("Postgres backend requested but TRADEGUMI_DATABASE_URL is not set")
        self._conn: Optional[Any] = None
        self._lock = threading.Lock()
        try:
            import psycopg
            self._psycopg = psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg is required for Postgres backend") from exc

    def _get_conn(self) -> Any:
        with self._lock:
            if self._conn is None or self._conn.closed:
                self._conn = self._psycopg.connect(self.dsn)
            return self._conn

    def connect(self) -> Any:
        return self._get_conn()

    def _translate(self, sql: str) -> str:
        """Translate SQLite-style ? placeholders to psycopg %s."""
        # Naive replacement — safe for our controlled SQL.  If literal ?
        # appears in string literals this will break; keep SQL in code.
        return sql.replace("?", "%s")

    def init_schema(self) -> None:
        with self._lock:
            conn = self._get_conn()
            # Use idempotent CREATE TABLE ... IF NOT EXISTS
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
            # Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_at ON evaluated_opportunities(evaluated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_symbol ON evaluated_opportunities(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_decision ON evaluated_opportunities(final_decision)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_symbol ON evaluated_opportunities(evaluated_at, symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_eval_decision ON evaluated_opportunities(evaluated_at, final_decision)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_signal_type ON evaluated_opportunities(signal_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_first_blocker ON evaluated_opportunities(first_blocker)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_opp ON criterion_results(opportunity_id, evaluated_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_strategy_metrics_criteria_name_opp ON criterion_results(criterion_name, opportunity_id)")
            # Journal table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id SERIAL PRIMARY KEY,
                    signal_id TEXT UNIQUE NOT NULL,
                    signal_timestamp TIMESTAMPTZ NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
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
                    created_at TIMESTAMPTZ NOT NULL
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
        """Execute SQL and return the cursor (caller should consume and close)."""
        conn = self._get_conn()
        translated = self._translate(sql)
        return conn.execute(translated, params or ())

    def executemany(self, sql: str, params: list[tuple]):
        conn = self._get_conn()
        translated = self._translate(sql)
        with conn.cursor() as cur:
            cur.executemany(translated, params)
        conn.commit()

    def fetchall(self, sql: str, params: Optional[tuple] = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        translated = self._translate(sql)
        with conn.cursor() as cur:
            cur.execute(translated, params or ())
            columns = [desc[0] for desc in cur.description] if cur.description else []
            return [dict(zip(columns, row)) for row in cur.fetchall()]

    def fetchone(self, sql: str, params: Optional[tuple] = None) -> Optional[dict[str, Any]]:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    @contextmanager
    def transaction(self) -> Generator[Any, None, None]:
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close(self) -> None:
        with self._lock:
            if self._conn and not self._conn.closed:
                self._conn.close()
                self._conn = None


# ── Singleton factory ─────────────────────────────────────────────────────────

_backend_instance: Optional[DBBackend] = None
_backend_lock = threading.Lock()


def get_db(backend: Optional[str] = None, database_url: Optional[str] = None) -> DBBackend:
    """Return the configured persistence backend (singleton).

    Parameters
    ----------
    backend:
        Override the backend type ("sqlite" | "postgres").  Used in tests.
    database_url:
        Override the connection DSN.  Used in tests.
    """
    global _backend_instance
    if _backend_instance is not None:
        return _backend_instance

    with _backend_lock:
        # Double-checked locking
        if _backend_instance is not None:
            return _backend_instance

        chosen = (backend or os.getenv("TRADEGUMI_DB_BACKEND", BACKEND)).lower()
        if chosen == "postgres":
            try:
                dsn = database_url or os.getenv("TRADEGUMI_DATABASE_URL", DATABASE_URL)
                _backend_instance = PostgresBackend(dsn=dsn)
                log.info("Persistence backend: postgres (%s)", dsn.split("@")[-1].split("/")[0])
            except Exception as exc:
                log.warning("Failed to initialise Postgres backend (%s); falling back to SQLite", exc)
                fallback = os.getenv("TRADEGUMI_SQLITE_FALLBACK", "true" if SQLITE_FALLBACK else "false").lower() in ("true", "1", "yes")
                if not fallback:
                    raise
                _backend_instance = SQLiteBackend()
        else:
            _backend_instance = SQLiteBackend()
            log.info("Persistence backend: sqlite (%s)", _backend_instance.db_path)

        # Ensure schema is ready on first use
        _backend_instance.init_schema()
        return _backend_instance


def close_db() -> None:
    global _backend_instance
    with _backend_lock:
        if _backend_instance is not None:
            _backend_instance.close()
            _backend_instance = None
