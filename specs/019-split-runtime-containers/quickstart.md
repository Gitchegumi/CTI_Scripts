# Quickstart: Three-Service TradeGumi Runtime

How to build, run, and verify the split into **tradegumi-worker**,
**tradegumi-api**, and **tradegumi-dashboard**.

## Prerequisites

- Docker + docker-compose.
- A populated `.env` (see `.env.example`) including:
  - `TRADEGUMI_DATABASE_URL` (Postgres) and `TRADEGUMI_REDIS_URL` (Redis) — from #108.
  - Broker creds (used by the worker, and by the API for **read-only** account/positions).
  - `NEXT_PUBLIC_API_URL` for the dashboard (in compose, set to `http://tradegumi-api:8199`).
- Postgres/Redis come up as part of the compose stack (#108 already added them).

## Bring up the stack

```bash
docker compose up -d --build
docker compose ps          # expect: postgres, redis, tradegumi-worker, tradegumi-api, tradegumi-dashboard
```

Expected healthy state:
- `tradegumi-worker` — healthy via Redis heartbeat (no published port).
- `tradegumi-api` — healthy via `http://localhost:8199/api/status`.
- `tradegumi-dashboard` — healthy via port 3000; loads data through the API.

## Smoke test the data plane

```bash
# API serves runtime state read from Redis (worker must be publishing)
curl -s http://localhost:8199/api/status | jq .

# Issue a command through the API → worker should apply it (no restart)
curl -s -X POST http://localhost:8199/api/config/mode -d 'mode=alert_only'
# worker heartbeat should reflect the new mode within a loop cycle:
docker exec <redis> redis-cli GET tradegumi:heartbeat:worker
```

## Verify isolation (the whole point)

These map directly to the success criteria in `spec.md`.

> **Validation results**
> - **SC-001 — ✅ VERIFIED 2026-06-14** (US1 MVP, pre-US2 layout where the API
>   still runs in-thread with the worker in the `tradegumi` service): killing
>   `tradegumi-dashboard` left the worker trading with no errors in the docker
>   logs; `postgres`, `redis`, and `tradegumi` were unaffected.

```bash
# SC-001: kill the dashboard mid-loop; worker keeps trading, API stays up
docker compose kill tradegumi-dashboard
# worker heartbeat ts keeps advancing; API still returns 200:
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8199/api/status   # -> 200

# SC-002: kill the worker; API + dashboard still serve persisted analytics
docker compose kill tradegumi-worker
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8199/api/status   # -> 200
# dashboard renders Postgres-backed journal/metrics (no live worker required)

# SC-003: restart one service; the other two keep running (restart count unchanged)
docker compose restart tradegumi-api
docker compose ps          # worker + dashboard uptime not reset

# bring everything back
docker compose up -d
```

## Verify command durability (FR-010)

```bash
# Stop the worker, issue a config command, then start the worker:
docker compose stop tradegumi-worker
curl -s -X POST http://localhost:8199/api/config/mode -d 'mode=demo'   # API records desired_config
docker compose start tradegumi-worker
# On startup the worker reconciles desired_config and comes up in 'demo':
docker exec <redis> redis-cli GET tradegumi:desired_config
docker exec <redis> redis-cli GET tradegumi:heartbeat:worker           # mode == demo
```

## Local development (non-Docker)

```bash
# Worker only (loop, no API server thread anymore):
PYTHONPATH=src python -m tradegumi.main

# API only (separate process/entrypoint):
PYTHONPATH=src python -m tradegumi.api_main

# Dashboard:
cd dashboard && NEXT_PUBLIC_API_URL=http://localhost:8199 npm run dev
```

## Tests

```bash
cd src && poetry run pytest tradegumi/tests/test_commands.py \
                            tradegumi/tests/test_api_reads_redis.py -q
```

## Rollback

The pre-split combined container remains in git history. To revert, restore the
single `tradegumi` service in `docker-compose.yml`, the combined `Dockerfile`,
and `entrypoint.sh`, then `docker compose up -d --build`. No schema migration is
involved (no Postgres changes), so rollback is config/image-only.
