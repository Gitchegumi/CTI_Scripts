# Implementation Plan: Journal and Dashboard Controls

**Branch**: `005-journal-dashboard-controls` | **Date**: 2026-05-05 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/005-journal-dashboard-controls/spec.md`

## Summary

Fix the remaining trust issues across strategy metrics, Signal Journal maintenance, Developing-mode manual trade correction, and main dashboard trade history. The implementation will keep signal strategy behavior unchanged while improving date range normalization, journal export and maintenance actions, mode display labels, local trade-history reliability, optional correlation fallback, and hydration-safe dashboard rendering.

The feature extends existing Python JSONL/SQLite-backed journal and trade-history helpers plus existing Next.js dashboard pages and proxy routes. No destructive migration is planned. Existing `alert_only` values remain the internal compatibility value and are displayed as "Developing" in UI copy.

## Technical Context

**Language/Version**: Python 3.11 backend target; TypeScript / Next.js dashboard  
**Primary Dependencies**: Python stdlib HTTP server, SQLite, JSONL files, existing React hooks/components and Next.js route handlers  
**Storage**: Existing `src/tradegumi/data/strategy_metrics.db`, `src/tradegumi/data/manual_trades.db`, and `src/tradegumi/data/signal_journal.jsonl`; no new external store  
**Testing**: pytest for Python storage/API behavior; dashboard lint/typecheck or focused component/manual validation where automated browser tests are not already present  
**Target Platform**: Docker-hosted TradeGumi service plus authenticated web dashboard  
**Project Type**: Web application with Python trading backend and Next.js frontend  
**Performance Goals**: Dashboard trade history returns 50 records within the existing 30-second polling cadence; journal export of 1,000 records completes in under 2 seconds for a single operator  
**Constraints**: No strategy threshold or entry-rule changes; no internal mode value migration; preserve existing records; destructive actions require confirmation; no secrets in logs or docs  
**Scale/Scope**: Single operator, local journal/history data, three internal modes (`alert_only`, `demo`, `live`), dashboard and journal pages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Feature changes diagnostics, journal maintenance, labels, and history display only; no signal criteria, thresholds, layer order, or entry behavior may change. |
| II. Execution Layer Abstraction | PASS | Broker/source trade history remains consumed through existing runtime client and unified history boundaries; dashboard must still show local manual records when broker calls fail. |
| III. Risk-First | PASS | No order placement, risk bypass, or live execution path is added. Developing-mode P&L edits are local record corrections only. |
| IV. Observable by Default | PASS | Fixes improve visible date accuracy, exportability, maintenance feedback, and dashboard trade-history observability; operational errors are handled intentionally rather than hidden. |
| V. Configuration-Driven Operations | PASS | Internal mode values remain config-driven; display label mapping is a presentation concern. |
| Security & Credential Hygiene | PASS | Existing journal authentication remains required for protected journal/trade endpoints; no credentials or account secrets added. |
| Code Quality & Documentation | PASS | Python changes will require useful module/function/helper docstrings and intention-revealing names. |
| Pull Request Policy | PENDING | `tasks.md` must include "Submit PR with DockeGumi as reviewer" as the final task. |

No gates failed. No complexity violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/005-journal-dashboard-controls/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- checklists/
|   `-- requirements.md
|-- contracts/
|   |-- strategy-metrics-api.md
|   |-- signal-journal-api.md
|   |-- manual-trades-api.md
|   `-- dashboard-ui.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- strategy_metrics.py          # UPDATE: inclusive calendar end-date normalization and range tests
|-- journal.py                   # UPDATE: export, purge, reset-to-pending helpers over JSONL
|-- manual_trades.py             # UPDATE: explicit P&L correction handling in alert_only/Developing mode
|-- api_server.py                # UPDATE: journal endpoints, history fallback, metrics range behavior
`-- tests/
    |-- test_strategy_metrics.py # UPDATE: inclusive end-date coverage
    |-- test_journal.py          # NEW/UPDATE: export, purge, reset-to-pending coverage
    `-- test_manual_trades.py    # UPDATE: P&L edit permission and dashboard history coverage

dashboard/src/
|-- app/
|   |-- strategy-metrics/page.tsx          # UPDATE: date range request/display behavior
|   |-- journal/page.tsx                   # UPDATE: export, purge, reset controls
|   |-- manual-trades/page.tsx             # UPDATE: Developing label and P&L edit control
|   `-- api/
|       |-- journal/route.ts               # UPDATE: proxy export, purge, reset actions
|       |-- trades/history/route.ts        # UPDATE: preserve valid fallback/error payloads
|       `-- strategy-metrics/*/route.ts    # REVIEW: pass normalized range params consistently
|-- components/
|   |-- TradeHistory.tsx                   # UPDATE: hydration-safe formatting/fallback display
|   `-- SettingsPanel.tsx                  # UPDATE: mode display label
|-- hooks/
|   `-- useData.ts                         # UPDATE: optional correlation fallback and trade-history errors
|-- lib/
|   `-- api.ts                             # UPDATE: journal export/purge/reset clients and display labels
`-- types/
    `-- index.ts                           # UPDATE: journal export/reset and manual P&L fields

docs/
|-- strategy-metrics.md          # UPDATE: inclusive selected end-date semantics
`-- signal-journal.md            # NEW/UPDATE: export, purge, reset, optimization fields
```

**Structure Decision**: Keep the current Python backend plus Next.js dashboard/proxy layout. Extend existing journal, metrics, and manual trade modules instead of introducing a new service or database.

## Phase 0: Research

See [research.md](research.md) for decisions and alternatives.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for entities and state transitions.

See [contracts/strategy-metrics-api.md](contracts/strategy-metrics-api.md), [contracts/signal-journal-api.md](contracts/signal-journal-api.md), [contracts/manual-trades-api.md](contracts/manual-trades-api.md), and [contracts/dashboard-ui.md](contracts/dashboard-ui.md) for API and UI behavior.

See [quickstart.md](quickstart.md) for validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design artifacts keep signal logic and strategy parameters out of scope. |
| II. Execution Layer Abstraction | PASS | Contracts require local manual history fallback when broker/source calls fail and do not add broker-specific dashboard logic. |
| III. Risk-First | PASS | Manual P&L edits are record corrections; no execution or risk enforcement behavior changes. |
| IV. Observable by Default | PASS | Contracts require explicit success/failure feedback, export metadata, and intentional fallbacks for missing optional data. |
| V. Configuration-Driven Operations | PASS | `alert_only` stays the internal config value; "Developing" is a display mapping. |
| Security & Credential Hygiene | PASS | Protected journal/trade operations continue to require existing journal auth. |
| Code Quality & Documentation | PASS | Task generation must include docstring and code-quality tasks for Python changes. |
| Pull Request Policy | PENDING | Final task must submit PR with DockeGumi as reviewer. |

No post-design gates failed.
