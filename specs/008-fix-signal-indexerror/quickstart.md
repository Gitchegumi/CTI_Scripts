# Quickstart: Validate signal stack readiness

## Backend Tests

Run the focused signal-engine tests:

```powershell
pytest src/tradegumi/tests/test_signal_engine.py
```

Run metrics diagnostics coverage:

```powershell
pytest src/tradegumi/tests/test_strategy_metrics.py
```

Run both together before final handoff:

```powershell
pytest src/tradegumi/tests/test_signal_engine.py src/tradegumi/tests/test_strategy_metrics.py
```

## Manual Diagnostic Check

1. Trigger a strategy metrics evaluation with short or empty M5 candle data using the existing test double or local diagnostics harness.
2. Confirm the candidate does not raise `IndexError`.
3. Confirm the diagnostic includes `stage=signal_stack`, `timeframe=M5`, `missing_input=last_closed_candle_or_indicator_window`, and `error_type=DataNotReady`.
4. Confirm `decision_reason`, `first_blocker`, `all_blockers`, `blocking_layer`, and `blocked_signal` show a data-not-ready outcome.
5. Trigger a valid aligned M5 data evaluation and confirm it reaches candle-close gate and signal rule criteria.

## Documentation Check

If strategy metrics documentation lists signal-engine missing-data diagnostics, update it to mention `DataNotReady` and the readiness count fields.
