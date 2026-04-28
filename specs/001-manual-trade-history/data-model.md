# Data Model: Manual Trade History

**Feature**: 001-manual-trade-history
**Date**: 2026-04-28

## Entities

### ManualTrade (existing — extended)

Stored in `src/tradegumi/data/manual_trades.db`, table `manual_trades`.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | Auto-increment |
| `symbol` | TEXT NOT NULL | e.g. `EURUSD` (normalized uppercase) |
| `direction` | TEXT NOT NULL | `'long'` or `'short'` |
| `entry_price` | REAL NOT NULL | |
| `exit_price` | REAL | NULL if trade still open |
| `entry_time` | TEXT NOT NULL | ISO 8601 |
| `exit_time` | TEXT | ISO 8601; NULL if open |
| `pnl` | REAL DEFAULT 0.0 | Computed from price delta |
| `pnl_percent` | REAL DEFAULT 0.0 | Computed |
| `status` | TEXT DEFAULT 'open' | `'open'` or `'closed'` |
| `notes` | TEXT DEFAULT '' | Free-form text |
| `tags` | TEXT DEFAULT '[]' | **NEW** — JSON array of strings |
| `created_at` | TEXT NOT NULL | ISO 8601 |
| `updated_at` | TEXT NOT NULL | ISO 8601 |

**Migration**: `ALTER TABLE manual_trades ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'`
guarded by a column-existence check in `init_schema()`.

**Constraints**:

- `direction` CHECK: `('long', 'short')`
- `status` CHECK: `('open', 'closed')`
- Tags normalized to lowercase, trimmed, at write time.
- Max tag length: 50 characters per tag; max 20 tags per trade.

---

### TradeAnnotation (new)

Stored in the same `manual_trades.db` file, new table `trade_annotations`.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | INTEGER PK | Auto-increment |
| `trade_id` | TEXT NOT NULL | Oanda trade ID or `"manual-{id}"` |
| `trade_source` | TEXT NOT NULL | `'broker'` or `'manual'` |
| `notes` | TEXT NOT NULL DEFAULT '' | Free-form text, max 1000 chars |
| `tags` | TEXT NOT NULL DEFAULT '[]' | JSON array of strings |
| `updated_at` | TEXT NOT NULL | ISO 8601 |

**Unique constraint**: `(trade_id, trade_source)` — one annotation record per trade.

**Indexes**:

- `idx_annotations_trade_id ON trade_annotations(trade_id)`

**Notes**:

- For broker trades, `trade_id` is the Oanda string ID returned by `GET /api/trades`.
- For manual trades, `trade_id` is `"manual-{manual_trade.id}"`.
- `trade_source` disambiguates ID space collisions.
- Upserting: `INSERT OR REPLACE` on `(trade_id, trade_source)`.

---

## TypeScript Types (updated)

In `dashboard/src/types/index.ts`:

```typescript
export interface ManualTrade {
  id: number;
  symbol: string;
  direction: "long" | "short";
  entry_price: number;
  exit_price: number | null;
  entry_time: string;
  exit_time: string | null;
  pnl: number;
  pnl_percent: number;
  status: "open" | "closed";
  notes: string;
  tags: string[];        // NEW — default []
  created_at: string;
  updated_at: string;
}

export interface TradeAnnotation {  // NEW
  trade_id: string;
  trade_source: "broker" | "manual";
  notes: string;
  tags: string[];
  updated_at: string;
}
```

---

## State Transitions

### ManualTrade status

```
open ──[exit_price provided]──► closed
```

Transition triggered when `exit_price` is set (create or update). No reverse transition;
once closed, a trade stays closed unless `exit_price` is cleared via edit.

### TradeAnnotation

No status. Upsert semantics: create on first annotation, replace on subsequent updates.
