"""Shared Postgres test helpers.

The app is Postgres-only (no SQLite fallback), so DB-backed tests need a live
Postgres.  Point ``TRADEGUMI_TEST_DATABASE_URL`` at a throwaway database to run
them; without it the DB-backed tests skip.
"""

import os
from datetime import datetime, timezone

import pytest

TEST_DSN = os.getenv("TRADEGUMI_TEST_DATABASE_URL", "")

requires_postgres = pytest.mark.skipif(
    not TEST_DSN,
    reason="Set TRADEGUMI_TEST_DATABASE_URL to run Postgres-backed tests",
)

_shared_backend = None


def get_test_backend():
    """Return a shared Postgres backend with freshly truncated tables.

    Skips the calling test when no test DSN is configured.  Also disables the
    hourly retention auto-prune so record/read assertions stay deterministic.
    """
    if not TEST_DSN:
        pytest.skip("Set TRADEGUMI_TEST_DATABASE_URL to run Postgres-backed tests")

    global _shared_backend
    from tradegumi.persistence import PostgresBackend

    if (
        _shared_backend is None
        or _shared_backend._conn is None
        or getattr(_shared_backend._conn, "closed", False)
    ):
        _shared_backend = PostgresBackend(dsn=TEST_DSN)
        _shared_backend.init_schema()

    _shared_backend.execute(
        "TRUNCATE journal_entries, criterion_results, evaluated_opportunities RESTART IDENTITY CASCADE"
    )

    import tradegumi.strategy_metrics as sm
    sm._last_prune_at = datetime.now(timezone.utc)

    return _shared_backend
