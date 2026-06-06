# Feature Specification: High-Value KC Band Pullbacks

**Feature Branch**: `017-tune-pullback-signals`  
**Created**: 2026-06-05  
**Status**: Draft  
**Input**: User description: "https://github.com/Gitchegumi/CTI_Scripts/issues/103"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Partial Retracement Outside Midline (Priority: P1)

As the strategy owner, I want the strategy to recognize a pullback when price has broken outside the Keltner Channel (KC) outer band, triggers a valid pullback trigger candle, and retraces back inside the outer KC band but does **not** make it all the way to the midline, provided trend momentum is still strong.

**Why this priority**: Catching strong continuation setups where the retracement is shallow is highly profitable. Waiting for price to reach the midline misses these high-value setups.

**Independent Test**: Replay a historical trend period where price breaks below the lower KC band, retraces up to cross the lower band but turns back down before reaching the midline, with a valid bearish trigger candle and negative MACD histogram. Verify a SELL `high_value_pullback` signal is emitted.

**Acceptance Scenarios**:

1. **Given** a Downtrend, price has moved below the lower KC band, price retraces into the lower KC band but does not reach the midline, a bearish trigger candle pattern is present, and the MACD histogram is less than 0, **When** evaluated, **Then** a SELL `high_value_pullback` signal is emitted.
2. **Given** an Uptrend, price has moved above the upper KC band, price retraces into the upper KC band but does not reach the midline, a bullish trigger candle pattern is present, and the MACD histogram is greater than 0, **When** evaluated, **Then** a BUY `high_value_pullback` signal is emitted.

---

### User Story 2 - Rejection Remaining Completely Outside Outer KC Band (Priority: P1)

As the strategy owner, I want the strategy to recognize extremely strong continuation pullbacks when price breaks outside the KC outer band, triggers a valid pullback trigger candle, but does **not** even return inside the outer KC band, provided trend momentum is still strong.

**Why this priority**: In very high-momentum trends, price does not even re-enter the outer KC band before resuming the trend. This is the most aggressive pullback setup and must be captured.

**Independent Test**: Replay a trend period where price breaks below the lower KC band, forms a bearish trigger candle whose high remains below the lower KC band, with a negative MACD histogram. Verify a SELL `high_value_pullback` signal is emitted.

**Acceptance Scenarios**:

1. **Given** a Downtrend, price has moved below the lower KC band, price remains entirely below the lower KC band, a bearish trigger candle pattern is present, and the MACD histogram is less than 0, **When** evaluated, **Then** a SELL `high_value_pullback` signal is emitted.
2. **Given** an Uptrend, price has moved above the upper KC band, price remains entirely above the upper KC band, a bullish trigger candle pattern is present, and the MACD histogram is greater than 0, **When** evaluated, **Then** a BUY `high_value_pullback` signal is emitted.

---

### User Story 3 - MACD Momentum Verification Gate (Priority: P1)

As the strategy owner, I want these aggressive, shallow pullbacks to require momentum alignment via the MACD histogram, rejecting the setup if momentum shows signs of fading (MACD histogram >= 0 for shorts, <= 0 for longs).

**Why this priority**: Because these pullbacks do not reach the value area (midline), they carry higher risk. Verifying that momentum is still strongly aligned reduces false signals on trend exhaustion.

**Independent Test**: Replay a trend period where price remains outside the outer band and forms a trigger candle, but the MACD histogram is >= 0 for a short or <= 0 for a long. Verify no signal is emitted.

**Acceptance Scenarios**:

1. **Given** a Downtrend, price is below the lower KC band, a bearish trigger candle pattern is present, but the MACD histogram is greater than or equal to 0, **When** evaluated, **Then** the signal is rejected.
2. **Given** an Uptrend, price is above the upper KC band, a bullish trigger candle pattern is present, but the MACD histogram is less than or equal to 0, **When** evaluated, **Then** the signal is rejected.

---

### User Story 4 - Existing Pullback Behavior Remains Intact (Priority: P2)

As the strategy owner, I want the existing midline pullback logic to continue functioning unchanged, ensuring deep-retracement pullbacks still generate normal pullback signals.

**Why this priority**: Deep pullbacks remain a core setup and should not be affected by the addition of the new shallow pullback conditions.

**Independent Test**: Replay a standard midline pullback setup and verify it triggers a `pullback` type signal.

**Acceptance Scenarios**:

1. **Given** a standard pullback to the midline zone that passes all existing rules, **When** evaluated, **Then** a `pullback` signal is emitted.

### Edge Cases

- **Trigger Candle Validation**: The trigger candle must satisfy all existing shape requirements (body-to-range ratio, rejection wick ratio) even if it remains outside the KC band.
- **Multiple Signals in Trend**: If multiple candles satisfy the high-value pullback conditions, standard cooldown and suppression rules must prevent double-entry.
- **No Prior Outer Band Breach**: If price did not move outside the KC outer band within the lookback window, no high-value pullback can trigger, even if MACD is aligned.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST detect a new signal type `"high_value_pullback"` when the high-value pullback conditions are met.
- **FR-002**: For Downtrends, high-value pullback conditions MUST require:
  - Price has broken below the lower KC band within the Keltner sequence lookback (`PULLBACK_KC_BREAK_LOOKBACK_BARS`).
  - The current trigger candle close is below the KC midline/center line.
  - The current MACD histogram is strictly less than 0 (`macd_current < 0`).
  - Stoch RSI, structure, and trigger candle shape requirements are satisfied.
- **FR-003**: For Uptrends, high-value pullback conditions MUST require:
  - Price has broken above the upper KC band within the Keltner sequence lookback (`PULLBACK_KC_BREAK_LOOKBACK_BARS`).
  - The current trigger candle close is above the KC midline/center line.
  - The current MACD histogram is strictly greater than 0 (`macd_current > 0`).
  - Stoch RSI, structure, and trigger candle shape requirements are satisfied.
- **FR-004**: High-value pullback logic MUST support both the case where price does not reach the KC midline but returns inside the outer KC band, and the case where price remains outside the outer KC band.
- **FR-005**: The Keltner pullback sequence check (`_pullback_keltner_sequence`) MUST return a result indicating if the high-value pullback sequence conditions are met, bypassing the `near_midline` requirement.
- **FR-006**: Existing normal pullback sequence check (prior break plus `near_midline`) MUST remain functional and continue to classify as `"pullback"`.
- **FR-007**: High-value pullback signals MUST be recorded in the Signal Journal, strategy metrics, and Discord alerts with `signal_type="high_value_pullback"`.

### Key Entities *(include if feature involves data)*

- **High-Value Pullback Candidate**: An evaluated pullback opportunity where price does not return to the midline, but starts outside the KC band and retains momentum direction.
- **High-Value Pullback Signal**: An emitted signal of type `"high_value_pullback"`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of simulated scenarios with price outside the KC outer band, a valid trigger candle, and matching MACD histogram sign result in a `"high_value_pullback"` signal.
- **SC-002**: 100% of scenarios where the MACD histogram is not aligned (e.g. >= 0 for Downtrend) do NOT result in a `"high_value_pullback"` signal.
- **SC-003**: Standard midline pullbacks continue to trigger and are classified as `"pullback"` in 100% of regression scenarios.
- **SC-004**: The Signal Journal log correctly includes the `"high_value_pullback"` type for the new setup.

## Assumptions

- **Symmetry**: Bullish/Uptrend high-value pullbacks are symmetric to the bearish/Downtrend requirements: they require price to have broken above the upper band, remain above the midline, and MACD histogram to remain above 0.
- **Suppression**: Standard suppression/cooldown rules (e.g. prime signal suppression) apply to `"high_value_pullback"` signals just like they do to normal `"pullback"` and `"continuation"` signals.
- **Execution parameters**: Standard stop loss and take profit calculations apply.
