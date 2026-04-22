#!/bin/bash
set -e

# ===========================================
# TradeGumi Entrypoint
# Manages both the Python bot and Next.js dashboard processes
# ===========================================

# Load .env into the environment so both the Python bot and Next.js
# server can read all configured variables at runtime.
if [ -f /app/.env ]; then
    set -a
    # shellcheck disable=SC1091
    source /app/.env
    set +a
    echo "[entrypoint] Loaded /app/.env"
fi

shutdown() {
    echo "[entrypoint] SIGTERM received, shutting down gracefully..."
    kill -TERM $BOT_PID $DASHBOARD_PID 2>/dev/null || true
    wait $BOT_PID 2>/dev/null || true
    wait $DASHBOARD_PID 2>/dev/null || true
    echo "[entrypoint] Shutdown complete"
    exit 0
}

trap shutdown SIGTERM SIGINT

# Start the bot process in background
echo "[entrypoint] Starting TradeGumi bot..."
cd /app
export PYTHONPATH=/app/src
poetry run python -m tradegumi.main &
BOT_PID=$!

# Start the dashboard process in background
echo "[entrypoint] Starting TradeGumi dashboard..."
cd /app/dashboard
PORT=3000 npm start &
DASHBOARD_PID=$!

echo "[entrypoint] Both processes started (bot=$BOT_PID, dashboard=$DASHBOARD_PID)"

# Wait for either process to exit
wait -n $BOT_PID $DASHBOARD_PID 2>/dev/null || true
EXIT_CODE=$?

echo "[entrypoint] A process exited (code=$EXIT_CODE), shutting down..."
kill $BOT_PID $DASHBOARD_PID 2>/dev/null || true
wait $BOT_PID 2>/dev/null || true
wait $DASHBOARD_PID 2>/dev/null || true
exit $EXIT_CODE