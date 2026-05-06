# Quickstart: Journal and Dashboard Controls

## Prerequisites

- Run from repository root.
- Use a test copy or temporary data path when validating destructive journal actions.
- Keep implementation code unchanged until `spec.md`, `plan.md`, `tasks.md`, and analysis are complete.

## Validation Steps

### Strategy Metrics Inclusive End Date

1. Seed or create strategy metric records on `2026-05-06T00:00:00`, `2026-05-06T12:00:00`, `2026-05-06T23:59:59.999`, and `2026-05-07T00:00:00`.
2. Request or select range `start=2026-05-06`, `end=2026-05-06`.
3. Verify the three `2026-05-06` records are included and the `2026-05-07` record is excluded.
4. Repeat for summary, opportunities, comparison, and export.

### Signal Journal Export

1. Create Pending and graded Signal Journal records with notes and diagnostic fields.
2. Filter Signal Journal to Pending.
3. Export CSV.
4. Verify the CSV contains only Pending records and includes signal identity, signal details, diagnostics, grade/status, notes, and timestamps.
5. Export an empty filter and verify a valid header-only CSV.

### Signal Journal Purge

1. Create Signal Journal records and manual trade records.
2. Choose a Signal Journal filter.
3. Open purge confirmation and cancel; verify no entries are removed.
4. Confirm purge; verify only matching Signal Journal entries are removed.
5. Verify manual trade records remain.

### Reset to Pending

1. Grade a Signal Journal entry.
2. Use Reset to Pending.
3. Verify grade is Pending, grade timestamp is cleared, notes remain, and signal diagnostics remain.

### Developing Mode Manual P&L

1. Set mode to `alert_only`.
2. Verify UI displays "Developing".
3. Edit a manual trade P&L value and save.
4. Verify manual trade table, stats, dashboard history, and export show the correction.
5. Switch to `demo` or `live`; verify P&L edit is unavailable or rejected while notes/tags remain editable.

### Dashboard Trade History

1. Create manual trade records.
2. Force broker/source trade history unavailable or return an error.
3. Request `/api/trades/history?count=50`.
4. Verify the response is valid and includes manual trades.
5. Open the dashboard and verify Trade History displays records.
6. Remove or omit trade correlation data and verify the dashboard does not repeatedly log 404s.
7. Verify React hydration error #418 does not appear during page load.

## Recommended Test Commands

```powershell
$env:NUMBA_DISABLE_JIT='1'
python -m pytest src\tradegumi\tests\test_strategy_metrics.py src\tradegumi\tests\test_manual_trades.py src\tradegumi\tests\test_journal.py -p no:cacheprovider
```

Run dashboard lint/typecheck according to the package scripts available in `dashboard/package.json`.
