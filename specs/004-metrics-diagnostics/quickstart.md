# Quickstart: Metrics Diagnostics

1. Run the Python unit tests for strategy metrics:

   ```powershell
   python -m pytest src/tradegumi/tests/test_strategy_metrics.py
   ```

2. Export a period containing skipped opportunities and inspect:

   - `trend_decision.no_trend_reason`
   - `criteria[].expected_pass`
   - `criteria[].pass_mismatch`
   - `criteria[].blocked_signal`
   - `first_blocker`
   - `all_blockers`
   - `blocking_layer`
   - `summary.top_blockers`

3. Confirm diagnostic-only scope:

   - No threshold constants changed.
   - No entry rules changed.
   - No strategy optimization or forward labels added.
   - Engine/data failures remain `indeterminate`.
