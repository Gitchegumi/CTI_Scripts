# Quickstart: Strategy Metrics

## Prerequisites

- Python dependencies installed for the TradeGumi backend.
- Dashboard dependencies installed under `dashboard/`.
- `JOURNAL_TOKEN` configured when testing authenticated dashboard routes.

## Backend Validation

1. Run Python tests:

   ```powershell
   pytest src/tradegumi/tests tests
   ```

2. Start the backend in alert-only mode:

   ```powershell
   python src/tradegumi/main.py --mode alert_only --log-level INFO
   ```

3. Let at least one signal loop complete while markets are open, or use a test fixture to seed diagnostic records.

4. Verify the summary endpoint returns counts:

   ```powershell
   Invoke-RestMethod "http://localhost:8199/api/strategy-metrics/summary?start=2026-04-24&end=2026-05-01"
   ```

5. Verify near-miss drill-down:

   ```powershell
   Invoke-RestMethod "http://localhost:8199/api/strategy-metrics/opportunities?start=2026-04-24&end=2026-05-01&near_miss=true"
   ```

6. Verify the compact diagnostic state file exists and contains the latest summary:

   ```powershell
   Get-Content src/tradegumi/data/strategy_metrics.json
   ```

7. Record signal-loop diagnostic overhead from backend logs or the seeded performance test. The added diagnostic capture should stay below 100 ms per evaluated symbol.

## Dashboard Validation

1. Start the dashboard:

   ```powershell
   cd dashboard
   npm run dev
   ```

2. Open `/strategy-metrics`.

3. Select the last 7 days and confirm the page distinguishes:

   - no evaluated opportunities,
   - evaluated opportunities with no emitted signals,
   - emitted signals,
   - incomplete diagnostic data.

4. Confirm the top blocker table shows combined ranking and criterion details.

5. Compare the last 7 days against the prior 7 days and confirm deltas are shown.

6. Export the current summary and verify the exported JSON includes the selected date range, counts, blockers, and any data-quality warnings.

7. With a seeded 90-day diagnostic dataset, confirm the summary page loads in under 2 seconds.

## Acceptance Checks

- No existing signal emission, risk-check, or execution behavior changes.
- Every evaluated opportunity has a final decision or an explicit incomplete-data reason.
- Rejected opportunities with exactly one failed required criterion are marked `near_miss`.
- At least 90 days of diagnostic data are retained by default.
