# Implementation Plan: Continuation Management Events

**Branch**: `018-continuation-management` | **Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/018-continuation-management/spec.md`

## Summary

Convert continuation signals from standalone trade entries into lifecycle management events for active pullback-originated trades. The implementation will keep pullback signal generation as the entry source, route same-direction continuation signals through a managed-trade layer that can tighten stop loss or extend take profit within configurable limits, classify final outcomes from the managed SL/TP state, and expose lifecycle counters through journal exports, strategy metrics, and dashboard views.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16.2.4 / React 19.2.4 dashboard under `dashboard/`  
**Primary Dependencies**: Python stdlib `json`, `datetime`, `threading`, dataclasses, SQLite; pandas/numpy/ta-lib signal stack; existing dashboard `fetch`, React hooks, TypeScript types; pytest; Next ESLint/TypeScript checks  
**Storage**: Existing Signal Journal JSONL at `src/tradegumi/data/signal_journal.jsonl`; existing strategy metrics SQLite DB at `src/tradegumi/data/strategy_metrics.db`; additive JSONL fields, additive SQLite columns/tables as needed, and legacy-readable exports  
**Testing**: pytest in `src/tradegumi/tests/`; dashboard checks via `npm run lint` and `npm run build` when UI/types change  
**Target Platform**: Windows / Linux local operator environment, Docker Compose deployment, TradeGumi API on port 8199 with Next dashboard proxy  
**Project Type**: Python trading signal backend plus Next.js dashboard  
**Performance Goals**: Preserve engine evaluation under 200ms per symbol; journal/metrics export remains responsive for 1,000+ journal rows under 2 seconds; continuation management lookup/update adds no operator-visible alert delay  
**Constraints**: Do not remove continuation detection, bypass signal layers, import broker-specific clients into lifecycle logic, weaken risk checks, hardcode secrets, or make managed entries invisible to Discord/journal/metrics consumers; legacy journal and metrics records remain readable  
**Scale/Scope**: Tier 1 and Tier 2 watchlist symbols; signal engine continuation path, journal lifecycle fields, metrics summary/export, outcome accounting, dashboard journal/metrics display, tests, and docs/contracts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Pullback and continuation detection gates remain intact; the feature changes how emitted continuation evidence is consumed after signal evaluation, not which signal layers pass. |
| II. Execution Layer Abstraction | PASS | Managed lifecycle uses signal/journal price levels and existing candle/outcome shapes; no broker-specific client imports are planned. |
| III. Risk-First | PASS | Pullback entries keep existing risk checks and position sizing. Continuation management may only reduce risk or extend reward within configured limits and must never increase accepted risk. |
| IV. Observable by Default | PASS | Entry events, accepted/rejected management events, SL/TP changes, warnings, and managed outcomes are recorded in journal/export/metrics and remain dashboard-visible. |
| V. Configuration-Driven Operations | PASS | Favorable-move thresholds, break-even behavior, TP extension multiples, and extension caps will follow existing environment-driven config style. |
| Security & Credential Hygiene | PASS | No new secrets, credentials, external auth surfaces, or credential-bearing logs are introduced. |
| Code Quality & Documentation | PASS | New lifecycle helpers require intention-revealing names, useful docstrings, and tests for non-obvious risk/outcome transitions. |
| Pull Request Policy | PASS | No reviewer was identified in the feature context; task generation must include a final task to ask the user for the reviewer before opening the PR. |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/018-continuation-management/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- managed-trade-journal-fields.md
|   |-- continuation-management-flow.md
|   |-- managed-outcome-accounting.md
|   |-- strategy-metrics-managed-trades.md
|   `-- dashboard-managed-lifecycle.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- signal_engine.py              # preserve detection; route continuation evidence without entry duplication
|-- journal.py                    # managed trade fields, management event append/update/export behavior
|-- strategy_metrics.py           # managed lifecycle counters and export fields
|-- signal_outcomes.py            # managed SL/TP outcome classification
|-- config.py                     # env-driven management thresholds and caps
|-- risk.py                       # reuse R/SL/TP semantics; no risk bypass
`-- tests/
    |-- test_signal_engine.py     # continuation no-entry and pullback-entry behavior
    |-- test_journal.py           # lifecycle state, management event, export, reset/purge/manual flows
    |-- test_signal_outcomes.py   # managed TP/SL/BE/profit-protected accounting
    `-- test_strategy_metrics.py  # lifecycle counters and managed outcome summaries

dashboard/src/
|-- app/journal/page.tsx          # distinguish entry, management, and outcome rows
|-- app/strategy-metrics/page.tsx # managed lifecycle summary cards/tables
`-- types/index.ts                # shared lifecycle and metrics field types

docs/
`-- signal-journal.md             # document managed lifecycle fields if the doc exists or is created
```

**Structure Decision**: Extend existing signal journal, outcome, and strategy metrics ownership boundaries. Do not add a broker-specific management service or a separate lifecycle store unless implementation proves JSONL-only updates cannot satisfy durability and export needs; any SQLite additions must be additive and legacy-safe.

## Phase 0: Research

See [research.md](research.md) for decisions on active-trade identity, continuation routing, management thresholds, profit protection, storage shape, metrics, dashboard exposure, and legacy compatibility.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for trade entry events, trade management events, managed outcomes, and configuration state transitions.

See [contracts/managed-trade-journal-fields.md](contracts/managed-trade-journal-fields.md), [contracts/continuation-management-flow.md](contracts/continuation-management-flow.md), [contracts/managed-outcome-accounting.md](contracts/managed-outcome-accounting.md), [contracts/strategy-metrics-managed-trades.md](contracts/strategy-metrics-managed-trades.md), and [contracts/dashboard-managed-lifecycle.md](contracts/dashboard-managed-lifecycle.md) for storage/export, lifecycle flow, accounting, metrics, and dashboard contracts.

See [quickstart.md](quickstart.md) for validation steps.

Agent context was updated in [AGENTS.md](../../AGENTS.md) to point at this plan.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design keeps pullback and continuation criteria intact and reclassifies continuation after emission as management evidence rather than entry permission. |
| II. Execution Layer Abstraction | PASS | Design relies on broker-agnostic journal records, signal prices, and candle outcome evidence; execution clients remain behind existing interfaces. |
| III. Risk-First | PASS | Management rules explicitly reject risk-increasing SL changes, cap TP extensions, and preserve entry risk as the baseline for R accounting. |
| IV. Observable by Default | PASS | Contracts require visible entry events, management events, old/new SL/TP values, rejection reasons, warnings, and managed outcome metrics. |
| V. Configuration-Driven Operations | PASS | All thresholds and caps are defined as configuration values with sane defaults and no hardcoded strategy magic in lifecycle logic. |
| Security & Credential Hygiene | PASS | Design introduces no credential-bearing fields or external secret handling. |
| Code Quality & Documentation | PASS | Data model and contracts call out state transitions that need named helpers, docstrings, and focused regression tests. |
| Pull Request Policy | PASS | Task generation must include a final ask-back for reviewer identification before PR creation. |

No post-design gate violations.

## Complexity Tracking

*No violations.*
