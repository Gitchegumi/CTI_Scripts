# Feature Specification: Continuation Management Events

**Feature Branch**: `018-continuation-management`  
**Created**: 2026-06-11  
**Status**: Draft  
**Input**: User description: "GitHub issue #100: Convert continuation signals into trade management events after pullback entry"

## Current Evidence

- The current-week journal export `signal-journal-all-2026-06-11.csv` contains 101 journal rows, all with `signal_type=continuation` and zero pullback entries.
- Of the 62 resolved continuation outcomes in that export, 59 reached stop loss and 3 reached take profit, producing a 95.2% stop-loss rate among resolved continuation-originated entries.
- The current-week metrics export `strategy-metrics-2026-06-08-to-2026-06-11.json` covers 2026-06-08 through 2026-06-12 UTC and reports 102,036 total evaluations, 441 emitted signals, 17,439 rejected signals, 84,155 skipped signals, 2,892 near misses, zero trade opportunities, and 340 prime-suppressed signals.
- This evidence reinforces the feature goal: continuation is reaching the journal and outcome accounting as if it were an entry stream, while pullback-originated trade entries are absent from the current signal record.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open Trades Only From Pullbacks (Priority: P1)

As a trader reviewing alerts and journal output, I want pullback signals to create new trade entries while continuation signals stop appearing as standalone trade entries, so the trade history matches the intended entry model.

**Why this priority**: The current behavior can make continuation alerts dominate the journal and obscure whether the strategy is actually finding pullback entries.

**Independent Test**: Can be tested by processing a signal sequence containing both pullback and continuation signals for the same symbol and direction, then confirming only the pullback creates a new open trade.

**Acceptance Scenarios**:

1. **Given** no active trade exists for a symbol and direction, **When** a valid pullback signal is observed, **Then** the system creates a new open trade linked to that pullback.
2. **Given** no active trade exists for a symbol and direction, **When** a continuation signal is observed without a qualifying pullback entry, **Then** the system records it as non-entry signal activity and does not create a new trade entry.
3. **Given** an active pullback-originated trade exists, **When** another pullback signal appears for the same symbol and direction before the active trade closes, **Then** the system does not create a duplicate trade entry.

---

### User Story 2 - Manage Active Trades With Continuations (Priority: P2)

As a trader with an active pullback-originated trade, I want same-direction continuation signals to become management events that may adjust stop loss and take profit, so strong follow-through can protect gains or extend targets without creating duplicate trades.

**Why this priority**: Continuation logic remains valuable, but its business value comes after trade entry as trade-management evidence.

**Independent Test**: Can be tested by opening a pullback trade, applying continuation events at different favorable-move levels, and verifying accepted events update current stop loss and/or take profit according to configured rules.

**Acceptance Scenarios**:

1. **Given** an active pullback-originated trade exists and price has moved favorably enough, **When** a same-direction continuation event is observed, **Then** the system records a management event and may tighten the current stop loss.
2. **Given** an active pullback-originated trade exists and continuation strength remains high, **When** a same-direction continuation event qualifies for target extension, **Then** the system records the old and new take profit and applies the extension within configured limits.
3. **Given** an active pullback-originated trade exists but the continuation event does not meet the management criteria, **When** the event is evaluated, **Then** the system records a rejected management event with a clear rejection reason and leaves the current stop loss and take profit unchanged.
4. **Given** an active pullback-originated trade exists, **When** continuation events continue appearing, **Then** the system prevents unlimited take-profit extension by enforcing configured extension limits.

---

### User Story 3 - Account For Managed Outcomes Correctly (Priority: P3)

As a trader reviewing performance, I want outcomes to reflect the final managed trade result, so a stop-loss exit beyond break-even is counted as a win instead of a loss merely because the exit used the stop-loss level.

**Why this priority**: Outcome reporting drives trust in the strategy and avoids misclassifying profit-protected exits.

**Independent Test**: Can be tested by applying management events that move stop loss to break-even or beyond, then closing trades through take profit, loss stop, break-even stop, profit stop, and manual close paths.

**Acceptance Scenarios**:

1. **Given** a buy trade has its current stop loss moved above entry, **When** price later hits that stop loss, **Then** the trade closes as a profit-protected win.
2. **Given** a sell trade has its current stop loss moved below entry, **When** price later hits that stop loss, **Then** the trade closes as a profit-protected win.
3. **Given** a trade exits at the original or adjusted take profit, **When** outcome accounting is generated, **Then** the trade is counted as a win.
4. **Given** a trade exits at break-even, **When** outcome accounting is generated, **Then** the trade is counted as break-even rather than win or loss.
5. **Given** a trade is manually closed for profit or loss, **When** outcome accounting is generated, **Then** the result reflects the actual manual close outcome.

---

### User Story 4 - Report Lifecycle Metrics Separately (Priority: P4)

As a strategy operator, I want metrics and exports to distinguish pullback entries, continuation management events, and final managed outcomes, so I can compare raw signal behavior against managed trade performance.

**Why this priority**: Operational diagnostics need to show whether continuation events improve trade management rather than simply increasing alert volume.

**Independent Test**: Can be tested by exporting a mixed lifecycle sample and confirming entry counts, management-event counts, accepted/rejected management counts, and managed-outcome metrics are separately visible.

**Acceptance Scenarios**:

1. **Given** a batch contains pullback entries and continuation management events, **When** journal/export data is produced, **Then** each row clearly identifies whether it is an entry event, a management event, or an outcome record.
2. **Given** continuation management events are accepted and rejected, **When** metrics are summarized, **Then** accepted and rejected counts are reported separately.
3. **Given** a managed trade closes, **When** metrics are summarized, **Then** managed-trade outcomes are reported separately from raw signal outcomes.
4. **Given** a continuation event in the opposite direction occurs while a trade remains active, **When** metrics are summarized, **Then** it is counted as an opposite-direction warning rather than a new entry.

### Edge Cases

- Continuation appears before any qualifying pullback entry for the same symbol and direction.
- Same-direction continuation appears after a trade has already reached its configured maximum number of target extensions.
- Continuation appears in the opposite direction while the original trade remains open.
- Pullback appears for the opposite direction while an active trade remains open.
- Price reaches a stop-loss level that has been moved to break-even or profit before the original take-profit level is reached.
- Management event evaluation cannot safely improve stop loss or take profit without increasing risk.
- Multiple continuation events arrive close together for the same active trade.
- A trade closes between signal observation and management-event evaluation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST create new trade entries only from qualifying pullback signals when no active trade exists for the same symbol and direction.
- **FR-002**: The system MUST prevent continuation signals from normally creating new trade entries while an active pullback-originated trade exists for the relevant symbol.
- **FR-003**: The system MUST link each open trade to the pullback signal that created it.
- **FR-004**: The system MUST record continuation signals observed during an active same-direction trade as trade management events linked to that trade.
- **FR-005**: The system MUST record whether each continuation management event was accepted or rejected.
- **FR-006**: The system MUST preserve the reason for each accepted or rejected management event.
- **FR-007**: The system MUST track old and new stop-loss values whenever a management event changes the current stop loss.
- **FR-008**: The system MUST track old and new take-profit values whenever a management event changes the current take profit.
- **FR-009**: The system MUST support configurable rules for favorable-move thresholds before stop-loss tightening is allowed.
- **FR-010**: The system MUST support configurable break-even behavior after sufficient favorable movement.
- **FR-011**: The system MUST support configurable take-profit extension behavior when continuation strength remains high.
- **FR-012**: The system MUST cap take-profit extension using configurable limits such as maximum extension count or maximum target distance.
- **FR-013**: The system MUST prevent a management event from increasing trade risk beyond the current accepted risk.
- **FR-014**: The system MUST treat opposite-direction continuation signals during an active trade as warning or exit-management evidence rather than automatic new entries.
- **FR-015**: The system MUST keep useful continuation events available for management even when duplicate prime-entry suppression would otherwise hide redundant entry alerts.
- **FR-016**: The system MUST classify trade exits as win, loss, break-even, or profit-protected win based on the actual final exit level relative to entry and direction.
- **FR-017**: The system MUST count a stop-loss exit beyond entry as a win when it locks in profit.
- **FR-018**: The system MUST count a stop-loss exit at entry as break-even.
- **FR-019**: The system MUST count a stop-loss exit worse than entry as a loss.
- **FR-020**: The system MUST count manual close outcomes according to whether the final close produced profit or loss.
- **FR-021**: The journal and exports MUST distinguish entry events from management events.
- **FR-022**: Metrics MUST report pullback entries opened, continuation management events observed, continuation events accepted, continuation events rejected, take-profit extensions, stop-loss tightenings, break-even moves, profit-protected stop wins, opposite-direction continuation warnings, average captured risk multiple, maximum favorable excursion before exit, and the difference between original-target outcomes and managed-trade outcomes.

### Key Entities

- **Trade Entry Event**: A pullback-originated trade opening event. Key attributes include trade identifier, entry signal identifier, entry signal type, symbol, direction, entry price, initial stop loss, initial take profit, current stop loss, current take profit, risk at entry, opened time, and open or closed status.
- **Trade Management Event**: A continuation-originated event linked to an active trade. Key attributes include management event identifier, trade identifier, source signal identifier, source signal type, event time, price at event, old stop loss, new stop loss, old take profit, new take profit, reason, accepted flag, and rejection reason.
- **Managed Trade Outcome**: The final result of a trade after entry and any management events. Key attributes include trade identifier, close time, close price, exit reason, result category, captured risk multiple, maximum favorable excursion, and comparison against the original unmanaged target.
- **Management Rule Configuration**: User-adjustable settings that control favorable-move thresholds, break-even movement, take-profit extension, maximum extension limits, and opposite-direction continuation handling.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a sample containing the 92 continuation-only rows described in issue #100 and no pullback rows, zero new trade entries are created from continuation signals alone.
- **SC-002**: In the current-week sample containing 101 continuation rows and zero pullback rows, zero new trade entries are created from continuation signals alone.
- **SC-003**: In a mixed signal sample with active pullback trades, 100% of same-direction continuation management events are linked to the correct active trade or recorded with a clear rejection reason.
- **SC-004**: Journal/export review of a mixed lifecycle sample lets an operator distinguish entry events from management events in every row without inspecting surrounding context.
- **SC-005**: 100% of stop-loss exits beyond break-even are categorized as profit-protected wins in outcome reporting.
- **SC-006**: 100% of take-profit extensions remain within configured extension limits.
- **SC-007**: Metrics summaries include all lifecycle counters and managed-outcome comparisons for every completed evaluation batch.
- **SC-008**: Duplicate-entry noise from continuation signals is reduced by at least 90% in samples where an active same-direction pullback trade already exists.

## Assumptions

- Pullback remains the intended primary trade-entry signal for this strategy.
- Continuation logic remains valuable and should be retained as trade-management evidence rather than removed.
- A trade is considered active until it reaches take profit, reaches stop loss, is manually closed, or is otherwise invalidated by existing lifecycle rules.
- Baseline management rules may use common favorable-move thresholds such as 1R, 1.5R, or progress toward take profit, provided the thresholds are configurable.
- Existing alert, journal, export, and metrics consumers remain in scope because the issue explicitly calls out Discord output, journal output, and metrics.
- Historical raw signal records remain useful for diagnostics, but managed-trade reporting should become the source of truth for lifecycle outcomes.
