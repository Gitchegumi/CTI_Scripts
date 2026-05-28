# Feature Specification: Alert Signal Auto-Grading

**Feature Branch**: `013-alert-signal-autograding`  
**Created**: 2026-05-27  
**Status**: Draft  
**Input**: User description: "Implement alert-only/developing signal auto-grading in CTI_Scripts / TradeGumi. Alert-only signals should be tracked after firing and automatically graded as TP, SL, still open, ambiguous, expired, or invalidated while reusing dashboard price observations, avoiding duplicate market-data polling, preserving manual overrides, integrating with prime signal suppression, exposing results in journal/dashboard/API/export surfaces, and preparing for a future streaming price source without using undocumented OANDA browser or chart endpoints."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-Grade Alert-Only Signals (Priority: P1)

As a TradeGumi operator, I want alert-only and developing-mode signals to be tracked after they fire and automatically resolved when market movement reaches their target or stop so that simulated signal performance is measurable without manual review of every signal.

**Why this priority**: This is the core value of the feature. Alert-only signals currently create review burden and incomplete outcome data unless a human grades them.

**Independent Test**: Can be fully tested by creating alert-only BUY and SELL journal entries, providing ordered price observations, and verifying that each entry stays open until the correct target or stop condition is reached.

**Acceptance Scenarios**:

1. **Given** an unresolved alert-only BUY signal with a target and stop, **When** observed market prices reach the target first, **Then** the signal is closed with a target outcome, exit time, exit price, checked time, and auto-graded source.
2. **Given** an unresolved alert-only BUY signal with a target and stop, **When** observed market prices reach the stop first, **Then** the signal is closed with a stop outcome, exit time, exit price, checked time, and auto-graded source.
3. **Given** an unresolved alert-only SELL signal with a target and stop, **When** observed market prices reach the target first, **Then** the signal is closed with a target outcome, exit time, exit price, checked time, and auto-graded source.
4. **Given** an unresolved alert-only SELL signal with a target and stop, **When** observed market prices reach the stop first, **Then** the signal is closed with a stop outcome, exit time, exit price, checked time, and auto-graded source.
5. **Given** an unresolved alert-only signal and new market prices that do not reach target or stop, **When** the signal is evaluated, **Then** it remains open with an updated checked time and excursion metrics when available.

---

### User Story 2 - Reuse Live Price Observations (Priority: P1)

As an operator running the dashboard, I want the dashboard and auto-grader to consume the same live price observations so that signal grading does not double market-data traffic or produce conflicting price views.

**Why this priority**: Duplicate polling can waste rate limits and create inconsistent outcomes. Shared observations also prepare the system for a later streaming source.

**Independent Test**: Can be fully tested by running the dashboard price update path with one unresolved signal and verifying that each dashboard observation is also available to the evaluator, with no second independent price loop required for grading.

**Acceptance Scenarios**:

1. **Given** the dashboard receives a live price observation for a symbol, **When** unresolved alert-only signals exist for the same symbol, **Then** the evaluator uses that observation to update eligible signal outcomes.
2. **Given** no unresolved alert-only signals exist for a symbol, **When** dashboard prices update for that symbol, **Then** the dashboard continues to receive updates without creating unnecessary grading work.
3. **Given** the current live-price mechanism polls once per second, **When** auto-grading is enabled, **Then** the same one-second observations feed both dashboard display and outcome evaluation without a separate polling loop for the evaluator.

---

### User Story 3 - Preserve Manual Review Control (Priority: P1)

As a strategy analyst, I want manually graded or manually locked signal entries to remain under human control so that automated grading does not overwrite intentional corrections or annotations.

**Why this priority**: Manual grading is a trust boundary. Auto-grading is only useful if analysts can override or reset outcomes without fighting the system.

**Independent Test**: Can be fully tested by manually grading an alert-only signal, feeding prices that would otherwise produce a different outcome, and verifying that the manual result is preserved unless the entry is reset to become eligible again.

**Acceptance Scenarios**:

1. **Given** a signal has a manual override, **When** later price observations reach target or stop, **Then** auto-grading does not overwrite the manual outcome.
2. **Given** a signal is manually reset to pending without a manual lock, **When** later price observations reach target or stop, **Then** the signal becomes eligible for auto-grading again.
3. **Given** a manual override reason is recorded, **When** the journal is viewed or exported, **Then** the reason remains visible with the result.

---

### User Story 4 - Resolve Prime Signal Conflicts (Priority: P2)

As a TradeGumi operator, I want new same-symbol signals to respect unresolved prime signals while allowing a new prime after the prior prime has been auto-graded so that the journal never has duplicate active prime entries for the same symbol.

**Why this priority**: Auto-grading and prime suppression must agree on whether the prior signal is still open. Otherwise the system can either block valid new opportunities or create duplicate active primes.

**Independent Test**: Can be fully tested by creating a prime signal, feeding observations that either do or do not resolve it, and then firing another same-symbol signal.

**Acceptance Scenarios**:

1. **Given** an active prime signal remains unresolved, **When** a new same-symbol signal fires, **Then** the new signal is blocked or invalidated according to existing prime-filter behavior and the invalidated-by-prime count increases.
2. **Given** an active prime signal has already been auto-graded as target or stop, **When** a new same-symbol signal fires, **Then** the old prime is no longer active and the new signal can become the prime.
3. **Given** a same-symbol signal arrives while the evaluator cannot determine target/stop ordering for the existing prime, **When** the conflict is processed, **Then** the ambiguous state is recorded and no duplicate unresolved prime is created.

---

### User Story 5 - Review Outcomes in Journal and Exports (Priority: P2)

As a strategy analyst, I want auto-graded status, outcome, source, exit details, ambiguity, and manual override flags to appear in the journal, dashboard, API responses, and exports so that simulated performance can be audited without bloating the main view.

**Why this priority**: Automated results must be visible and explainable. Compact presentation keeps the journal usable.

**Independent Test**: Can be fully tested by auto-grading signals with target, stop, open, ambiguous, expired, invalidated, and manual outcomes, then checking journal views, API responses, and exports.

**Acceptance Scenarios**:

1. **Given** a signal has been auto-graded, **When** the journal is viewed, **Then** the status, outcome, source, exit time, and exit price are visible in a compact form.
2. **Given** a signal is ambiguous, **When** the journal detail is viewed, **Then** the ambiguous reason is visible.
3. **Given** journal records are exported, **When** exported data is inspected, **Then** the new outcome fields are included where practical without breaking existing export consumers.

### Edge Cases

- A price observation includes both target and stop touches in the same evaluator cycle without clear ordering; the signal is marked ambiguous rather than forcing a target or stop outcome.
- Only midpoint price is available; the signal may be graded only if the recorded source clearly identifies midpoint-based grading.
- A signal has missing direction, target, stop, entry price, or timestamp data; it is not falsely closed and records an auditable unresolved, expired, invalidated, or ambiguous state as appropriate.
- Multiple unresolved alert-only signals exist for the same symbol; each eligible signal is evaluated from observations for that symbol without creating duplicate active prime state.
- Legacy journal entries lack new outcome fields; they remain readable and receive safe default values.
- Price observations arrive out of order or with duplicate timestamps; outcome ordering remains deterministic and auditable.
- The evaluator is unavailable or disabled; dashboard price updates and signal generation continue without trade execution side effects.
- Existing exports and dashboard views must remain usable even when new fields are absent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST evaluate unresolved alert-only and developing-mode signal journal entries after they fire.
- **FR-002**: System MUST NOT generate new signals, execute trades, change order placement, or modify risk controls as part of outcome evaluation.
- **FR-003**: System MUST update only signal journal outcome, status, audit, and related summary fields when auto-grading signals.
- **FR-004**: System MUST define a shared price observation record that can identify symbol, observation time, bid, ask, midpoint, data source, and received time when those values are available.
- **FR-005**: System MUST support observation source labels for dashboard live polling, future live streaming, historical candles, and manual backfill.
- **FR-006**: System MUST feed auto-grading from the same live price observations used by the dashboard whenever those observations are available.
- **FR-007**: System MUST NOT create a second independent live market-data polling loop solely for auto-grading.
- **FR-008**: System MUST preserve the current dashboard live-price update cadence for the first implementation unless existing configuration explicitly changes it.
- **FR-009**: System MUST maintain a short rolling history of recent price observations sufficient to evaluate active unresolved signals.
- **FR-010**: System MUST avoid unbounded price-observation retention; if observations are persisted, retention MUST be bounded or cleaned up.
- **FR-011**: System MUST evaluate only unresolved eligible signals for the same symbol as each new observation.
- **FR-012**: System MUST close a BUY signal as target-hit when bid price reaches or exceeds the target.
- **FR-013**: System MUST close a BUY signal as stop-hit when bid price reaches or falls below the stop.
- **FR-014**: System MUST close a SELL signal as target-hit when ask price reaches or falls below the target.
- **FR-015**: System MUST close a SELL signal as stop-hit when ask price reaches or exceeds the stop.
- **FR-016**: System MUST allow midpoint-only grading only when the outcome source clearly records that the result is midpoint-based rather than execution-quality bid/ask grading.
- **FR-017**: System MUST record open, target, stop, ambiguous, expired, invalidated, manual, and no-outcome states using safe defaults for legacy entries.
- **FR-018**: System MUST record outcome source, exit time, exit price, most recent checked time, and manual override indicators when available.
- **FR-019**: System SHOULD record observations-to-outcome or bars-to-outcome, maximum favorable excursion, and maximum adverse excursion when source data is sufficient.
- **FR-020**: System MUST preserve existing manually graded or manually locked entries and MUST NOT overwrite them through auto-grading.
- **FR-021**: System MUST allow an entry reset to pending to become eligible for auto-grading again unless it remains manually locked.
- **FR-022**: System MUST record an ambiguous outcome and reason when target and stop appear hit in the same evaluation cycle without reliable ordering.
- **FR-023**: System MUST use first observed target-or-stop touch as the outcome for ordered live observations.
- **FR-024**: System MUST let future lower-timeframe or historical fallback data use the same outcome-evaluation behavior and outcome-source audit fields.
- **FR-025**: System MUST check whether an existing prime/open signal has already been resolved before applying same-symbol prime suppression to a new signal.
- **FR-026**: System MUST allow a new same-symbol signal to become prime when the prior prime has resolved by target or stop.
- **FR-027**: System MUST block or invalidate a new same-symbol signal according to existing prime-filter behavior when the prior prime remains unresolved.
- **FR-028**: System MUST increment invalidated-by-prime counts when a new signal is blocked by an unresolved prime.
- **FR-029**: System MUST prevent duplicate open prime signals for a symbol unless existing behavior explicitly permits them.
- **FR-030**: System MUST expose status, outcome, outcome source, exit time, exit price, auto-graded/manual state, and ambiguity reason through journal review surfaces.
- **FR-031**: System MUST keep journal UI additions compact and readable.
- **FR-032**: System MUST keep existing journal entries, manual grading, exports, and dashboards backward compatible.
- **FR-033**: System MUST NOT use undocumented broker browser, chart-drawing, developer-tools, or web UI automation endpoints for this feature.
- **FR-034**: System MUST use only supported market price, candle, journal, dashboard, and internal data sources for outcome grading.
- **FR-035**: System MUST NOT hardcode account identifiers, instruments, credentials, or secrets.

### Key Entities *(include if feature involves data)*

- **Signal Journal Entry**: A fired alert-only or developing-mode signal with direction, symbol, target, stop, status, outcome, outcome source, exit details, manual override state, ambiguity reason, and excursion metrics.
- **Price Observation**: A market-price fact for one symbol at one point in time, carrying bid, ask, midpoint, source, observation time, and received time when available.
- **Rolling Price History**: A bounded recent collection of price observations used to evaluate currently open signals and audit observed movement.
- **Outcome Evaluation**: The deterministic decision that an unresolved signal remains open, hit target, hit stop, became ambiguous, expired, was invalidated, or stayed manually controlled.
- **Prime Signal State**: The per-symbol active/open signal state used to decide whether a new same-symbol signal may become prime or must be blocked/invalidated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In tested BUY and SELL scenarios, target and stop outcomes are recorded correctly for 100% of bid/ask observation cases.
- **SC-002**: In tested no-hit scenarios, unresolved signals remain open after evaluation in 100% of cases.
- **SC-003**: In tested manual override scenarios, auto-grading overwrites manually controlled entries in 0 cases.
- **SC-004**: In midpoint-only test cases, 100% of auto-graded outcomes record a midpoint-specific outcome source.
- **SC-005**: Auto-grading introduces zero additional independent live market-data polling loops beyond the dashboard live-price source.
- **SC-006**: In tested same-symbol prime scenarios, unresolved primes block or invalidate new signals and resolved primes allow new signals in 100% of cases.
- **SC-007**: In ambiguous same-cycle target/stop scenarios, 100% of outcomes record an ambiguous state and auditable reason.
- **SC-008**: Journal API responses, dashboard views, and exports include the new outcome fields for auto-graded records while legacy records remain readable.
- **SC-009**: Existing signal generation and execution behavior remains unchanged in regression tests covering non-alert-only trade paths.

## Assumptions

- Alert-only and developing-mode journal entries can be identified from existing signal metadata or safely defaulted when older records do not include explicit mode fields.
- The dashboard already has a live price path suitable for sharing observations with an evaluator.
- The first implementation can keep rolling observations in memory as long as unresolved signals can still be evaluated from new incoming observations.
- Historical candle or manual backfill grading is optional for the first implementation but should fit the same observation and outcome interfaces.
- Expiration and invalidation rules should follow existing journal or prime-suppression behavior where those concepts already exist.
- The future streaming upgrade should replace the observation source without changing journal outcome semantics.
