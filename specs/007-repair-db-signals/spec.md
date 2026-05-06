# Feature Specification: Repair DB-backed page performance and restore signal pipeline progression through candle-close-gated signal evaluation

**Feature Branch**: `007-repair-db-signals`  
**Created**: 2026-05-06  
**Status**: Draft  
**Input**: User description: "Repair DB-backed page performance and restore signal pipeline progression through candle-close-gated signal evaluation."

## Clarifications

### Session 2026-05-06

- Q: What data volume defines the page-performance target? -> A: Representative local/dev production-like data used to reproduce current 5+ second loads.
- Q: May response shapes or visible page behavior change for performance? -> A: Preserve existing behavior and response shape unless a documented exception is required to prevent pathological loading.
- Q: How should pre-close candle evaluations be treated? -> A: Keep them eligible for later evaluation by deferring or marking them as waiting, not permanently blocked.
- Q: What time basis should candle boundary decisions use? -> A: Timezone-aware deterministic M5 timeframe boundaries.
- Q: Are strategy threshold or parameter changes in scope? -> A: No, unless tests prove the current implementation applies a threshold incorrectly.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fast DB-backed operator pages (Priority: P1)

As an operator reviewing strategy activity, I need database-backed pages to load quickly enough for normal interactive use so I can inspect metrics, journals, and dashboard history without waiting several seconds for every page.

**Why this priority**: Slow pages block routine diagnosis and make production operations impractical even when the underlying data is available.

**Independent Test**: Can be tested by loading strategy metrics, signal journal, manual trade journal, and dashboard trade history with representative local data and confirming that each page is usable within the target time while showing the same information as before.

**Acceptance Scenarios**:

1. **Given** representative local strategy and journal data, **When** an operator opens a DB-backed page, **Then** the page presents the same user-facing data without a 5+ second wait under normal local/dev volume.
2. **Given** a page has a large history behind it, **When** an operator opens the page with its default filters, **Then** the system limits work to the data needed for that view and avoids unnecessary full-history loading.
3. **Given** a DB-backed page performs multiple data reads, **When** the page loads, **Then** repeated reads, waterfalls, and avoidable duplicate requests are reduced so the page becomes interactive promptly.

---

### User Story 2 - Valid trend candidates reach signal evaluation (Priority: P1)

As an operator relying on strategy signals, I need a valid trend candidate to progress through signal data preparation, candle-close gating, and signal rule evaluation so signals can be emitted or rejected for real strategy reasons instead of being permanently blocked by incomplete data or timing diagnostics.

**Why this priority**: The current signal pipeline records zero signal-rule evaluations and zero emissions, which means strategy decisions are not being reached even when trend criteria pass.

**Independent Test**: Can be tested by running signal-pipeline scenarios with insufficient candles, exactly sufficient candles, pre-close candles, closed M5 candles, and a trend-valid candidate, then confirming the candidate reaches signal rule evaluation when inputs are complete and closed.

**Acceptance Scenarios**:

1. **Given** a trend-valid candidate with complete signal data and a fully closed M5 candle, **When** the pipeline evaluates the opportunity, **Then** signal rules are reached and the result is either emitted or rejected by rule logic.
2. **Given** there are insufficient candles or indicator windows, **When** signal data is prepared, **Then** the system records a clear diagnostic reason without raising an index error or breaking the pipeline.
3. **Given** evaluation occurs before the current M5 candle closes, **When** the candle-close gate runs, **Then** the candidate is deferred or clearly marked as waiting without preventing a later closed-candle evaluation.
4. **Given** trend criteria pass for a candidate, **When** a required signal input is missing, **Then** diagnostics identify the missing input accurately and do not misclassify the result as a strategy-rule rejection.

---

### User Story 3 - Actionable diagnostics and measurement (Priority: P2)

As a maintainer diagnosing production behavior, I need lightweight timing, query, pipeline, and gating diagnostics that identify where latency or signal blockage occurs without changing normal user-facing behavior.

**Why this priority**: Fixing the issues requires evidence of which pages/endpoints are slowest and why valid candidates are blocked, and future regressions need to be detectable.

**Independent Test**: Can be tested by running local measurement steps and reviewing metrics output to confirm slow page paths, signal data completeness, candle gate state, and signal rule progression are visible and accurate.

**Acceptance Scenarios**:

1. **Given** a DB-backed page is measured locally, **When** the maintainer follows the documented verification steps, **Then** they can compare before/after load behavior or reproduce the measurement method.
2. **Given** signal metrics are exported after evaluation, **When** valid closed-candle candidates exist, **Then** the metrics can show nonzero signal-rule evaluation counts.
3. **Given** diagnostics collection encounters malformed or incomplete signal data, **When** metrics are recorded, **Then** diagnostics remain useful and do not break signal evaluation.

### Edge Cases

- DB-backed pages with empty tables must load quickly and show the existing empty-state behavior.
- DB-backed pages with large historical tables must not fetch unbounded data unless a user explicitly requests that broader range.
- Existing filters, date ranges, and page defaults must preserve current user-facing behavior unless a narrower default is explicitly required to remove a pathological load.
- Duplicate frontend components requesting the same data must not trigger inconsistent page state.
- Missing, stale, current, or timezone-misaligned candle data must produce deterministic gate outcomes.
- Signal data preparation must handle zero candles, one candle, exactly enough candles, and indicator windows that are shorter than required.
- Diagnostic labels must consistently use `signal_engine_data`; any legacy misspelling such as `singal_engine_data` must not fragment metrics.
- Timing or profiling diagnostics must remain lightweight enough that they do not create the latency being investigated.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST identify the slowest database-backed pages or data paths among strategy metrics, signal journal, manual trade journal, dashboard trade history, and related views.
- **FR-002**: System MUST make DB-backed pages load quickly under normal local/development data volume while preserving the existing user-facing information and interaction model.
- **FR-003**: System MUST avoid unnecessary repeated data loading, client-side waterfall loading, and duplicate page requests where they materially contribute to page latency.
- **FR-004**: System MUST avoid unbounded history retrieval and unnecessary full-dataset processing for default page views.
- **FR-005**: System MUST preserve existing response shape and visible behavior unless a change is explicitly documented as necessary for performance.
- **FR-006**: System MUST add lightweight timing, logging, profiling, or documented measurement where useful to identify and verify performance improvements.
- **FR-007**: System MUST preserve response correctness for optimized DB-backed data paths through practical regression coverage.
- **FR-008**: System MUST safely handle insufficient signal candles and indicator windows without raising `IndexError: list index out of range`.
- **FR-009**: System MUST select the correct last closed candle and complete indicator window for signal evaluation.
- **FR-010**: System MUST make M5 candle-close gate behavior deterministic at before-close, exact-close, and after-close boundaries.
- **FR-011**: System MUST allow a trend-valid candidate with complete signal data and a closed candle to reach signal rule evaluation.
- **FR-012**: System MUST prevent pre-close gate decisions from becoming permanent blocks that stop later closed-candle evaluation.
- **FR-013**: System MUST keep useful diagnostics for missing data, gate state, rule evaluation, emitted/rejected signals, and indeterminate outcomes.
- **FR-014**: System MUST ensure diagnostics collection does not break trading or signal-pipeline progression.
- **FR-015**: System MUST use consistent diagnostic naming for `signal_engine_data` and account for any existing misspelling so metrics remain interpretable.
- **FR-016**: System MUST NOT loosen strategy thresholds or tune parameters unless investigation proves the current threshold implementation is being applied incorrectly.
- **FR-017**: System MUST include regression coverage for insufficient candles, exactly enough candles, last closed candle selection, M5 close boundary behavior, candle gate before close, candle gate at/after close, and full trend-valid progression to signal rule evaluation.

### Key Entities *(include if feature involves data)*

- **DB-backed Page View**: An operator-facing page that reads persisted strategy, journal, trade, or dashboard history data and has expected default loading behavior.
- **Strategy Metrics**: Aggregated and detailed records describing evaluated opportunities, criteria outcomes, signal-pipeline stages, diagnostics, and counts.
- **Signal Candidate**: A potential trading opportunity that has passed or failed trend detection and may proceed to signal data preparation and rule evaluation.
- **Signal Engine Data**: The prepared candle, indicator, and context inputs needed for candle-close gating and signal rules.
- **Candle Close Gate**: The timing decision that determines whether an M5 candle is complete enough for signal rules to evaluate.
- **Diagnostic Event**: A recorded explanation of missing data, waiting state, evaluation state, rejection, emission, or indeterminate pipeline outcome.
- **Performance Measurement**: A local measurement or lightweight runtime timing record used to compare page and endpoint behavior before and after optimization.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Normal local/development loads of strategy metrics, signal journal, manual trade journal, and dashboard trade history no longer take 5 or more seconds.
- **SC-002**: The slowest DB-backed pages or data paths are documented with a before/after measurement or a repeatable local measurement method.
- **SC-003**: Existing visible data and interactions for optimized DB-backed pages remain equivalent unless a documented performance-motivated exception is approved.
- **SC-004**: Signal data preparation no longer produces `IndexError: list index out of range` for insufficient candle or indicator input scenarios.
- **SC-005**: A trend-valid candidate with complete signal data and a fully closed M5 candle reaches signal rule evaluation in regression testing.
- **SC-006**: Metrics can show nonzero signal-rule evaluation counts when valid closed-candle candidates exist.
- **SC-007**: Candle-close gate tests pass for before-close, exact-close, and after-close boundary cases.
- **SC-008**: Diagnostics continue to explain missing-data and waiting states without causing signal evaluation failures.

## Assumptions

- Normal local/development data volume means the existing project seed, fixture, or production-like local data used by maintainers to reproduce the 5+ second page loads.
- The default performance goal is to remove multi-second page waits without changing business meaning, not to introduce a new analytics product or archival workflow.
- Pagination, filtering, indexing, batching, caching, or computed-field reuse may be acceptable when they preserve visible behavior or are documented as required to avoid pathological loads.
- Signal rules and strategy thresholds are presumed valid and remain unchanged unless tests demonstrate a threshold is implemented incorrectly.
- M5 candle-close behavior should be timezone-aware and deterministic based on candle timeframe boundaries, not wall-clock ambiguity.
- Pre-close candidates may be deferred, retried, or left eligible for later evaluation as long as they are not permanently misclassified as blocked.
- The existing local development and test workflow remains the target verification environment.
