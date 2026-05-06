# Quickstart: Repair DB-backed page performance and signal pipeline progression

## Prerequisites

- Work from repository root: `E:\GitHub\CTI_Scripts`.
- Backend Python package and tests live under `src/`.
- Dashboard package lives under `dashboard/`.
- Existing local SQLite files live under `src/tradegumi/data/`.

## Baseline Performance Measurement

1. Start the existing backend/dashboard workflow used for local development.
2. Measure the default load for:
   - strategy metrics page
   - signal journal page
   - manual trade journal page
   - dashboard trade history
3. Record elapsed time, data volume, and any slow route/query labels before code changes.
4. For SQLite-backed slow paths, inspect query plans for the exact queries before changing indexes.

## Backend Test Commands

From `src/`:

```powershell
poetry run pytest tradegumi/tests/test_strategy_metrics.py
poetry run pytest tradegumi/tests
```

From repository root, if tests target the root-level suite:

```powershell
pytest tests/tradegumi
```

## Dashboard Verification Commands

From `dashboard/`:

```powershell
npm run lint
npm run build
```

## Signal Regression Verification

Run the focused signal tests added for this feature and confirm coverage for:

- insufficient candles
- exactly enough candles
- last closed candle selection
- M5 before-close gate
- M5 exact-close gate
- M5 after-close gate
- trend-valid candidate reaching signal rule evaluation

## Acceptance Verification

- DB-backed pages no longer take 5+ seconds under normal local/dev data volume.
- Optimized routes preserve existing response shape unless an exception is documented.
- Metrics can show nonzero `signal_rules_evaluated` when valid closed-candle candidates exist.
- `signal_engine_data` no longer fails with `IndexError: list index out of range`.
- Diagnostics remain useful for missing data and gate waiting states.

## Measurements Captured During Implementation

- `python -m pytest tradegumi/tests/test_signal_engine.py -q`: 5 tests passed in 3.48s inside the default sandbox.
- `python -m pytest tradegumi/tests/test_strategy_metrics.py -q`: 41 tests passed in 31.01s when allowed to write temporary SQLite files.
- `test_seeded_summary_performance` continues to assert seeded metrics summary work stays under 5 seconds for 250 writes plus summary.
- Strategy metrics opportunities now fetch all selected criteria in one batch instead of one query per opportunity.
- The strategy metrics page no longer fetches comparison data until the operator enables Compare mode.
