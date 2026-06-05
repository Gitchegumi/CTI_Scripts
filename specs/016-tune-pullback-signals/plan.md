# Implementation Plan: Tune Pullback Signal Alerts

**Branch**: `016-tune-pullback-signals` | **Date**: 2026-06-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/016-tune-pullback-signals/spec.md`

## Summary

Tune the existing CTI-v1.2 pullback path so valid pullback opportunities become pullback alerts and Signal Journal rows instead of being filtered out by overly strict trigger candle, Keltner value-area, and Stoch RSI gates. Keep continuation behavior distinct, preserve risk/execution boundaries, make MACD diagnostic-only by default for pullbacks with an explicit opt-in hard-block mode, and expand diagnostics so strategy metrics can quantify evaluated, rejected, emitted, journaled, and prime-suppressed pullback opportunities.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16 / React 19 dashboard only if existing metrics types or UI summaries need follow-up  
**Primary Dependencies**: Existing pandas/pandas-ta indicator stack; existing `SignalEngine`, `SignalDiagnostic`, `EvaluatedOpportunity`, `StrategyMetrics`, JSONL Signal Journal helpers, Discord alert flow, and env-backed `config.py` thresholds  
**Storage**: Existing SQLite strategy metrics database; existing JSONL Signal Journal; no new durable signal store  
**Testing**: pytest in `src/tradegumi/tests/`; dashboard lint/build only if dashboard code changes  
**Target Platform**: Docker Compose TradeGumi backend on TrueNAS host; local backend API on port 8199; dashboard proxy  
**Project Type**: Python trading backend plus dashboard reporting  
**Performance Goals**: Preserve the existing 5-second signal-engine cadence; avoid additional provider candle fetches per symbol; keep metrics summary/export usable for default reporting ranges; keep per-candidate diagnostics lightweight enough for normal watchlist size  
**Constraints**: Do not bypass strategy layers, risk checks, or execution guards; do not change funded/live promotion workflow; do not add broker-specific signal logic; all material thresholds must be config-driven; Discord/journal/metrics must preserve pullback vs continuation identity  
**Scale/Scope**: One TradeGumi process evaluating the active watchlist, typically tens of symbols, over existing H1/M15/M5 candle windows and strategy metrics/reporting periods

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | This feature intentionally uses the constitution's strategy-version exception path for pullback Layer 2 gates. Pullback still requires a complete path: larger-trend context, structure, value-area sequence, exhaustion, trigger, and risk. MACD remains soft by default for pullbacks per the spec. |
| II. Execution Layer Abstraction | PASS | Changes remain in strategy, config, metrics, journal, and alert surfaces using broker-neutral candle/signal data. |
| III. Risk-First | PASS | No order placement, sizing, daily loss, drawdown, or max-position behavior changes. Any emitted signal still flows through existing risk controls before orders. |
| IV. Observable by Default | PASS | Plan requires stable blockers and counts for evaluated, rejected, near-miss, emitted, journaled, and prime-suppressed pullbacks. |
| V. Configuration-Driven Operations | PASS | Trigger shape, value-area tolerance, exhaustion memory, and optional MACD hard-block behavior are planned as env-backed settings. |
| Security & Credential Hygiene | PASS | No new credentials, external services, or secret-bearing logs. |
| Code Quality & Documentation | PASS | New or changed Python helpers require docstrings and intention-revealing names; comments should explain tuning tradeoffs only where needed. |
| Pull Request Policy | PASS | Later task generation must include a final PR task with the reviewer identified by user or feature context. |

## Project Structure

### Documentation (this feature)

```text
specs/016-tune-pullback-signals/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- pullback-configuration.md
|   |-- signal-diagnostics.md
|   `-- reporting-exports.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- config.py                  # Add trigger-shape and optional MACD pullback settings
|-- signal_engine.py           # Tune pullback trigger, KC sequence, Stoch RSI, diagnostics, and strategy identity
|-- indicators.py              # Only if candle-pattern direction/shape normalization belongs outside signal_engine.py
|-- strategy_metrics.py        # Add/verify pullback outcome counts and blocker summaries
|-- journal.py                 # Verify pullback rows/export fields and prime-suppression visibility
|-- alerts.py                  # Verify Discord/operator alert payload preserves pullback signal type
`-- tests/
    |-- test_signal_engine.py
    |-- test_strategy_metrics.py
    `-- test_journal.py

.env.example                   # Document new env-backed pullback tuning knobs
dashboard/src/                 # Only if dashboard types/UI need new metric fields
```

**Structure Decision**: Keep the targeted tuning in the existing signal, metrics, journal, and config modules. The current code already has explicit CTI-v1.2 pullback helpers and tests, so this feature should refine those surfaces rather than introduce a separate strategy subsystem.

## Current Code Findings

- Attached baseline files are the authoritative evidence for this feature: `C:/Users/User/Downloads/tradegumi 20260605/signal-journal-all-2026-06-05.csv` and `C:/Users/User/Downloads/tradegumi 20260605/strategy-metrics-2026-06-01-to-2026-06-05.json`.
- The Signal Journal baseline has 92 rows, all `signal_type=continuation` and `strategy=CTI-v1.1-continuation-test`; it has zero journaled pullback rows despite 70 total prime-suppressed follow-on signals in the export.
- The metrics baseline covers `2026-06-01T00:00:00+00:00` through `2026-06-06T00:00:00+00:00`, with 128,966 total evaluated opportunities, 466 emitted, 18,710 rejected, 109,789 skipped, and 2,267 near misses.
- Metrics summary shows 1,542 pullback-type opportunities and 2 `CTI-v1.2-pullback` strategy counts, but those pullbacks are not present in the exported Signal Journal, so implementation must validate both emitted metrics and journaled alert rows.
- Pullback rule baseline from the metrics file: `pullback_trigger_candle` passes 1,342 / 18,713 (7.17%) and fails 17,371; `keltner_pullback_sequence` passes 3,405 / 18,713 (18.20%) and fails 15,308; `stoch_rsi` passes 6,596 / 18,713 (35.25%) and fails 12,117; `pullback_structure` passes 17,710 / 18,713 (94.64%); `pullback_15m_bridge` passes 30,164 / 30,164 (100%).
- Near-miss reasons in the metrics baseline are dominated by `pullback_trigger_candle_failed` (1,717), followed by `confidence` (211), `pullback_kc_sequence_failed` (177), `pullback_stoch_rsi_failed` (90), and `pullback_structure_failed` (72).
- `src/tradegumi/signal_engine.py` already has `PULLBACK_STRATEGY_VERSION = "CTI-v1.2-pullback"` and helper boundaries for pullback trend bridge, structure, Keltner sequence, trigger candle, and Stoch RSI.
- `_pullback_trigger()` currently depends on pattern flags only; issue #99 requires candle body/range and rejection-wick shape checks so valid hammer/shooting-star style candles pass without accepting generic or directionally weak candles.
- `_pullback_keltner_sequence()` already requires a prior outer-band break and a midline tolerance, but the plan must verify tolerance semantics, reporting context, and configurability against the current 18.20% pass-rate baseline.
- `_pullback_stoch_rsi()` already supports recent exhaustion memory over a short recent window; the plan must make the lookback and thresholds explicit, measurable, and covered by tests.
- Pullback MACD is currently recorded as `macd_soft_score`; this feature adds/validates an explicit configuration path for hard-block behavior only when enabled.
- `strategy_metrics.py` already stores `strategy`, `signal_type`, criterion rows, near misses, and prime-suppression summaries. This feature must add or verify pullback-specific aggregate counts without breaking existing exports.
- `journal.py` already exports `signal_type`, `pullback_trigger`, `pullback_bridge_status`, `pullback_rejection_reason`, and prime fields. This feature must ensure emitted pullbacks become rows when valid and suppressed pullbacks remain countable.

## Phase 0: Research

See [research.md](research.md) for local design decisions on trigger candle shape, value-area tolerance, exhaustion memory, MACD behavior, diagnostics, testing strategy, and use of the attached June 1-5 baseline data.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for pullback candidate, trigger candle profile, value-area sequence, exhaustion memory, diagnostic summary, alert, and journal/reporting state.

See [contracts/pullback-configuration.md](contracts/pullback-configuration.md), [contracts/signal-diagnostics.md](contracts/signal-diagnostics.md), and [contracts/reporting-exports.md](contracts/reporting-exports.md) for env settings, signal diagnostic criteria, and metrics/journal/export expectations.

See [quickstart.md](quickstart.md) for validation scenarios and targeted test commands.

Agent context was updated in [AGENTS.md](../../AGENTS.md) to point at this plan.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The design uses the constitution's documented strategy-version exception path, keeps required gates and stable blockers, and makes MACD soft-default explicit and test-backed. |
| II. Execution Layer Abstraction | PASS | No provider-specific or broker-specific behavior is introduced. |
| III. Risk-First | PASS | Risk and execution layers remain unchanged and downstream of any emitted signal. |
| IV. Observable by Default | PASS | Diagnostics and reporting contracts cover pass/fail blockers, alert/journal counts, and prime suppression. |
| V. Configuration-Driven Operations | PASS | All material tuning knobs are planned as env-backed settings and included in threshold-version hashing. |
| Security & Credential Hygiene | PASS | No secret handling changes. |
| Code Quality & Documentation | PASS | Helper docstrings and focused tests are required for changed signal and reporting behavior. |
| Pull Request Policy | PASS | Task generation must include reviewer handling from user or feature context. |

## Complexity Tracking

No constitution violations or complexity exceptions are required. The pullback MACD
soft-scoring behavior uses the constitution's documented strategy-version exception path.
