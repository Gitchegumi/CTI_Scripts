# Research: Forex Market Hours Rescan

## Decision: Treat the forex trading week as Sunday 17:00 Eastern through Friday 17:00 Eastern

**Rationale**: The reported bug occurs because existing session logic treats every Sunday as closed for non-crypto symbols, but the intended behavior is the full forex trading week. Forex is generally available 24 hours per day during the trading week, opening Sunday at 17:00 Eastern and closing Friday at 17:00 Eastern. The session helper should classify Sunday 16:00:00 CT / 17:00:00 ET and later as open, all normal weekdays as open, and Friday 16:00:00 CT / 17:00:00 ET and later as closed for the weekend break.

**Alternatives considered**:

- Keep Sunday closed until Monday. Rejected because it directly contradicts the forex trading week.
- Open Sunday at 17:05 ET as the current comment suggests for one provider. Rejected for this feature because the operator requirement states 17:00 ET and the broader forex market convention uses the 17:00 ET weekly boundary.
- Keep Friday open until midnight. Rejected because the forex weekend break begins at the Friday 17:00 ET close.
- Make the weekly boundaries configurable before fixing behavior. Deferred because the immediate defect has clear expected boundaries and adding configuration would increase scope.

## Decision: Use timezone-aware conversion around US Central and Eastern weekly boundaries

**Rationale**: The user reported Central time while existing code evaluates New York time. The plan should preserve one canonical session decision while tests validate Central and Eastern equivalents, including daylight saving behavior.

**Alternatives considered**:

- Compare naive local times. Rejected because it is vulnerable to host timezone and daylight saving changes.
- Store separate Central and Eastern schedules. Rejected because it risks divergent behavior; one canonical session decision with tested conversions is simpler.

## Decision: Keep forex market-session state separate from symbol availability

**Rationale**: Forced rescans depend on both global session state and broker/account symbol availability. The bug reports "none of the symbols are available," but the desired outcome is for an open forex session to evaluate each symbol independently. A market-closed decision should not be reused as an all-symbol unavailable result.

**Alternatives considered**:

- Skip availability checks on forced rescan. Rejected because unavailable symbols still need to be excluded for valid account or instrument reasons.
- Treat all symbols as available whenever the forex market is open. Rejected because account-specific availability can still be false.

## Decision: Add diagnostic reasons only where existing payloads cannot distinguish outcomes

**Rationale**: The dashboard already derives market-open state from loop-state symbol entries and rescan is already an API command. The smallest useful contract is to ensure loop/watchlist/rescan results can distinguish `market_closed` from `symbol_unavailable`, without introducing a new UI surface unless the existing one cannot render it.

**Alternatives considered**:

- Add a new diagnostics endpoint. Deferred because existing `/api/data/loop_state`, `/api/data/watchlist`, and rescan callbacks already carry operational state.
- Log-only diagnostics. Rejected because the operator needs visible state, and Constitution IV requires observable machine-readable outputs.

## Decision: Preserve existing scan cadence and signal evaluation rules

**Rationale**: This feature is a session/availability correction. Changing scan cadence, indicator thresholds, tiers, risk limits, or watchlist scoring would make the fix harder to validate and could violate signal integrity expectations.

**Alternatives considered**:

- Rescore all watchlist logic around forex session changes. Rejected as unrelated.
- Change signal engine eligibility while fixing sessions. Rejected because normal signal gates already cover actionable evaluation.
