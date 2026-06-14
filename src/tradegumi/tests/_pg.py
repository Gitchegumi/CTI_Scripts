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


def get_test_backend():
    """Return the application Postgres backend, pointed at the test database.

    Uses the process-wide ``get_db()`` singleton (so app-internal calls such as
    the signal journal's reads/writes hit the same database the test inspects),
    pointed at ``TRADEGUMI_TEST_DATABASE_URL`` and with all tables truncated for
    a clean slate.  Skips the calling test when no test DSN is configured.  Also
    disables the hourly retention auto-prune so record/read assertions stay
    deterministic.
    """
    if not TEST_DSN:
        pytest.skip("Set TRADEGUMI_TEST_DATABASE_URL to run Postgres-backed tests")

    # Ensure the app's no-arg get_db() (used inside journal/strategy_metrics)
    # resolves to the throwaway test database, never a real one.
    os.environ["TRADEGUMI_DATABASE_URL"] = TEST_DSN
    from tradegumi.persistence import get_db

    db = get_db(database_url=TEST_DSN)
    db.execute(
        "TRUNCATE journal_entries, criterion_results, evaluated_opportunities RESTART IDENTITY CASCADE"
    )

    import tradegumi.strategy_metrics as sm
    sm._last_prune_at = datetime.now(timezone.utc)

    return db
