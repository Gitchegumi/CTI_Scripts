# Implementation Plan: Pullback Signal Bridge and Shock Suppression

**Branch**: `015-pullback-shock-filter` | **Date**: 2026-05-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/015-pullback-shock-filter/spec.md`

## Summary

Split the current CTI-v1.1 dual-path signal stack into explicit continuation and pullback paths. Keep continuation behavior and strategy labeling as `CTI-v1.1-continuation-test`. Add a new pullback bridge that can pass when current M15 LR has flattened during a retracement but recent M15 memory, the H1 anchor, M5 structure, Keltner pullback sequence, approved trigger candle, and Stoch RSI exhaustion support the setup. Tighten volatility shock behavior so active symbol suppression blocks all new entries during the suppression window while preserving clean-LR no-trade behavior when shock filtering removes too much data.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16 / React 19 dashboard only if strategy metrics UI types require follow-up
**Primary Dependencies**: Existing pandas/pandas-ta indicator stack; existing `ExecutionClient`, `Candle`, `VolatilityShockFilter`, `SignalEngine`, `StrategyMetrics`, and JSONL Signal Journal helpers
**Storage**: Existing JSONL Signal Journal; existing SQLite strategy metrics database; no new durable market-data store
**Testing**: pytest in `src/tradegumi/tests/`; dashboard build only if dashboard types/UI are changed
**Target Platform**: Docker Compose TradeGumi backend on TrueNAS host; local dashboard/API
**Project Type**: Python trading backend plus dashboard reporting
**Performance Goals**: Preserve 5-second signal-engine cadence; avoid extra provider candle fetches per symbol beyond existing cached H1/M15/M5 windows; keep metrics export usable for the default 7-day range
**Constraints**: No broker-specific logic in signal rules; no risk or execution bypass; no global strategy rename; all new thresholds env-var configurable; no source implementation before spec approval
**Scale/Scope**: Per-symbol M5/M15/H1 signal checks over the existing watchlist, typically tens of symbols

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS WITH SPECIFIED EXCEPTION | This feature intentionally changes signal gates. Pullback still requires a complete path: H1 anchor, 15m memory bridge, M5 structure, Keltner sequence, Stoch RSI, trigger candle, and risk. MACD is explicitly moved to soft scoring only for pullbacks. |
| II. Execution Layer Abstraction | PASS | Changes are in strategy/diagnostic modules and continue to consume broker-neutral `Candle` data through `ExecutionClient`. |
| III. Risk-First | PASS | No order placement, sizing, daily loss, drawdown, or position-limit behavior changes. Existing risk checks remain after signal generation. |
| IV. Observable by Default | PASS | Plan adds pullback-specific criteria, blockers, version labels, journal/export fields, and shock suppression diagnostics. |
| V. Configuration-Driven Operations | PASS | New memory, Keltner, Stoch RSI, trigger, and shock thresholds are env-var driven in `config.py`. |
| Security & Credential Hygiene | PASS | No new credentials or secret-bearing logs. |
| Code Quality & Documentation | PASS | Implementation tasks require docstrings for new/changed helpers and intention-revealing names for strategy diagnostics. |
| Pull Request Policy | PASS | Final task list includes DockeGumi reviewer PR task. |

## Project Structure

### Documentation (this feature)

```text
specs/015-pullback-shock-filter/
|-- spec.md
|-- plan.md
|-- tasks.md
|-- test-plan.md
|-- rollback-observability.md
`-- checklists/
    `-- requirements.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- config.py                  # Add env-driven pullback bridge/KC/Stoch/shock thresholds
|-- signal_engine.py           # Split explicit continuation/pullback paths, M15 memory bridge, pullback diagnostics, strategy labels
|-- volatility_shock.py        # M5/M15 threshold rules, body+range rule, suppression windows, all-entry blocking semantics
|-- indicators.py              # Add/normalize direction-specific approved trigger helpers if pandas-ta semantics need wrapping
|-- journal.py                 # Export/store pullback trigger, bridge, and shock suppression fields if not already present
|-- strategy_metrics.py        # Preserve strategy/signal_type from diagnostics; add pullback blocker summaries/export fields
|-- alerts.py                  # Verify callback/alert payloads preserve strategy and signal_type, update only if missing
|-- main.py                    # Ensure `diagnostic.to_opportunity()` receives emitted signal strategy/signal_type before persistence
`-- tests/
    |-- test_signal_engine.py
    |-- test_volatility_shock.py
    |-- test_strategy_metrics.py
    `-- test_journal.py
```

**Structure Decision**: Keep strategy behavior inside `signal_engine.py` for the first pass because continuation and pullback already live there. Add focused private helpers or small dataclasses only where they make pullback bridge, structure, Keltner sequence, and trigger diagnostics testable without broad refactors. Keep shock state in `volatility_shock.py`.

## Current Code Findings

- `src/tradegumi/signal_engine.py:310` `get_threshold_version()` already hashes CTI-v1.1 continuation/pullback thresholds but must include new pullback memory, KC sequence, trigger, Stoch, and shock thresholds.
- `src/tradegumi/signal_engine.py:620` `classify_trend_bias()` currently models 1H+15M continuation bias, while `classify_trend_decision()` at line 706 requires all three LR timeframes. Pullback needs a distinct bridge instead of relying on current all-timeframe classification.
- `src/tradegumi/signal_engine.py:1060` `_get_trend()` classifies trend before signal path evaluation and currently returns `trend=None` before pullback logic can consider recent 15m memory.
- `src/tradegumi/signal_engine.py:1176` `_get_signal()` currently mixes shared indicator calculation, continuation, and pullback logic in one method.
- `src/tradegumi/signal_engine.py:1644` pullback logic currently uses relaxed outer-band proximity and still requires MACD; this conflicts with the new prior-band-break plus midline retracement requirement and MACD-soft-only requirement.
- `src/tradegumi/signal_engine.py:1727` current pullback `Signal` emits strategy `CTI-v1.1-continuation-test`; this must become `CTI-v1.2-pullback` for pullbacks only.
- `src/tradegumi/signal_engine.py:1926` shock suppression currently blocks only when shock changed trend and shock direction matches signal direction. New behavior must block both continuation and pullback entries whenever symbol suppression is active.
- `src/tradegumi/volatility_shock.py:87`, `:123`, and `:158` detect single-, two-, and three-bar rules using shifted ATR; defaults are currently 3.0/4.0/5.0 and need M5/M15-specific true-range plus body/range defaults.
- `src/tradegumi/volatility_shock.py:315` filters LR candles at 2.5x ATR and `_get_trend()` already returns no trend when clean data is insufficient; preserve and test this behavior.
- `src/tradegumi/strategy_metrics.py:127` `EvaluatedOpportunity` has `strategy` and `signal_type`, but `SignalDiagnostic.to_opportunity()` in `signal_engine.py:266` does not populate strategy or signal type from the emitted signal. This is a metrics versioning risk.
- `src/tradegumi/journal.py:80` exports `strategy` and `signal_type`, and `append_signal()` stores them from the signal; add pullback-specific diagnostic fields if needed.
- `src/tradegumi/indicators.py:122` delegates candlestick detection to pandas-ta, while `candlestick_score()` at line 217 already treats hammer, shooting star, and engulfing as strong patterns. Pullback trigger logic must validate direction explicitly rather than relying on generic pattern presence.
- Existing tests in `src/tradegumi/tests/test_signal_engine.py:601` cover CTI-v1.1 continuation/pullback basics, but the existing pullback test uses outer-band proximity, requires MACD, and does not assert the new pullback strategy version.

## Phase 0: Research

No external research is required. The design is based on local inspection of the existing TradeGumi signal engine, volatility shock filter, metrics, journal, and tests. Implementation should avoid changing provider, risk, and execution behavior.

## Phase 1: Technical Design

### Strategy Versioning

- Add explicit constants near the `Signal`/engine surface:
  - continuation: `CTI-v1.1-continuation-test`
  - pullback: `CTI-v1.2-pullback`
- Ensure emitted `Signal.strategy`, `Signal.signal_type`, `SignalDiagnostic`, `EvaluatedOpportunity`, journal rows, callbacks, and exports preserve those values.
- Update `SignalDiagnostic.to_opportunity()` or the diagnostic construction sites so metrics no longer default emitted rows to `CTI-v1`/`pullback` when a continuation signal was emitted.

### Continuation Path

- Keep the existing continuation requirements close to current behavior:
  - 1h and 15m trend alignment remain important.
  - MACD remains allowed as a hard confirmation.
  - Keltner may continue to favor current midline/extension behavior.
  - Signal strategy remains exactly `CTI-v1.1-continuation-test`.
- Refactor only enough to isolate continuation criteria names and outputs from pullback criteria.

### Pullback Path

- Add a pullback trend bridge that evaluates:
  - H1 anchor aligned and above threshold.
  - Recent M15 LR aligned within `PULLBACK_15M_MEMORY_CANDLES`, default 4 closed M15 candles.
  - Current M15 flat, weakly aligned, or mildly below threshold is allowed.
  - Current M15 strongly opposite is rejected using `PULLBACK_15M_STRONG_OPPOSITE_MULTIPLIER`, default 1.25x normal M15 threshold.
  - M5 structure supports the intended direction.
- Add M5 pullback structure:
  - Long: recent HH/HL and protected higher low not violated.
  - Short: recent LH/LL and protected lower high not violated.
  - Proposed `PULLBACK_STRUCTURE_LOOKBACK_BARS`, default 12 M5 closed candles.
- Add Keltner pullback sequence:
  - Prior outer band break in trend direction within `PULLBACK_KC_BREAK_LOOKBACK_BARS`, default 10 M5 bars.
  - Current trigger candle near KC midline within `PULLBACK_KC_MIDLINE_TOLERANCE_ATR`, default 0.35 ATR.
  - Optional channel-width cap/fallback `PULLBACK_KC_MIDLINE_TOLERANCE_CHANNEL_WIDTH`, default 0.25.
- Add trigger candle gate:
  - Long: hammer or bullish engulfing.
  - Short: shooting star or bearish engulfing.
  - No generic candlestick confirmation may pass this gate.
- Add Stoch RSI pullback gate:
  - Long: K or D <= 25, or recent K low <= 30 and K crosses/rises.
  - Short: K or D >= 75, or recent K high >= 70 and K crosses/rolls down.
- MACD should be recorded as `macd_soft_score` or equivalent confidence context for pullbacks and must not be a required criterion.

### Volatility Shock Filter

- Add timeframe-aware shock thresholds:
  - `SHOCK_M5_TRUE_RANGE_ATR_MULTIPLE`, default 4.0.
  - `SHOCK_M15_TRUE_RANGE_ATR_MULTIPLE`, default 3.5.
  - `SHOCK_BODY_ATR_MULTIPLE`, default 3.0.
  - `SHOCK_BODY_RANGE_ATR_MULTIPLE`, default 3.5.
  - `SHOCK_M5_SUPPRESSION_CANDLES`, default 4 M5 candles.
  - `SHOCK_M15_SUPPRESSION_CANDLES`, default 3 M15 candles, translated to M5-equivalent time where needed.
- Keep shifted/prior ATR baselines.
- In `SignalEngine.check_symbol()`, active shock suppression should return a skipped diagnostic before signal stack for both continuation and pullback, regardless of shock direction or whether filtered LR changed trend.
- Preserve clean-LR behavior: if filtering removes too much data, return no-trade/indeterminate and do not fall back to raw LR.

### Metrics and Journal

- Add stable criterion/blocker names for:
  - `pullback_1h_anchor_failed`
  - `pullback_15m_bridge_allowed`
  - `pullback_15m_bridge_strong_opposite`
  - `pullback_structure_failed`
  - `pullback_kc_sequence_failed`
  - `pullback_trigger_candle_failed`
  - `pullback_trigger_hammer`
  - `pullback_trigger_shooting_star`
  - `pullback_trigger_bullish_engulfing`
  - `pullback_trigger_bearish_engulfing`
  - `pullback_stoch_rsi_failed`
  - `pullback_macd_soft_score`
  - `volatility_shock_suppression`
- Ensure `strategy_metrics.py` summary/export can group/filter by `strategy` and `signal_type`; add summary counts if absent.
- Ensure `journal.py` exports retain `strategy` and `signal_type`, and add pullback bridge/trigger fields if the signal carries them.

## Phase 2: Implementation Plan

1. Add config defaults and `.env.example` documentation for pullback bridge, Keltner sequence, Stoch RSI, trigger, and shock thresholds.
2. Add tests first in `src/tradegumi/tests/test_signal_engine.py` for allowed long/short pullbacks, version labels, MACD soft behavior, and reject cases.
3. Add tests in `src/tradegumi/tests/test_volatility_shock.py` for M5/M15 thresholds, body/range rule, suppression windows, and below-threshold non-suppression.
4. Add metrics/journal tests in `src/tradegumi/tests/test_strategy_metrics.py` and `src/tradegumi/tests/test_journal.py` for strategy/signal-type distinction and pullback/shock export fields.
5. Refactor `signal_engine.py` to compute shared indicator context, then call explicit continuation and pullback path helpers.
6. Implement the pullback trend memory bridge using existing candle windows; avoid additional provider fetches.
7. Implement M5 structure, Keltner sequence, trigger candle, and Stoch RSI gates with stable diagnostics.
8. Adjust shock suppression in `check_symbol()` so active suppression blocks all entries for the symbol.
9. Update `volatility_shock.py` thresholds and suppression-window calculations.
10. Update metrics/journal propagation so emitted continuation and pullback rows preserve exact strategy labels.
11. Run targeted pytest suites and update docs if operator-facing field names change.

## Test Plan

See [test-plan.md](test-plan.md).

## Rollback and Observability

See [rollback-observability.md](rollback-observability.md).

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS WITH SPECIFIED EXCEPTION | The feature deliberately redefines pullback gates while retaining a complete required path and preserving continuation behavior. |
| II. Execution Layer Abstraction | PASS | No broker-specific imports or execution changes are planned. |
| III. Risk-First | PASS | Risk checks remain after any emitted signal and before orders. |
| IV. Observable by Default | PASS | Pullback bridge, trigger, blocker, version, and shock suppression diagnostics are required. |
| V. Configuration-Driven Operations | PASS | All thresholds are planned as env-var backed config. |
| Security & Credential Hygiene | PASS | No secret handling changes. |
| Code Quality & Documentation | PASS | Helper boundaries and docstrings are explicit implementation tasks. |
| Pull Request Policy | PASS | Included in tasks. |

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| --- | --- | --- |
| Signal Integrity constitution currently says Layer 0 is 15m + 5m LR agreement and Layer 2 includes MACD as required. | This feature intentionally introduces a pullback path where recent 15m memory can bridge current flat 15m and MACD is soft-only. | Keeping the old all-current-LR/MACD requirements would continue missing the intended pullback entries. |
