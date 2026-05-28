# Quickstart: Alert Signal Auto-Grading

## Backend Tests

Run focused tests:

```powershell
pytest src/tradegumi/tests/test_price_observations.py src/tradegumi/tests/test_signal_outcomes.py src/tradegumi/tests/test_journal.py
```

Run broader backend regression:

```powershell
pytest src/tradegumi/tests
```

## Dashboard Checks

When dashboard types or UI change:

```powershell
cd dashboard
npm run lint
npm run build
```

## Manual Validation

1. Start TradeGumi in `alert_only` mode.
2. Confirm the one-second backend pricing loop still runs once for the scan symbols.
3. Fire or seed an alert-only signal with target and stop.
4. Publish or observe prices that do not hit target/stop and confirm the journal remains open with checked time updated.
5. Publish or observe a BUY target, BUY stop, SELL target, and SELL stop case and confirm outcomes are recorded correctly.
6. Manually grade one entry, publish conflicting prices, and confirm the manual result is preserved.
7. Reset a manually graded entry to pending and confirm it can be auto-graded again unless manually locked.
8. Create a same-symbol prime conflict and confirm unresolved prime blocks the new signal while resolved TP/SL prime allows replacement.
9. Export the journal and confirm the new outcome fields appear without breaking legacy fields.
10. Review the dashboard journal view for compact status/outcome/source/exit/ambiguous display.
