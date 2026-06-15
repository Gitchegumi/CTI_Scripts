# Feature Specification: Forex Market Hours Rescan

**Feature Branch**: `022-market-hours-rescan`  
**Created**: 2026-06-15  
**Status**: Draft  
**Input**: User description: "Currently, the market timing is a little off. It's telling me the markets are closed at 21:40 Central US time on Sunday when they are, in fact, open. They open at 16:00 Central 17:00 Eastern on Sunday in America. It's also saying that none of the symbols are available when doing a forces rescan. This should not just focus on Sunday; it should accurately match the actual open times of the FOREX market."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recognize the Forex Trading Week (Priority: P1)

As an operator monitoring forex trading signals, I need the system to recognize the actual weekly forex trading window from Sunday 17:00 Eastern / 16:00 Central through Friday 17:00 Eastern / 16:00 Central so that signal scanning and availability decisions match the live market rather than a simplified weekday calendar.

**Why this priority**: Incorrectly reporting forex markets closed prevents timely scanning during live sessions and undermines trust in all downstream symbol availability results.

**Independent Test**: Can be fully tested by evaluating market status across the weekly forex open, weekday continuous trading period, Friday close, and weekend closure.

**Acceptance Scenarios**:

1. **Given** the local reference time is Sunday 21:40 Central US time, **When** the operator checks forex market status, **Then** the system reports the forex market as open.
2. **Given** the local reference time is Sunday 15:59 Central US time, **When** the operator checks forex market status, **Then** the system reports the weekly forex session as not yet open.
3. **Given** the local reference time is Sunday 16:00 Central US time / 17:00 Eastern US time, **When** the operator checks forex market status, **Then** the system treats the weekly forex session as open.
4. **Given** the local reference time is a normal weekday between the Sunday open and Friday close, **When** the operator checks forex market status, **Then** the system reports the forex market as open.
5. **Given** the local reference time is Friday 16:00 Central US time / 17:00 Eastern US time, **When** the operator checks forex market status, **Then** the system treats the weekly forex session as closed for the weekend break.

---

### User Story 2 - Forced Rescan Preserves Symbol Availability (Priority: P2)

As an operator running a forced rescan while the forex market is open, I need available symbols to remain eligible for scanning so that a rescan does not incorrectly suppress the whole watchlist.

**Why this priority**: A forced rescan is a recovery and verification tool; marking every symbol unavailable during an open session leaves the operator unable to confirm active opportunities.

**Independent Test**: Can be fully tested by triggering a forced rescan during the open forex trading week and verifying that symbols with valid market access are reported as available or individually unavailable based on their own status, not a global closed-market decision.

**Acceptance Scenarios**:

1. **Given** the forex market is open between Sunday 16:00 Central / 17:00 Eastern and Friday 16:00 Central / 17:00 Eastern, **When** the operator starts a forced rescan, **Then** the system evaluates each configured forex symbol for availability instead of marking all symbols unavailable.
2. **Given** some symbols are unavailable for symbol-specific reasons during an open forex market, **When** the operator starts a forced rescan, **Then** unavailable results identify only the affected symbols and do not hide available symbols.
3. **Given** a forced rescan completes during an open forex market, **When** the operator reviews the rescan result, **Then** the result clearly distinguishes forex market-open status from per-symbol availability.

---

### User Story 3 - Explain Market-Closed Decisions (Priority: P3)

As an operator reviewing scan diagnostics, I need forex market-closed and symbol-unavailable decisions to include clear timing context so that I can quickly tell whether a blocked scan is expected or erroneous.

**Why this priority**: Clear diagnostics reduce confusion when weekly session boundaries, time zones, daylight saving changes, and symbol-level availability interact.

**Independent Test**: Can be fully tested by checking scan diagnostics around the weekly forex open and close boundaries and confirming the displayed reason includes the relevant boundary and timezone context.

**Acceptance Scenarios**:

1. **Given** forex market status is closed before the Sunday weekly open, **When** scan diagnostics are shown, **Then** the diagnostics include the next expected Sunday open time in Central and Eastern US terms.
2. **Given** forex market status is closed after the Friday weekly close, **When** scan diagnostics are shown, **Then** the diagnostics include the next expected Sunday open time in Central and Eastern US terms.
3. **Given** a symbol is unavailable while the forex market is open, **When** scan diagnostics are shown, **Then** the diagnostics identify the symbol-specific reason instead of reporting a global market closure.

### Edge Cases

- Sunday forex session boundary exactly at 16:00 Central / 17:00 Eastern must be treated as open, not closed.
- Friday forex session boundary exactly at 16:00 Central / 17:00 Eastern must be treated as closed for the weekend break.
- Weekday forex sessions between the Sunday open and Friday close must remain open across midnight and normal daily rollover periods unless a separate configured blackout applies.
- Daylight saving time must not shift the intended US Central and Eastern weekly session interpretation.
- Forced rescans that span the weekly open or close boundary must evaluate availability using the market status applicable at the time each scan decision is made.
- Non-forex symbols with distinct trading calendars or temporary unavailability must remain individually reportable without changing the forex market state.
- User-facing text must not claim all symbols are unavailable when only the market status check failed or when individual symbols need separate availability checks.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST recognize the forex trading week as open from Sunday 16:00 Central US time / 17:00 Eastern US time until Friday 16:00 Central US time / 17:00 Eastern US time.
- **FR-002**: System MUST report Sunday 21:40 Central US time as open for forex instruments.
- **FR-003**: System MUST treat the exact Sunday forex open boundary as inclusive, so the session is open at 16:00:00 Central US time.
- **FR-004**: System MUST treat the exact Friday forex close boundary as closed for the weekend break.
- **FR-005**: System MUST preserve accurate forex market status across Central and Eastern US timezone displays, including daylight saving transitions.
- **FR-006**: Users MUST be able to trigger a forced rescan during an open forex market without the system marking every configured symbol unavailable because of an incorrect global closed-market state.
- **FR-007**: System MUST evaluate symbol availability independently during a forced rescan and report symbol-specific unavailability without suppressing symbols that are available.
- **FR-008**: System MUST clearly distinguish global forex market-closed status from per-symbol unavailable status in operator-visible scan results or diagnostics.
- **FR-009**: System MUST provide enough timing context in forex market-closed diagnostics for an operator to understand the relevant weekly open and close boundaries.
- **FR-010**: System MUST avoid changing unrelated signal eligibility rules, watchlist membership, risk gates, or symbol configuration while correcting forex market timing and rescan availability behavior.

### Key Entities

- **Forex Market Session**: The trading-session status for forex instruments, including whether the market is open or closed and the relevant weekly open/close boundaries.
- **Symbol Availability**: The per-symbol eligibility result used during scans and forced rescans, including available status and any symbol-specific unavailable reason.
- **Forced Rescan Result**: The operator-visible outcome of a manual rescan request, including forex market status, symbol availability outcomes, and diagnostic reasons.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At Sunday 21:40 Central US time, 100% of configured forex instruments are reported as market-open unless a separate instrument-specific availability check says otherwise.
- **SC-002**: At Sunday 16:00 Central US time, the forex market-open decision succeeds on the first status check in boundary tests.
- **SC-003**: At Friday 16:00 Central US time, the forex market-closed decision succeeds on the first status check in boundary tests.
- **SC-004**: During the open forex trading week, a forced rescan reports available configured forex symbols as available in at least 99% of valid scan attempts, excluding symbols with explicit symbol-specific unavailability.
- **SC-005**: In diagnostic review, operators can distinguish "market closed" from "symbol unavailable" outcomes for every forced rescan result.
- **SC-006**: The correction introduces no new false forex market-open result before Sunday 16:00 Central or after Friday 16:00 Central in boundary validation.

## Assumptions

- Forex instruments use a weekly market session that opens Sunday at 16:00 Central US time / 17:00 Eastern US time and closes Friday at 16:00 Central US time / 17:00 Eastern US time.
- Existing watchlist symbols and signal rules remain in scope; adding or removing tradable symbols is out of scope.
- Per-symbol availability may still fail for valid symbol-specific reasons, and this feature only prevents incorrect global closure or blanket unavailable decisions.
- Operator-facing diagnostics already have a place to show scan or availability reasons; this feature requires clear content there but does not require a new dashboard surface unless no existing surface can represent the distinction.
