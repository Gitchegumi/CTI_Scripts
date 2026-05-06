# Implementation Plan: Repair DB-backed page performance and restore signal pipeline progression

**Branch**: `007-repair-db-signals` | **Date**: 2026-05-06 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/007-repair-db-signals/spec.md`

## Summary

Repair DB-backed dashboard and journal pages so normal local/dev page loads no longer take 5+ seconds, while restoring signal-pipeline progression so trend-valid, closed-candle candidates reach signal rule evaluation. The technical approach is to profile the existing backend and dashboard data paths, apply focused query/loading/index fixes that preserve response shape, add practical performance measurements, and repair signal data preparation plus M5 candle-close gate timing with deterministic tests.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; TypeScript/React 19 with Next.js 16.2.4 under `dashboard/`  
**Primary Dependencies**: Python stdlib `sqlite3`, pandas/numpy/TA indicator stack, pytest; Next.js route handlers and browser fetch components  
**Storage**: SQLite databases in `src/tradegumi/data/strategy_metrics.db` and `src/tradegumi/data/manual_trades.db`, dashboard JSON/state files where already used  
**Testing**: pytest for backend and signal behavior; dashboard `npm run lint`/targeted build checks where frontend files change  
**Target Platform**: Local operator dashboard and Docker-hosted TradeGumi service  
**Project Type**: Python trading backend plus Next.js dashboard frontend  
**Performance Goals**: DB-backed pages under normal local/dev data volume no longer take 5+ seconds; optimized endpoints should have repeatable local timing evidence  
**Constraints**: Preserve API response shape and visible behavior unless documented; do not loosen thresholds; diagnostics must not break the signal pipeline; use timezone-aware deterministic candle handling  
**Scale/Scope**: DB-backed strategy metrics, signal journal, manual trade journal, dashboard trade history, related API endpoints, and signal pipeline stages from trend-valid candidate through rule evaluation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Repairs progression through existing layers without bypassing thresholds or forcing signals. |
| II. Execution Layer Abstraction | PASS | Work remains in dashboard, persistence, diagnostics, and broker-agnostic signal modules. |
| III. Risk-First | PASS | No order placement, position sizing, drawdown, or execution-risk behavior is changed. |
| IV. Observable by Default | PASS | Adds timing evidence and improves missing-data/gate diagnostics while keeping JSON/dashboard observability. |
| V. Configuration-Driven Operations | PASS | No hardcoded strategy tuning or operational mode change is planned. |
| Security & Credential Hygiene | PASS | No new secrets or credential logging; performance logs must avoid raw sensitive payloads. |
| Code Quality & Documentation | PASS | New/modified Python helpers require intention-revealing names, useful docstrings, and focused tests. |
| Pull Request Policy | PASS | `tasks.md` must end with submitting a PR with DockeGumi as reviewer. |

No gates failed. No complexity violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/007-repair-db-signals/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- dashboard-db-pages.md
|   `-- signal-pipeline.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- api_server.py                    # inspect related backend endpoint behavior
|-- database.py                      # inspect SQLite/session/query helpers and indexes
|-- journal.py                       # inspect signal journal persistence/export paths
|-- manual_trades.py                 # inspect manual trade journal queries and stats
|-- signal_engine.py                 # repair signal data preparation and candle gate logic
|-- signal_processor.py              # inspect trend -> signal engine orchestration
|-- strategy_metrics.py              # optimize metrics storage/export/summary diagnostics
|-- tests/
|   |-- test_strategy_metrics.py     # extend diagnostics/performance behavior coverage
|   `-- test_*.py                    # add focused signal/manual trade tests as appropriate

dashboard/src/
|-- app/
|   |-- api/journal/route.ts
|   |-- api/manual-trades/[[...id]]/route.ts
|   |-- api/manual-trades/stats/route.ts
|   |-- api/strategy-metrics/*/route.ts
|   |-- api/trades/history/route.ts
|   |-- journal/page.tsx
|   |-- manual-trades/page.tsx
|   `-- strategy-metrics/page.tsx
|-- components/TradeHistory.tsx
|-- hooks/useData.ts
`-- lib/api.ts

tests/tradegumi/
`-- test_database.py                 # extend DB/index/query behavior coverage if practical

docs/
|-- signal-journal.md
`-- strategy-metrics.md
```

**Structure Decision**: Keep changes inside existing Python backend modules, Next dashboard routes/pages/components, and current docs/tests. Do not introduce a new service, replacement ORM, or broad dashboard rewrite.

## Affected Backend Modules

- `src/tradegumi/strategy_metrics.py`: metrics persistence/export/summary, signal diagnostic fields, query aggregation, and any SQLite index/migration helpers.
- `src/tradegumi/journal.py`: signal journal reads/writes/export and dashboard-backed journal data paths.
- `src/tradegumi/manual_trades.py`: manual trade history/stats reads and bounded result behavior.
- `src/tradegumi/database.py`: shared SQLite connection/session helpers, schema/index setup, and query timing instrumentation if centralized.
- `src/tradegumi/api_server.py`: backend API paths if dashboard routes proxy to the Python service.
- `src/tradegumi/signal_engine.py`: signal data preparation, last closed candle/window selection, candle-close gate, and diagnostics.
- `src/tradegumi/signal_processor.py` and `src/tradegumi/decision_engine.py`: trend-valid candidate progression into the signal engine and diagnostic recording.

## Affected Frontend Pages/Components

- `dashboard/src/app/strategy-metrics/page.tsx` and `dashboard/src/app/api/strategy-metrics/*/route.ts`
- `dashboard/src/app/journal/page.tsx` and `dashboard/src/app/api/journal/*/route.ts`
- `dashboard/src/app/manual-trades/page.tsx` and `dashboard/src/app/api/manual-trades/*/route.ts`
- `dashboard/src/components/TradeHistory.tsx` and `dashboard/src/app/api/trades/history/route.ts`
- `dashboard/src/hooks/useData.ts` and `dashboard/src/lib/api.ts` for shared fetch/waterfall behavior.

## Database Query/Index Strategy

- Measure page/API latency first with lightweight timers around candidate slow reads.
- Inspect query plans and table schemas for metrics, journals, manual trades, and trade history.
- Add additive indexes for common filters/orderings such as timestamp/date, symbol, decision/outcome/status, and history sort keys where query plans show scans.
- Bound default result sets through existing filters, pagination, or date windows while preserving response shape.
- Avoid N+1 patterns and repeated serialization by batching reads and computing summaries once per request where possible.
- Keep migrations/schema setup idempotent for existing local SQLite files.

## Signal Pipeline Modules To Inspect

- Trend candidate creation and handoff in `signal_processor.py`/`decision_engine.py`.
- Signal stack data preparation in `signal_engine.py`.
- Candle and indicator window generation in `signal_engine.py` and `indicators.py`.
- M5 close gate logic, timezone conversion, and timeframe boundary calculations.
- Diagnostic recording in `strategy_metrics.py`, including `signal_engine_data` versus legacy `singal_engine_data` spelling.
- Metrics summary/export aggregation for `total_evaluated`, `signal_rules_evaluated`, `signal_emitted`, incomplete counts, and gate pass/fail counts.

## Test Strategy

- Add backend regression tests for insufficient candles, exactly enough candles, last closed candle selection, M5 before/exact/after close gate behavior, and full trend-valid path reaching signal rule evaluation.
- Add metrics tests proving diagnostics remain accurate and do not raise when data is incomplete.
- Add DB/query tests where practical for bounded results, index/schema setup, and response correctness.
- Add dashboard route/page tests only if existing tooling supports them cheaply; otherwise verify with `npm run lint` and targeted manual/local timing steps.
- Preserve existing strategy threshold expectations; tests should fail if thresholds are loosened.

## Rollback Risk

- Performance changes are mostly additive indexes, bounded queries, and reduced duplicate loads, with low rollback risk if response shapes stay stable.
- Signal pipeline repairs have higher behavioral impact because rule evaluation may resume; rollback should be possible by reverting the focused signal data/gate helpers without touching thresholds or execution code.
- Any schema/index change must be idempotent and compatible with existing SQLite files.
- New diagnostics must be additive or backward-compatible so dashboard exports remain consumable.

## Performance Measurement Strategy

- Capture baseline timings for strategy metrics summary/opportunities/export, signal journal, manual trade stats/history, and dashboard trade history before changing queries.
- Use lightweight per-endpoint or per-query timing logs only around suspected slow paths.
- Use local SQLite query plans for the slowest queries before and after index/query changes.
- Record before/after timings in `quickstart.md`, implementation notes, or final report with the exact commands or page paths used.
- Confirm the optimized DB-backed pages no longer take 5+ seconds under normal local/dev data volume.

## Phase 0: Research

See [research.md](research.md) for decisions and alternatives.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for entities, constraints, and state transitions.

See [contracts/dashboard-db-pages.md](contracts/dashboard-db-pages.md) and [contracts/signal-pipeline.md](contracts/signal-pipeline.md) for response and pipeline contracts.

See [quickstart.md](quickstart.md) for local validation and measurement steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design requires reaching rule evaluation only after valid trend, complete data, and closed candle; thresholds remain intact. |
| II. Execution Layer Abstraction | PASS | Contracts do not add broker-specific signal logic or execution dependencies. |
| III. Risk-First | PASS | Signal evaluation may resume, but risk and execution gates are not bypassed or modified. |
| IV. Observable by Default | PASS | Design improves timing and pipeline observability while preserving diagnostic exports. |
| V. Configuration-Driven Operations | PASS | No non-configurable strategy parameters are introduced. |
| Security & Credential Hygiene | PASS | Diagnostics and performance logs avoid secrets and raw credential-bearing payloads. |
| Code Quality & Documentation | PASS | Plan and tasks require docstrings for modified Python helpers and focused regression tests. |
| Pull Request Policy | PASS | Final generated task must submit a PR with DockeGumi as reviewer. |

No post-design gates failed.
