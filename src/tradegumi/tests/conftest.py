"""Pytest fixtures shared across the tradegumi test suite."""

import pytest

from tradegumi.tests._pg import get_test_backend


@pytest.fixture
def pg_backend():
    """Function-scoped Postgres backend with truncated tables (skips without a DSN)."""
    yield get_test_backend()


@pytest.fixture
def api_app():
    """A fresh FastAPI app instance for the TradeGumi API service."""
    from tradegumi.api_app import create_app
    return create_app()


@pytest.fixture
def client(api_app):
    """TestClient bound to a fresh API app (hermetic; deps patched per-test)."""
    from fastapi.testclient import TestClient
    with TestClient(api_app) as test_client:
        yield test_client


@pytest.fixture
def no_auth(monkeypatch):
    """Disable API-key auth by clearing JOURNAL_TOKEN (default for most tests)."""
    monkeypatch.setattr("tradegumi.config.JOURNAL_TOKEN", "", raising=False)


@pytest.fixture
def with_token(monkeypatch):
    """Enable API-key auth with a known token; returns the token string."""
    token = "test-token"
    monkeypatch.setattr("tradegumi.config.JOURNAL_TOKEN", token, raising=False)
    return token
