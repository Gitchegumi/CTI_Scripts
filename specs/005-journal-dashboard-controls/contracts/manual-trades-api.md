# Contract: Manual Trade P&L and Developing Mode

## Scope

Applies to manual trade create, update, unified list, dashboard history, summary, and export behavior.

## Mode Display

| Internal Value | User-Facing Label |
| --- | --- |
| `alert_only` | Developing |
| `demo` | Demo |
| `live` | Live |

Internal values remain unchanged in storage and compatibility APIs.

## P&L Update Rules

### Allowed in Developing Mode

When current mode is `alert_only`, manual trade updates may include:

- `pnl`
- `pnl_percent`
- existing protected trade facts already allowed in alert_only
- notes and tags

### Restricted Outside Developing Mode

When current mode is `demo` or `live`, protected trade facts including `pnl` and `pnl_percent` are not editable. Notes and tags remain editable where already supported.

## Dashboard History

`GET /api/trades/history?count=50`

### Behavior

- Requires existing journal authentication.
- Returns local manual trade records when they exist.
- Broker/source trade-history failure does not cause a 500 if local manual history is readable.
- Response shape remains compatible with dashboard `ClosedTrade`.

## Validation

- Update manual P&L in `alert_only`; verify saved value in manual list, dashboard history, stats, and export.
- Attempt protected P&L update in `demo` or `live`; verify rejection or unavailable UI.
- Force source history unavailable; verify local manual records still return.
