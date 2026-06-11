# Quickstart: Continuation Management Events

## Backend Tests

The issue #100 reference set has 92 continuation-heavy rows with no valid
pullback entries. The current-week export from 2026-06-08 through 2026-06-11
has 101 signals with zero pullback entries and nearly all continuation entries
failing when treated as entries. Use those files only as replay fixtures; the
expected result is that continuation rows become management evidence or
rejections, never fresh trade entries.

Run focused lifecycle tests:

```powershell
python -m pytest src/tradegumi/tests/test_signal_engine.py src/tradegumi/tests/test_journal.py src/tradegumi/tests/test_signal_outcomes.py src/tradegumi/tests/test_strategy_metrics.py
```

Run the existing Python test suite:

```powershell
python -m pytest src/tradegumi/tests
```

## Dashboard Checks

When dashboard types or views change:

```powershell
cd dashboard
npm run lint
npm run build
```

## Manual Validation Scenarios

1. Replay a continuation-only sample with no pullback rows and confirm zero trade entries are opened.
2. Replay the current-week sample with 101 continuation rows and zero pullback rows and confirm zero continuation-created entries.
3. Emit a pullback signal with no active same-direction trade and confirm a new `trade_id` and entry lifecycle role are recorded.
4. Emit a same-direction continuation after favorable movement reaches the break-even threshold and confirm a management event moves current SL to break-even.
5. Emit a same-direction continuation after favorable movement reaches the profit-protection threshold and confirm SL tightens beyond entry without increasing risk.
6. Emit qualifying continuations until TP extension caps are reached and confirm later events are rejected with cap reasons.
7. Emit an opposite-direction continuation while a trade is open and confirm it records a warning instead of a new trade.
8. Close a BUY trade at an SL above entry and a SELL trade at an SL below entry and confirm both count as profit-protected wins.
9. Export the Signal Journal and strategy metrics and confirm lifecycle fields and counters are present.
10. Open the journal and strategy metrics dashboards and confirm lifecycle roles, management decisions, and managed outcomes are visible.

## Python Review Notes

New lifecycle helpers should keep short docstrings when they encode a business
rule rather than a direct data move. In particular, document:

- Pullback versus continuation identity helpers.
- Managed-trade lookup and race recheck helpers.
- Management decision and evidence-writing helpers.
- Managed exit classification.
- Metrics lifecycle aggregation.

Prefer explicit reason strings from the journal constants for every rejection
or warning path so exported rows stay stable across UI, API, and CSV consumers.
