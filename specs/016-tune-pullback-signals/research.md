# Research: Tune Pullback Signal Alerts

## Decision: Use explicit candle-shape math in addition to pattern names

**Rationale**: Issue #99 points to `pullback_trigger_candle` as the largest choke point and asks for hammer/shooting-star style rejection with body less than roughly 33% of total candle movement. Pattern flags alone can miss acceptable rejection candles or accept candles without the intended wick/body relationship. The trigger gate should use candle body, total range, upper wick, lower wick, close location, and direction relative to the value area.

**Alternatives considered**:

- Pattern-name-only trigger: simple, but it is the current weak point and does not expose enough tuning context.
- Lower the existing trigger threshold globally: faster, but risks accepting directionally weak candles without explaining why.
- Add all candlestick patterns: rejected because the spec asks for conservative rejection candles, not broader candlestick confirmation.

## Decision: Keep value-area sequence as prior outer-band move plus configurable midline zone

**Rationale**: The existing pullback concept is valid: a pullback should follow a prior trend-side outer-band move, then return toward the Keltner midline or comparable value area. The current pass rate indicates tolerance or timing may be too tight, so the implementation should preserve prior outer-band evidence while making the midline zone explicit, normalized, and reported.

**Alternatives considered**:

- Require exact midline contact: rejected because it can miss valid pierces, near touches, and fast rejection candles.
- Remove prior outer-band requirement: rejected because it would blur trend pullbacks with ordinary range retracements.
- Use a fixed price-distance tolerance: rejected because symbols and instruments have different volatility scales.

## Decision: Treat Stoch RSI as exhaustion memory, not current-bar perfection

**Rationale**: Pullbacks often begin to reject after recent oversold/overbought evidence has already appeared. Requiring the current bar to be perfect can make the signal arrive late or fail entirely. The gate should support current exhaustion or recent exhaustion with recovery/roll-down evidence inside a configurable lookback window.

**Alternatives considered**:

- Require current crossover only: rejected because it is too strict for the intended earlier entry.
- Remove Stoch RSI from pullback gating: rejected because the user wants exhaustion/rejection, not random retracement alerts.
- Use broad momentum score only: rejected because stable blocker names and thresholds are needed for diagnostics.

## Decision: MACD is soft by default with explicit opt-in hard-block mode

**Rationale**: The spec states MACD should not be a hard pullback entry filter by default. MACD remains useful as confidence and diagnostic context, and an explicit env-backed hard-block option lets the operator compare behavior if needed without changing code.

**Alternatives considered**:

- Keep MACD hard-required: rejected because it undermines the desired earlier pullback entry.
- Remove MACD from diagnostics: rejected because it removes useful tuning evidence.
- Hard-disable MACD forever: rejected because the operator may want a conservative comparison mode.

## Decision: Add pullback-specific outcome counts to metrics using existing persistence

**Rationale**: The repository already stores evaluated opportunities, criterion results, near-miss reasons, strategy counts, signal-type counts, and prime suppression summaries. The feature should build on those tables and summaries rather than create a parallel reporting store.

**Alternatives considered**:

- Add a new pullback report file: rejected because it creates another source of truth.
- Infer all counts from journal rows only: rejected because rejected and near-miss candidates never become journal rows.
- Use logs only: rejected because logs are not durable, filterable reporting artifacts.

## Decision: Test with focused fixtures and representative replay data

**Rationale**: The risky behavior is rule qualification. Unit fixtures should cover exact gate behavior and blocker naming, while replay/simulation data validates that representative periods now produce pullback rows without flooding invalid setups.

**Alternatives considered**:

- Only run historical replay: too coarse to diagnose which gate regressed.
- Only run unit tests: not enough to prove issue #99's journal/Discord outcome improves.
- Tune thresholds manually from one sample: rejected because the issue warns against blindly lowering every threshold.

## Decision: Treat the June 1-5 attached files as the measurable baseline

**Rationale**: The user supplied the relevant data files for this spec. `signal-journal-all-2026-06-05.csv` proves the operator-visible alert stream has 92 continuation rows and zero pullback rows. `strategy-metrics-2026-06-01-to-2026-06-05.json` proves the engine evaluated pullback-type opportunities and records the actual choke points: trigger candle 7.17% pass rate, Keltner pullback sequence 18.20% pass rate, Stoch RSI 35.25% pass rate, structure 94.64% pass rate, and 15m bridge 100% pass rate.

**Alternatives considered**:

- Use only the GitHub issue summary: rejected because the supplied metrics file covers June 1-5 and has updated aggregate counts.
- Use only the journal export: rejected because it cannot explain rejected and near-miss pullback candidates.
- Use only the metrics export: rejected because operator-facing success requires actual journaled/Discord pullback rows.
