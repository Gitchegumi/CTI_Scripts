# Quickstart Validation: Manual Trade History

**Feature**: 001-manual-trade-history
**Date**: 2026-04-28

Use this guide to validate the feature end-to-end after implementation.

## Prerequisites

- Bot running locally: `cd src && poetry run python -m tradegumi.main --mode alert_only`
- Dashboard running: `cd dashboard && npm run dev`
- `JOURNAL_TOKEN` set in `.env` (e.g. `JOURNAL_TOKEN=testtoken123`)
- Browser open at `http://localhost:3000`

---

## 0. Verify Production Image is Current (TrueNAS)

This runs as a **single combined container** (bot + dashboard in one image). Before any
validation, confirm the image is current:

1. Build and push the latest image:

   ```bash
   docker build -t ghcr.io/gitchegumi/cti-scripts:latest .
   docker push ghcr.io/gitchegumi/cti-scripts:latest
   ```

2. In TrueNAS GUI, pull the new image and redeploy the container.
3. In container logs, confirm you see both:
   - `API server running on :8199` (Python bot)
   - `Next.js ready on http://:::3000` (dashboard)

Note: `NEXT_PUBLIC_API_URL` set in TrueNAS GUI env vars has no effect — `NEXT_PUBLIC_`
variables are baked into the Next.js bundle at image build time.

---

## 1. Verify Page Loads (FR-001)

1. In a browser where you are NOT logged in, navigate to `http://localhost:3000/manual-trades`.
2. **Expected**: Redirected to `/journal/login?from=/manual-trades`.
3. Log in with the journal token.
4. **Expected**: Redirected back to `/manual-trades`. Page renders with trade history
   table (or empty state message). No 404 errors in the browser console.

---

## 2. Add a Manual Trade in alert_only Mode (FR-003)

1. Confirm the bot mode shows `alert_only` in the dashboard header.
2. On `/manual-trades`, click **+ Add Trade**.
3. Fill in: Symbol=`EURUSD`, Direction=`Long`, Entry Price=`1.08500`,
   Entry Time=today 09:00, Tags=`cti-setup`.
4. Submit the form.
5. **Expected**: New trade appears in the table with status `open`, tag `cti-setup` visible.

---

## 3. Close the Trade (FR-004)

1. Click **Edit** (✎) on the trade just added.
2. Set Exit Price=`1.09000`, Exit Time=today 11:00.
3. Save.
4. **Expected**: Trade status changes to `closed`. P&L shows `+$0.00500` (or pip-value
   equivalent). Trade now eligible for dashboard merge.

---

## 4. Verify Trade Appears on Main Dashboard (FR-008)

1. Navigate to `http://localhost:3000` (main dashboard).
2. Within 30 seconds (one polling cycle), find the `EURUSD` trade in the **Trade History**
   component.
3. **Expected**: The manually entered trade appears alongside any broker trades, sorted by
   close time.

---

## 5. Verify Mode Locking (FR-003 / FR-004 / FR-005)

1. From the Settings Panel on the main dashboard, switch mode to `demo`.
2. Navigate to `/manual-trades`.
3. **Expected**: **+ Add Trade** button is hidden. Edit (✎) and Delete (🗑) buttons are
   replaced by an **annotate** button.

---

## 6. Add Notes and Tags in demo Mode (FR-006 / FR-007)

1. With mode=`demo`, click the annotate button on any trade.
2. Enter a note: `"Solid setup — KC middle bounce"`.
3. Add tags: `london-session`, `high-confidence`.
4. Save.
5. **Expected**: Note and tags persist on the trade row after page reload.

---

## 7. Filter by Tag (FR-010)

1. In the trade history table on `/manual-trades`, use the tag filter.
2. Filter to `cti-setup`.
3. **Expected**: Only trades tagged `cti-setup` are shown.

---

## 8. Delete a Manual Trade (FR-005)

1. Switch mode back to `alert_only`.
2. Click Delete (🗑) on the manual trade.
3. Confirm deletion.
4. **Expected**: Trade removed from `/manual-trades` table and from the main dashboard
   Trade History within one polling cycle.
