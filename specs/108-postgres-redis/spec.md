# Feature Specification: Postgres + Redis Migration

**Feature Branch**: `issue/108-postgres-redis` | **Created**: 2026-06-12  
**Status**: In Progress  
**Input**: GitHub issue #108

## Problem

TradeGumi is outgrowing the current local-file persistence model. Strategy metrics are now relational analytics data, not just debug output. The bot/dashboard currently relies on a mix of SQLite, JSON snapshots, and append-only JSONL journal data. That is workable for early development, but it will become increasingly slow and fragile as the evaluated opportunity count, signal journal, manual trades, and dashboard usage grow.

## Goal

Implement both Postgres and Redis together with clear separation of responsibilities:

- **Postgres**: durable source of truth for queryable trading/strategy history.
- **Redis**: fast operational cache for hot runtime state and dashboard reads.

## Architecture

```text
TradeGumi bot/API/dashboard
   |
   |-- Postgres
   |     - evaluated opportunities
   |     - criterion results
   |     - signal journal entries
   |     - manual trades
   |     - trade outcomes
   |     - export/reporting queries
   |
   |-- Redis
         - latest loop state
         - latest prices
         - active signals
         - watchlist snapshot
         - short-lived strategy summary cache
         - optional pub/sub for future live dashboard updates
```

## Scope

### 1. Add infrastructure services

Update local/container deployment to include:

- `postgres` service
- `redis` service
- persistent Postgres volume
- Redis configuration appropriate for cache/runtime state
- healthchecks for both services
- environment variables for connection settings

Suggested env vars:

```env
TRADEGUMI_DATABASE_URL=postgresql://tradegumi:***@postgres:5432/tradegumi
TRADEGUMI_REDIS_URL=redis://redis:6379/0
```

> **Update:** the SQLite fallback was dropped. Postgres is required; there is no
> `TRADEGUMI_DB_BACKEND` / `TRADEGUMI_SQLITE_FALLBACK` toggle.

### 2. Add a persistence layer

Create a database access layer so the application is not hardwired directly to file paths.

Requirements:

- Postgres is the single source of truth — no SQLite fallback.
- Add Postgres support as the primary service deployment path.
- Avoid scattering raw connection logic across the codebase.
- Add migrations for Postgres schema creation.
- Preserve existing data model semantics where possible.

### 3. Move Strategy Metrics to Postgres

Migrate the current strategy metrics tables into Postgres:

- `evaluated_opportunities`
- `criterion_results`

Keep indexes for the main dashboard/query patterns:

- date range
- symbol
- final decision
- signal type
- first blocker
- criterion name
- opportunity ID

### 4. Move the Signal Journal into Postgres

> **Reconciled decision:** Postgres `journal_entries` is the authoritative store
> for the signal journal. Every application read (`read_journal`, exports, the
> strategy-metrics journal aggregations, and the append/grade/management logic)
> reads from Postgres, and every mutation (append, grade, purge) persists to
> Postgres. The append-only `signal_journal.jsonl` file is legacy: it is kept as
> a best-effort export/backup snapshot and can be imported into a fresh database
> with `backfill_from_jsonl`, but the application never reads it for queries.

Provide a Postgres-backed `journal_entries` table that supports:

- filtering by date range
- symbol
- signal type
- lifecycle role
- grade/status/outcome
- prime suppression fields
- managed lifecycle fields
- export generation

### 5. Use Redis for hot runtime state

Redis should cache runtime/dashboard state, not replace durable storage.

Suggested Redis keys/TTLs:

```text
loop_state                    TTL 5-10 sec
latest_prices                 TTL 5-10 sec
watchlist                     TTL 5-30 min
active_signals                TTL 1-5 min
strategy_summary:<filters>    TTL 30-120 sec
```

Redis can also support pub/sub later, but that should not be required for the initial implementation.

### 6. Update API/dashboard reads

Dashboard/API routes should prefer:

1. Redis for hot runtime state and short-lived cached summaries.
2. Postgres for durable historical data (single source of truth).

## Acceptance Criteria

- [ ] `docker-compose.yml` includes working Postgres and Redis services.
- [ ] Application can connect to Postgres and Redis using env vars.
- [ ] Strategy metrics can be written to Postgres.
- [ ] Strategy metrics summary/opportunity queries can read from Postgres.
- [ ] Signal journal records are mirrored into a queryable Postgres `journal_entries` table.
- [ ] Signal journal source of truth is reconciled: JSONL remains authoritative; Postgres is a best-effort mirror kept consistent across append/grade/purge.
- [ ] Redis stores latest runtime/dashboard state.
- [ ] Redis caches expensive strategy summary responses using filter-aware cache keys.
- [ ] Postgres is required; the SQLite path/fallback is removed.
- [ ] Existing dashboard/API behavior remains functional after migration.
- [ ] README/deployment docs are updated with the new architecture and env vars.
