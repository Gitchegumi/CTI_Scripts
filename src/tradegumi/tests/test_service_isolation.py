"""Tests for per-service health detection (specs/019-split-runtime-containers US3).

The worker has no HTTP port, so its liveness is the freshness of a Redis
heartbeat. These unit tests cover the heartbeat-based health logic used by both
the worker's docker healthcheck (``tradegumi.healthcheck``) and the API's
``worker_live`` flag. The container-level restart-isolation behaviour
(SC-003/SC-004) is verified on a live stack (task T026 / quickstart.md).
"""
import time

import tradegumi.api.deps as api_server
import tradegumi.healthcheck as healthcheck


def _patch_heartbeat(monkeypatch, value):
    monkeypatch.setattr("tradegumi.persistence.redis.get_heartbeat", lambda: value)


def test_healthcheck_fresh_heartbeat_passes(monkeypatch):
    _patch_heartbeat(monkeypatch, {"ts": time.time(), "loop_count": 5, "mode": "demo"})
    assert healthcheck.check_worker() == 0


def test_healthcheck_missing_heartbeat_fails(monkeypatch):
    _patch_heartbeat(monkeypatch, None)
    assert healthcheck.check_worker() == 1


def test_healthcheck_stale_heartbeat_fails(monkeypatch):
    monkeypatch.setenv("TRADEGUMI_WORKER_HEARTBEAT_STALE_SECONDS", "150")
    _patch_heartbeat(monkeypatch, {"ts": time.time() - 600, "loop_count": 5})
    assert healthcheck.check_worker() == 1


def test_healthcheck_malformed_heartbeat_fails(monkeypatch):
    _patch_heartbeat(monkeypatch, {"ts": "not-a-number"})
    assert healthcheck.check_worker() == 1


def test_unknown_healthcheck_mode_returns_2():
    assert healthcheck.main(["healthcheck", "bogus"]) == 2


def test_worker_live_true_when_fresh(monkeypatch):
    _patch_heartbeat(monkeypatch, {"ts": time.time(), "loop_count": 1})
    assert api_server.worker_live() is True


def test_worker_live_false_when_missing(monkeypatch):
    _patch_heartbeat(monkeypatch, None)
    assert api_server.worker_live() is False


def test_worker_live_false_when_stale(monkeypatch):
    monkeypatch.setenv("TRADEGUMI_WORKER_HEARTBEAT_STALE_SECONDS", "150")
    _patch_heartbeat(monkeypatch, {"ts": time.time() - 600})
    assert api_server.worker_live() is False


def test_worker_live_false_when_redis_raises(monkeypatch):
    def _boom():
        raise RuntimeError("redis down")

    monkeypatch.setattr("tradegumi.persistence.redis.get_heartbeat", _boom)
    assert api_server.worker_live() is False
