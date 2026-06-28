# Quickstart: FastAPI TradeGumi API Service

**Feature**: 023-fastapi-api-migration
**Date**: 2026-06-28

How to run, exercise, and validate the rebuilt API service locally. Commands run
from the repo root unless noted. The external contract is unchanged — port 8199,
the same `/api/*` paths, and the same `entrypoint.api.sh`.

## Prerequisites

- Python 3.13 + Poetry (project uses `src/pyproject.toml`).
- Running Postgres (required — the API fails fast without it) and Redis
  (optional — degrades if absent). Easiest via `docker compose up postgres redis`.
- `.env` populated (see `.env.example`). No new secret is required for the
  FastAPI migration.

## Install dependencies

```bash
cd src
poetry install            # installs fastapi + uvicorn (main) and httpx + pytest (dev)
```

## Run the API locally

The module entrypoint is unchanged; it now boots Uvicorn internally:

```bash
# from repo root
export PYTHONPATH=src
cd src && poetry run python -m tradegumi.api_main
# API listens on http://localhost:8199 (TRADEGUMI_API_PORT to override)
```

In Docker (unchanged):

```bash
docker compose up tradegumi-api    # entrypoint.api.sh → python -m tradegumi.api_main
```

## Smoke-test the endpoints

```bash
# Health / status (also the compose healthcheck)
curl -s http://localhost:8199/api/status | jq .

# New: interactive docs + schema (FR-020)
open http://localhost:8199/docs           # Swagger UI
curl -s http://localhost:8199/openapi.json | jq '.info'

# An open analytics endpoint
curl -s "http://localhost:8199/api/strategy-metrics/summary?start=2026-06-01&end=2026-06-28" | jq .

# A protected endpoint (401 without the key when JOURNAL_TOKEN is set)
curl -i http://localhost:8199/api/trades/manual
curl -i -H "X-API-Key: $JOURNAL_TOKEN" http://localhost:8199/api/trades/manual

# A control action (accepted → command_id; 503 if the command channel is down)
curl -s -X POST http://localhost:8199/api/config/mode \
  -H 'Content-Type: application/json' -d '{"mode":"demo"}' | jq .
```

## Validate parity / behavior

```bash
cd src
poetry run pytest tradegumi/tests/test_api_*.py -q       # parity, auth, command-channel suites
poetry run pytest -q                                      # full suite
```

Manual degradation checks:

- **Fail-fast**: stop Postgres, start the API → it must exit/refuse to serve.
- **Degrade**: stop Redis, start the API (Postgres up) → `/api/strategy-metrics/*`
  and `/api/data/journal` still serve; `/api/status` reports `worker_live:false`.
- **Broker down**: with no broker creds, `/api/positions` and
  `/api/trades/history` return `503 {"error":"client not available"}` while
  analytics keep serving.

## What changed for developers

- Routes now live in `src/tradegumi/api/routes/<concern>.py`; the app factory is
  `src/tradegumi/api_app.py` (`create_app()`); shared dependencies are in
  `src/tradegumi/api/deps.py`.
- Add an endpoint by editing only its concern's router and reusing existing
  dependencies — no monolithic handler to touch.
- `src/tradegumi/api_server.py` is removed after cutover.

## Verification checklist (maps to Success Criteria)

- [ ] All endpoints in `contracts/api-endpoints.md` return matching status + parsed structure (SC-001/002).
- [ ] No order-placement route exists; broker access is read-only (SC-004).
- [ ] Postgres-up / Redis+broker-down → analytics, journal, metrics still serve (SC-005).
- [ ] Postgres-down at startup → service refuses to start (SC-006).
- [ ] `pytest` parity/auth/command-channel suites pass (SC-007).
- [ ] `/docs`, `/redoc`, `/openapi.json` reachable; `/api/*` behavior unchanged (FR-020).
