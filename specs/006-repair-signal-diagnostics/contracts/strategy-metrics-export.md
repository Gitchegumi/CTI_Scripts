# Contract: Strategy Metrics Export

The strategy metrics export remains JSON-compatible. Existing fields stay present; this feature adds fields and clarifies values.

## Summary Object

Existing summary fields remain unchanged:

- `start`
- `end`
- `total_evaluated`
- `emitted_count`
- `rejected_count`
- `skipped_count`
- `indeterminate_count`
- `near_miss_count`
- `criterion_summaries`
- `top_blockers`
- `first_blocker`
- `all_blockers`
- `blocking_layer`
- `threshold_version_counts`
- `data_quality_warnings`

Added summary fields:

- `pipeline_funnel`: Object with stage counts for `total_evaluated`, `trend_skipped`, `trend_candidate_found`, `signal_data_complete`, `signal_data_missing`, `candle_close_gate_passed`, `candle_close_gate_waiting_or_failed`, `signal_rules_evaluated`, `signal_rejected`, `signal_emitted`, and `indeterminate`.
- `near_miss_reason_counts`: Object keyed by stable near-miss reason.
- `threshold_version_unknown_reasons`: Object keyed by stable unknown reason.

## Opportunity Object

Existing opportunity fields remain unchanged.

Added opportunity fields:

- `pipeline_state`: Stable stage classification.
- `near_miss_reason`: Null or a stable reason.
- `threshold_version_unknown_reason`: Null or a stable reason when `threshold_version` is unknown.

Required blocker behavior:

- Missing required signal data uses `final_decision = indeterminate`.
- Missing required signal data populates `decision_reason`, `first_blocker`, `all_blockers`, and `blocking_layer`.
- Rejected opportunities are reserved for strategy, confidence, or risk rules that could be evaluated and failed.

## Criterion Object

Existing criterion fields remain unchanged.

Added criterion fields:

- `diagnostic_state`: Stable state for evaluation, missing data, malformed data, waiting, not applicable, or engine error.
- `reason`: Stable reason for failure, blocker, or impossible evaluation.
- `context`: Compact object with debugging details.

Required criterion behavior:

- Required failed or missing criteria that block progression set `blocked_signal = true`.
- Required impossible evaluations explain why `passed` or `expected_pass` is null.
- Non-blocking failures explain why they are non-blocking.

## Candle Close Gate Context

When `criterion_name = candle_close_gate`, `context` includes these fields when available:

- `current_time`
- `candle_open_time`
- `candle_close_time`
- `seconds_until_close`
- `seconds_since_close`
- `timeframe`
- `gate_rule`
- `margin_units`

Stable gate reasons include:

- `candle_close_gate:passed`
- `candle_close_gate:waiting_for_close`
- `candle_close_gate:stale_candle`
- `candle_close_gate:missing_timing_data`
- `candle_close_gate:failed`

## Compatibility

- Consumers that ignore unknown fields must continue to work.
- Existing field names must not be removed or renamed.
- New fields must be serializable as JSON scalars, arrays, or objects.
