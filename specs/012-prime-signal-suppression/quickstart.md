# Quickstart: Prime Signal Suppression

## Backend Tests

Run focused journal and metrics tests:

```powershell
python -m pytest src/tradegumi/tests/test_journal.py src/tradegumi/tests/test_strategy_metrics.py
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

1. Emit one signal for a symbol with no active prime and confirm the journal row is active prime with suppressed count `0`.
2. Emit same-symbol same-direction and opposite-direction signals before target/stop is reached and confirm no new actionable row appears.
3. Confirm the existing prime's suppressed count and latest suppressed timestamp update.
4. Provide candle movement that reaches BUY target, BUY stop, SELL target, and SELL stop before a later same-symbol signal and confirm old prime closes while the later signal becomes prime.
5. Provide one candle that touches both target and stop and confirm inferred stop plus ambiguous flag.
6. Restart the process or re-read persisted journal state and confirm the unresolved prime still suppresses a later same-symbol signal.
7. Export the journal and confirm prime fields are present.
8. Open the journal dashboard and confirm suppressed count appears compactly for affected entries.
