"""Pytest fixtures shared across the tradegumi test suite."""

import pytest

from tradegumi.tests._pg import get_test_backend


@pytest.fixture
def pg_backend():
    """Function-scoped Postgres backend with truncated tables (skips without a DSN)."""
    yield get_test_backend()
