# Data Model: Repair Signal Pipeline Diagnostics

## Evaluated Opportunity

Represents one symbol evaluation in the strategy metrics export.

**Existing fields retained**: `id`, `evaluated_at`, `symbol`, `timeframe`, `mode`, `strategy`, `direction`, `trend`, `final_decision`, `decision_reason`, `confidence`, `failed_criteria_count`, `near_miss`, `data_complete`, `data_quality_notes`, `threshold_version`, `created_at`, `criteria`, `first_blocker`, `all_blockers`, `blocking_layer`, `trend_decision`.

**Added or clarified fields**:

- `pipeline_state`: Stable stage classification such as `trend_skipped`, `trend_candidate_signal_data_missing`, `trend_candidate_candle_close_waiting`, `trend_candidate_candle_close_failed`, `signal_rules_evaluated`, `signal_rejected`, `signal_emitted`, or `indeterminate`.
- `near_miss_reason`: Null unless `near_miss = true`; stable reason explaining the near miss.
- `threshold_version_unknown_reason`: Present when `threshold_version = unknown` and a practical explanation is available.

**Validation rules**:

- Missing or incomplete signal data keeps `final_decision = indeterminate`.
- Rule failures that block signal progression use `final_decision = rejected`.
- No valid trend remains `final_decision = skipped`.
- Open-candle waiting must not automatically set `near_miss = true`.

## Criterion Diagnostic

Represents one criterion in an opportunity's `criteria` array.

**Existing fields retained**: `criterion_name`, `layer`, `measured_value`, `threshold_value`, `threshold_operator`, `passed`, `expected_pass`, `pass_mismatch`, `margin`, `normalized_margin`, `required`, `blocked_signal`, `data_quality`.

**Added or clarified fields**:

- `diagnostic_state`: `evaluated`, `missing_data`, `malformed_data`, `waiting`, `not_applicable`, or `engine_error`.
- `reason`: Stable reason for failures or impossible evaluations.
- `context`: Compact diagnostic context such as expected input name, timeframe, available count, current timestamp, candle timestamps, or indicator column availability.

**Validation rules**:

- Required missing or malformed criteria that stop progression set `blocked_signal = true`.
- Required failed criteria that stop progression set `blocked_signal = true`.
- A non-blocking failure must include a reason explaining why it does not stop progression.
- `passed = null` with `expected_pass = true` requires an explicit diagnostic state explaining why evaluation was impossible.

## Candle Close Gate Diagnostic

Specialized criterion context for `candle_close_gate`.

**Fields**:

- `current_time`
- `candle_open_time`
- `candle_close_time`
- `seconds_until_close`
- `seconds_since_close`
- `timeframe`
- `gate_rule`
- `margin`
- `margin_units`
- `normalized_margin`
- `reason`

**State transitions**:

- Before close: `waiting_for_close` or equivalent explicit waiting/deferred state.
- At or after close within allowed rule: `passed`.
- After close but outside allowed rule or with stale timing: explicit failure reason such as `stale_candle`.
- Missing timestamps: data-quality blocker rather than misleading margin math.

## Blocker

Stable reason that prevents progression.

**Fields**:

- `first_blocker`: First blocker in pipeline order.
- `all_blockers`: All blockers detected for the opportunity.
- `blocking_layer`: Layer for the first blocker, such as `trend`, `data_quality`, `signal_engine`, `timing`, `signal_stack`, `confidence`, or `risk`.

**Validation rules**:

- Indeterminate data-quality outcomes populate blocker fields.
- Top blockers include rejected, skipped, and indeterminate opportunities that have blockers.
- Blocker names remain stable enough for report-to-report comparison.

## Summary Funnel

Aggregate view of stage counts.

**Fields**:

- `total_evaluated`
- `trend_skipped`
- `trend_candidate_found`
- `signal_data_complete`
- `signal_data_missing`
- `candle_close_gate_passed`
- `candle_close_gate_waiting_or_failed`
- `signal_rules_evaluated`
- `signal_rejected`
- `signal_emitted`
- `indeterminate`

**Validation rules**:

- Counts reconcile with exported opportunities for the selected range.
- The funnel makes the largest candidate dropout stage visible.

## Near Miss Summary

Aggregate view of near misses.

**Fields**:

- `near_miss_count`
- `near_miss_reason_counts`

**Validation rules**:

- `near_miss_count` equals the sum of `near_miss_reason_counts`.
- Ordinary open-candle waiting is not counted unless it satisfies a documented near-miss rule.

## Threshold Version Summary

Aggregate threshold-version provenance.

**Fields**:

- `threshold_version_counts`
- `threshold_version_unknown_reasons`

**Validation rules**:

- Existing counts remain present.
- Unknown rows include best-effort reasons when practical.
