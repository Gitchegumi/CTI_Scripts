# Feature Specification: Pullback Signal Bridge and Shock Suppression

**Feature Branch**: `015-pullback-shock-filter`
**Created**: 2026-05-30
**Status**: Draft
**Input**: User description: "Fix pullback signal detection so valid trend pullbacks can fire earlier, and fix the volatility shock filter so major news-like candles actually suppress unsafe entries without becoming overly sensitive. Preserve continuation version CTI-v1.1-continuation-test and introduce pullback version CTI-v1.2-pullback."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Earlier Valid Pullbacks (Priority: P1)

As the strategy owner, I want pullback entries to be evaluated separately from continuation entries so a valid trend pullback can fire while the current 15m LR is flat or weak from the retracement, provided the 1h anchor and recent 15m trend memory still support the trade.

**Why this priority**: The current engine mostly catches continuation entries after the move resumes, missing the intended pullback setup near the Keltner midline.

**Independent Test**: Feed controlled long and short pullback market states with recent aligned 15m trend memory, current flat 15m, intact 5m structure, prior outer Keltner break, midline retracement, approved trigger candle, and Stoch RSI exhaustion. The engine emits a pullback signal before continuation conditions are required.

**Acceptance Scenarios**:

1. **Given** a recent 15m uptrend, current 15m flat, valid 1h uptrend, intact 5m HH/HL, prior upper Keltner break, midline pullback, hammer candle, and oversold Stoch RSI, **When** the symbol is evaluated, **Then** a BUY pullback signal is allowed with strategy `CTI-v1.2-pullback`.
2. **Given** the same long setup with a bullish engulfing trigger instead of a hammer, **When** the symbol is evaluated, **Then** a BUY pullback signal is allowed with strategy `CTI-v1.2-pullback`.
3. **Given** a recent 15m downtrend, current 15m flat, valid 1h downtrend, intact 5m LH/LL, prior lower Keltner break, midline pullback, shooting star candle, and overbought Stoch RSI, **When** the symbol is evaluated, **Then** a SELL pullback signal is allowed with strategy `CTI-v1.2-pullback`.
4. **Given** the same short setup with a bearish engulfing trigger instead of a shooting star, **When** the symbol is evaluated, **Then** a SELL pullback signal is allowed with strategy `CTI-v1.2-pullback`.

---

### User Story 2 - Preserve Continuation Versioning (Priority: P1)

As the strategy owner, I want continuation and pullback outputs to carry different strategy names so journal exports and metrics can separate CTI-v1.1 continuation behavior from CTI-v1.2 pullback behavior.

**Why this priority**: The current code already labels continuation signals as `CTI-v1.1-continuation-test`; pullback behavior must not globally rename or blur that existing strategy output.

**Independent Test**: Evaluate controlled continuation and pullback setups in the same reporting period and verify signals, journal rows, callback payloads, and strategy metrics preserve distinct `strategy` and `signal_type` values.

**Acceptance Scenarios**:

1. **Given** a continuation signal is emitted, **When** the signal is journaled and recorded in metrics, **Then** its strategy remains exactly `CTI-v1.1-continuation-test` and its signal type is `continuation`.
2. **Given** a pullback signal is emitted, **When** the signal is journaled and recorded in metrics, **Then** its strategy is exactly `CTI-v1.2-pullback` and its signal type is `pullback`.
3. **Given** strategy metrics or Signal Journal exports include both signal types, **When** the data is grouped or filtered, **Then** continuation and pullback rows remain distinguishable by strategy and signal type.

---

### User Story 3 - Volatility Shock Blocks Unsafe Entries (Priority: P1)

As the strategy owner, I want major abnormal candles to suppress all new entries for the affected symbol so news-like spikes cannot create unsafe continuation or pullback signals.

**Why this priority**: Current shock diagnostics can mark a symbol as shocked while still allowing entries unless direction and trend-change conditions line up, which does not reliably protect the strategy.

**Independent Test**: Feed M5 and M15 candles with true range/body multiples above and below configured thresholds, then evaluate continuation and pullback candidates during the suppression window.

**Acceptance Scenarios**:

1. **Given** an M5 candle has true range at least 4.0x prior ATR, **When** any new entry is evaluated during the configured suppression window, **Then** both continuation and pullback entries are blocked for that symbol.
2. **Given** an M15 candle has true range at least 3.5x prior ATR, **When** any new entry is evaluated during the translated suppression window, **Then** both continuation and pullback entries are blocked for that symbol.
3. **Given** a candle range/body is below the configured shock thresholds, **When** a valid signal is evaluated, **Then** shock suppression does not block the entry.
4. **Given** shock candle filtering leaves insufficient clean LR candles, **When** trend classification runs, **Then** the symbol is treated as no-trade rather than falling back to contaminated raw LR.

---

### User Story 4 - Explain Pullback Rejections (Priority: P2)

As the strategy owner, I want metrics and journal exports to show exactly why pullback candidates failed so I can tune the strategy without mistaking missing diagnostics for bad market conditions.

**Why this priority**: Pullback logic adds new gates that need reviewable blockers: 1h anchor, 15m bridge, 5m structure, Keltner sequence, trigger candle, Stoch RSI, and shock suppression.

**Independent Test**: Run reject-case fixtures and verify metrics/export rows contain stable blocker names and diagnostic contexts for each pullback-specific gate.

**Acceptance Scenarios**:

1. **Given** a pullback candidate fails the 15m bridge because current 15m is strongly opposite, **When** metrics are recorded, **Then** the first blocker identifies strong opposite 15m rejection.
2. **Given** a pullback candidate lacks a prior Keltner band break, violates structure, has an unapproved trigger candle, or lacks Stoch RSI exhaustion, **When** metrics are recorded, **Then** the matching pullback-specific blocker is visible in strategy metrics and exports.
3. **Given** MACD is negative for a valid pullback, **When** all required pullback gates pass, **Then** MACD may reduce confidence but does not appear as a hard blocker.

### Edge Cases

- Current 15m LR is flat or weakly aligned after a recent aligned 15m trend: pullback bridge may pass if 1h and 5m structure remain valid.
- Current 15m LR is strongly opposite the 1h anchor: pullback bridge must fail even if recent memory was aligned.
- Pullback breaks the most recent higher low or lower high: structure must fail.
- Prior outer Keltner break is missing: Keltner sequence must fail even if price is currently near the midline.
- Trigger candle is generic or directionally wrong: pullback trigger must fail.
- Bullish or bearish engulfing must be directionally validated, not accepted solely because a generic engulfing column appears.
- Shock suppression is active while trend is still classifiable: suppression blocks entries before signal emission.
- Shock filtering removes too much data: classify as no-trade/indeterminate with clear diagnostics instead of using raw LR.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST evaluate continuation and pullback entries through separate strategy paths with separate required gates.
- **FR-002**: Continuation signals MUST keep current-style trend-following behavior where 1h and 15m alignment remain important, MACD may remain a hard confirmation, Keltner logic may favor breakout/extension behavior, and emitted continuation signals use exactly `CTI-v1.1-continuation-test`.
- **FR-003**: Pullback signals MUST use exactly `CTI-v1.2-pullback` and MUST NOT cause continuation signals to be renamed, shortened, or globally upgraded to v1.2.
- **FR-004**: Pullback evaluation MUST require a valid 1h trend anchor aligned with the intended direction.
- **FR-005**: Pullback evaluation MUST allow current 15m LR to be flat, weakly aligned, or mildly below strength threshold when 15m LR was aligned within the configured recent closed-candle memory window.
- **FR-006**: Pullback evaluation MUST reject current 15m LR when it is strongly opposite the intended direction.
- **FR-007**: Pullback evaluation MUST require intact 5m structure: HH/HL for long pullbacks and LH/LL for short pullbacks.
- **FR-008**: Long pullbacks MUST require prior upper Keltner Channel break within a configured recent M5 lookback, retracement near the Keltner midline, and no violation of the recent higher low.
- **FR-009**: Short pullbacks MUST require prior lower Keltner Channel break within a configured recent M5 lookback, retracement near the Keltner midline, and no violation of the recent lower high.
- **FR-010**: Long pullback trigger candles MUST be limited to hammer or bullish engulfing.
- **FR-011**: Short pullback trigger candles MUST be limited to shooting star or bearish engulfing.
- **FR-012**: Existing hammer and shooting star rules MUST be reused where present, and engulfing triggers MUST be directionally validated.
- **FR-013**: Generic candlestick confirmation MUST NOT pass the pullback trigger gate unless it is one of the approved direction-specific patterns.
- **FR-014**: Pullback evaluation MUST require Stoch RSI exhaustion or recovery/roll-down from exhaustion using configurable thresholds.
- **FR-015**: MACD MUST NOT be a hard blocker for pullback entries; it may only affect confidence or diagnostics.
- **FR-016**: Threshold/version hash logic MUST include all new pullback-specific thresholds and shock thresholds that materially affect signal behavior.
- **FR-017**: Volatility shock detection MUST identify abnormal candles using prior ATR so the shock candle does not inflate its own baseline.
- **FR-018**: Volatility shock suppression MUST block both continuation and pullback entries for the affected symbol while suppression is active.
- **FR-019**: Volatility shock suppression MUST NOT require shock direction to match the candidate direction and MUST NOT require the shock to change the trend before blocking entries.
- **FR-020**: Shock filtering for LR MUST NOT permanently poison trend calculations; if not enough clean candles remain, the engine MUST classify the opportunity as no-trade/indeterminate rather than falling back to raw LR.
- **FR-021**: Strategy metrics MUST expose pullback-specific blockers for 1h trend, 15m bridge, strong opposite 15m, 5m structure, Keltner sequence, trigger candle, Stoch RSI, MACD soft score, and shock suppression.
- **FR-022**: Signal Journal exports MUST include enough fields to distinguish continuation and pullback signal type, strategy version, approved trigger candle type, pullback bridge status, and shock suppression diagnostics.
- **FR-023**: Tests MUST cover allowed long and short pullbacks, continuation version preservation, required reject cases, shock suppression, and below-threshold shock non-suppression.

### Key Entities *(include if feature involves data)*

- **Continuation Signal**: A trend-following signal emitted by the existing continuation logic with strategy `CTI-v1.1-continuation-test` and signal type `continuation`.
- **Pullback Signal**: A signal emitted by the new pullback logic after trend memory, 5m structure, Keltner sequence, trigger candle, and Stoch RSI gates pass; strategy `CTI-v1.2-pullback`, signal type `pullback`.
- **15m Trend Memory**: Recent closed-M15 evidence that the 15m trend was aligned before the current pullback flattened or weakened the current 15m LR.
- **Pullback Structure State**: 5m HH/HL or LH/LL context plus the most recent protected higher low/lower high.
- **Keltner Pullback Sequence**: Prior outer-band break in trend direction, retracement toward midline, and valid trigger candle near the midline.
- **Pullback Trigger Candle**: Approved pattern for pullback entry: hammer, bullish engulfing, shooting star, or bearish engulfing with directional validation.
- **Volatility Shock Suppression State**: Per-symbol suppression window generated from abnormal M5/M15 candles, with timeframe, candle time, ATR multiple, suppression until, and candles remaining.
- **Strategy Diagnostic Opportunity**: Metrics record that must preserve strategy, signal type, threshold hash, criteria, blockers, and shock diagnostics.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All specified pullback long and short allowed-case tests emit `CTI-v1.2-pullback` signals.
- **SC-002**: All continuation regression tests continue to emit `CTI-v1.1-continuation-test` when a continuation signal is produced.
- **SC-003**: 100% of required pullback reject-case tests identify the expected first blocker or blocker category in metrics.
- **SC-004**: 100% of active shock suppression tests block both continuation and pullback candidates while below-threshold shock tests do not suppress.
- **SC-005**: Strategy metrics and Signal Journal export fixtures preserve distinct strategy and signal type values for continuation and pullback rows.
- **SC-006**: Threshold version hash changes when any configured pullback-specific threshold changes and remains stable when unrelated runtime state changes.

## Assumptions

- The primary user is the strategy owner/operator reviewing signals, metrics, and Signal Journal exports.
- Existing execution, risk, watchlist, and market-data provider behavior remain out of scope except where they consume signal diagnostics.
- Defaults should be conservative: start with 4 closed M15 memory candles, 1.25x strong-opposite 15m threshold, 10 M5 Keltner-break lookback bars, 0.35 ATR midline tolerance capped by 25% channel width, M5 shock true-range threshold 4.0x ATR, M15 shock true-range threshold 3.5x ATR, and combined body/range shock rule at body >= 3.0x ATR and range >= 3.5x ATR.
- Existing pandas-ta candlestick pattern output is available for hammer, shooting star, and engulfing detection; if pattern semantics differ from the comments in `indicators.py`, implementation must normalize direction in tests.
- The first implementation pass should remain alert/demo safe and must be reviewed before any funded/live promotion.
