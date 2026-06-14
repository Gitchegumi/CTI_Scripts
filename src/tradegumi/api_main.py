"""Standalone entrypoint for the TradeGumi API service.

Runs only the HTTP API server (analytics + control). The trading worker runs in
a separate process/container; this process serves:

- hot runtime status from the worker's Redis ``loop_state`` snapshot,
- file-based state (watchlist/signals/loop_state) from the shared data volume
  (mounted read-only),
- durable analytics (journal, strategy metrics) directly from Postgres,
- account/positions/trade-history from its own **read-only** execution client.

It never runs the trading loop and never places orders — order placement is
worker-only (Constitution III, Risk-First). See
specs/019-split-runtime-containers.
"""
from __future__ import annotations

import logging as log
import signal
import sys
import time
from pathlib import Path
from types import FrameType
from typing import Optional

# Make the tradegumi package importable when run as ``python -m tradegumi.api_main``.
sys.path.insert(0, str(Path(__file__).parent.parent))

from tradegumi import config
from tradegumi.api_server import API_PORT, start_api_server


def _setup_logging(level: str = "INFO") -> None:
    """Configure logging to match the worker's format for consistent output."""
    log.basicConfig(
        level=getattr(log, level.upper(), log.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Start the API server and run until SIGTERM/SIGINT.

    Fails fast if Postgres is unreachable, since serving analytics is the API's
    primary responsibility. Redis and the broker are optional at startup: the
    API degrades (stale/empty hot state, ``503`` on account endpoints) rather
    than refusing to start, so analytics stay available during partial outages.
    """
    _setup_logging()
    config.validate_config()

    try:
        from tradegumi.persistence import get_db
        get_db()
        log.info("API: connected to Postgres persistence backend")
    except Exception as exc:
        log.error("API: cannot reach Postgres via TRADEGUMI_DATABASE_URL: %s", exc)
        raise

    server = start_api_server()
    log.info("API service listening on port %d", API_PORT)

    stopping = {"flag": False}

    def _shutdown(signum: int, _frame: Optional[FrameType]) -> None:
        log.info("API: signal %s received, shutting down", signum)
        stopping["flag"] = True

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        while not stopping["flag"]:
            time.sleep(1)
    finally:
        server.shutdown()
        log.info("API: stopped")


if __name__ == "__main__":
    main()
