# Signal Journal Controls

The Signal Journal stores optimization evidence separately from the Manual Trade Journal. Signal actions do not delete or mutate manual trade records.

## Export

`Export CSV` downloads the active Signal Journal grade filter. `All` exports every signal; `Pending`, `TP Hit`, `SL Hit`, `Manual`, and `Expired` export only that grade.

The CSV includes signal identity, symbol, timestamp, strategy, confidence, emitted trade details, indicator/diagnostic snapshots, grade, grade timestamp, notes, and legacy fields when older records contain them.

## Purge

`Purge` removes Signal Journal entries only after confirmation. The purge scope matches the active grade filter. This is intended for clearing stale signals created under old strategy parameters.

## Reset To Pending

`Reset to Pending` is available on graded signal groups. It changes the selected signal back to `PENDING`, clears grade-specific outcome fields such as `grade_timestamp`, `outcome`, `score`, and review timestamps, and preserves the original signal data, diagnostics, and user notes.

## Developing Mode

The UI displays `Developing` for the stored internal mode value `alert_only`. Existing records keep `alert_only` for backward compatibility. Developing mode allows manual trade corrections, including P&L edits, because the bot is not executing the trade automatically.
