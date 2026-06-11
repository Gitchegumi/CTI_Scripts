# Signal Journal Controls

The Signal Journal stores optimization evidence separately from the Manual Trade Journal. Signal actions do not delete or mutate manual trade records.

## Market Data Streaming

TradeGumi can grade Signal Journal outcomes from the shared market data observation path. With `TRADEGUMI_MARKET_DATA_MODE=streaming`, Oanda pricing stream events are normalized into `PriceObservation` records and immediately sent to the same journal evaluator used by polling. Heartbeats update stream liveness only; they do not create journal observations.

If the stream fails authentication, disconnects repeatedly, or misses the configured heartbeat window, TradeGumi falls back to the existing polling path so TP/SL outcome grading and dashboard prices continue. Operators can tune stream reconnect behavior with `TRADEGUMI_STREAM_RECONNECT_SECONDS`, `TRADEGUMI_STREAM_HEARTBEAT_TIMEOUT_SECONDS`, `TRADEGUMI_STREAM_BACKOFF_MAX_SECONDS`, and `TRADEGUMI_STREAM_MAX_RECONNECT_ATTEMPTS`.

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

## Prime Signal Suppression

The first unresolved actionable signal for a symbol becomes that symbol's active prime. While the prime remains unresolved, later same-symbol signals are suppressed at the journal layer instead of creating new actionable rows. Suppression is symbol-specific and applies to both same-direction and opposite-direction follow-on signals.

Prime records include:

- `prime_active` shows whether the record is still the unresolved prime for its symbol.
- `prime_suppressed_signal_count` counts follow-on signals suppressed by this prime.
- `prime_suppressed_last_at` records the latest suppressed signal timestamp.
- `prime_suppressed_same_direction_count` and `prime_suppressed_opposite_direction_count` summarize repeated firing and chop symptoms when available.
- `prime_suppressed_signal_outcomes` preserves each suppressed signal's identity, including strategy, signal type, and pullback trigger context when available.
- `prime_closed_reason`, `prime_closed_at`, and `prime_close_ambiguous` record inferred or manual prime resolution.

Before suppressing a follow-on signal, the journal checks market candles carried by the emitted signal to infer whether the active prime touched its take profit or stop loss. BUY primes close by target when candle high reaches take profit and by stop when candle low reaches stop loss. SELL primes close by target when candle low reaches take profit and by stop when candle high reaches stop loss. If both are touched in the same candle, the journal records conservative stop-first closure and marks the close ambiguous.

Suppressed signals do not create setup rows, do not require grading, and do not count as usable strategy-stat opportunities. They remain auditable through the active prime's suppression fields and strategy metrics.

## Continuation Management Lifecycle

Pullback signals are the only lifecycle rows that can open a new managed trade entry. When a pullback is usable for strategy stats, the journal records `lifecycle_role=entry`, a stable `trade_id`, initial/current SL and TP values, and `risk_at_entry`.

Continuation signals are preserved as evidence but do not create new trade entries. A same-direction continuation can manage the active pullback trade by moving SL to break-even, tightening SL into profit protection, or extending TP within configured caps. The evidence row records `lifecycle_role=management`, `management_accepted`, `management_reason`, old/new SL and TP values, the source signal id, and the linked trade id.

If a continuation arrives with no active pullback trade, the row is rejected with `management_rejection_reason=no_active_trade` and remains excluded from strategy stats. Opposite-direction continuations while a trade is active are recorded as `lifecycle_role=warning` so chop and reversal pressure remain visible without opening a conflicting trade.

Managed exits use current managed SL/TP levels before legacy original levels. A protected SL above BUY entry or below SELL entry is classified as a win, an SL at entry is classified as break-even, and normal adverse SL exits remain losses. Manual close rows with an exit price also receive managed result fields such as `managed_exit_reason`, `managed_result_category`, and `captured_r`.

Strategy metrics summarize this lifecycle with pullback entries opened, continuation management events observed/accepted/rejected, SL tighten and break-even moves, TP extensions, profit-protected SL wins, opposite-direction warnings, average captured R, and managed-versus-original result deltas.

## Alert-Only Auto-Grading

Alert-only and Developing-mode signals can be auto-graded from shared price observations after they are journaled. The evaluator does not generate signals, place trades, close positions, or call Oanda directly. It consumes the same `PriceObservation` records published from the backend one-second pricing path that feeds dashboard state.

Outcome fields are additive and safe for legacy records:

- `status` is one of `pending`, `open_simulated`, `closed`, `ambiguous`, `invalidated`, or `expired`.
- `outcome` is one of `tp`, `sl`, `ambiguous`, `expired`, `manually_closed`, `invalidated_by_prime`, `invalidated_by_system`, or `none`.
- `outcome_source` records whether the result came from `live_price_observation_1s`, midpoint fallback, a future stream, candle data, manual review, or system prime filtering.
- `exit_time`, `exit_price`, and `outcome_checked_at` record the evaluator audit trail.
- `observations_to_outcome`, `max_favorable_excursion`, and `max_adverse_excursion` summarize observed movement when available.
- `ambiguous_reason` explains unresolved ordering, such as target and stop appearing hit in the same evaluator cycle.
- `manually_overridden` and `manual_override_reason` protect human review decisions.

Bid/ask grading uses executable-side prices: BUY targets and stops use bid; SELL targets and stops use ask. If only midpoint is available, auto-grading may still close the signal, but `outcome_source` explicitly records midpoint-based grading so it is not confused with execution-quality bid/ask grading.

Manual grades are authoritative. A manually graded or manually locked signal is skipped by the evaluator. Resetting a signal to pending clears auto outcome fields and makes the signal eligible for auto-grading again unless a manual lock remains.

The first implementation keeps price observations in bounded memory. A future Oanda pricing stream should publish the same observation shape with `source=oanda_pricing_stream`, allowing the evaluator and dashboard read paths to remain unchanged.

## Purge

`Purge` removes Signal Journal entries only after confirmation. The purge scope matches the active grade filter. This is intended for clearing stale signals created under old strategy parameters.

## Reset To Pending

`Reset to Pending` is available on graded signal groups. It changes the selected signal back to `PENDING`, clears grade-specific outcome fields such as `grade_timestamp`, exit details, outcome source, score, and review timestamps, and preserves the original signal data, diagnostics, and user notes.

`Mark Invalid` preserves the original signal evidence and notes while setting `trade_grade` to `INVALID`, `usable_for_strategy_stats` to false, and `stats_exclusion_reason` to `manual_invalidated`.

## Developing Mode

The UI displays `Developing` for the stored internal mode value `alert_only`. Existing records keep `alert_only` for backward compatibility. Developing mode allows manual trade corrections, including P&L edits, because the bot is not executing the trade automatically.
