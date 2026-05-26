# Feature Specification: Prime Signal Suppression

**Feature Branch**: `012-prime-signal-suppression`  
**Created**: 2026-05-26  
**Status**: Draft  
**Input**: User description: "Implement a prime-signal suppression system for TradeGumi's signal journal. Repeated same-symbol signals should not create new actionable journal rows while a prior unresolved prime signal exists unless the prime is inferred closed by TP or SL, or otherwise resolved by existing manual, stale, invalidation, purge, or reset flows."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Suppress Repeated Open Signals (Priority: P1)

As a TradeGumi operator reviewing the signal journal, I want only the first unresolved signal for each symbol to remain actionable so that duplicate same-symbol entries do not clutter grading or distort strategy analysis.

**Why this priority**: This is the core value of the feature. It directly reduces noisy repeated journal rows and preserves one clear actionable setup per symbol.

**Independent Test**: Can be fully tested by emitting a signal for a symbol, then emitting additional same-symbol signals before the first setup reaches an outcome, and verifying that the journal keeps one actionable entry with an increased suppressed count.

**Acceptance Scenarios**:

1. **Given** no unresolved prime signal exists for AUDUSD, **When** a new AUDUSD signal reaches the journal, **Then** the journal records the signal as the active prime for AUDUSD with zero suppressed signals.
2. **Given** an unresolved BUY prime exists for AUDUSD and no prime outcome was reached before a later BUY signal, **When** the later BUY signal reaches the journal, **Then** no new actionable journal row is created and the AUDUSD prime's suppressed count increases by one.
3. **Given** an unresolved BUY prime exists for AUDUSD and no prime outcome was reached before a later SELL signal, **When** the later SELL signal reaches the journal, **Then** no new actionable journal row is created and the AUDUSD prime's suppressed count increases by one.
4. **Given** an unresolved AUDUSD prime exists, **When** a GBPJPY signal reaches the journal, **Then** the AUDUSD prime does not suppress the GBPJPY signal.

---

### User Story 2 - Replace Prime After Inferred Outcome (Priority: P1)

As a strategy analyst, I want a same-symbol follow-on signal to become actionable only after the prior prime signal is inferred to have reached its target or stop so that the journal reflects sequential trade opportunities rather than unresolved duplicates.

**Why this priority**: Suppression is only useful if it still allows genuine subsequent opportunities after the prior setup has resolved.

**Independent Test**: Can be fully tested by creating a prime signal, providing market movement that reaches either target or stop before a later same-symbol signal, and verifying that the earlier prime closes while the later signal becomes the new prime.

**Acceptance Scenarios**:

1. **Given** an unresolved BUY prime exists and market movement reaches the prime target before a later same-symbol signal, **When** the later signal reaches the journal, **Then** the old prime is marked closed by inferred target and the later signal becomes the active prime.
2. **Given** an unresolved BUY prime exists and market movement reaches the prime stop before a later same-symbol signal, **When** the later signal reaches the journal, **Then** the old prime is marked closed by inferred stop and the later signal becomes the active prime.
3. **Given** an unresolved SELL prime exists and market movement reaches the prime target before a later same-symbol signal, **When** the later signal reaches the journal, **Then** the old prime is marked closed by inferred target and the later signal becomes the active prime.
4. **Given** an unresolved SELL prime exists and market movement reaches the prime stop before a later same-symbol signal, **When** the later signal reaches the journal, **Then** the old prime is marked closed by inferred stop and the later signal becomes the active prime.

---

### User Story 3 - Audit Suppression Outcomes (Priority: P2)

As a strategy analyst, I want suppression counts, closure reasons, and ambiguous outcomes to be visible in journal details, exports, and metrics so that repeated firing and chop symptoms can be evaluated later.

**Why this priority**: Suppression must not hide evidence. Operators need compact visibility in the dashboard and analysts need exported and aggregated data.

**Independent Test**: Can be fully tested by suppressing signals, exporting the journal, viewing the signal card/detail, and reviewing metrics totals by symbol and closure outcome.

**Acceptance Scenarios**:

1. **Given** a prime has suppressed later signals, **When** the operator views the signal journal card or detail, **Then** the view shows the suppressed count compactly.
2. **Given** journal records include prime suppression fields, **When** the operator exports journal data, **Then** the export includes prime status, suppressed count, latest suppressed time, closure reason, closure time, and ambiguity status.
3. **Given** multiple symbols have suppressed signals, **When** strategy metrics are reviewed, **Then** metrics show total suppressed signals and suppressed signals by symbol.
4. **Given** a prime has both target and stop touched in a single unknowable interval, **When** the prime is closed by inference, **Then** the closure uses the conservative stop outcome and records the outcome as ambiguous.

---

### User Story 4 - Preserve Existing Journal Workflows (Priority: P2)

As a TradeGumi operator, I want manual grading, invalidation, stale handling, reset, purge, exports, setup grouping, and strategy-stat eligibility to continue working so that suppression improves journal quality without breaking existing review workflows.

**Why this priority**: The signal journal is already used for analysis and operator review. Suppression must integrate with existing outcomes instead of replacing them.

**Independent Test**: Can be fully tested by exercising existing grade, invalidate, reset, stale/expired, purge, export, dashboard, and stats flows alongside suppressed and active prime records.

**Acceptance Scenarios**:

1. **Given** an active prime is manually graded or invalidated, **When** a later same-symbol signal reaches the journal, **Then** the resolved old prime no longer suppresses the later signal.
2. **Given** existing stale or expired signal logic marks a prime no longer actionable, **When** a later same-symbol signal reaches the journal, **Then** the stale or expired prime no longer suppresses the later signal.
3. **Given** journal state is purged or reset according to existing controls, **When** later signals reach the journal, **Then** no stale prime state remains from the purged or reset records.

### Edge Cases

- A later same-symbol signal has the opposite direction from the active prime; it is still suppressed until the prime reaches an outcome or is otherwise resolved.
- Target and stop are both touched before the follow-on signal and their ordering cannot be determined; the conservative stop outcome is used and the ambiguity is auditable.
- Multiple rapid same-symbol signals arrive close together; at most one unresolved active prime exists for the symbol.
- Prime state is reloaded after process restart; persisted unresolved primes still suppress later same-symbol signals.
- A prime has missing or unusable target, stop, direction, entry price, or timestamp data; suppression must remain auditable and must not corrupt journal state.
- Legacy journal records without prime fields remain readable and exportable.
- Suppressed signals must not require manual grading, create duplicate setup rows, count as trade opportunities, or be included as usable strategy statistics.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST identify at most one active unresolved prime signal per symbol.
- **FR-002**: System MUST make a new journaled signal the active prime for its symbol when no active unresolved prime exists for that symbol.
- **FR-003**: System MUST initialize a new prime with a suppressed signal count of zero.
- **FR-004**: System MUST check an existing same-symbol active prime for an inferred target or stop outcome before deciding whether a later same-symbol signal can create a new actionable journal row.
- **FR-005**: System MUST infer a BUY prime target outcome when market movement reaches or exceeds the prime target before the later signal.
- **FR-006**: System MUST infer a BUY prime stop outcome when market movement reaches or falls below the prime stop before the later signal.
- **FR-007**: System MUST infer a SELL prime target outcome when market movement reaches or falls below the prime target before the later signal.
- **FR-008**: System MUST infer a SELL prime stop outcome when market movement reaches or exceeds the prime stop before the later signal.
- **FR-009**: System MUST use a conservative stop outcome when target and stop are both touched within an interval whose order cannot be known.
- **FR-010**: System MUST record whether an inferred close was ambiguous when the outcome ordering cannot be known.
- **FR-011**: System MUST close the old prime and allow the later same-symbol signal to create a new prime when the old prime is inferred to have reached target or stop.
- **FR-012**: System MUST suppress a later same-symbol signal when the active prime has not reached target or stop and is not otherwise resolved.
- **FR-013**: System MUST increment the active prime's suppressed signal count whenever a later same-symbol signal is suppressed.
- **FR-014**: System MUST record the latest suppressed signal time for the active prime whenever suppression occurs.
- **FR-015**: System SHOULD preserve compact metadata about suppressed signals when the existing journal model can store it without making exports or dashboard views noisy.
- **FR-016**: System MUST suppress same-symbol follow-on signals regardless of whether they match or oppose the prime direction.
- **FR-017**: System SHOULD distinguish same-direction and opposite-direction suppressed counts when this can be integrated without excessive schema or UI complexity.
- **FR-018**: System MUST persist prime status and suppression evidence so active prime state is recoverable after restart.
- **FR-019**: System MUST ensure rapid same-symbol signal handling cannot create two active primes for the same symbol.
- **FR-020**: System MUST clear or deactivate prime status when a signal is manually graded, manually invalidated, marked stale or expired by existing logic, reset or purged by existing journal controls, or closed by inferred target or stop.
- **FR-021**: System MUST show a compact suppressed count on the signal journal card or detail view when a prime has suppressed signals.
- **FR-022**: System MUST include prime suppression fields in journal exports, including prime activity, suppressed count, latest suppressed time, closed reason, closed time, and ambiguity status when present.
- **FR-023**: System MUST include suppressed signal metadata in JSON export when such metadata is stored.
- **FR-024**: System MUST expose metrics for total prime-suppressed signals, prime-suppressed signals by symbol, inferred target closures, inferred stop closures, and ambiguous closures.
- **FR-025**: System SHOULD expose same-direction and opposite-direction suppression metrics if directional suppression counts are stored.
- **FR-026**: System MUST NOT change strategy signal rules, threshold tuning, confidence scoring, volatility shock logic, Keltner logic, StochRSI logic, MACD logic, broker execution behavior, or order placement behavior as part of this feature.
- **FR-027**: System MUST preserve existing signal journal creation, manual grading, manual invalidation, reset to pending, stale or expired behavior, journal purge, export behavior, dashboard rendering, setup grouping, duplicate logic, and strategy-stat eligibility behavior.
- **FR-028**: System MUST ensure suppressed signals are not counted as usable strategy statistics, trade opportunities, duplicate setup rows, or items requiring manual grading.
- **FR-029**: System MUST keep legacy journal records without prime suppression fields readable in dashboard, metrics, and export flows.

### Key Entities *(include if feature involves data)*

- **Prime Signal**: The active unresolved journal entry for one symbol. It carries normal signal evidence plus prime activity state, suppressed count, latest suppressed time, optional suppressed metadata, closure reason, closure time, and ambiguity status.
- **Suppressed Signal Evidence**: Audit evidence that a later same-symbol emitted signal was not converted into a new actionable journal row because an unresolved prime remained open.
- **Inferred Prime Closure**: A journal state transition showing that a prime was considered resolved because market movement reached the prime target or stop before a later same-symbol signal.
- **Prime Suppression Metrics**: Aggregated counts used to evaluate repeated firing by symbol, closure outcome, ambiguity, and optionally same-direction versus opposite-direction suppression.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In repeated same-symbol signal scenarios where the active prime has not reached target or stop, zero additional actionable journal rows are created for those follow-on signals.
- **SC-002**: For every suppressed follow-on signal, the active prime's suppressed count increases by exactly one and the latest suppressed time reflects the most recent suppressed signal.
- **SC-003**: After a restart, an unresolved active prime continues suppressing later same-symbol signals in 100% of tested restart recovery scenarios.
- **SC-004**: When prior market movement reaches a prime target or stop before a later same-symbol signal, the later signal becomes actionable in 100% of tested BUY and SELL target/stop scenarios.
- **SC-005**: When target and stop are both touched in an unknowable interval, the recorded outcome is stop and the ambiguity is visible in 100% of tested ambiguous scenarios.
- **SC-006**: Journal exports contain the required prime suppression fields for all exported signal records.
- **SC-007**: Dashboard journal views show suppressed count for prime records with suppressed signals without adding more than one compact line of card/detail text.
- **SC-008**: Existing signal journal, export, dashboard, grading, invalidation, stale, purge, and strategy-stat tests continue to pass.

## Assumptions

- Existing journal outcome states can represent manual grading, manual invalidation, stale or expired state, reset, and purge well enough to deactivate a prime.
- Existing market movement data is sufficient to evaluate whether a prime target or stop was touched between the prime entry time and a later signal time.
- Prime suppression is scoped to journal and analytics behavior only; it does not alter signal generation, confidence scoring, risk rules, or broker execution.
- The first implementation may store total suppressed count and latest suppressed time even if richer suppressed signal metadata or same/opposite direction counts require a later iteration.
- Legacy records are treated as non-active primes unless they contain enough persisted prime state to prove they are active and unresolved.
