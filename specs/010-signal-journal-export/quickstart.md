# Quickstart: Signal Journal Export

## Automated Validation

1. Run focused backend journal tests:

   ```powershell
   python -m pytest src/tradegumi/tests/test_journal.py
   ```

2. Run dashboard static checks:

   ```powershell
   npm run lint
   npm run build
   ```

   Run these from `dashboard/`.

## Manual Validation

1. Start the TradeGumi API and dashboard with the usual local environment.
2. Open the Signal Journal page and authenticate if prompted.
3. Choose a range that includes known recent signals and excludes older broken-run records.
4. Click `Export CSV`.
5. Verify the browser downloads a file named like `signal-journal-YYYY-MM-DD-to-YYYY-MM-DD.csv`.
6. Open the CSV and confirm every row falls inside the selected range using `evaluated_at`, or `created_at`/`signal_timestamp` when `evaluated_at` is absent.
7. Change the visible grade filter and export again; confirm only that grade appears.
8. Choose a range with no matching records; confirm the page shows a no-records message and no file is downloaded.
9. Confirm grading, reset-to-pending, notes, purge confirmation, and journal grouping still behave as before.
