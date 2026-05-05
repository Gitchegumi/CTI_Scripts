# Implementation Plan: Metrics Diagnostics

**Branch**: `004-metrics-diagnostics` | **Date**: 2026-05-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/004-metrics-diagnostics/spec.md`

## Summary

Improve diagnostic trust in the strategy metrics export without changing any trading behavior. The implementation will add explicit trend-classification diagnostics, compute threshold expected-pass values through persistence/export, repair blocker assignment for skipped and rejected opportunities, and update summary aggregation so skipped no-trend blockers are visible alongside rejected criterion blockers. Engine/API/data failures remain indeterminate; strategy decisions remain skipped or rejected.

## Technical Context

**Language/Version**: Python 3.11 signal engine and metrics backend
**Primary Dependencies**: Existing local indicator helpers, pandas-derived LR outputs, Python stdlib SQLite/JSON metrics storage
**Storage**: Existing local strategy metrics SQLite database plus JSON export/state payloads, extended with additive diagnostic fields
**Testing**: pytest unit tests for trend classification diagnostics, threshold expected-pass behavior, blocker assignment, and aggregation
**Target Platform**: Docker-hosted TradeGumi service and existing dashboard/API export consumers
**Project Type**: Python trading backend with dashboard-facing JSON diagnostics
**Performance Goals**: Diagnostic enrichment adds negligible per-symbol overhead and keeps summary/export behavior within existing single-operator expectations
**Constraints**: Do not change thresholds, entry rules, risk behavior, trading frequency, broker abstraction, or parameter optimization; preserve JSON export compatibility
**Scale/Scope**: Single strategy owner reviewing tens of thousands of evaluations per reporting period

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Diagnostics are additive and must not change signal eligibility, thresholds, or emission paths. |
| II. Execution Layer Abstraction | PASS | Work stays in signal diagnostics and metrics storage/export; no broker-specific imports are added to strategy logic. |
| III. Risk-First | PASS | Risk checks remain unchanged and risk blockers are only reported more clearly. |
| IV. Observable by Default | PASS | Every skipped/rejected/indeterminate evaluation becomes more explainable in JSON state/export. |
| V. Configuration-Driven Operations | PASS | Active thresholds are reported from existing constants/versioning; no configuration values are changed. |
| Security & Credential Hygiene | PASS | No secrets, credentials, or external services are introduced. |
| Code Quality & Documentation | PASS | New helpers require intention-revealing names and useful Python docstrings. |
| Pull Request Policy | PENDING | Any generated task list must include "Submit PR with DockeGumi as reviewer" as the final task. |

No gates failed. No complexity violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/004-metrics-diagnostics/
|-- spec.md
|-- plan.md
|-- quickstart.md
|-- follow-on.md
|-- checklists/
|   `-- requirements.md
`-- contracts/
    `-- metrics-diagnostics-export.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- signal_engine.py                 # UPDATE: classify trend decisions and attach trend diagnostics
|-- strategy_metrics.py              # UPDATE: persist/export expected_pass, blockers, trend_decision, threshold-version counts
`-- tests/
    `-- test_strategy_metrics.py     # UPDATE: unit coverage for diagnostics and aggregation

docs/
`-- strategy-metrics.md              # NEW/UPDATE: metrics export interpretation guide
```

**Structure Decision**: Extend the existing metrics module and signal diagnostic object. Avoid a new service, new database, dashboard rewrite, or strategy-rule refactor.

## Phase 0: Research

- Current trend-strength criteria use `abs_gte`, so strength can pass while classification still returns flat when timeframe signs disagree.
- Current blocker aggregation primarily counts rejected failed criteria, which misses skipped no-trend opportunities where classification logic, not a failed threshold, is the blocker.
- Current criterion records compute `expected_pass` in memory but do not persist or rehydrate it, leaving JSON exports incomplete after database reads.
- Additive columns/fields are sufficient to preserve existing export compatibility.

## Phase 1: Design & Contracts

See [contracts/metrics-diagnostics-export.md](contracts/metrics-diagnostics-export.md) for the additive export contract.

See [quickstart.md](quickstart.md) for validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Trend helper reports the existing classification result and reason; it does not relax direction agreement or strength thresholds. |
| II. Execution Layer Abstraction | PASS | Contract fields use generic symbols, slopes, criteria, and blockers only. |
| III. Risk-First | PASS | Risk remains an unchanged blocker layer. |
| IV. Observable by Default | PASS | Exports and summaries explain actual blockers, including no-trend classification blockers. |
| V. Configuration-Driven Operations | PASS | Threshold versions remain diagnostic metadata only. |
| Security & Credential Hygiene | PASS | No credential-bearing fields are added. |
| Code Quality & Documentation | PASS | Planned Python helpers have docstrings and focused tests. |
| Pull Request Policy | PENDING | Must be enforced in `/speckit-tasks`. |

No post-design gates failed.
