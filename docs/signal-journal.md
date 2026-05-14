# Signal Journal Controls

The Signal Journal stores optimization evidence separately from the Manual Trade Journal. Signal actions do not delete or mutate manual trade records.

## Export

`Export CSV` downloads the active Signal Journal grade filter and optional export date/time range. `All` exports every signal in the selected range; `Pending`, `TP Hit`, `SL Hit`, `Manual`, and `Expired` export only that grade.

Range filtering uses `evaluated_at` when a record has it, then `created_at`, then the legacy `signal_timestamp`. This lets operators exclude stale signals from old broken strategy runs without purging or changing stored journal data.

The CSV is returned as a browser download with attachment headers and a range-aware filename such as `signal-journal-2026-05-01-to-2026-05-14.csv`. If the selected export scope matches no records, the page shows a message and does not download an empty file.

The CSV includes signal identity, opportunity identity when present, symbol, timeframe, mode, direction, trend, final decision, decision reason, confidence, blocker diagnostics, evaluated/created timestamps, emitted trade details, grade/status, trade result and P&L fields when present, notes, and legacy fields when older records contain them. Nested criteria or diagnostics are JSON-encoded into deterministic flat CSV cells.

## Setup Outcomes

New emitted signals include setup outcome fields that separate signal delivery from tradable setup quality:

- `setup_group_id` groups the same symbol, direction, and strategy within `SIGNAL_SETUP_GROUP_WINDOW_MINUTES` minutes. The default window is 10 minutes.
- `is_duplicate_setup` is true when a signal joins an active setup group instead of starting a new tradable setup.
- `entry_valid_at_signal` records whether signal-time price was still within the configured entry tolerance.
- `entry_miss_distance` stores absolute distance and ATR-normalized distance from the suggested entry.
- `signal_age_bars` records elapsed M5 bars since the setup condition first became true.
- `late_signal` is true when price had already moved beyond valid entry tolerance.
- `usable_for_strategy_stats` is true only for unique, fresh, entry-valid setup records.
- `stats_exclusion_reason` explains exclusions such as `duplicate_setup`, `late_signal`, `stale_signal`, `missing_entry_context`, or `manual_invalidated`.
- `trade_grade` uses the normalized vocabulary `TP_HIT`, `SL_HIT`, `BE`, `MISSED_ENTRY`, `LATE_SIGNAL`, `DUPLICATE`, `INVALID`, and `PENDING`.

Emitted signals do not count as trade opportunities unless `usable_for_strategy_stats` is true. Strategy metrics report emitted signal count separately from `trade_opportunity_count`, with excluded and unknown eligibility records counted outside tradable setup statistics.

## Purge

`Purge` removes Signal Journal entries only after confirmation. The purge scope matches the active grade filter. This is intended for clearing stale signals created under old strategy parameters.

## Reset To Pending

`Reset to Pending` is available on graded signal groups. It changes the selected signal back to `PENDING`, clears grade-specific outcome fields such as `grade_timestamp`, `outcome`, `score`, and review timestamps, and preserves the original signal data, diagnostics, and user notes.

`Mark Invalid` preserves the original signal evidence and notes while setting `trade_grade` to `INVALID`, `usable_for_strategy_stats` to false, and `stats_exclusion_reason` to `manual_invalidated`.

## Developing Mode

The UI displays `Developing` for the stored internal mode value `alert_only`. Existing records keep `alert_only` for backward compatibility. Developing mode allows manual trade corrections, including P&L edits, because the bot is not executing the trade automatically.
