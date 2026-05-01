# Contract: Manual Trades API

All endpoints require the existing journal authentication when accessed through protected dashboard/manual-trade routes. Backend mutation rules must re-check current bot mode at save time.

## GET `/api/trades/manual`

Returns the unified current-mode trade history for the manual trades interface.

### Query Parameters

- `symbol` optional: Filter by symbol.
- `status` optional: `open` or `closed`.
- `tag` optional: Filter by tag.
- `start_date` optional: Include trades on or after this timestamp/date.
- `end_date` optional: Include trades on or before this timestamp/date.
- `limit` optional: Maximum records, default 100.

### Response `200`

```json
[
  {
    "id": "manual:42",
    "source": "manual",
    "source_trade_id": "42",
    "bot_mode": "alert_only",
    "is_manual": true,
    "symbol": "EURUSD",
    "direction": "long",
    "entry_price": 1.0801,
    "exit_price": 1.0831,
    "entry_time": "2026-05-01T14:00:00-05:00",
    "exit_time": "2026-05-01T15:00:00-05:00",
    "volume": null,
    "status": "closed",
    "fees": 0,
    "pnl": 30,
    "pnl_percent": 0.28,
    "notes": "Clean setup",
    "tags": ["cti-setup"],
    "has_overrides": false,
    "permissions": {
      "can_edit_all_fields": true,
      "can_edit_notes_tags": true,
      "can_delete": true
    },
    "created_at": "2026-05-01T14:01:00-05:00",
    "updated_at": "2026-05-01T15:01:00-05:00"
  }
]
```

## GET `/api/trades/manual/stats`

Returns summary statistics for the current mode's unified trade history.

### Response `200`

```json
{
  "bot_mode": "alert_only",
  "total_trades": 12,
  "closed_trades": 10,
  "open_trades": 2,
  "wins": 6,
  "losses": 4,
  "win_rate": 60,
  "total_pnl": 145.75,
  "avg_pnl": 14.58,
  "avg_pnl_percent": 0.22
}
```

## GET `/api/trades/history`

Returns the same current-mode unified trade-history records as `/api/trades/manual`, formatted for the main dashboard Trade History component. `/api/trades` may remain the raw execution-source endpoint; `/api/trades/history` is the unified dashboard/manual history view.

### Query Parameters

- `count` optional: Maximum records, default 50.
- `symbol` optional: Filter by symbol.
- `tag` optional: Filter by tag.
- `start_date` optional: Include trades on or after this timestamp/date.
- `end_date` optional: Include trades on or before this timestamp/date.

### Response `200`

```json
[
  {
    "id": "manual:42",
    "source": "manual",
    "source_trade_id": "42",
    "bot_mode": "alert_only",
    "is_manual": true,
    "symbol": "EURUSD",
    "side": "BUY",
    "volume": null,
    "open_price": 1.0801,
    "close_price": 1.0831,
    "open_time": "2026-05-01T14:00:00-05:00",
    "close_time": "2026-05-01T15:00:00-05:00",
    "realized_pl": 30,
    "financing": 0,
    "pnl": 30,
    "notes": "Clean setup",
    "tags": ["cti-setup"],
    "has_overrides": false
  }
]
```

## POST `/api/trades/manual`

Creates a manually entered trade for the current mode. Creation is allowed only when current mode is `alert_only` unless future requirements explicitly expand that behavior.

### Request

```json
{
  "symbol": "EURUSD",
  "direction": "long",
  "entry_price": 1.0801,
  "exit_price": 1.0831,
  "entry_time": "2026-05-01T14:00:00-05:00",
  "exit_time": "2026-05-01T15:00:00-05:00",
  "notes": "Clean setup",
  "tags": ["cti-setup"]
}
```

### Responses

- `201`: Created historical trade record.
- `400`: Invalid field values.
- `403`: Current mode does not allow manual trade creation.
- `401`: Unauthorized.

## PUT `/api/trades/manual/{id}`

Updates an existing displayed trade by canonical id. `id` may identify a manual trade or a non-manual source trade.

### Request

```json
{
  "symbol": "EURUSD",
  "direction": "long",
  "entry_price": 1.0801,
  "exit_price": 1.0831,
  "entry_time": "2026-05-01T14:00:00-05:00",
  "exit_time": "2026-05-01T15:00:00-05:00",
  "volume": 1000,
  "status": "closed",
  "fees": 0,
  "pnl": 30,
  "pnl_percent": 0.28,
  "notes": "Corrected after review",
  "tags": ["cti-setup", "reviewed"]
}
```

### Rules

- In `alert_only`, all exposed fields may be updated.
- In `alert_only`, updates to non-manual source trades are stored as local overrides.
- In any other mode, only `notes` and `tags` may be updated.
- Permission is evaluated at save time.

### Responses

- `200`: Updated merged trade record.
- `400`: Invalid field values.
- `403`: Request attempts to modify fields that are protected in the current mode.
- `404`: Trade identity not found in current-mode history.
- `401`: Unauthorized.

## DELETE `/api/trades/manual/{id}`

Deletes a manually created trade from the current mode.

### Rules

- Allowed only for manually created trades.
- Allowed only when current mode is `alert_only`.
- Non-manual historical trades are never deleted by this endpoint.

### Responses

- `200`: `{ "ok": true }`.
- `403`: Current mode or trade origin does not allow deletion.
- `404`: Trade not found.
- `401`: Unauthorized.

## Dashboard Proxy Routes

The Next.js routes under `/api/manual-trades` proxy the backend endpoints above, preserve query parameters, forward the journal token as `X-API-Key`, and return upstream status codes and JSON bodies.

`/api/manual-trades/export` is a reserved static route and must not be treated as a trade id by `/api/manual-trades/[[...id]]`.

## GET `/api/trades/manual/export`

Returns the current bot mode's unified trade-history dataset as structured JSON for LLM and agentic workflows.

### Query Parameters

- `symbol` optional: Filter by symbol.
- `tag` optional: Filter by tag.
- `start_date` optional: Include trades on or after this timestamp/date.
- `end_date` optional: Include trades on or before this timestamp/date.
- `limit` optional: Maximum records, default 1000.

### Response `200`

```json
{
  "schema_version": "manual-trade-agent-export.v1",
  "schema_name": "Agent Export",
  "generated_at": "2026-05-01T16:00:00-05:00",
  "bot_mode": "alert_only",
  "scope": {
    "symbol": null,
    "tag": null,
    "start_date": null,
    "end_date": null,
    "limit": 1000
  },
  "chunking": {
    "chunk_index": 1,
    "chunk_count": 1,
    "record_offset": 0,
    "record_limit": 1000
  },
  "summary": {
    "record_count": 12,
    "manual_count": 7,
    "non_manual_count": 5,
    "override_count": 2,
    "tag_count": 4
  },
  "field_metadata": {
    "displayed_values": "Values shown in dashboard/manual trade history after local overrides are applied.",
    "source_values": "Original source-owned values when available.",
    "overridden_fields": "Fields corrected locally for AI-assisted strategy review."
  },
  "analysis_context": {
    "purpose": "Evaluate trading strategy outcomes and support AI-assisted adjustments.",
    "mode_isolation": "Records belong only to the exported bot mode.",
    "legacy_default": "Records without historical mode metadata are classified as alert_only."
  },
  "records": []
}
```

### Responses

- `200`: Agent export package.
- `400`: Invalid filters.
- `401`: Unauthorized.
- `500`: Export generation failed.

The Next.js route `/api/manual-trades/export` proxies this endpoint and returns the same JSON structure.
