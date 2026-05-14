# Quickstart: Signal Setup Outcomes

## Prerequisites

- Work on branch `011-signal-setup-outcomes`.
- Use the active feature directory `specs/011-signal-setup-outcomes`.
- Keep strategy thresholds, signal generation rules, risk logic, and broker execution behavior unchanged.

## Validation Steps

1. Run focused journal tests:

   ```powershell
   python -m pytest src/tradegumi/tests/test_journal.py
   ```

2. Run focused strategy metrics tests:

   ```powershell
   python -m pytest src/tradegumi/tests/test_strategy_metrics.py
   ```

3. Run the broader Python test suite when implementation touches shared signal, alert, or metrics behavior:

   ```powershell
   python -m pytest src/tradegumi/tests
   ```

4. If dashboard journal types or UI change, run dashboard checks:

   ```powershell
   npm run lint
   npm run build
   ```

   from the `dashboard/` directory.

## Manual Checks

- Append a first signal and confirm it starts a setup group with `is_duplicate_setup` false.
- Append a second same-symbol, same-direction, same-strategy signal inside the configured 10-minute default window and confirm it reuses the group, has `is_duplicate_setup` true, `trade_grade` `DUPLICATE`, and `usable_for_strategy_stats` false.
- Append a same-context signal outside the grouping window and confirm it starts a new group.
- Verify a signal exactly at entry tolerance is entry-valid.
- Verify a signal beyond entry tolerance records absolute miss distance, ATR-normalized distance when ATR exists, `late_signal` true when appropriate, and false stats eligibility.
- Manually invalidate a signal and confirm `trade_grade` becomes `INVALID` and stats eligibility becomes false while original evidence remains.
- Export or view legacy journal records and confirm missing setup fields do not break the workflow.

## Expected Outcome

Strategy opportunity counts only include journal records where `usable_for_strategy_stats` is true. Raw emitted signal counts remain available only as signal-emission evidence, not as tradable setup opportunity counts.
