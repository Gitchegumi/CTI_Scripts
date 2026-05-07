# Contract: Signal Stack Readiness Diagnostic

## Data-Not-Ready Diagnostic

When the signal stack cannot safely evaluate because the last closed M5 candle or indicator window is unavailable, the diagnostic payload must include:

```json
{
  "stage": "signal_stack",
  "timeframe": "M5",
  "missing_input": "last_closed_candle_or_indicator_window",
  "error_type": "DataNotReady",
  "required_candles": 50,
  "available_candles": 17,
  "required_closed_candles": 2,
  "available_closed_candles": 1,
  "required_indicator_window": 14,
  "available_indicator_window": 0,
  "message": "Signal stack skipped because the last closed candle or required indicator window is unavailable."
}
```

Counts may be higher than the example if the active signal stack requires more history. Existing compatibility fields such as `available_count` or `required_count` may remain present.

## Decision Classification

For data-not-ready outcomes:

- `final_decision` is the existing deferred or indeterminate decision state.
- `decision_reason` is specific, preferably `signal_stack_data_not_ready` if compatible with existing summaries.
- `first_blocker` is `signal_engine_data:missing` or `signal_stack:data_not_ready`.
- `all_blockers` contains the same blocker.
- `blocking_layer` is `data_quality` unless existing summaries explicitly require `signal_stack`.
- The required `signal_engine_data` criterion has `blocked_signal = true`.

For complete input outcomes:

- `signal_engine_data` is not marked missing.
- Existing candle-close-gate and signal rule criteria determine the final decision.
- Existing strategy rejection semantics remain unchanged.

## Compatibility Rules

- Do not remove or rename existing metrics JSON fields.
- Do not export raw candle lists in the diagnostic.
- Do not report normal data-not-ready conditions as raw `IndexError`.
- Malformed indicator data may still be classified separately from normal warmup/short-data readiness.
