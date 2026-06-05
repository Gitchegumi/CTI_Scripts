# Contract: Reporting And Exports

## Strategy Metrics Summary

For every requested reporting period with pullback evaluation enabled, the summary must expose or preserve:

- `signal_type_counts.pullback`
- `strategy_counts.CTI-v1.2-pullback`
- pullback candidates evaluated
- pullback candidates rejected by gate
- pullback near misses
- pullback alerts emitted
- pullback alerts journaled
- pullback alerts suppressed by prime-signal logic
- `near_miss_reason_counts` keyed by stable pullback reason names
- criterion summaries for trigger candle, Keltner pullback sequence, Stoch RSI, structure, and MACD soft/hard behavior

## Strategy Metrics Opportunity Rows

Opportunity rows must preserve:

- `strategy`
- `signal_type`
- `direction`
- `final_decision`
- `near_miss`
- `near_miss_reason`
- `threshold_version`
- criterion result contexts for pullback gates

## Signal Journal Rows

Emitted pullback alerts must produce exportable journal rows with:

- `strategy=CTI-v1.2-pullback`
- `signal_type=pullback`
- `pullback_trigger`
- `pullback_bridge_status`
- `pullback_rejection_reason` when relevant
- prime-suppression lifecycle fields already used by the journal

## Discord / Operator Alerts

Operator-facing alerts must preserve pullback identity:

- Pullback signal type must be visible in the signal payload or message text.
- Strategy identity must remain distinguishable from continuation.
- No continuation-only label should be used for pullback alerts.

## Validation Expectations

- Representative replay data that contains valid pullbacks must produce at least one journaled pullback row.
- Continuation summary/export behavior must remain distinguishable and regression-tested.
- Prime-suppressed pullbacks must count as suppressed, not as ordinary gate failures.
