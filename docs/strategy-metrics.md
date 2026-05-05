# Strategy Metrics Export Guide

Strategy metrics explain why each evaluated opportunity emitted, rejected, skipped, or ended indeterminate. They are diagnostic evidence only; they do not tune thresholds or make the bot trade more often.

## Trend Decision

`trend_decision` explains the trend filter after linear regression values are measured.

- `strength_passed_1h`, `strength_passed_15m`, and `strength_passed_5m` show whether each timeframe met its absolute strength threshold.
- `direction_1h`, `direction_15m`, and `direction_5m` show the sign of each regression value as `up`, `down`, `flat`, `missing`, or `invalid`.
- `directions_agree` is true only when all three directions are the same actionable direction.
- `strengths_all_passed` is true only when all three strength checks passed.
- `trend_classification_input` records the regression values and thresholds used for classification.
- `trend_classification_output` records `trend_result`, `final_direction`, and `no_trend_reason`.

## No-Trend Reasons

- `insufficient_strength_1h`: only 1h trend strength failed.
- `insufficient_strength_15m`: only 15m trend strength failed.
- `insufficient_strength_5m`: only 5m trend strength failed.
- `multiple_insufficient_strength`: more than one trend strength failed.
- `direction_conflict`: all strengths passed, but 1h/15m/5m directions did not agree.
- `missing_data`: one or more LR values were unavailable.
- `invalid_lr_result`: one or more LR values were non-finite or malformed.
- `flat_after_classification`: inputs looked usable but classification still produced flat.
- `unknown`: fallback when a more specific reason cannot be determined.

## Criterion Auditing

`expected_pass` is recalculated from `measured_value`, `threshold_value`, and `threshold_operator` when possible. `pass_mismatch` is true when the recalculated value differs from the stored `passed` value. `blocked_signal` is true when a failed required criterion stopped signal generation.

## Blockers

`first_blocker` is the first known blocker for an opportunity. `all_blockers` lists every known blocker, including trend classification reasons such as `trend:direction_conflict`. `blocking_layer` identifies where the signal stopped, such as `trend`, `entry`, `risk`, `data_quality`, or `engine`.

`top_blockers` summarizes blockers across the report. It includes skipped and rejected opportunities with known blockers, so no-trend skips are visible in summary-level diagnostics.

## Decision Counts

- `emitted`: a signal passed strategy gates.
- `rejected`: a directional opportunity was stopped by strategy, confidence, or risk criteria.
- `skipped`: the strategy intentionally skipped before an actionable entry, such as no trend or cooldown.
- `indeterminate`: data, API, engine, missing candle, missing candle time, or incomplete diagnostic failures.
