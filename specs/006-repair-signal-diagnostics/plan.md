# Implementation Plan: Repair Signal Pipeline Diagnostics

**Branch**: `006-repair-signal-diagnostics` | **Date**: 2026-05-06 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/006-repair-signal-diagnostics/spec.md`

## Summary

Repair strategy metrics diagnostics so valid directional trend candidates that stop after trend classification are attributed to the correct signal pipeline stage. The implementation keeps strategy thresholds and entry rules unchanged while adding structured signal data completeness diagnostics, candle-close gate timing diagnostics, meaningful near-miss reasons, data-quality blocker aggregation, threshold-version unknown explanations, and a summary funnel through the pipeline.

The feature extends the existing Python signal engine diagnostics and SQLite/JSON metrics export path. No trading strategy, risk, broker, or execution behavior changes are planned.

## Technical Context

**Language/Version**: Python 3.11 backend target  
**Primary Dependencies**: Python stdlib, SQLite, pandas-backed existing indicators, existing `tradegumi` modules  
**Storage**: Existing `src/tradegumi/data/strategy_metrics.db` with additive columns only; existing JSON export shape remains compatible  
**Testing**: pytest focused on `src/tradegumi/tests/test_strategy_metrics.py`  
**Target Platform**: Docker-hosted TradeGumi service and local operator diagnostics export  
**Project Type**: Python trading backend with dashboard-consumed JSON diagnostics  
**Performance Goals**: Summary/export aggregation remains suitable for the current metrics report scale of at least 25,118 evaluated opportunities; existing seeded summary performance test remains under 5 seconds for 250 writes  
**Constraints**: Do not tune thresholds, loosen trend rules, force trades, change trade execution, optimize profitability, or add broad architecture unrelated to diagnostics and gating  
**Scale/Scope**: Single operator reviewing strategy metrics exports across local SQLite-backed opportunities and criteria

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The feature records and classifies diagnostics only; it must not change signal thresholds, layer order, or entry criteria. |
| II. Execution Layer Abstraction | PASS | Work stays in broker-agnostic signal diagnostics and metrics aggregation; no broker client changes are required. |
| III. Risk-First | PASS | No order placement, position sizing, risk bypass, or live execution path is modified. |
| IV. Observable by Default | PASS | The feature improves blocked-signal observability, data-quality reasons, gate timing, and export summaries. |
| V. Configuration-Driven Operations | PASS | Existing config values remain unchanged; threshold-version reporting only explains provenance. |
| Security & Credential Hygiene | PASS | No secrets, external credentials, or raw broker payloads are introduced into exports or docs. |
| Code Quality & Documentation | PASS | Python changes require useful docstrings and intention-revealing helpers; documentation must explain new fields. |
| Pull Request Policy | PASS | `tasks.md` includes "Submit PR with DockeGumi as reviewer" as the final task. |

No gates failed. No complexity violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/006-repair-signal-diagnostics/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- checklists/
|   `-- requirements.md
|-- contracts/
|   `-- strategy-metrics-export.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- signal_engine.py                     # UPDATE: signal data and candle-close diagnostics
|-- strategy_metrics.py                  # UPDATE: validation, storage, aggregation, funnel, near-miss reasons
`-- tests/
    `-- test_strategy_metrics.py         # UPDATE: focused diagnostic and summary tests

docs/
`-- strategy-metrics.md                  # UPDATE: export field and classification definitions
```

**Structure Decision**: Keep all behavior in the existing Python backend diagnostics and metrics modules. Add only compatible metrics fields and focused tests/docs; do not introduce a new service, store, or frontend workflow for this feature.

## Phase 0: Research

See [research.md](research.md) for decisions and alternatives.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for export entities, fields, and state transitions.

See [contracts/strategy-metrics-export.md](contracts/strategy-metrics-export.md) for the additive JSON export contract.

See [quickstart.md](quickstart.md) for validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design adds diagnostics around existing trend, signal-stack, and gate decisions without changing thresholds or criteria. |
| II. Execution Layer Abstraction | PASS | Contracts describe export fields only and do not introduce broker-specific signal logic. |
| III. Risk-First | PASS | Risk and execution remain out of scope. |
| IV. Observable by Default | PASS | Design requires data-quality blockers, candle-close timing, near-miss reasons, and funnel counts. |
| V. Configuration-Driven Operations | PASS | Existing threshold-version hash remains the source; unknown reasons are explanatory metadata. |
| Security & Credential Hygiene | PASS | Compact diagnostic context excludes raw candle dumps and secrets. |
| Code Quality & Documentation | PASS | Tasks must include docstring and code-quality validation for modified Python helpers. |
| Pull Request Policy | PASS | Final task submits PR with DockeGumi as reviewer. |

No post-design gates failed.
