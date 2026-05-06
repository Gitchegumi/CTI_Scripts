# Contract: Dashboard UI Behavior

## Strategy Metrics Page

- Start and End date inputs remain calendar-date controls.
- Selecting an End date includes that whole date in summary, opportunities, comparison, and export.
- Export filename and visible metadata should not imply day-1 truncation.

## Signal Journal Page

- Adds Export CSV action.
- Export respects active grade filter.
- Adds Purge action with destructive confirmation.
- Purge confirmation states the scope and approximate matched count.
- Adds row-level Reset to Pending action for graded entries.
- Reset action preserves notes and original signal diagnostics.
- Page refreshes after purge or reset.

## Manual Trades Page

- Displays "Developing" anywhere current mode `alert_only` is shown to users.
- Allows P&L editing only in Developing mode.
- Shows read-only/annotation-only language for Demo and Live mode.

## Main Dashboard

- Trade History displays manual trade records when they exist.
- Missing trade correlations display empty confidence/correlation values without repeated console 404s.
- Hydration-sensitive date/time text must render consistently or be isolated to client-only rendering.
- `/api/trades/history?count=50` failure must not be silently ignored; user-visible state should distinguish no trades from load failure when appropriate.
