# Feature Specification: Strategy Metrics

**Feature Branch**: `002-strategy-metrics`  
**Created**: 2026-05-01  
**Status**: Draft  
**Input**: User description: "I need to collect meaningful data so that I can work toward improving the strategy. It just went a full week without a single signal, but I have no idea how close it got, or if the grading criteria is too strict or not strict enough. I'll leave it up to you as to what metrics would be most helpful. Give me some propositions that I can clarify."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review No-Signal Periods (Priority: P1)

As the strategy owner, I want to review each evaluated market opportunity during a period with no signals so that I can see whether the strategy was inactive because the market never came close or because one or two grading criteria repeatedly blocked otherwise viable setups.

**Why this priority**: This directly addresses the current inability to learn from a full week with no signals.

**Independent Test**: Can be fully tested by selecting a no-signal date range and confirming the review shows evaluated opportunities, blocked criteria, and near-miss counts without requiring any signal to have fired.

**Acceptance Scenarios**:

1. **Given** a selected date range with no emitted signals, **When** the user reviews strategy metrics, **Then** the user can see how many opportunities were evaluated and how close the best opportunities came to passing.
2. **Given** an evaluated opportunity that failed grading, **When** the user opens its details, **Then** the user can see which criteria passed, which failed, and the margin by which each failed criterion missed its threshold.

---

### User Story 2 - Compare Criterion Strictness (Priority: P2)

As the strategy owner, I want to compare grading criteria across evaluated opportunities so that I can identify which thresholds may be too strict, too loose, or rarely relevant.

**Why this priority**: Knowing which criteria suppress signals most often is necessary before adjusting the strategy responsibly.

**Independent Test**: Can be fully tested by reviewing a completed analysis period and verifying that each grading criterion has pass rate, fail rate, near-miss rate, and average margin information.

**Acceptance Scenarios**:

1. **Given** a set of evaluated opportunities, **When** the user views criterion diagnostics, **Then** each criterion shows how often it passed, failed, blocked a signal, and nearly passed.
2. **Given** a criterion that frequently blocks otherwise strong opportunities, **When** the user reviews diagnostics, **Then** the system highlights it as a candidate for threshold review without recommending an automatic strategy change.

---

### User Story 3 - Track Changes Over Time (Priority: P3)

As the strategy owner, I want to compare metric summaries across time windows so that I can understand whether strategy inactivity is normal, worsening, or caused by a recent market or configuration change.

**Why this priority**: Time-window comparison turns one quiet week into evidence instead of an isolated anecdote.

**Independent Test**: Can be fully tested by selecting two date ranges and confirming that the system compares evaluated opportunities, near-misses, emitted signals, and top blocking criteria.

**Acceptance Scenarios**:

1. **Given** two selected analysis periods, **When** the user compares them, **Then** the system shows changes in opportunity volume, signal volume, near-miss volume, and criterion pass/fail behavior.
2. **Given** a period with unusually low opportunity volume, **When** the user reviews the comparison, **Then** the system distinguishes low market opportunity from strict grading criteria wherever the collected data supports that distinction.

### Edge Cases

- A selected period contains no evaluated opportunities at all; the system must report that no diagnostic conclusion can be drawn for that period.
- A selected period contains evaluated opportunities but no emitted signals; diagnostics must still show near-misses and blocker patterns.
- A criterion is missing or unavailable for some opportunities; summaries must identify incomplete data instead of silently treating it as pass or fail.
- Multiple criteria fail for the same opportunity; the system must distinguish all failed criteria from the decisive blockers used in summary counts.
- A grading threshold changes during the selected period; metrics must make that change visible or separate results by threshold version.
- A metric value is extreme or malformed; the system must exclude it from aggregate conclusions and flag the affected opportunity for review.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST record every evaluated opportunity whether or not it emits a signal.
- **FR-002**: System MUST record the final signal decision for each evaluated opportunity as emitted, rejected, skipped, or indeterminate.
- **FR-003**: System MUST record each grading criterion evaluated for an opportunity, including the measured value, threshold or target, pass/fail result, and failure margin when applicable.
- **FR-004**: System MUST identify near-miss opportunities as rejected opportunities that failed by exactly one grading criterion.
- **FR-005**: System MUST summarize evaluated opportunity volume, emitted signal volume, rejection volume, skip volume, near-miss volume, and indeterminate volume for a selected date range.
- **FR-006**: System MUST summarize each grading criterion by pass count, fail count, pass rate, fail rate, near-miss contribution, and average failure margin.
- **FR-007**: System MUST identify the criteria that most often block otherwise promising opportunities using a combined ranking score that balances blocker frequency, failure margin, and the quality of the rejected opportunity.
- **FR-008**: System MUST preserve at least 90 days of historical diagnostic data for comparison.
- **FR-009**: Users MUST be able to select a date range and view diagnostic summaries for that period.
- **FR-010**: Users MUST be able to inspect individual evaluated opportunities from a summary and see criterion-level details.
- **FR-011**: Users MUST be able to compare two date ranges and see changes in opportunity volume, signal volume, near-miss volume, and top blocking criteria.
- **FR-012**: System MUST clearly label incomplete or indeterminate diagnostics so the user does not mistake missing data for strategy behavior.
- **FR-013**: System MUST avoid making automatic strategy changes; diagnostics may identify candidates for review but final threshold decisions remain user-controlled.
- **FR-014**: System MUST allow export or capture of diagnostic summaries in a form suitable for later review outside the live dashboard.

### Key Entities

- **Evaluated Opportunity**: A market setup or analysis cycle that was graded for possible signal generation. Key attributes include timestamp, symbol or instrument, direction if applicable, final decision, overall score or grade when available, and diagnostic completeness.
- **Grading Criterion Result**: The result of one criterion evaluated for an opportunity. Key attributes include criterion name, measured value, threshold or target, pass/fail status, margin from threshold, and whether it contributed to rejection.
- **Diagnostic Summary**: Aggregated metrics for a selected date range. Key attributes include opportunity counts, signal counts, near-miss counts, criterion pass/fail rates, blocker rankings, and data-quality warnings.
- **Comparison Period**: A selected date range used for before/after or week-over-week comparison. Key attributes include start date, end date, summary metrics, and differences from another period.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After one week of operation, the user can determine whether zero signals were caused primarily by low evaluated opportunity count, strict grading criteria, incomplete data, or an indeterminate cause.
- **SC-002**: 100% of evaluated opportunities in a selected period have a visible final decision and either criterion-level diagnostics or a clear incomplete-data reason.
- **SC-003**: For any selected date range with at least 20 evaluated opportunities, the user can identify the top three signal-blocking criteria within 2 minutes.
- **SC-004**: At least 95% of rejected opportunities show all failed criteria and their failure margins.
- **SC-005**: The user can compare two date ranges and see changes in opportunity volume, signal volume, near-miss volume, and top blocking criteria in one review flow.
- **SC-006**: Diagnostic summaries reduce manual log review time for no-signal weeks by at least 75% compared with inspecting raw strategy output manually.

## Assumptions

- The primary user is the strategy owner/operator investigating signal quality and threshold strictness.
- The strategy already evaluates candidate opportunities internally even when it does not emit a signal.
- The first version focuses on diagnostics and review, not automated optimization or threshold adjustment.
- Existing strategy behavior must remain unchanged while metrics are collected.
- Diagnostic data may be stored locally and reviewed by a single user.
- Metrics should favor explainability over prediction; the goal is to show why signals did or did not happen.
