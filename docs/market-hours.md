# Forex Market Hours

TradeGumi treats forex instruments as one continuous **weekly** trading session
rather than a simplified Monday–Friday calendar. This matches the live forex
market and fixes the case where Sunday evening (e.g., 21:40 Central) was
incorrectly reported as closed.

## Weekly session boundaries

| Boundary | US Central | US Eastern |
| --- | --- | --- |
| Weekly **open** (Sunday) | 16:00 CT | 17:00 ET |
| Weekly **close** (Friday) | 16:00 CT | 17:00 ET |

- The **Sunday open is inclusive**: 16:00:00 CT / 17:00:00 ET is open; 15:59:59
  CT is still closed.
- The **Friday close** is for the weekend break: 15:59:59 CT is still open;
  16:00:00 CT / 17:00:00 ET is closed.
- Monday through Thursday are continuously open across midnight and normal daily
  rollover (unless a separate swap blackout applies).
- Saturday, Sunday before the open, and Friday after the close are closed.

The decision is made in a single canonical **US Eastern** reference, so US
Central and Eastern displays — and daylight saving transitions — always agree on
one open/closed truth. A Central wall-clock time and its equivalent Eastern
wall-clock time produce the same result.

## Reason codes

Closed forex sessions report a stable reason for diagnostics:

| Reason | Meaning |
| --- | --- |
| `open` | The forex market is open. |
| `before_weekly_open` | Sunday, before the 17:00 ET weekly open. |
| `after_weekly_close` | Friday, after the 17:00 ET weekly close. |
| `weekend_break` | Saturday (and the rest of the weekend break). |

Closed forex states also carry a human-readable `session_boundary`, e.g.
`Next forex weekly open Sunday 16:00 CT / 17:00 ET`.

## Other symbol categories

- **Commodities** (XAUUSD, XAGUSD, OIL) intentionally follow the forex weekly
  session.
- **Crypto** (BTCUSD, ETHUSD, LTCUSD, XRPUSD) is always open.
- **Indices** keep their own weekday session windows and are not part of the
  forex week.

## Forced rescan availability

A forced rescan during an open forex session evaluates each symbol
independently. A global closed-market decision never collapses the whole
watchlist into "unavailable". Each symbol reports one of:

| Availability reason | Meaning |
| --- | --- |
| `available` | Eligible for scanning. |
| `market_closed` | The forex market is closed (a global condition). |
| `account_instrument_unavailable` | Not offered for the configured account. |
| `configured_unavailable` | Explicitly marked unavailable in configuration. |

`market_closed` is only used when the forex session itself is closed, so an
available symbol is never suppressed because another symbol is unavailable.

## Where this is surfaced

- **Loop state** (`/api/data/loop_state`): each symbol entry carries additive
  `market_open`, `availability_state`, `availability_reason`, and
  `session_boundary` fields.
- **Rescan callbacks**: include `market_open`, per-symbol `availability`, and
  `symbols_checked` / `symbols_available` / `symbols_unavailable` counts (the
  existing `trigger` field is preserved for backward compatibility).
- **Dashboard**: market-open polling is derived from the `market_open`
  diagnostic and ignores symbol-specific unavailability.

## Implementation

- `src/tradegumi/session_rules.py` — weekly forex boundaries and the
  `market_session_status` helper.
- `src/tradegumi/pre_session_scanner.py` — per-symbol availability evaluation.
- `src/tradegumi/main.py` — loop-state diagnostics, forced-rescan availability
  summary, and closed-market notifications.
