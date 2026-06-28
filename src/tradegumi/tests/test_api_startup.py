"""Startup fail-fast test: the API refuses to start without Postgres (US3)."""

import pytest


def test_main_fails_fast_when_postgres_unreachable(monkeypatch):
    """`api_main.main()` must raise before Uvicorn serves if Postgres is down."""
    from tradegumi import api_main

    monkeypatch.setattr("tradegumi.config.validate_config", lambda: None)

    def unreachable():
        raise ConnectionError("could not connect to postgres")
    monkeypatch.setattr("tradegumi.persistence.get_db", unreachable)

    # If the fail-fast check is bypassed, this sentinel would be reached and the
    # test would fail with a clearer message than a hung server.
    def should_not_run(*a, **k):
        raise AssertionError("Uvicorn started despite Postgres being unreachable")
    monkeypatch.setattr("uvicorn.run", should_not_run)

    with pytest.raises(ConnectionError):
        api_main.main()
