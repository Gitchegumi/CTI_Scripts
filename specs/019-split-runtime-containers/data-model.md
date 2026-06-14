# Phase 1 Data Model: Split Runtime into API, Dashboard, and Worker Containers

This feature is an architectural split, not a new domain feature, so it adds **no
new Postgres tables**. The durable schema from #108 (`evaluated_opportunities`,
`criterion_results`, `journal_entries`) is unchanged and remains the analytics
source of truth read by the API service.

What this feature *does* introduce is the **cross-process data plane on Redis**:
the keys and channels that replace what was previously shared in-memory between
the worker loop and the API thread. All Redis keys use the existing
`tradegumi:` prefix applied by `RedisCache._key`.

## Redis keys — worker → API (state snapshots, one-way)

These already exist or follow the existing snapshot pattern; the change is that
the **API now reads them** instead of in-process `get_runtime_state()`.

| Key (after prefix) | Producer | Consumer | TTL | Shape |
| --- | --- | --- | --- | --- |
| `tradegumi:loop_state` | worker | API | 10s | JSON-safe runtime snapshot (loop_count, mode, program, phase, market state, last loop timing) — **never** includes the live `client` |
| `tradegumi:latest_prices` | worker | API | 10s | `{symbol: price}` map of most recent observed prices |
| `tradegumi:watchlist` | worker | API | 300s | Current ranked watchlist with tiers/scores |
| `tradegumi:active_signals` | worker | API | 300s | Currently active/open signals snapshot |
| `tradegumi:strategy_summary:<filters>` | API | API | 60s | Cached strategy summary (existing) |

**Staleness contract**: if `loop_state` is missing/expired when the API reads it,
the API treats the worker as "not currently publishing" and reports a degraded
state (rather than serving stale data as if live).

## Redis keys/channels — API → worker (commands)

New. Pairs a fast pub/sub channel with a durable desired-config key so commands
issued while the worker is briefly down are not lost (FR-005, FR-010).

| Name (after prefix) | Type | Producer | Consumer | Purpose |
| --- | --- | --- | --- | --- |
| `tradegumi:commands` | pub/sub channel | API | worker | Low-latency command delivery (mode/program/phase/challenge_type change, rescan) |
| `tradegumi:desired_config` | key (no TTL) | API | worker | Last-write-wins desired config; worker reconciles against it on each loop and at startup |
| `tradegumi:command_ack:<command_id>` | key | worker | API (optional) | Short-TTL acknowledgement so the API can confirm a command was applied |

## Redis key — worker health (heartbeat)

| Key (after prefix) | Producer | Consumer | TTL | Shape |
| --- | --- | --- | --- | --- |
| `tradegumi:heartbeat:worker` | worker | docker healthcheck + API | ~150s (≥2–3× the 60s loop; refreshed each loop) | `{ "ts": <epoch>, "loop_count": <int>, "mode": "<mode>" }` |

**Health contract**: the worker's docker healthcheck reads
`tradegumi:heartbeat:worker` and fails if the key is missing or its `ts` is older
than a freshness threshold (e.g. 2–3× the loop interval, ~150s for a 60s loop).
The key TTL MUST be ≥ that threshold so the heartbeat never expires between the
worker's once-per-loop refreshes (otherwise health flaps). The API may surface the
same key as "worker live/stale" for the dashboard.

## Entities (conceptual)

### Command message

A single operator instruction created by the API and consumed by the worker.

| Field | Type | Notes |
| --- | --- | --- |
| `command_id` | string (uuid) | Idempotency / ack correlation |
| `type` | enum | `set_mode` \| `set_program` \| `set_phase` \| `set_challenge_type` \| `rescan` |
| `payload` | object | Type-specific (e.g. `{ "mode": "demo" }`); empty for `rescan` |
| `issued_at` | ISO-8601 | When the API accepted the request |
| `source` | string | e.g. `dashboard`, `api` |

Validation:
- `type` MUST be one of the known command types; unknown types are rejected at
  the API with `400` (never published).
- Config-changing commands MUST carry a valid value for their dimension
  (e.g. `mode ∈ {alert_only, demo, live}`), validated at the API boundary.
- `rescan` is idempotent and carries no payload.

State transitions (config commands):
`accepted (API)` → `published (Redis)` + `desired_config updated` →
`consumed (worker)` → `applied (worker runtime + heartbeat reflects new mode)` →
`acked (optional)`.

### Worker heartbeat

Liveness record proving the worker loop is cycling. Produced once per loop
iteration; absence/staleness = unhealthy. Not durable (Redis TTL only).

### Runtime snapshot

The JSON-safe projection of worker state for the API/dashboard. Already produced
by `set_runtime_state`; the contract is that it excludes any non-serializable
live object (notably the execution `client`).

## Service boundary summary

| Service | Inbound | Reads | Writes | Live broker client |
| --- | --- | --- | --- | --- |
| **tradegumi-worker** | none (no public port) | `desired_config`, `commands`, Postgres | `loop_state`/`watchlist`/`active_signals`/`heartbeat` (Redis), Postgres analytics | yes — **read + order placement** (only place orders happen) |
| **tradegumi-api** | HTTP 8199 | `loop_state`/`watchlist`/`active_signals` (Redis), Postgres analytics | `commands`/`desired_config` (Redis), strategy summary cache | yes — **read-only** (positions/account/trade history); never places orders |
| **tradegumi-dashboard** | HTTP 3000 | tradegumi-api over `NEXT_PUBLIC_API_URL` | — | no |
