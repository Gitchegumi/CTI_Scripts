# Implementation Plan: Prime Signal Suppression

**Branch**: `012-prime-signal-suppression` | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/012-prime-signal-suppression/spec.md`

## Summary

Add persistent prime-signal suppression to the Signal Journal so each symbol has at most one active unresolved prime signal. The implementation will keep signal generation untouched, evaluate an existing prime against intervening candle highs/lows before a follow-on same-symbol signal is journaled, close and replace primes after inferred TP/SL outcomes, or suppress the follow-on signal by updating suppression evidence on the active prime. Dashboard, export, and metrics surfaces will expose compact suppression evidence while preserving existing journal workflows.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16.2.4 / React 19.2.4 dashboard under `dashboard/`  
**Primary Dependencies**: Python stdlib `json`, `datetime`, `threading`, dataclasses; existing `ExecutionClient` candle model; existing dashboard `fetch`, React hooks, TypeScript types; pytest; Next ESLint/TypeScript checks  
**Storage**: Existing append-only Signal Journal JSONL at `src/tradegumi/data/signal_journal.jsonl`; existing strategy metrics SQLite DB at `src/tradegumi/data/strategy_metrics.db`; additive JSONL fields and additive metric fields only  
**Testing**: pytest in `src/tradegumi/tests/`; dashboard checks via `npm run lint` and `npm run build` when UI/types change  
**Target Platform**: Local operator TradeGumi API on port 8199 with Docker/Next dashboard proxy  
**Project Type**: Python trading backend plus Next.js dashboard  
**Performance Goals**: Resolve prime lookup, TP/SL inference, suppression update, or prime replacement without operator-visible delay; preserve journal/export responsiveness for 1,000+ records under 2 seconds  
**Constraints**: Do not retune or bypass strategy layers, threshold logic, confidence scoring, broker execution, risk enforcement, setup outcome eligibility rules, or order placement; legacy journal records remain readable  
**Scale/Scope**: Signal Journal append/grade/reset/purge/export helpers, candle outcome inference hook, strategy metrics summary/export fields, dashboard journal card/detail display, tests, and docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The feature operates after a signal has fired and does not change the four signal layers or firing thresholds. |
| II. Execution Layer Abstraction | PASS | Outcome inference uses the existing broker-agnostic candle interface shape and does not import broker-specific clients into strategy logic. |
| III. Risk-First | PASS | No position sizing, drawdown, risk checks, or order placement behavior changes are planned. |
| IV. Observable by Default | PASS | Suppression counts, inferred close reasons, latest suppressed time, and ambiguity state become visible in journal records, exports, dashboard, and metrics. |
| V. Configuration-Driven Operations | PASS | No new strategy thresholds are introduced; optional candle lookback bounds should use existing configuration style if needed. |
| Security & Credential Hygiene | PASS | No new secrets, credentials, or external auth surfaces are introduced. |
| Code Quality & Documentation | PASS | New Python helpers require intention-revealing names, useful docstrings, and focused tests for non-obvious outcome inference. |
| Pull Request Policy | PASS | `tasks.md` must include the final DockeGumi reviewer PR task. |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/012-prime-signal-suppression/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- signal-journal-prime-fields.md
|   |-- prime-suppression-flow.md
|   |-- strategy-metrics-prime-suppression.md
|   `-- signal-journal-ui.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- journal.py                    # prime lookup, TP/SL inference, suppression updates, export fields
|-- alerts.py                     # preserves append_signal call path; pass optional candle context only if needed
|-- strategy_metrics.py           # aggregate/export prime suppression counts
|-- api_server.py                 # journal/metrics route behavior remains compatible
`-- tests/
    |-- test_journal.py           # prime creation, suppression, inference, restart, export, grading/reset/purge behavior
    `-- test_strategy_metrics.py  # suppression aggregate/export metrics

dashboard/src/
|-- app/journal/page.tsx          # compact suppressed count display and local type shape
|-- app/strategy-metrics/page.tsx # metrics display only if existing summary view supports compact addition
`-- types/index.ts                # shared journal/metrics field types

docs/
`-- signal-journal.md             # document prime fields and stats counting rule if the doc exists or is created
```

**Structure Decision**: Keep prime suppression inside existing journal and metrics ownership boundaries. Do not introduce a new service, separate prime registry, broker-specific implementation, or strategy-rule changes.

## Phase 0: Research

See [research.md](research.md) for decisions on persistent prime state, active-prime resolution, candle inference, ambiguity, concurrency, suppressed metadata, metrics, and legacy behavior.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for prime signal fields, suppressed evidence, inferred closure states, and lifecycle rules.

See [contracts/signal-journal-prime-fields.md](contracts/signal-journal-prime-fields.md), [contracts/prime-suppression-flow.md](contracts/prime-suppression-flow.md), [contracts/strategy-metrics-prime-suppression.md](contracts/strategy-metrics-prime-suppression.md), and [contracts/signal-journal-ui.md](contracts/signal-journal-ui.md) for storage/export, flow, metrics, and dashboard contracts.

See [quickstart.md](quickstart.md) for validation steps.

Agent context was updated in [AGENTS.md](../../AGENTS.md) to point at this plan.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design suppresses journal rows only after emitted signals reach the journal path; it leaves strategy gates untouched. |
| II. Execution Layer Abstraction | PASS | Design depends on candle high/low data by interface shape and test doubles, not broker-specific clients. |
| III. Risk-First | PASS | No risk or execution behavior is changed by the design. |
| IV. Observable by Default | PASS | Suppression and inferred closure fields are auditable in storage, exports, dashboard, and metrics. |
| V. Configuration-Driven Operations | PASS | No magic strategy thresholds are added; implementation should reuse existing config style for any operational lookback guard. |
| Security & Credential Hygiene | PASS | No credential-bearing data or new secrets are introduced. |
| Code Quality & Documentation | PASS | Planned helpers need docstrings and tests for prime resolution and ambiguous close behavior. |
| Pull Request Policy | PASS | Task generation must carry the DockeGumi reviewer PR task. |

No post-design gate violations.
