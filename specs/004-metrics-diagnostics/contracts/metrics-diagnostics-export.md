# Metrics Diagnostics Export Contract

## Opportunity Additions

Each opportunity may include:

```json
{
  "trend_decision": {
    "strength_passed_1h": true,
    "strength_passed_15m": true,
    "strength_passed_5m": true,
    "direction_1h": "up",
    "direction_15m": "up",
    "direction_5m": "down",
    "directions_agree": false,
    "strengths_all_passed": true,
    "trend_classification_input": {
      "lr_1h": 0.009,
      "lr_15m": 0.011,
      "lr_5m": -0.003,
      "threshold_1h": 0.005,
      "threshold_15m": 0.008,
      "threshold_5m": 0.002
    },
    "trend_classification_output": {
      "trend_result": "flat",
      "final_direction": "none",
      "no_trend_reason": "direction_conflict"
    },
    "trend_result": "flat",
    "final_direction": "none",
    "no_trend_reason": "direction_conflict"
  }
}
```

Supported `no_trend_reason` values:

- `insufficient_strength_1h`
- `insufficient_strength_15m`
- `insufficient_strength_5m`
- `multiple_insufficient_strength`
- `direction_conflict`
- `missing_data`
- `invalid_lr_result`
- `flat_after_classification`
- `unknown`

## Criterion Additions

Threshold-based criteria must expose:

- `expected_pass`: computed result from measured value, threshold value, and threshold operator when computable.
- `pass_mismatch`: true when `expected_pass` and `passed` are both populated and differ.
- `blocked_signal`: true when a failed required criterion blocks signal generation.

## Blocker Fields

Opportunity-level:

- `first_blocker`: first known blocker key.
- `all_blockers`: all known blocker keys.
- `blocking_layer`: layer that stopped the signal, such as `trend`, `entry`, `risk`, `data_quality`, or `engine`.

Summary-level:

- `top_blockers`: ranked blockers across skipped and rejected opportunities.
- `threshold_version_counts`: counts grouped by threshold version when versions appear in the report.

## Count Semantics

- `emitted`: signal emitted by strategy.
- `rejected`: strategy found a directional opportunity but required criteria, confidence, or risk stopped it.
- `skipped`: strategy intentionally skipped before an actionable entry, including no-trend classification.
- `indeterminate`: data, API, engine, missing-candle, missing-time, or incomplete diagnostic failures.
