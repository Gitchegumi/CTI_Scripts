# Research: Manual Trade History Page

**Feature**: 001-manual-trade-history
**Date**: 2026-04-28

## Finding 1 — Root Cause of Production 404

**Confirmed**: `JOURNAL_TOKEN` is set and working in production — the page loads and
auth passes. The 404 errors are inside the page content, not on the page route itself.

Browser console shows two 404s on page load:

- `GET /api/status` → 404
- `GET /api/manual-trades` → 404

**Deployment context**: This is a **single combined container** — both the Python bot
(`:8199`) and the Next.js dashboard (`:3000`) run inside the same image
(`ghcr.io/gitchegumi/cti-scripts:latest`). Deployed via TrueNAS GUI.

`NEXT_PUBLIC_API_URL=http://10.0.0.116:8199` set in TrueNAS GUI **has no effect**.
`NEXT_PUBLIC_` variables are baked into the Next.js bundle at image build time, not
injected at runtime. `localhost:8199` is the correct value for the single-container
deployment (bot and dashboard colocated), and it is already the default in
`next.config.js` and set as a runtime `ENV` in the Dockerfile `final` stage.

**Root cause (confirmed)**: Two defects in the CI pipeline prevent a successful image
push even after merging to master:

1. **Missing `ARG` in `dashboard` stage**: `next.config.js` evaluates
   `process.env.NEXT_PUBLIC_API_URL` during `npm run build` (the rewrites config is
   embedded in the `.next/server` bundle at build time). The Dockerfile `dashboard`
   stage has no `ARG NEXT_PUBLIC_API_URL` declaration, so the value is `undefined`
   at build time rather than `http://localhost:8199`. The fallback in `next.config.js`
   (`?? 'http://localhost:8199'`) only applies in JavaScript; `process.env` without
   an ARG returns `undefined`, not the fallback, during the webpack build phase.

2. **Missing `actions: write` permission on `build` job**: The `build` job uses
   `cache-to: type=gha,mode=max`, which requires write access to the GitHub Actions
   cache. The job only declares `contents: read` and `packages: write`. Without
   `actions: write`, the GHA cache write fails, which in some versions of
   `docker/build-push-action` causes the entire step to error — meaning the image is
   never pushed to GHCR even after a master merge.

Additionally, no `build-args` are passed to either `validate` or `build` steps, so
the `ARG` fix alone is insufficient — the value must also be injected through the CI.

**Fix required** (two code changes, no GitHub repo variables needed):

1. **Dockerfile** (`dashboard` stage): Add before `RUN npm run build`:

   ```dockerfile
   ARG NEXT_PUBLIC_API_URL=http://localhost:8199
   ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
   ```

2. **Workflow** (`.github/workflows/docker-publish.yml`):
   - Add `actions: write` to the `build` job permissions.
   - Add `build-args: NEXT_PUBLIC_API_URL=http://localhost:8199` to both
     `validate` and `build` docker build steps.

`localhost:8199` is hardcoded in the workflow because it is always correct for
the single-container deployment — no GitHub Actions repository variable needed.

After merging this branch to master, the CI `build` job will push a corrected image.
In TrueNAS GUI, pull the new image and redeploy. Confirm container logs show both
`API server running on :8199` and `Next.js ready on http://:::3000`.

---

## Finding 2 — Tags Storage Strategy

**Decision**: JSON array string in SQLite `TEXT` column.

- Format: `'["cti-setup", "missed-entry"]'` stored as TEXT.
- Normalized at write time: lowercase, trimmed whitespace.
- Default: `'[]'` (empty JSON array).

**Rationale**: SQLite has no array type. JSON string avoids comma-separator edge cases
and is trivially round-tripped via Python `json.loads`/`json.dumps` and `JSON.parse`/
`JSON.stringify` in TypeScript. Single-user scale means no JSON query performance concern.

**Alternatives considered**:

- Comma-separated string: fails on tags containing commas.
- Separate junction table: overkill for < 1000 trades, single user.

---

## Finding 3 — Automated Trade Annotations Storage

**Decision**: New `trade_annotations` table in the existing `manual_trades.db` SQLite
file. Keyed by `(trade_id, trade_source)` unique pair.

- `trade_source = 'broker'` for Oanda automated trades.
- `trade_source = 'manual'` for manual trades (redundant with `manual_trades.notes`/
  `tags`, but allows unified annotation lookup).
- New Python module: `src/tradegumi/trade_annotations.py`.
- New Next.js API route: `dashboard/src/app/api/trade-annotations/route.ts`.

**Rationale**: Broker `ClosedTrade` records are ephemeral (fetched from Oanda API on
demand, not stored locally). A separate annotations table persists only the user-added
overlay data, not the full trade record.

---

## Finding 4 — Dashboard Integration Approach

**Decision**: Client-side merge in `useData.ts` + `page.tsx`.

New `useManualTrades` hook fetches `GET /api/manual-trades?status=closed`. In `page.tsx`,
closed manual trades are mapped to `ClosedTrade` shape and merged with broker trades
before passing to `<TradeHistory>`.

**ManualTrade → ClosedTrade mapping**:

| ManualTrade | ClosedTrade | Transform |
| --- | --- | --- |
| `id` | `id` | `"manual-" + id` |
| `symbol` | `symbol` | direct |
| `direction` | `side` | `"long"→"BUY"`, `"short"→"SELL"` |
| `entry_price` | `open_price` | direct |
| `exit_price ?? 0` | `close_price` | fallback 0 |
| `entry_time` | `open_time` | direct |
| `exit_time ?? ""` | `close_time` | fallback empty |
| `pnl` | `pnl` | direct |
| `0` | `volume` | not tracked |
| `pnl` | `realized_pl` | approximation |
| `0` | `financing` | not tracked |

Only `status === "closed"` manual trades included in dashboard merge.

**Alternatives considered**:

- New `/api/trades/combined` Python endpoint: more backend complexity, couples domains.
- Extend Python `/api/trades` handler: violates separation of concerns.

---

## Finding 5 — Mode-Aware UI Enforcement

**Decision**: Gate all trade data mutations (add, edit, delete) on `mode === "alert_only"`.
In `demo`/`live` modes, replace action buttons with an annotation button that opens an
inline notes/tags editor.

**UI matrix**:

| Mode | Add Trade | Edit Trade | Delete Trade | Annotate |
| --- | --- | --- | --- | --- |
| `alert_only` | ✅ | ✅ | ✅ | ✅ in edit form |
| `demo` | ❌ | ❌ | ❌ | ✅ annotation panel |
| `live` | ❌ | ❌ | ❌ | ✅ annotation panel |

**Gap in current implementation**: The edit (`✎`) and delete (`🗑`) buttons currently
appear for all modes. Only the "Add Trade" button is correctly mode-gated.
