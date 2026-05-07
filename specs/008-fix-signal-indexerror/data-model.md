# Data Model: Signal Stack Readiness

## M5 Candle Set

Represents raw candles returned for one candidate evaluation.

**Fields**:

- `raw_candle_count`: total M5 candles returned before closed-candle filtering.
- `closed_candle_count`: M5 candles whose close time is at or before evaluation time.
- `latest_raw_candle_time`: timestamp of the latest returned candle when available.
- `selected_closed_candle_time`: timestamp of the candle selected for signal evaluation when available.

**Validation Rules**:

- Raw count may be zero and must not cause indexing.
- Closed count must meet the signal stack's closed-candle requirement before signal rules run.
- The currently forming candle must not be selected as the closed candle.

## Indicator Window

Represents usable indicator rows after calculation, warmup, and null filtering.

**Fields**:

- `required_indicator_window`: minimum usable rows required by the signal stack.
- `available_indicator_window`: usable rows available for the selected closed-candle window.
- `indicator_timestamp`: timestamp associated with the final usable indicator row when available.
- `aligned_with_closed_candle`: whether the final usable indicator row matches the selected closed candle.

**Validation Rules**:

- Available usable rows must meet or exceed the required indicator window.
- Final usable indicator values must exist for StochRSI, MACD, and Keltner inputs before their values are indexed.
- If timestamps are available, the final usable row must align with the selected closed candle timestamp.

## Readiness Diagnostic

Represents a normal data-not-ready outcome before signal rules evaluate.

**Fields**:

- `stage`: `signal_stack`.
- `timeframe`: `M5`.
- `missing_input`: `last_closed_candle_or_indicator_window`.
- `error_type`: `DataNotReady`.
- `required_candles`, `available_candles`.
- `required_closed_candles`, `available_closed_candles`.
- `required_indicator_window`, `available_indicator_window`.
- `message`: operator-readable explanation.

**Validation Rules**:

- Must be returned for normal short-data readiness failures.
- Must not include raw candle payloads or credentials.
- Must be compatible with existing metrics JSON by adding fields rather than removing existing fields.

## Signal Decision Metadata

Represents how the candidate is classified after readiness validation.

**Fields**:

- `final_decision`: existing deferred or indeterminate state for data-not-ready outcomes.
- `decision_reason`: specific readiness reason such as `signal_stack_data_not_ready`.
- `first_blocker`: `signal_engine_data:missing` or `signal_stack:data_not_ready`.
- `all_blockers`: includes the specific readiness blocker.
- `blocking_layer`: `data_quality` or `signal_stack` according to existing summary conventions.
- `blocked_signal`: true for the required signal-engine data criterion when data is missing.

**State Transitions**:

- Trend candidate + missing readiness input -> data-not-ready decision metadata.
- Trend candidate + complete aligned readiness input -> candle-close gate and existing signal rules.
- Complete signal rules + failed required indicator criterion -> strategy rejected.
- Complete signal rules + all required criteria pass -> emitted candidate proceeds to existing downstream layers.
