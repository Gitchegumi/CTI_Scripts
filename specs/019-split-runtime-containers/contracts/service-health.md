# Contract: Per-Service Health and Isolation

Satisfies FR-007 (each service reports only its own health) and FR-008 / FR-004
(isolated, non-cascading restarts).

## tradegumi-worker (no public HTTP port)

- **Liveness signal**: Redis key `tradegumi:heartbeat:worker`, refreshed once per
  loop iteration with `{ "ts": <epoch>, "loop_count": <int>, "mode": "<mode>" }`
  and a TTL of ~150s (≥2–3× the 60s loop interval, so the key never expires
  between refreshes — a shorter TTL than the loop interval would make health
  flap).
- **Docker healthcheck**: a small Python command that reads the heartbeat and
  exits non-zero if the key is missing or `ts` is older than a freshness
  threshold (recommend 2–3× the loop interval, e.g. 150s for a 60s loop).
- **Reflects only the worker**: heartbeat freshness depends solely on the worker
  loop cycling; it is independent of API or dashboard status.

Example healthcheck (compose):
```yaml
healthcheck:
  test: ["CMD", "python", "-m", "tradegumi.healthcheck", "worker"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

## tradegumi-api (HTTP 8199)

- **Docker healthcheck**: `curl -f http://localhost:8199/api/status` (the target
  already used by the current combined healthcheck).
- **Reflects only the API**: a `200` means the HTTP server is serving. The API's
  payload MAY include a `worker_live` flag derived from the worker heartbeat for
  the dashboard, but API health itself does not fail when the worker is down —
  that independence is the point (FR-002 / SC-002).

## tradegumi-dashboard (HTTP 3000)

- **Docker healthcheck**: HTTP check against the Next.js server root on port 3000.
- **Degraded state**: when `tradegumi-api` is unreachable, the dashboard renders
  a clear degraded/disconnected state rather than crashing or showing a blank
  page (spec edge case).

## Isolation requirements

- Each service sets `restart: unless-stopped` independently.
- There is **no** shared-process entrypoint (`wait -n` is removed); a crash in
  one container's main process restarts only that container.
- `depends_on` with `condition: service_healthy`: worker and api depend on
  Postgres + Redis healthy; dashboard depends on api healthy. Startup ordering is
  enforced, but a dependency restarting later MUST NOT force-restart an
  already-running dependent (verified by the isolation smoke test).

## Verification (maps to success criteria)

| Check | Success criterion |
| --- | --- |
| Kill dashboard mid-loop → worker keeps cycling (heartbeat ts keeps advancing), API still `200` | SC-001 |
| Kill worker → API still `200` and serves Postgres-backed analytics; dashboard renders persisted data | SC-002 |
| Restart any one service → other two stay up (no restart count increment) | SC-003 |
| Single-service failure → only that service's health goes red | SC-004 |
