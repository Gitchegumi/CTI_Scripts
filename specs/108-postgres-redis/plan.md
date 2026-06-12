# Implementation Plan: Postgres + Redis Migration

**Branch**: `issue/108-postgres-redis` | **Date**: 2026-06-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/108-postgres-redis/spec.md`

## Summary

Add Postgres and Redis services to the TradeGumi deployment, create a persistence abstraction layer, migrate strategy metrics and signal journal from SQLite/JSONL to Postgres-backed storage, use Redis for hot runtime state and summary caching, and update the dashboard/API layer to read from the new stores while keeping SQLite as a fallback.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js dashboard under `dashboard/`  
**Primary Dependencies**: psycopg3 (postgres), redis-py (redis); existing SQLite3, pandas, numpy, ta-lib, discord.py  
**Storage**: SQLite (`strategy_metrics.db`, `manual_trades.db`), JSONL (`signal_journal.jsonl`) → Postgres (`tradegumi` db); Redis for cache  
**Testing**: pytest in `src/tradegumi/tests/`; dashboard checks via `npm run lint` and `npm run build` when UI/types change  
**Target Platform**: Docker Compose deployment; local dev fallback via SQLite  
**Project Type**: Python trading signal backend + Next.js dashboard  
**Performance Goals**: Strategy metrics queries < 500ms for 30-day ranges; Redis cache hit < 10ms; journal export < 2s for 1,000 rows  
**Constraints**: Do not remove SQLite path (keep as fallback); do not break existing JSONL audit trail; preserve all existing API response shapes; no hardcoded connection strings; all new deps added to `pyproject.toml`; migrations must be idempotent  

## Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | No signal logic touched |
| II. Execution Layer Abstraction | PASS | No broker execution changes |
| III. Risk-First | PASS | No risk/order logic touched |
| IV. Observable by Default | PASS | All data paths remain observable; Redis only accelerates reads |
| V. Configuration-Driven | PASS | DB backend + URLs driven by env vars |
| Security & Credential Hygiene | PASS | DB credentials via env vars; no secrets in code |
| Pull Request Policy | PASS | Reviewer `Gitchegumi` already assigned on PR #110 |

## Project Structure

```text
CTI_Scripts/
├── docker-compose.yml                          # + postgres, redis
├── Dockerfile                                  # unchanged
├── .env.example                                # + DB/Redis env vars
├── src/pyproject.toml                           # + psycopg3, redis
├── src/tradegumi/
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── base.py                             # Backend enum, DB abstract base
│   │   ├── postgres.py                         # Postgres connection + schema
│   │   ├── sqlite.py                           # SQLite compatibility shim
│   │   ├── migrations/
│   │   │   ├── __init__.py
│   │   │   ├── 001_strategy_metrics.sql
│   │   │   └── 002_signal_journal.sql
│   │   └── redis.py                            # Redis cache helpers
│   ├── strategy_metrics.py                     # updated to use persistence layer
│   ├── journal.py                              # updated to use persistence layer
│   ├── api_server.py                           # updated to prefer persistence
│   └── config.py                               # + DB/Redis env vars
└── specs/108-postgres-redis/
    ├── spec.md
    ├── plan.md
    └── README.md
```

## Execution Order

### Phase 1: Infrastructure
1. Update `docker-compose.yml` with postgres + redis services
2. Add env vars to `.env.example`
3. Add `psycopg`, `redis` to `pyproject.toml`

### Phase 2: Persistence Layer
4. Create `src/tradegumi/persistence/` package
5. Implement base abstraction (`Backend`, `DBInterface`)
6. Implement Postgres backend with schema creation
7. Implement SQLite fallback shim (thin wrapper over existing code)
8. Implement Redis cache helpers

### Phase 3: Schema & Migrations
9. Write migration `001_strategy_metrics.sql` (evaluated_opportunities, criterion_results + indexes)
10. Write migration `002_signal_journal.sql` (journal_entries + indexes)

### Phase 4: Migrate Application Code
11. Update `strategy_metrics.py` to use persistence layer
12. Update `journal.py` to use persistence layer
13. Update `api_server.py` to prefer persistence reads

### Phase 5: Dashboard / API
14. Ensure dashboard proxy routes remain unchanged (they call the same API shapes)
15. Add Redis-backed status/runtime state caching

### Phase 6: Validation & Docs
16. Update `README.md` with new architecture
17. Run existing tests to ensure no regressions
18. PR review with Gitchegumi
