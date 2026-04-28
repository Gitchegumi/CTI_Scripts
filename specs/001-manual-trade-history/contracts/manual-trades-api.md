# Contract: Manual Trades API (Updated)

**Feature**: 001-manual-trade-history
**Date**: 2026-04-28
**Base path**: `/api/manual-trades` (Next.js proxy → Python `:8199/api/trades/manual`)

All endpoints require `tg_journal_auth` cookie matching `JOURNAL_TOKEN`.

---

## GET /api/manual-trades

List manual trades with optional filters.

**Query params**:

| Param | Type | Description |
| --- | --- | --- |
| `symbol` | string | Filter by symbol (e.g. `EURUSD`) |
| `status` | string | `open` or `closed` |
| `start_date` | ISO string | Entry time >= this date |
| `end_date` | ISO string | Entry time <= this date |

**Response** `200 OK`:

```json
[
  {
    "id": 1,
    "symbol": "EURUSD",
    "direction": "long",
    "entry_price": 1.08512,
    "exit_price": 1.09001,
    "entry_time": "2026-04-25T09:30:00+00:00",
    "exit_time": "2026-04-25T11:15:00+00:00",
    "pnl": 0.00489,
    "pnl_percent": 0.45,
    "status": "closed",
    "notes": "Clean breakout above KC middle",
    "tags": ["cti-setup", "london-session"],
    "created_at": "2026-04-25T09:30:05+00:00",
    "updated_at": "2026-04-25T11:15:10+00:00"
  }
]
```

**Changes from v1**: Response now includes `tags: string[]` field.

---

## POST /api/manual-trades

Create a new manual trade.

**Request body**:

```json
{
  "symbol": "EURUSD",
  "direction": "long",
  "entry_price": 1.08512,
  "exit_price": 1.09001,
  "entry_time": "2026-04-25T09:30:00+00:00",
  "exit_time": "2026-04-25T11:15:00+00:00",
  "notes": "Optional note",
  "tags": ["cti-setup"]
}
```

Required: `symbol`, `direction`, `entry_price`, `entry_time`.
Optional: `exit_price`, `exit_time`, `notes`, `tags`.

**Response** `201 Created`: Created `ManualTrade` object (same shape as GET item).

**Changes from v1**: Request now accepts optional `tags: string[]`.

---

## PUT /api/manual-trades/:id

Update an existing manual trade.

**Request body**: Any subset of writable fields:

```json
{
  "exit_price": 1.09001,
  "exit_time": "2026-04-25T11:15:00+00:00",
  "notes": "Updated note",
  "tags": ["cti-setup", "scaled-out"]
}
```

**Response** `200 OK`: Updated `ManualTrade` object.

**Changes from v1**: Request now accepts optional `tags: string[]`.

---

## DELETE /api/manual-trades/:id

Delete a manual trade.

**Response** `200 OK`:

```json
{ "deleted": true }
```

No changes from v1.

---

## GET /api/manual-trades/stats

Summary statistics for all manual trades.

**Response** `200 OK`:

```json
{
  "total_trades": 42,
  "closed_trades": 38,
  "open_trades": 4,
  "wins": 24,
  "losses": 14,
  "win_rate": 63.16,
  "total_pnl": 1.84,
  "avg_pnl": 0.048,
  "avg_pnl_percent": 0.44
}
```

No changes from v1.
