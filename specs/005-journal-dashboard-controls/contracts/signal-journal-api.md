# Contract: Signal Journal Maintenance

## Scope

Applies to Signal Journal list, export, purge, grade, notes, and reset-to-pending operations.

## List

`GET /api/journal`

Returns Signal Journal entries newest-first. Malformed legacy lines are skipped without preventing valid records from loading.

## Export

`GET /api/journal/export?grade=<grade-or-ALL>&format=csv`

### Behavior

- Requires existing journal authentication.
- CSV is the required export format.
- Export respects the active grade filter.
- Empty exports are valid and include headers.
- Optional JSON export may be added if it includes metadata and records.

### Required CSV Fields

`signal_id`, `symbol`, `direction`, `strategy`, `signal_timestamp`, `grade`, `grade_timestamp`, `confidence`, `entry_price`, `stop_loss`, `take_profit`, `lot_size`, `atr`, `rr`, `notes`, `discord_msg_id`, diagnostic fields available on the record, and outcome fields when already present.

## Purge

`DELETE /api/journal?grade=<grade-or-ALL>`

### Behavior

- Requires existing journal authentication.
- Requires UI confirmation before the request is sent.
- Deletes only Signal Journal entries matching the requested grade scope.
- Does not delete manual trade history.
- Returns the removed count and remaining count.

## Reset to Pending

`POST /api/journal/reset`

### Request

```json
{
  "signal_id": "EURUSD:BUY:2026-05-05T12:00:00-05:00"
}
```

### Behavior

- Requires existing journal authentication.
- Sets `grade` to `PENDING`.
- Sets `grade_timestamp` to null.
- Clears outcome-specific grade fields only if they exist and keep the entry classified as complete.
- Preserves original signal fields, diagnostics, and notes.

## Notes and Grade

Existing notes and grade endpoints continue to work. Grade values remain `TP_HIT`, `SL_HIT`, `MANUAL_CLOSE`, and `EXPIRED`; Pending is set via reset rather than by treating it as a completed grade.
