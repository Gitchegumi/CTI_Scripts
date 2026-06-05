# Strategy Metrics Export Guide

Strategy metrics explain why each evaluated opportunity emitted, rejected, skipped, or ended indeterminate. They are diagnostic evidence only; they do not tune thresholds or make the bot trade more often.

## Date Ranges

Strategy Metrics uses an inclusive calendar-day UI and an exclusive internal query boundary. When the dashboard sends a date-only `end` value such as `2026-05-06`, the backend queries records before `2026-05-07T00:00:00`, so all opportunities evaluated on May 6 are included and May 7 records are excluded.

If callers send a timestamped `end` value, it is treated as the exact exclusive upper bound.

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

Required criteria that cannot evaluate because data is missing or malformed also set `blocked_signal` when that missing data stops progression. In that case `diagnostic_state`, `reason`, and `context` explain why evaluation was impossible instead of leaving a silent `passed = null`.

## Blockers

`first_blocker` is the first known blocker for an opportunity. `all_blockers` lists every known blocker, including trend classification reasons such as `trend:direction_conflict`. `blocking_layer` identifies where the signal stopped, such as `trend`, `entry`, `risk`, `data_quality`, or `engine`.

`top_blockers` summarizes blockers across the report. It includes skipped, rejected, and indeterminate opportunities with known blockers, so no-trend skips and missing signal data are visible in summary-level diagnostics.

## Decision Counts

- `emitted`: a signal passed strategy gates.
- `rejected`: a directional opportunity was stopped by strategy, confidence, or risk criteria.
- `skipped`: the strategy intentionally skipped before an actionable entry, such as no trend or cooldown.
- `indeterminate`: data, API, engine, missing candle, missing candle time, or incomplete diagnostic failures.

`rejected` does not include opportunities that are merely waiting for a candle to close or unable to evaluate because required data is missing. Those are classified as skipped or indeterminate according to the blocker.

## Pullback Summary

`pullback_summary` provides a strategy-specific rollup for `CTI-v1.2-pullback` diagnostics. It counts evaluated, rejected, near-miss, emitted, journaled, and prime-suppressed pullbacks, and groups rejected pullbacks by stable gate blocker names such as `pullback_trigger_candle_failed`, `pullback_kc_sequence_failed`, `pullback_stoch_rsi_failed`, and `pullback_structure_failed`.

The rollup uses explicit `signal_type=pullback`, pullback strategy names, or persisted pullback criterion names so legacy diagnostic rows remain reportable when possible.

## Signal Engine Data

`signal_engine_data` describes whether the signal stack had enough data to evaluate a directional trend candidate. Missing inputs keep the final decision indeterminate and use stable blockers such as `signal_engine_data:missing`.

The criterion `context` should name the compact missing input category, such as candles, last closed candle or indicator window, malformed price or indicator data, ATR, stochastic RSI, price data, or an indicator column. Raw candle arrays are not exported.

When a trend-valid M5 candidate cannot safely enter the signal stack because the last fully closed candle or required indicator window is unavailable, the decision reason is `signal_stack_data_not_ready`. The diagnostic uses `error_type: DataNotReady`, `missing_input: last_closed_candle_or_indicator_window`, and includes required/available counts for raw candles, closed candles, and usable indicator rows. This is a normal readiness state, not a strategy rejection and not a raw `IndexError`.

OANDA provider failures are also reported as indeterminate data/API failures rather than strategy rejections. Stable provider reasons include `oanda_gateway_timeout`, `oanda_rate_limited`, `oanda_candle_fetch_failed`, `oanda_request_failed`, and `oanda_response_malformed`. Provider diagnostic context includes safe troubleshooting fields such as method, path, status code, instrument, granularity, retry attempts, and retryability; it must not include API tokens or authorization headers.

## Candle Close Gate

`candle_close_gate` describes whether a candidate was evaluated at the intended candle timing. The gate rule is `pass_after_candle_close`: a candidate can proceed only when the relevant candle has closed. If evaluation occurs before close, the opportunity is treated as waiting for candle close rather than a strategy rejection.

Gate context includes `current_time`, `candle_open_time`, `candle_close_time`, `seconds_until_close`, `seconds_since_close`, `timeframe`, `gate_rule`, and `margin_units`. Margin values for this gate are expressed in seconds.

Stable gate reasons include:

- `candle_close_gate:passed`
- `candle_close_gate:waiting_for_close`
- `candle_close_gate:stale_candle`
- `candle_close_gate:missing_timing_data`
- `candle_close_gate:failed`

## Near Misses

`near_miss` is true only when a rejected opportunity failed exactly one required blocking criterion and that blocker satisfies the documented near-miss rule. Ordinary open-candle waiting is not a near miss.

`near_miss_reason` names the blocking criterion or stable blocker that made the opportunity a near miss. `near_miss_reason_counts` summarizes those reasons, and `near_miss_count` must equal the sum of the reason counts.

## Pipeline Funnel

`pipeline_funnel` summarizes where evaluated opportunities fall out of the pipeline:

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

Use the funnel to identify whether the next blocker is trend qualification, signal data completeness, candle timing, signal rules, or another indeterminate failure.

## Threshold Versions

`threshold_version_counts` remains the count of exported opportunities by strategy threshold version. When the version is `unknown`, `threshold_version_unknown_reasons` explains the best available reason, such as legacy or missing threshold provenance.
