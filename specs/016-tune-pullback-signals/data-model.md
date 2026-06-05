# Data Model: Tune Pullback Signal Alerts

## Pullback Candidate

Represents one evaluated opportunity before final signal emission.

**Fields**:

- `symbol`: Instrument identifier.
- `direction`: Intended trade direction, `BUY` or `SELL`.
- `strategy`: Expected pullback strategy identity.
- `signal_type`: `pullback`.
- `evaluated_at`: Candle-close or evaluation timestamp.
- `trend_context`: Larger-trend and bridge status used to allow or reject the pullback.
- `structure_context`: Higher-low/lower-high structure evidence.
- `value_area_context`: Prior outer-area move, current value-area distance, tolerance, and pass/fail state.
- `trigger_context`: Candle-shape and pattern evidence.
- `exhaustion_context`: Current and recent Stoch RSI evidence.
- `macd_context`: Soft confidence context by default; hard-block context only when explicitly enabled.
- `prime_suppression_context`: Whether an otherwise valid signal was suppressed by active prime-signal state.
- `final_decision`: `emitted`, `criteria_failed`, `suppressed`, or equivalent existing decision value.

**Validation Rules**:

- `direction` must match the trigger wick direction and trend context.
- A candidate cannot emit unless required trend, structure, value-area, trigger, and exhaustion gates pass.
- MACD cannot mark a candidate failed unless the explicit pullback MACD hard-block setting is enabled.

## Trigger Candle Profile

Represents candle-shape evidence for a pullback entry.

**Fields**:

- `pattern`: Approved pattern name such as `hammer`, `shooting_star`, `bullish_engulfing`, or `bearish_engulfing`.
- `body_size`: Absolute open-close distance.
- `full_range`: High-low distance.
- `body_to_range`: Body size divided by full range.
- `upper_wick`: High minus the larger of open/close.
- `lower_wick`: Smaller of open/close minus low.
- `rejection_wick_ratio`: Rejection wick divided by full range or body, according to the implemented setting.
- `close_position`: Close location within the candle range.
- `value_area_relation`: Whether the wick or close is near, through, or away from the value area.

**Validation Rules**:

- Full range must be positive.
- BUY triggers require lower-wick rejection; SELL triggers require upper-wick rejection.
- Body-to-range must be at or below the configured maximum.
- Directionally wrong or generic patterns fail.

## Value-Area Sequence

Represents a trend move followed by a pullback into the configured value area.

**Fields**:

- `prior_outer_break`: Whether price previously broke the trend-side outer band.
- `outer_break_lookback_bars`: Number of recent M5 bars searched.
- `midline`: Current value-area midline.
- `trigger_price`: Price used for distance evaluation.
- `distance_to_midline`: Absolute distance from trigger price to midline.
- `normalized_tolerance`: Effective accepted zone around the midline.
- `near_value_area`: Whether current price is inside the accepted zone.

**Validation Rules**:

- Prior outer break is required.
- Current value-area proximity is required.
- Tolerance must be derived from configured normalized values, not an unrelated hardcoded price distance.

## Exhaustion Memory

Represents Stoch RSI exhaustion evidence for a recent pullback window.

**Fields**:

- `k`: Current Stoch RSI K.
- `d`: Current Stoch RSI D.
- `recent_low`: Lowest recent K value for BUY pullbacks.
- `recent_high`: Highest recent K value for SELL pullbacks.
- `lookback_bars`: Number of recent bars considered.
- `recovery_or_roll_down`: Whether current momentum is moving away from exhaustion in the intended direction.

**Validation Rules**:

- BUY pullbacks pass on current oversold evidence or recent oversold memory with recovery.
- SELL pullbacks pass on current overbought evidence or recent overbought memory with roll-down.
- Stale exhaustion outside the configured window fails.

## Pullback Diagnostic Summary

Aggregates pullback behavior for metrics and exports.

**Fields**:

- `evaluated_count`
- `rejected_by_gate`: Counts keyed by stable blocker name.
- `near_miss_count`
- `near_miss_reason_counts`
- `emitted_count`
- `journaled_count`
- `prime_suppressed_count`
- `strategy_counts`
- `signal_type_counts`

**Validation Rules**:

- Counts must be filterable by reporting date range and optionally by symbol.
- Pullback and continuation counts must remain distinguishable.
- Prime suppression must not be mixed with ordinary rule-gate rejection.

## Pullback Alert / Journal Row

Represents an emitted pullback signal visible to operators.

**Fields**:

- `signal_id`
- `symbol`
- `direction`
- `strategy`
- `signal_type`
- `signal_timestamp`
- `entry_price`
- `stop_loss`
- `take_profit`
- `confidence`
- `pullback_trigger`
- `pullback_bridge_status`
- `pullback_rejection_reason`
- `prime_*` suppression and lifecycle fields when applicable

**Validation Rules**:

- Emitted pullback signals must use `signal_type=pullback`.
- Pullback rows must remain exportable through the existing Signal Journal export path.
- Suppressed follow-on signals must be countable through prime-suppression fields.
