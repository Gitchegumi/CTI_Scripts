"""Shared dependencies and runtime helpers for the FastAPI TradeGumi API.

This module is the single source of truth for the cross-cutting concerns the
API routes depend on:

- the cross-process **runtime state** bridge (in-process snapshot + the
  worker's Redis ``loop_state`` snapshot),
- a **read-only** execution client for account/positions/history reads,
- the worker **liveness** check derived from the Redis heartbeat,
- FastAPI dependency providers for the Postgres backend, the read-only
  execution client, and ``X-API-Key`` authentication.

Order placement is intentionally absent here and MUST NOT be added: order
placement is worker-only (Constitution III, Risk-First). The API only ever
builds clients for reads. These helpers were migrated verbatim-in-intent from
the previous ``tradegumi.api_server`` stdlib handler so behavior is preserved
across the framework change (see specs/023-fastapi-api-migration).
"""
from __future__ import annotations

import json
import logging as log
import os
import threading
import time as _time
from pathlib import Path
from typing import Any, Optional

from fastapi import Header, HTTPException, Request

from tradegumi import config

# Shared data volume (worker-produced state files, mounted read-only in the API
# container) and the public API port. Kept here so both the app factory and the
# routes import them from one place.
DATA_DIR = Path(__file__).parent.parent / "data"
API_PORT = int(os.getenv("TRADEGUMI_API_PORT", "8199"))

# ── Shared runtime state (set from main.py in the combined/worker process) ──
_runtime_state: dict = {}
_runtime_lock = threading.Lock()


def _json_safe_state(state: dict) -> dict:
    """Return the JSON-serializable subset of the runtime state.

    Live objects such as the execution client are dropped — they cannot be
    serialized and must never round-trip through Redis (a stringified client
    would break callers that expect the real object).
    """
    safe: dict = {}
    for key, value in state.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            continue
        safe[key] = value
    return safe


def set_runtime_state(state: dict) -> None:
    """Share the current runtime state (called from the worker's main loop).

    The authoritative copy is the in-process ``_runtime_state`` (it retains live
    objects like the execution client). Redis receives a JSON-safe snapshot of
    the *full merged* state for cross-process observability of the dashboard
    view, never just the partial update.
    """
    with _runtime_lock:
        _runtime_state.update(state)
        snapshot = _json_safe_state(_runtime_state)
    try:
        from tradegumi.persistence.redis import get_cache
        get_cache().set("loop_state", snapshot, ttl=10)
    except Exception as exc:
        log.debug("Redis runtime state cache update failed: %s", exc)


def get_runtime_state() -> dict:
    """Return the current runtime state, degrading gracefully when absent.

    In the combined/worker process the authoritative copy is the in-process
    ``_runtime_state`` (it retains live objects like the execution client), so
    that is returned when present.

    In the standalone API process the worker runs in a different process and
    never populates ``_runtime_state``; there we fall back to the JSON-safe
    snapshot the worker publishes to Redis under ``loop_state``. That snapshot
    intentionally lacks live objects (e.g. ``client``) — the API uses its own
    read-only client via :func:`get_api_execution_client`. Returns ``{}`` when
    neither source is available so callers degrade gracefully.
    """
    with _runtime_lock:
        if _runtime_state:
            return dict(_runtime_state)
    try:
        from tradegumi.persistence.redis import get_cache
        snapshot = get_cache().get("loop_state")
        if isinstance(snapshot, dict):
            return snapshot
    except Exception as exc:
        log.debug("Redis runtime-state read failed: %s", exc)
    return {}


# ── Read-only execution client for the standalone API process ──────────────
_api_client: Optional[Any] = None
_api_client_lock = threading.Lock()


def get_api_execution_client():
    """Return an execution client for the API's READ-ONLY endpoints.

    Prefers the worker's live client when running in the combined/worker process
    (shared via ``_runtime_state``). In the standalone API process there is no
    shared client, so one is built lazily from config and used solely for reads
    (``get_open_positions``, account info, ``get_trade_history``).

    The API exposes no order-placement route and MUST NOT place orders — order
    placement remains worker-only (Constitution III, Risk-First). Returns
    ``None`` when a client cannot be built so callers return ``503`` rather than
    crashing (e.g. broker creds absent in the API service).
    """
    live = get_runtime_state().get("client")
    if live is not None:
        return live
    global _api_client
    if _api_client is not None:
        return _api_client
    with _api_client_lock:
        if _api_client is None:
            try:
                if config.TRADEGUMI_MODE == "live":
                    from tradegumi.api.matchtrader_client import MatchTraderClient
                    _api_client = MatchTraderClient()
                else:
                    from tradegumi.api.oanda_client import OandaClient
                    _api_client = OandaClient()
            except Exception as exc:
                log.warning("API: could not build read-only execution client: %s", exc)
                return None
    return _api_client


def worker_live() -> bool:
    """Return True if the worker's Redis heartbeat is present and fresh.

    Lets the dashboard show worker connectivity without coupling API health to
    the worker — the API stays up and serving even when the worker is down.
    Freshness uses the same threshold as the worker's docker healthcheck. Any
    error (e.g. Redis down) reports not-live rather than raising.
    """
    try:
        from tradegumi.persistence.redis import get_heartbeat
        heartbeat = get_heartbeat()
        if not heartbeat or "ts" not in heartbeat:
            return False
        stale_after = int(os.getenv("TRADEGUMI_WORKER_HEARTBEAT_STALE_SECONDS", "150"))
        return (_time.time() - float(heartbeat["ts"])) <= stale_after
    except Exception:
        return False


def source_trade_history(count: int = 1000) -> list:
    """Return broker/source trade history when a runtime client is available.

    Reads are clamped to a safe range and broker failures degrade to an empty
    list (the dashboard still renders local manual trades). Never places orders.
    """
    client = get_api_execution_client()
    if not client:
        return []
    safe_count = max(1, min(int(count or 50), 500))
    try:
        return client.get_trade_history(count=safe_count)
    except Exception as e:
        log.warning("API: could not load source trade history: %s", e)
        return []


# ── FastAPI dependency providers ───────────────────────────────────────────


def get_db_dep():
    """FastAPI dependency returning the durable Postgres backend.

    Raises whatever ``get_db`` raises; routes that call durable analytics wrap
    their own try/except to map errors to the legacy 400/500 envelopes.
    """
    from tradegumi.persistence import get_db
    return get_db()


def get_execution_client_dep():
    """FastAPI dependency returning the read-only execution client or ``None``.

    Never raises — a ``None`` result lets broker-backed routes return ``503``
    ``{"error": "client not available"}`` while unrelated endpoints keep
    serving (graceful degradation, FR-010).
    """
    return get_api_execution_client()


def query_param(request: Request, name: str) -> Optional[str]:
    """Return a query-string value, treating missing/empty as ``None``.

    Mirrors the previous handler's ``_get_query_param`` (which dropped blank
    values), so downstream ``or None`` checks behave identically.
    """
    value = request.query_params.get(name)
    return value if value else None


async def read_json_body(request: Request) -> dict:
    """Parse a JSON request body leniently, returning ``{}`` on empty/invalid.

    Reproduces ``_read_body``: an empty body or malformed JSON yields ``{}`` so
    control endpoints surface their own ``400`` validation messages rather than
    raising. Non-object JSON also degrades to ``{}`` since callers expect a dict.
    """
    try:
        raw = await request.body()
        if not raw:
            return {}
        parsed = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def require_auth(x_api_key: str = Header(default="")) -> None:
    """FastAPI dependency enforcing the ``X-API-Key`` header.

    Compares the header against ``config.JOURNAL_TOKEN``. When the token is not
    configured, authentication is disabled (no-op), matching the previous
    handler. On mismatch, raises ``HTTPException(401)`` whose body is shaped as
    ``{"error": "Unauthorized"}`` by the app's exception handler (parity with
    the stdlib server, FR-011).
    """
    expected = config.JOURNAL_TOKEN
    if not expected:
        return
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
