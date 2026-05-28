# Implementation Plan: Alert Signal Auto-Grading

**Branch**: `013-alert-signal-autograding` | **Date**: 2026-05-27 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/013-alert-signal-autograding/spec.md`

## Summary

Add automatic outcome grading for alert-only/developing Signal Journal entries by introducing a shared price-observation layer fed from the existing one-second pricing path. A dedicated evaluator will consume price observations, update only journal outcome/status fields, preserve manual overrides, and keep prime-signal suppression aligned with resolved versus unresolved signal state. Dashboard/API/export surfaces will expose compact outcome fields, while the observation interface remains source-agnostic for a later Oanda pricing stream.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16.2.4 / React 19.2.4 dashboard under `dashboard/`  
**Primary Dependencies**: Python stdlib dataclasses, datetime, threading, collections; existing `ExecutionClient`, `PriceTick`, and journal helpers; existing dashboard `fetch` hooks and TypeScript types; pytest; Next ESLint/TypeScript checks  
**Storage**: Existing append-only Signal Journal JSONL at `src/tradegumi/data/signal_journal.jsonl`; optional in-memory rolling price history for first implementation; no unbounded observation persistence  
**Testing**: pytest in `src/tradegumi/tests/`; dashboard checks via `npm run lint` and `npm run build` when UI/types change  
**Target Platform**: Local TradeGumi backend API on port 8199 with Next dashboard proxy  
**Project Type**: Python trading backend plus Next.js dashboard  
**Performance Goals**: One-second pricing observations remain shared with no duplicate evaluator polling; unresolved same-symbol grading completes inside the existing loop without visible dashboard delay; journal/export remain responsive for 1,000+ records under 2 seconds  
**Constraints**: Do not alter signal generation, strategy thresholds, risk enforcement, broker execution, or order placement; do not use undocumented broker browser/chart endpoints; do not hardcode accounts, instruments, or secrets; preserve manual overrides and legacy journal records  
**Scale/Scope**: Shared price observation service, signal outcome evaluator, Signal Journal fields/export/reset/manual grade behavior, prime suppression resolution checks, API/dashboard journal display, tests, and operator docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The evaluator runs after a signal is journaled and cannot generate or approve signals. |
| II. Execution Layer Abstraction | PASS | Price observations are sourced through the broker-agnostic `ExecutionClient.get_pricing()` and shared observation interface, not signal logic importing broker clients. |
| III. Risk-First | PASS | No risk checks, position sizing, drawdown rules, or order placement behavior are changed. |
| IV. Observable by Default | PASS | Outcome, source, exit details, ambiguity, and manual override state become visible in journal records, exports, dashboard, and logs where appropriate. |
| V. Configuration-Driven Operations | PASS | The first implementation reuses the existing one-second pricing cadence and does not add hardcoded instruments or account values. |
| Security & Credential Hygiene | PASS | No new secrets or credential-bearing endpoints are introduced; undocumented broker UI endpoints are explicitly excluded. |
| Code Quality & Documentation | PASS | New Python modules and public helpers require docstrings and intention-revealing names. |
| Pull Request Policy | PASS | `tasks.md` must include the final DockeGumi reviewer PR task. |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/013-alert-signal-autograding/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- price-observation-service.md
|   |-- signal-outcome-evaluator.md
|   |-- signal-journal-outcome-fields.md
|   `-- signal-journal-ui.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- price_observations.py          # PriceObservation model, rolling history, shared publish/read service
|-- signal_outcomes.py             # Alert-only outcome evaluator and TP/SL/ambiguous decisions
|-- main.py                        # Publishes existing 1s pricing ticks into shared observations/evaluator
|-- api_server.py                  # Reuses shared observations for dashboard price/position response where practical
|-- journal.py                     # Outcome fields, manual override preservation, exports, reset, prime state alignment
|-- strategy_metrics.py            # Outcome/invalidated-by-prime summary fields if existing metrics surface fits
`-- tests/
    |-- test_price_observations.py
    |-- test_signal_outcomes.py
    |-- test_journal.py
    `-- test_strategy_metrics.py

dashboard/src/
|-- app/journal/page.tsx           # Compact outcome/source/exit/manual/ambiguous display
|-- app/api/journal/route.ts       # Proxy remains compatible with added fields
`-- types/index.ts                 # Journal outcome field types

docs/
`-- signal-journal.md              # Document auto-grading fields and manual override/reset behavior if present/created
```

**Structure Decision**: Keep live price observation ownership separate from signal generation and broker clients. Keep journal mutation in `journal.py`, grading decisions in `signal_outcomes.py`, and rolling live data in `price_observations.py` so a future streaming source can publish the same `PriceObservation` objects without rewriting the evaluator.

## Phase 0: Research

See [research.md](research.md) for decisions on shared observations, rolling history retention, bid/ask versus midpoint grading, manual overrides, prime suppression integration, dashboard reuse, and streaming readiness.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for price observations, rolling history, outcome fields, evaluator state transitions, and prime alignment.

See [contracts/price-observation-service.md](contracts/price-observation-service.md), [contracts/signal-outcome-evaluator.md](contracts/signal-outcome-evaluator.md), [contracts/signal-journal-outcome-fields.md](contracts/signal-journal-outcome-fields.md), and [contracts/signal-journal-ui.md](contracts/signal-journal-ui.md) for service, evaluator, storage/export, and UI/API contracts.

See [quickstart.md](quickstart.md) for validation steps.

Agent context was updated in [AGENTS.md](../../AGENTS.md) to point at this plan.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design evaluates only already-fired alert/developing entries and does not change the signal engine gates. |
| II. Execution Layer Abstraction | PASS | Design uses `ExecutionClient` price ticks and a provider-neutral observation model; Oanda-specific code stays inside the existing client. |
| III. Risk-First | PASS | Design never places, modifies, sizes, or closes live orders. |
| IV. Observable by Default | PASS | Journal/export/dashboard contracts include the audit fields needed to explain every auto outcome. |
| V. Configuration-Driven Operations | PASS | No hardcoded instruments/accounts or new strategy thresholds are introduced. |
| Security & Credential Hygiene | PASS | No secrets, browser automation, chart drawing, or undocumented broker endpoints are introduced. |
| Code Quality & Documentation | PASS | Planned modules have explicit docstring and naming tasks, plus focused tests for evaluator behavior. |
| Pull Request Policy | PASS | Task generation must carry the DockeGumi reviewer PR task. |

No post-design gate violations.
