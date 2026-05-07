# Implementation Plan: Fix signal stack IndexError

**Branch**: `008-fix-signal-indexerror` | **Date**: 2026-05-07 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/008-fix-signal-indexerror/spec.md`

## Summary

Fix the M5 signal stack so trend-valid candidates with missing last-closed candles or insufficient indicator windows are classified as data-not-ready instead of surfacing raw `IndexError`. The technical approach is to centralize readiness validation before indicator indexing, use only closed M5 candles for signal rules, verify usable indicator rows align with the selected candle, return structured diagnostics through existing criterion/metrics fields, and add focused regression tests for short and valid data paths.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`  
**Primary Dependencies**: Python stdlib `datetime`, pandas indicator dataframes, TradeGumi indicator helpers, pytest  
**Storage**: Existing strategy metrics SQLite/JSON exports only; no schema replacement planned  
**Testing**: pytest tests under `src/tradegumi/tests/` and existing strategy metrics tests  
**Target Platform**: Local operator service and Docker-hosted TradeGumi backend  
**Project Type**: Python trading backend with dashboard-consumed diagnostics  
**Performance Goals**: Readiness validation adds negligible work relative to indicator calculation and does not request less history than required  
**Constraints**: Do not tune thresholds, loosen trend rules, force signal emission, change entry criteria, bypass risk checks, or treat open candles as closed  
**Scale/Scope**: One signal-stack path for M5 candle/indicator readiness, diagnostics emitted through current metrics model, and targeted documentation/tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The feature preserves all four layers and only prevents missing-data indexing from masquerading as a signal-stack failure. |
| II. Execution Layer Abstraction | PASS | Changes remain inside broker-agnostic signal and diagnostics modules; no broker client coupling is introduced. |
| III. Risk-First | PASS | No order placement, risk sizing, drawdown, or execution behavior changes. |
| IV. Observable by Default | PASS | Data-not-ready states become explicit diagnostics with blockers and counts. |
| V. Configuration-Driven Operations | PASS | No strategy parameters or operational mode controls are hardcoded or retuned. |
| Security & Credential Hygiene | PASS | Diagnostics include counts/timestamps only and do not expose secrets or raw credential-bearing payloads. |
| Code Quality & Documentation | PASS | New helpers require intention-revealing names, docstrings, and focused tests. |
| Pull Request Policy | PASS | Generated tasks must end with submitting a PR with DockeGumi as reviewer. |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/008-fix-signal-indexerror/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   `-- signal-stack-readiness.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- signal_engine.py                 # last closed candle selection, readiness validation, indicator access, diagnostics
|-- strategy_metrics.py              # blocker/layer classification and metrics JSON compatibility
|-- indicators.py                    # existing indicator outputs consumed by readiness validation
`-- tests/
    |-- test_signal_engine.py        # short-candle, open-candle, indicator-window, valid-data tests
    `-- test_strategy_metrics.py     # blocker and JSON compatibility tests

docs/
`-- strategy-metrics.md              # readiness diagnostic documentation if current docs mention signal diagnostics
```

**Structure Decision**: Keep implementation in existing signal and diagnostics modules. Do not add a new service, rewrite the strategy engine, replace the metrics model, or modify dashboard behavior beyond existing documentation expectations.

## Phase 0: Research

See [research.md](research.md) for decisions and alternatives.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for readiness data and decision metadata.

See [contracts/signal-stack-readiness.md](contracts/signal-stack-readiness.md) for the diagnostic contract.

See [quickstart.md](quickstart.md) for local validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design requires complete closed-candle and indicator inputs before existing signal rules evaluate. |
| II. Execution Layer Abstraction | PASS | Interface remains the existing execution-client candle read path. |
| III. Risk-First | PASS | Risk layer remains untouched and cannot be bypassed by readiness classification. |
| IV. Observable by Default | PASS | Missing readiness receives structured diagnostics instead of raw exceptions. |
| V. Configuration-Driven Operations | PASS | Indicator periods are read from existing signal stack behavior and are not retuned. |
| Security & Credential Hygiene | PASS | Added diagnostics avoid secrets and raw account data. |
| Code Quality & Documentation | PASS | Design calls for docstrings on new/modified helpers and tests for defensive behavior. |
| Pull Request Policy | PASS | Final task list includes PR submission with DockeGumi review. |

No post-design gate violations.
