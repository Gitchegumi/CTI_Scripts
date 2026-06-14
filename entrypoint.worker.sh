#!/bin/bash
set -e

# ===========================================
# TradeGumi worker entrypoint
# Runs ONLY the trading loop (market data, scanning, signals, alerts, metrics).
# No dashboard, no public HTTP port. A crash here restarts only this container.
# ===========================================

# Load .env so the worker reads all configured variables at runtime.
if [ -f /app/.env ]; then
    set -a
    # shellcheck disable=SC1091
    source /app/.env
    set +a
    echo "[worker] Loaded /app/.env"
fi

cd /app
export PYTHONPATH=/app/src

# exec so the Python process is PID 1 and receives SIGTERM directly for the
# graceful shutdown handler in tradegumi.main.
echo "[worker] Starting TradeGumi worker loop..."
exec poetry run python -m tradegumi.main "$@"
