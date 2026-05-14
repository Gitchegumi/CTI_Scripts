# Implementation Plan: Signal Setup Outcomes

**Branch**: `011-signal-setup-outcomes` | **Date**: 2026-05-14 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/011-signal-setup-outcomes/spec.md`

## Summary

Add Signal Journal evaluation fields that separate raw emitted signals from tradable setup outcomes. The implementation will keep signal-generation thresholds intact while enriching new journal entries with setup grouping, duplicate detection, entry usability, signal age, normalized trade grade, and strategy-stat eligibility. Strategy metrics and dashboard/journal views will treat emitted signals as trade opportunities only when `usable_for_strategy_stats` is true, while legacy journal records remain readable.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16.2.4 / React 19.2.4 dashboard under `dashboard/`  
**Primary Dependencies**: Python stdlib `json`, `datetime`, `threading`, `sqlite3`, dataclasses; existing dashboard `fetch`, React hooks, TypeScript types; pytest; Next ESLint/TypeScript checks  
**Storage**: Existing append-only Signal Journal JSONL at `src/tradegumi/data/signal_journal.jsonl`; existing strategy metrics SQLite DB at `src/tradegumi/data/strategy_metrics.db`; additive fields/columns only  
**Testing**: pytest in `src/tradegumi/tests/`; dashboard checks via `npm run lint` and `npm run build` when UI/types change  
**Target Platform**: Local operator TradeGumi API on port 8199 with Docker/Next dashboard proxy  
**Project Type**: Python trading backend plus Next.js dashboard  
**Performance Goals**: Classify and append a signal with setup outcome fields without operator-visible delay; summarize 1,000 metrics/journal records in under 2 seconds for one operator  
**Constraints**: Do not retune strategy thresholds, bypass signal layers, alter broker execution behavior, place orders, or rewrite historical journal evidence except explicit manual invalidation; keep legacy records readable  
**Scale/Scope**: Signal Journal append/grade/reset/export helpers, strategy metrics eligibility aggregation, dashboard journal types/display, tests, and docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The feature annotates emitted signal evidence after the existing pipeline fires; it does not weaken or bypass the four signal layers. |
| II. Execution Layer Abstraction | PASS | No broker-specific execution client behavior is required; signal/setup classification uses journal and strategy context. |
| III. Risk-First | PASS | No position sizing, drawdown, order placement, or risk enforcement behavior changes. |
| IV. Observable by Default | PASS | New fields make duplicate, late, stale, invalid, and usable setup decisions visible in journal records and exports. |
| V. Configuration-Driven Operations | PASS | The setup grouping window is configurable and defaults to 10 minutes; thresholds are read from existing context, not retuned. |
| Security & Credential Hygiene | PASS | No secrets or credentials are introduced; journal auth and existing storage boundaries remain unchanged. |
| Code Quality & Documentation | PASS | Python helpers and public dataclasses need intention-revealing names, docstrings, and focused tests. |
| Pull Request Policy | PASS | `tasks.md` must include the final DockeGumi reviewer PR task. |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/011-signal-setup-outcomes/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- signal-journal-outcome-fields.md
|   |-- strategy-stats-eligibility.md
|   `-- signal-journal-ui.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- config.py                   # add setup grouping, entry tolerance, and stale-signal config
|-- journal.py                  # classify setup outcome fields, grade/manual invalidation behavior, export fields
|-- strategy_metrics.py         # persist and aggregate usable opportunity counts
|-- alerts.py                   # pass signal-time context into journal append path if needed
|-- signal_engine.py            # expose setup-condition timing context without changing signal rules if needed
`-- tests/
    |-- test_journal.py         # setup grouping, duplicate, entry validity, trade grade, legacy/export behavior
    `-- test_strategy_metrics.py # stats eligibility and opportunity count behavior

dashboard/src/
|-- app/journal/page.tsx        # display/filter normalized setup outcome fields where useful
`-- types/index.ts              # journal/metrics field types

docs/
`-- signal-journal.md           # document setup outcome fields and stats counting rule
```

**Structure Decision**: Keep the change inside existing journal and strategy metrics modules, with dashboard support only for displaying/typing the new evidence. Do not introduce a new database service, broker integration, order-management path, or strategy-rule rewrite.

## Phase 0: Research

See [research.md](research.md) for setup grouping, entry validity, signal-age, trade-grade, stats eligibility, and legacy compatibility decisions.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for the journal outcome fields, setup group, eligibility, and grade state model.

See [contracts/signal-journal-outcome-fields.md](contracts/signal-journal-outcome-fields.md), [contracts/strategy-stats-eligibility.md](contracts/strategy-stats-eligibility.md), and [contracts/signal-journal-ui.md](contracts/signal-journal-ui.md) for storage/export, metrics, and dashboard contracts.

See [quickstart.md](quickstart.md) for validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design records setup usability after a signal exists and preserves existing signal firing gates. |
| II. Execution Layer Abstraction | PASS | No execution-client imports or broker-specific fields are added to signal logic. |
| III. Risk-First | PASS | Risk enforcement remains outside this feature; outcome fields do not authorize trades. |
| IV. Observable by Default | PASS | Every exclusion from strategy stats has visible journal fields and stable export names. |
| V. Configuration-Driven Operations | PASS | Setup grouping window is configured rather than hardcoded, and existing tolerance context is reused. |
| Security & Credential Hygiene | PASS | No new credential surfaces or secret-bearing exports are introduced. |
| Code Quality & Documentation | PASS | Planned Python changes require docstrings, named helpers, and focused tests for non-obvious classification behavior. |
| Pull Request Policy | PASS | Task generation must carry the DockeGumi reviewer PR task. |

No post-design gate violations.
