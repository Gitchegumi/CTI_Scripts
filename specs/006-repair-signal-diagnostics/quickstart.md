# Quickstart: Repair Signal Pipeline Diagnostics

## Validate SpecKit Artifacts

1. Review `specs/006-repair-signal-diagnostics/spec.md`.
2. Review `specs/006-repair-signal-diagnostics/plan.md`.
3. Review `specs/006-repair-signal-diagnostics/tasks.md` after task generation.
4. Run the analysis step before implementation.

## Run Focused Tests

```powershell
python -m pytest src/tradegumi/tests/test_strategy_metrics.py
```

## Inspect Export Shape

Generate or fetch a strategy metrics export that includes opportunities, then confirm:

- Missing signal data opportunities are indeterminate with data-quality blockers.
- Candle close gate criteria include timing context and stable reasons.
- Open-candle waiting is not automatically counted as near miss.
- `near_miss_count` equals the sum of `near_miss_reason_counts`.
- `top_blockers` includes data-quality blockers when present.
- `pipeline_funnel` shows where candidates fall out.
- Existing JSON fields remain present.

## Documentation Check

Confirm `docs/strategy-metrics.md` defines:

- `skipped`
- `rejected`
- `indeterminate`
- `near_miss`
- `candle_close_gate`
- `signal_engine_data`
- `blocked_signal`
- `first_blocker`
- `all_blockers`
- `blocking_layer`
