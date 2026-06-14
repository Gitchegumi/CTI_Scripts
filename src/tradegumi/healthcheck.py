"""Healthcheck CLI for TradeGumi services.

Usage::

    python -m tradegumi.healthcheck worker

``worker`` mode reads the worker liveness heartbeat from Redis and exits 0 when
it is present and fresh, non-zero otherwise. The worker container has no public
HTTP port, so this is its docker healthcheck (see
specs/019-split-runtime-containers). Freshness is bounded by
``TRADEGUMI_WORKER_HEARTBEAT_STALE_SECONDS`` (default 150s), which must be >= the
worker's loop interval so a healthy worker is never reported stale.
"""
from __future__ import annotations

import os
import sys
import time


def check_worker() -> int:
    """Return 0 if the worker heartbeat is present and fresh, 1 otherwise."""
    from tradegumi.persistence.redis import get_heartbeat

    stale_after = int(os.getenv("TRADEGUMI_WORKER_HEARTBEAT_STALE_SECONDS", "150"))
    heartbeat = get_heartbeat()
    if not heartbeat or "ts" not in heartbeat:
        print("worker heartbeat missing")
        return 1
    try:
        age = time.time() - float(heartbeat["ts"])
    except (TypeError, ValueError):
        print("worker heartbeat malformed")
        return 1
    if age > stale_after:
        print(f"worker heartbeat stale ({age:.0f}s > {stale_after}s)")
        return 1
    print(f"worker heartbeat ok (age {age:.0f}s, loop {heartbeat.get('loop_count')})")
    return 0


def main(argv: list[str]) -> int:
    """Dispatch to the requested service healthcheck (default ``worker``)."""
    mode = argv[1] if len(argv) > 1 else "worker"
    if mode == "worker":
        return check_worker()
    print(f"unknown healthcheck mode: {mode}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
