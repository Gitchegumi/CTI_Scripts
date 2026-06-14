#!/bin/bash
set -e

# ===========================================
# TradeGumi API entrypoint
# Runs ONLY the HTTP API server (analytics + control on port 8199).
# Reads hot state from Redis and durable analytics from Postgres.
#
# NOTE: this is inert until the standalone API entrypoint module
# (tradegumi.api_main) exists — added in user story US2 of
# specs/019-split-runtime-containers. Until then the API still runs in-process
# with the worker.
# ===========================================

# Load .env so the API reads all configured variables at runtime.
if [ -f /app/.env ]; then
    set -a
    # shellcheck disable=SC1091
    source /app/.env
    set +a
    echo "[api] Loaded /app/.env"
fi

cd /app
export PYTHONPATH=/app/src

echo "[api] Starting TradeGumi API server..."
exec poetry run python -m tradegumi.api_main "$@"
