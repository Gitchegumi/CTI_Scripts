"""Status router — `/api/status`.

Serves the merged current configuration plus the worker's runtime snapshot,
including worker liveness from the heartbeat. Open (no auth).
"""
from __future__ import annotations

from fastapi import APIRouter

from tradegumi import config
from tradegumi.api.deps import get_runtime_state, worker_live

router = APIRouter()


@router.get("/api/status")
def get_status() -> dict:
    """Return current config + runtime state for the dashboard.

    The worker owns config post-split; it publishes a ``config`` block in the
    runtime snapshot, so the API mirrors the worker's live config (a config
    command applied by the worker is reflected here on its next snapshot). Falls
    back to local config in the combined process / tests. ``worker_live`` comes
    from the heartbeat (FR-007); hot fields degrade to defaults when the
    snapshot is stale/absent.
    """
    state = get_runtime_state()
    cfg = state.get("config") or {}
    default_tiers = (
        config.CTI_CHALLENGE_TIERS
        if config.CTI_CHALLENGE_TYPE != "instant"
        else config.CTI_INSTANT_TIERS
    )
    return {
        "mode": cfg.get("mode", config.TRADEGUMI_MODE),
        "challenge_type": cfg.get("challenge_type", config.CTI_CHALLENGE_TYPE),
        "program": cfg.get("program", config.CTI_PROGRAM),
        "phase": cfg.get("phase", config.CTI_PHASE),
        "daily_loss_pct": cfg.get("daily_loss_pct", config.CTI_DAILY_LOSS_PCT),
        "max_dd_pct": cfg.get("max_dd_pct", config.CTI_MAX_DD_PCT),
        "running": state.get("running", False),
        "worker_live": worker_live(),
        "loop_count": state.get("loop_count", 0),
        "last_signal_time": state.get("last_signal_time"),
        "market_data": state.get("market_data"),
        "tiers": cfg.get("tiers", default_tiers),
    }
