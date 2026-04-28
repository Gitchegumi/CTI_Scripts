# Contract: Trade Annotations API (New)

**Feature**: 001-manual-trade-history
**Date**: 2026-04-28
**Base path**: `/api/trade-annotations` (Next.js proxy → Python `:8199/api/trade-annotations`)

All endpoints require `tg_journal_auth` cookie matching `JOURNAL_TOKEN`.

---

## GET /api/trade-annotations

Fetch annotation for a specific trade.

**Query params**:

| Param | Type | Required | Description |
| --- | --- | --- | --- |
| `trade_id` | string | Yes | Oanda trade ID or `"manual-{id}"` |
| `trade_source` | string | No | `broker` (default) or `manual` |

**Response** `200 OK` (annotation found):

```json
{
  "trade_id": "12345678",
  "trade_source": "broker",
  "notes": "Solid CTI setup — Layer 2 confidence 87%",
  "tags": ["cti-setup", "high-confidence"],
  "updated_at": "2026-04-25T14:30:00+00:00"
}
```

**Response** `200 OK` (no annotation yet — return empty default):

```json
{
  "trade_id": "12345678",
  "trade_source": "broker",
  "notes": "",
  "tags": [],
  "updated_at": ""
}
```

Returns an empty annotation object rather than 404 to simplify client-side handling.

---

## POST /api/trade-annotations

Create or update (upsert) annotation for a trade.

**Request body**:

```json
{
  "trade_id": "12345678",
  "trade_source": "broker",
  "notes": "Solid CTI setup — Layer 2 confidence 87%",
  "tags": ["cti-setup", "high-confidence"]
}
```

Required: `trade_id`.
Optional: `trade_source` (default `"broker"`), `notes`, `tags`.

Semantics: If an annotation for `(trade_id, trade_source)` already exists, it is
replaced (INSERT OR REPLACE). All provided fields overwrite the stored values; omitted
optional fields are not changed.

**Response** `200 OK`: Saved `TradeAnnotation` object.

**Validation**:

- `notes` max 1000 characters.
- Each tag max 50 characters; max 20 tags per trade.
- Tags normalized: lowercase, trimmed whitespace, empty strings removed.
