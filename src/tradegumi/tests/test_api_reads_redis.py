"""Tests for the standalone API process reading worker state cross-process.

After the runtime split (specs/019-split-runtime-containers), the API runs in a
separate process from the worker. It must:

- serve runtime status from the worker's Redis ``loop_state`` snapshot when there
  is no in-process state (the worker populates state in a different process), and
- use its own read-only execution client (never the worker's live client, which
  does not exist in the API process), built lazily from config.

These are unit tests of that logic — no live Redis/Postgres/broker required.
After the FastAPI migration (specs/023-fastapi-api-migration) the cross-process
state helpers live in ``tradegumi.api.deps``; this module is aliased as
``api_server`` below so the behavioral assertions stay unchanged.
"""
import tradegumi.api.deps as api_server


def _reset_state():
    """Clear module-level state the accessors cache between tests."""
    with api_server._runtime_lock:
        api_server._runtime_state.clear()
    api_server._api_client = None


def test_runtime_state_prefers_in_process(monkeypatch):
    """When the worker populated in-process state, Redis is not consulted."""
    _reset_state()

    def _boom():  # pragma: no cover - must never be called
        raise AssertionError("Redis must not be read when in-process state exists")

    monkeypatch.setattr("tradegumi.persistence.redis.get_cache", _boom)
    api_server.set_runtime_state({"running": True, "loop_count": 7})

    state = api_server.get_runtime_state()
    assert state["running"] is True
    assert state["loop_count"] == 7
    _reset_state()


def test_runtime_state_falls_back_to_redis(monkeypatch):
    """With no in-process state (API process), read the worker's Redis snapshot."""
    _reset_state()

    snapshot = {"running": True, "loop_count": 42, "loop_state": {"symbols": []}}

    class _FakeCache:
        def get(self, key):
            assert key == "loop_state"
            return snapshot

    monkeypatch.setattr("tradegumi.persistence.redis.get_cache", lambda: _FakeCache())

    state = api_server.get_runtime_state()
    assert state["loop_count"] == 42
    assert state["loop_state"] == {"symbols": []}
    _reset_state()


def test_runtime_state_empty_when_redis_unavailable(monkeypatch):
    """A Redis outage degrades to an empty dict, never an exception."""
    _reset_state()

    class _DeadCache:
        def get(self, key):
            raise RuntimeError("redis down")

    monkeypatch.setattr("tradegumi.persistence.redis.get_cache", lambda: _DeadCache())

    assert api_server.get_runtime_state() == {}
    _reset_state()


def test_execution_client_prefers_worker_live_client(monkeypatch):
    """In the combined/worker process, the shared live client wins."""
    _reset_state()
    sentinel = object()
    api_server.set_runtime_state({"client": sentinel})

    assert api_server.get_api_execution_client() is sentinel
    _reset_state()


def test_execution_client_built_readonly_when_no_worker(monkeypatch):
    """In the API process (no shared client), build one lazily from config."""
    _reset_state()

    # No in-process state and no snapshot client.
    monkeypatch.setattr("tradegumi.persistence.redis.get_cache", lambda: type("C", (), {"get": lambda self, k: None})())

    built = []

    class _FakeOanda:
        def __init__(self):
            built.append(self)

    monkeypatch.setattr(api_server.config, "TRADEGUMI_MODE", "alert_only")
    monkeypatch.setattr("tradegumi.api.oanda_client.OandaClient", _FakeOanda)

    client = api_server.get_api_execution_client()
    assert isinstance(client, _FakeOanda)
    # Cached: a second call returns the same instance, not a new build.
    assert api_server.get_api_execution_client() is client
    assert len(built) == 1
    _reset_state()


def test_execution_client_none_when_build_fails(monkeypatch):
    """If the client cannot be built (e.g. missing creds), return None for a 503."""
    _reset_state()
    monkeypatch.setattr("tradegumi.persistence.redis.get_cache", lambda: type("C", (), {"get": lambda self, k: None})())

    class _Broken:
        def __init__(self):
            raise RuntimeError("no creds")

    monkeypatch.setattr(api_server.config, "TRADEGUMI_MODE", "alert_only")
    monkeypatch.setattr("tradegumi.api.oanda_client.OandaClient", _Broken)

    assert api_server.get_api_execution_client() is None
    _reset_state()
