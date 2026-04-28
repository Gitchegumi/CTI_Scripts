# Implementation Plan: Manual Trade History Page

**Branch**: `001-manual-trade-history` | **Date**: 2026-04-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-manual-trade-history/spec.md`

## Summary

Fix the production API 404s caused by a stale combined container image (rebuild + push required),
complete the unified trade history view (manual and automated trades), add tags support to
manual trades, add a trade annotations store for automated trades, enforce mode-aware CRUD
controls, and surface manual trades in the main dashboard `TradeHistory` component via a
client-side merge.

The page loads and auth passes in production. The 404s are on `/api/status` and
`/api/manual-trades` — the App Router handlers don't exist in the stale build. The full
backend infrastructure is correctly implemented locally. This work is primarily additive:
Docker rebuild + schema extension for tags + new trade-annotations table + client-side
data merging + UI mode-locking.

## Technical Context

**Language/Version**: TypeScript / Next.js 14+ (dashboard); Python 3.11 (bot backend)
**Primary Dependencies**: React, Tailwind CSS, Next.js App Router (dashboard); SQLite3,
aiohttp-free stdlib HTTP server (Python backend)
**Storage**: SQLite (`manual_trades.db` at `src/tradegumi/data/`) for manual trades and
the new trade annotations table
**Testing**: No test framework currently in use for dashboard; pytest available for Python
**Target Platform**: Web browser (Next.js dashboard served from Docker or `npm start`)
**Project Type**: Web application (Next.js frontend + Python HTTP backend)
**Performance Goals**: Page load < 3s; manual trade appears in dashboard within 30s
(one polling cycle)
**Constraints**: Auth required via `JOURNAL_TOKEN` cookie (middleware + API handlers);
broker `ClosedTrade` data is read-only; SQLite must remain the only data store (no external
DB); no breaking changes to existing Python API endpoints
**Scale/Scope**: Single user; tens to hundreds of trades; no concurrency concerns

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | ✅ PASS | No signal logic touched |
| II. Execution Layer Abstraction | ✅ PASS | No broker execution changes |
| III. Risk-First | ✅ PASS | No risk/order logic touched |
| IV. Observable by Default | ⚠️ GAP | Manual trade CRUD is not currently posted to Discord. Logging trade add/edit/delete is acceptable as info-level (not required to Discord), but operations MUST be written to Python logs. No constitution violation — but worth noting. |
| V. Configuration-Driven | ✅ PASS | Mode-aware UI behavior driven by `trading_mode` from `/api/status` |
| Security & Credential Hygiene | ✅ PASS | Auth enforced at middleware + API handler level; no new credentials |
| Pull Request Policy | 📋 PENDING | DockeGumi MUST be requested as reviewer |

No gates failed. No complexity violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/001-manual-trade-history/
├── plan.md              # This file
├── research.md          # Phase 0 findings
├── data-model.md        # Phase 1 schema
├── quickstart.md        # Phase 1 validation guide
├── contracts/
│   ├── trade-annotations-api.md
│   └── manual-trades-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
dashboard/src/
├── app/
│   ├── manual-trades/
│   │   └── page.tsx                       # UPDATE: mode-lock, combined view, tags UI
│   └── api/
│       ├── manual-trades/
│       │   ├── [[...id]]/route.ts         # UPDATE: pass tags field through
│       │   └── stats/route.ts             # no change
│       └── trade-annotations/
│           └── route.ts                   # NEW: proxy to Python trade annotations API
├── components/
│   └── TradeHistory.tsx                   # no change needed
├── hooks/
│   └── useData.ts                         # UPDATE: add useManualTrades hook
└── types/
    └── index.ts                           # UPDATE: add tags to ManualTrade; add TradeAnnotation

src/tradegumi/
├── manual_trades.py                       # UPDATE: add tags column
├── api_server.py                          # UPDATE: add /api/trade-annotations endpoints
└── trade_annotations.py                   # NEW: SQLite CRUD for automated trade annotations
```

**Structure Decision**: Web application with Python backend. No new projects introduced.
All changes are additive to existing modules.

---

## Phase 0: Research

*Research findings for all unknowns identified in Technical Context.*

### Finding 1 — Root Cause of Production 404

**Decision**: The 404 has two contributing causes that must both be addressed:

1. **Primary**: `JOURNAL_TOKEN` env var is almost certainly not set (or wrong) in the
   production environment. The middleware's `isAuthed` check is `!!expected && token ===
   expected` — if `JOURNAL_TOKEN` is unset, `expected` is `undefined`, `!!expected` is
   `false`, and every request redirects to `/journal/login`. This redirect *looks* like a
   404 if the login page itself also fails or if the user interprets the login redirect
   as the page not existing.

2. **Secondary**: The `manual-trades/page.tsx` file shows as `M` (modified, unstaged) in
   git — meaning recent significant changes to the page have not been committed or deployed.
   The production server is running an older build that may predate some of these changes.

**Fix**: Verify `JOURNAL_TOKEN` is set in the production `.env` file. Commit and deploy
the current page changes.

**Rationale**: All routing infrastructure exists and is correct. No Next.js routing
changes required.

---

### Finding 2 — Tags Storage Strategy

**Decision**: Store tags as a JSON array string (`TEXT`) in SQLite:

- `manual_trades` table: add `tags TEXT NOT NULL DEFAULT '[]'`
- New `trade_annotations` table: `tags TEXT NOT NULL DEFAULT '[]'`

Storing as JSON (`["cti-setup", "missed-entry"]`) rather than comma-separated avoids
parsing edge cases for tags containing commas.

**Rationale**: SQLite has no native array type. JSON string is the idiomatic approach
for SQLite; Python's stdlib `json` module handles serialization/deserialization. Tags are
normalized to lowercase and stripped of leading/trailing whitespace at write time.

**Alternatives considered**:

- Comma-separated string: simpler but fails on tags with commas.
- Separate `tags` junction table: overkill for single-user app with < 1000 trades.

---

### Finding 3 — Automated Trade Annotations Storage

**Decision**: New `trade_annotations` SQLite table in the same `manual_trades.db` file,
keyed by `(trade_id, trade_source)` pair:

```sql
CREATE TABLE IF NOT EXISTS trade_annotations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id     TEXT NOT NULL,
    trade_source TEXT NOT NULL DEFAULT 'broker',  -- 'broker' or 'manual'
    notes        TEXT NOT NULL DEFAULT '',
    tags         TEXT NOT NULL DEFAULT '[]',
    updated_at   TEXT NOT NULL,
    UNIQUE(trade_id, trade_source)
);
```

This is separate from `manual_trades` because broker `ClosedTrade` records come from the
Oanda API and are not stored in the local DB — only the annotation overlay is stored.

**Rationale**: Keeps all annotation state in a single SQLite file. `trade_id` for broker
trades is the Oanda string ID (e.g., `"12345678"`). `trade_id` for manual trades is
`"manual-{id}"`. The `trade_source` discriminator avoids collisions.

**New Python module**: `src/tradegumi/trade_annotations.py` handles CRUD for this table.
**New Next.js route**: `dashboard/src/app/api/trade-annotations/route.ts` proxies to
Python backend.

---

### Finding 4 — Dashboard Integration Approach

**Decision**: Client-side merge in `useData.ts`. Add a `useManualTrades` hook that fetches
closed manual trades from `/api/manual-trades?status=closed`. In `dashboard/src/app/page.tsx`,
merge manual trades (mapped to `ClosedTrade` shape) with broker trades before passing to
`<TradeHistory>`.

**Mapping** `ManualTrade` → `ClosedTrade`:

| ManualTrade field | ClosedTrade field | Transform |
| --- | --- | --- |
| `"manual-" + id` | `id` | string prefix to avoid collision |
| `symbol` | `symbol` | direct |
| `direction === "long" ? "BUY" : "SELL"` | `side` | remap |
| `entry_price` | `open_price` | direct |
| `exit_price ?? 0` | `close_price` | fallback |
| `entry_time` | `open_time` | direct |
| `exit_time ?? ""` | `close_time` | fallback |
| `pnl` | `pnl` | direct |
| `0` | `volume` | not tracked |
| `pnl` | `realized_pl` | approximation |
| `0` | `financing` | not tracked |

Only manual trades with `status === "closed"` are merged into the dashboard view.

**Rationale**: No new backend endpoint required. The `ClosedTrade` shape used by
`TradeHistory.tsx` is already well-defined. Client-side merge keeps the data flow simple
and avoids Python backend changes for display logic.

**Alternatives considered**:

- New `/api/trades/combined` endpoint: requires Python backend change and more
  complex proxy logic in Next.js.
- Extend Python's `/api/trades` endpoint: couples manual trade logic into the broker
  trade handler, violating separation of concerns.

---

### Finding 5 — Mode-Aware UI Enforcement

**Decision**: Current page already fetches mode via `/api/status` and uses it to show/hide
the "Add Trade" button. The **missing** enforcement is that edit/delete action buttons
also appear in `demo`/`live` modes. Fix: gate edit/delete buttons on `mode === "alert_only"`;
in other modes show only an annotation button (notes/tags inline editor).

UI behavior matrix:

| Mode | Add Trade | Edit Trade Data | Delete Trade | Notes/Tags |
| --- | --- | --- | --- | --- |
| `alert_only` | ✅ | ✅ | ✅ | ✅ (in edit form) |
| `demo` | ❌ | ❌ | ❌ | ✅ (annotation panel) |
| `live` | ❌ | ❌ | ❌ | ✅ (annotation panel) |

---

## Phase 1: Design & Contracts

### Data Model

See [data-model.md](data-model.md) for full schema.

**`manual_trades` table** (extend existing):

```sql
ALTER TABLE manual_trades ADD COLUMN tags TEXT NOT NULL DEFAULT '[]';
```

Existing rows default to empty JSON array. Schema migration runs on module load via
`init_schema()` with `ADD COLUMN IF NOT EXISTS` guard.

**`trade_annotations` table** (new):

```sql
CREATE TABLE IF NOT EXISTS trade_annotations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id     TEXT NOT NULL,
    trade_source TEXT NOT NULL DEFAULT 'broker',
    notes        TEXT NOT NULL DEFAULT '',
    tags         TEXT NOT NULL DEFAULT '[]',
    updated_at   TEXT NOT NULL,
    UNIQUE(trade_id, trade_source)
);
CREATE INDEX IF NOT EXISTS idx_annotations_trade_id ON trade_annotations(trade_id);
```

**TypeScript types** (update `types/index.ts`):

```typescript
export interface ManualTrade {
  // existing fields ...
  tags: string[];   // ADD — parsed from JSON, default []
}

export interface TradeAnnotation {
  trade_id: string;
  trade_source: "broker" | "manual";
  notes: string;
  tags: string[];
  updated_at: string;
}
```

### API Contracts

See [contracts/manual-trades-api.md](contracts/manual-trades-api.md) and
[contracts/trade-annotations-api.md](contracts/trade-annotations-api.md).

**Existing endpoints — updated to support tags:**

`GET /api/trades/manual` — response now includes `tags: string[]` on each trade.

`POST /api/trades/manual` — request body now accepts optional `tags: string[]`.

`PUT /api/trades/manual/:id` — request body now accepts optional `tags: string[]`.

**New endpoints:**

`GET /api/trade-annotations?trade_id={id}[&trade_source=broker]`
→ `TradeAnnotation` object (404 if not found → return empty annotation)

`POST /api/trade-annotations` — upsert annotation (insert or replace)
Body: `{ trade_id: string, trade_source: "broker"|"manual", notes?: string, tags?: string[] }`
→ Updated `TradeAnnotation`
