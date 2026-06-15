# Data Model: Forex Market Hours Rescan

## Forex Market Session Status

Represents the forex trading-session decision for a symbol at a specific evaluation time.

**Fields**

- `symbol`: Configured CTI symbol being evaluated.
- `category`: Symbol category used for session rules, with this feature focused on forex.
- `evaluated_at`: Timezone-aware timestamp of the session decision.
- `is_open`: Whether the forex market is open at `evaluated_at`.
- `reason`: Stable reason code such as `open`, `before_weekly_open`, `after_weekly_close`, or `weekend_break`.
- `session_boundary`: Human-readable boundary context when closed, such as the next Sunday open or Friday close in CT and ET.

**Validation Rules**

- Sunday 16:00:00 Central / 17:00:00 Eastern is open for forex instruments.
- Sunday 15:59:59 Central is not yet open for forex instruments.
- Normal weekdays after the Sunday open and before the Friday close are open for forex instruments.
- Friday 15:59:59 Central is still open for forex instruments.
- Friday 16:00:00 Central / 17:00:00 Eastern is closed for forex instruments.
- Saturday remains closed for forex instruments.

## Symbol Availability

Represents whether an individual configured symbol is eligible for scanning after forex market-session and account/instrument availability checks.

**Fields**

- `symbol`: Configured CTI symbol.
- `market_open`: Forex market-session decision used for this symbol.
- `available`: Whether this symbol may be included in the scan.
- `reason`: Stable reason code such as `available`, `market_closed`, `account_instrument_unavailable`, or `configured_unavailable`.
- `detail`: Operator-facing detail with enough context to understand the reason.

**Relationships**

- Belongs to one Forex Market Session Status decision.
- Appears within one Forced Rescan Result or loop-state snapshot.

**Validation Rules**

- `market_closed` can only be used when the forex market session status is closed.
- A symbol-specific unavailable reason must not be used to mark unrelated symbols unavailable.
- An available symbol must not be suppressed solely because another symbol is unavailable.

## Forced Rescan Result

Represents the operator-visible outcome of a manual or scheduled rescan.

**Fields**

- `trigger`: `api`, `periodic`, or `scheduled`.
- `requested_at`: Timezone-aware timestamp when the rescan was accepted or evaluated.
- `market_open`: Whether at least one configured forex symbol is in an open session.
- `symbols_checked`: Count of configured symbols considered.
- `symbols_available`: Count of symbols eligible for scanning.
- `symbols_unavailable`: Count of symbols excluded for market or symbol-specific reasons.
- `availability`: Per-symbol Symbol Availability results when exposed in diagnostics.
- `watchlist_counts`: Tier 1, Tier 2, and below-threshold counts from normal scan scoring.

**State Transitions**

1. Rescan requested by API, scheduled scan, or periodic scan.
2. Forex Market Session Status is evaluated per symbol/category.
3. Account/instrument availability is evaluated per symbol.
4. Eligible symbols are scanned normally.
5. Result is persisted to existing watchlist/loop-state outputs and callbacks.

**Validation Rules**

- During the open forex trading week, a forced rescan must not produce zero available symbols because of a global closed-market decision.
- Forced rescans that span the weekly forex open or close boundary must use the current decision time for each availability decision.
- Rescan output must distinguish zero available symbols due to true forex market closure from zero available symbols due to account/instrument availability.
