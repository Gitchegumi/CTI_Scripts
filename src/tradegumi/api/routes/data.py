"""Data router — file/state reads and latest prices.

Serves the worker-produced state files from the read-only data volume (or the
runtime snapshot) and the latest price observations. All endpoints are open
(no auth) and degrade to the previous default-empty payloads when a file is
absent.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request

from tradegumi import config
from tradegumi.api.deps import DATA_DIR, get_runtime_state, query_param

router = APIRouter()


@router.get("/api/data/loop_state")
def get_loop_state() -> dict:
    """Return the worker's loop_state snapshot, else the file, else a default."""
    runtime_loop_state = get_runtime_state().get("loop_state")
    if runtime_loop_state is not None:
        return runtime_loop_state
    f = DATA_DIR / "loop_state.json"
    if f.exists():
        return json.loads(f.read_text())
    return {"symbols": [], "mode": config.TRADEGUMI_MODE, "provider": "Oanda"}


@router.get("/api/data/watchlist")
def get_watchlist() -> dict:
    """Return the watchlist file, else the default empty tier structure."""
    f = DATA_DIR / "watchlist.json"
    if f.exists():
        return json.loads(f.read_text())
    return {"tier1": [], "tier2": [], "below": [], "ranked": []}


@router.get("/api/data/signals")
def get_signals():
    """Return the signals file, else an empty list."""
    f = DATA_DIR / "signals.json"
    if f.exists():
        return json.loads(f.read_text())
    return []


@router.get("/api/data/trade_correlations")
def get_trade_correlations():
    """Return the trade-correlations file, else an empty list (tolerates bad JSON)."""
    f = DATA_DIR / "trade_correlations.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
    return []


@router.get("/api/prices")
def get_prices(request: Request):
    """Return the latest price observations for the requested symbols."""
    from tradegumi.price_observations import DEFAULT_PRICE_HISTORY
    symbols = [
        s.strip().upper()
        for s in (query_param(request, "symbols") or "").split(",")
        if s.strip()
    ]
    observations = (
        DEFAULT_PRICE_HISTORY.latest_many(symbols).values() if symbols else []
    )
    return [observation.to_dict() for observation in observations]
