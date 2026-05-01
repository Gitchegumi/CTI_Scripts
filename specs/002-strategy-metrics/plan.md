# Implementation Plan: Strategy Metrics

**Branch**: `002-strategy-metrics` | **Date**: 2026-05-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-strategy-metrics/spec.md`

## Summary

Add diagnostic capture for every evaluated strategy opportunity so no-signal periods can be reviewed quantitatively. The implementation will preserve existing signal behavior, record criterion-level pass/fail/margin data locally, expose date-range summaries and opportunity drill-downs through the existing backend/dashboard pattern, and add a dashboard view for no-signal analysis, blocker ranking, and period comparison.

The core technical change is to split "evaluate opportunity" from "emit signal": the signal engine will produce structured diagnostics for trend, mandatory criteria, optional confirmation, confidence, cooldown, risk-block, and final decision, while only emitted signals continue through the existing alert/execution path.

Diagnostic records are written to SQLite for queryable history and to a compact JSON state file for constitution-required dashboard observability. Per-loop rejected diagnostic samples are not posted individually to Discord to avoid alert spam; emitted signals, risk-blocked actionable candidates, engine errors, and periodic no-signal diagnostic summaries remain observable through existing alert/log paths.

## Technical Context

**Language/Version**: Python 3.11 signal engine; TypeScript / Next.js 14+ dashboard  
**Primary Dependencies**: pandas and local indicator helpers for strategy evaluation; Python stdlib HTTP server for backend API; React and existing dashboard fetch hooks for UI  
**Storage**: SQLite diagnostic store under `src/tradegumi/data/` with optional JSON summary export for dashboard-friendly snapshots  
**Testing**: pytest for Python diagnostic capture/aggregation; dashboard currently has no dedicated test runner, so validation is via typecheck/lint where available plus quickstart manual checks  
**Target Platform**: Docker-hosted TradeGumi service plus authenticated web dashboard  
**Project Type**: Web application with Python trading backend and Next.js frontend  
**Performance Goals**: Add less than 100 ms per evaluated symbol on the 5-second signal loop; dashboard summaries load in under 2 seconds for 90 days of single-user diagnostic history  
**Constraints**: Existing signal firing, risk checks, and execution behavior must not change; no external database; retain at least 90 days of diagnostic data; no automatic strategy threshold changes; credentials remain in `.env` only  
**Scale/Scope**: Single operator, configured watchlist symbols, 5-second evaluation cadence, 90 days of local diagnostic history

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Diagnostic capture is additive. A signal still fires only when existing required layers, confidence, cooldown, and risk checks pass. |
| II. Execution Layer Abstraction | PASS | Diagnostics use the existing `ExecutionClient`-supplied candle/position data and do not import broker-specific clients into signal logic. |
| III. Risk-First | PASS | Risk checks remain mandatory before execution. Risk-blocked candidates are recorded as blocked diagnostics, not allowed through. |
| IV. Observable by Default | PASS | Evaluated opportunities and blockers are written to SQLite and a compact JSON state file; emitted signals, risk-blocked actionable candidates, engine errors, and periodic no-signal summaries remain visible through existing alert/log paths. |
| V. Configuration-Driven | PASS | Metric retention and any diagnostic display limits should be configurable without changing strategy code. Strategy thresholds are only reported, not changed. |
| Security & Credential Hygiene | PASS | No new secrets. Dashboard APIs reuse existing auth patterns. |
| Pull Request Policy | PENDING | Generated task list must include "Submit PR with DockeGumi as reviewer" as the final task. |

No gates failed. No complexity violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/002-strategy-metrics/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- strategy-metrics-api.md
|   `-- dashboard-ui.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- signal_engine.py              # UPDATE: return structured diagnostics alongside Signal
|-- main.py                       # UPDATE: persist diagnostics for every evaluated symbol
|-- strategy_metrics.py           # NEW: SQLite storage, aggregation, retention pruning
|-- data/
|   `-- strategy_metrics.json     # NEW: compact latest diagnostics state for dashboard visibility
|-- api_server.py                 # UPDATE: add strategy metrics endpoints
|-- config.py                     # UPDATE: add retention/display config defaults if absent
`-- tests/
    `-- test_strategy_metrics.py  # NEW: storage, aggregation, near-miss, retention tests

dashboard/src/
|-- app/
|   |-- strategy-metrics/
|   |   `-- page.tsx              # NEW: metrics review and comparison page
|   `-- api/
|       `-- strategy-metrics/
|           |-- _auth.ts          # NEW: shared auth helper for strategy metrics proxies
|           |-- summary/route.ts  # NEW: proxy summary requests to Python backend
|           |-- opportunities/route.ts # NEW: proxy detail requests to Python backend
|           |-- compare/route.ts  # NEW: proxy comparison requests to Python backend
|           `-- export/route.ts   # NEW: proxy export request
|-- hooks/useData.ts              # UPDATE: add strategy metrics hooks
|-- lib/api.ts                    # UPDATE: add strategy metrics client methods
`-- types/index.ts                # UPDATE: add diagnostic metric types
```

**Structure Decision**: Keep the existing Python backend plus Next.js dashboard structure. Add one backend module for persistence/aggregation, small API surfaces in both backend and dashboard proxy layers, and one dashboard page for user review. No new service, database server, or broker-specific module is introduced.

## Phase 0: Research

See [research.md](research.md) for decisions and alternatives.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for entity design.

See [contracts/strategy-metrics-api.md](contracts/strategy-metrics-api.md) and [contracts/dashboard-ui.md](contracts/dashboard-ui.md) for API and UI contracts.

See [quickstart.md](quickstart.md) for validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Data model separates diagnostic decisions from emitted signals; no relaxed pass condition is introduced. |
| II. Execution Layer Abstraction | PASS | Contracts and data model use symbols, criteria, and prices only; no Oanda/MatchTrader-specific schema fields. |
| III. Risk-First | PASS | Risk criteria are represented as blocking diagnostics, and execution remains gated by current risk checks. |
| IV. Observable by Default | PASS | Diagnostic records are queryable through API/dashboard, reflected in `strategy_metrics.json`, and retained locally for 90 days; export supports offline review. |
| V. Configuration-Driven | PASS | Retention and page defaults are config-level behavior; strategy thresholds stay reported from evaluation context. |
| Security & Credential Hygiene | PASS | Existing dashboard auth is reused; no secrets added. |
| Pull Request Policy | PENDING | Must be enforced in `/speckit-tasks`. |

No post-design gates failed.
