# Feature Specification: Metrics Diagnostics

**Feature Branch**: `004-metrics-diagnostics`
**Created**: 2026-05-05
**Status**: Draft
**Input**: User description: "Improve CTI_Scripts strategy metrics transparency so skipped opportunities explain exactly why they were skipped, especially no-trend cases where trend-strength checks pass but final trend classification is flat. Keep the pass diagnostic-only: do not change thresholds, loosen rules, optimize parameters, alter entries, or make the bot trade more often."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Explain No-Trend Skips (Priority: P1)

As the strategy owner, I want every skipped no-trend opportunity to show whether it failed strength, had conflicting directions, lacked usable data, or fell through classification so I can tell a real flat market from an opaque diagnostic gap.

**Why this priority**: The latest export shows trend-strength criteria passing sometimes while more than 42,000 evaluations emitted zero signals; no-trend skips are the current highest-value diagnostic blind spot.

**Independent Test**: Can be tested with opportunities whose 1h, 15m, and 5m trend strengths pass but directions conflict, and with opportunities where 15m strength fails.

**Acceptance Scenarios**:

1. **Given** all three trend strengths pass and the three directions do not agree, **When** the opportunity is exported, **Then** it shows`no_trend_reason = direction_conflict`, `directions_agree = false`, final direction`none`, and a flat trend result.
2. **Given** the 15m trend strength fails, **When** the opportunity is exported, **Then** it shows`no_trend_reason = insufficient_strength_15m` or `multiple_insufficient_strength`.

---

### User Story 2 - Trust Criterion Pass Diagnostics (Priority: P2)

As the strategy owner, I want threshold criteria to expose the expected pass result and mismatches so I can detect bad comparison logic without manually recalculating every threshold.

**Why this priority**: The previous `abs_gte` issue damaged trust in the export, and threshold criteria must be self-auditing before strategy tuning.

**Independent Test**: Can be tested with criteria containing measured value, threshold value, and threshold operator, including `abs_gte` positive and negative values.

**Acceptance Scenarios**:

1. **Given** a threshold-based criterion has measured value, threshold value, and threshold operator, **When** it is recorded, **Then** `expected_pass` is populated.
2. **Given** `expected_pass` differs from the recorded `passed` value, **When** it is exported, **Then** `pass_mismatch = true`.

---

### User Story 3 - Summarize Actual Blockers (Priority: P3)

As the strategy owner, I want skipped and rejected opportunities to expose first blocker, all blockers, blocking layer, and top blockers so I can see what truly stopped signals without mixing strategy rejections with engine failures.

**Why this priority**: Summary blocker rankings are only useful if skipped opportunities and trend-classification blockers are counted accurately.

**Independent Test**: Can be tested with a report containing skipped no-trend opportunities, failed required criteria, emitted opportunities, and engine/data failures.

**Acceptance Scenarios**:

1. **Given** a skipped opportunity has a blocking trend classification reason, **When** it is recorded, **Then** `first_blocker`, `all_blockers`, and `blocking_layer` identify the trend blocker.
2. **Given** a report contains skipped or blocked opportunities, **When** the summary is exported, **Then** `top_blockers` is not empty and reflects actual blockers.
3. **Given** data, API, or engine failures occur, **When** the summary is exported, **Then** they count as indeterminate and remain separate from strategy skipped or rejected counts.

### Edge Cases

- All three trend strengths pass, but one timeframe direction disagrees with the others.
- One trend strength fails versus multiple trend strengths failing.
- Trend data is missing, malformed, non-finite, or produced by an invalid linear regression result.
- A skipped opportunity has no failed required criterion because the blocker is classification logic rather than threshold failure.
- A required criterion fails in a skipped or rejected opportunity and must mark `blocked_signal = true`.
- Threshold version changes within the report period; the warning remains and counts by version are exposed where practical.
- Engine/API errors, missing candle data, missing candle time, and incomplete diagnostics must be indeterminate, not strategy skips.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST add trend-decision diagnostics to each evaluated opportunity whenever trend data is available or attempted.
- **FR-002**: Trend diagnostics MUST include per-timeframe strength pass values, per-timeframe directions, whether directions agree, whether all strengths passed, classification input, classification output, final direction, and`no_trend_reason`.
- **FR-003**: Supported`no_trend_reason` values MUST include `insufficient_strength_1h`, `insufficient_strength_15m`, `insufficient_strength_5m`, `multiple_insufficient_strength`, `direction_conflict`, `missing_data`, `invalid_lr_result`, `flat_after_classification`, and `unknown`.
- **FR-004**: System MUST populate `expected_pass` for threshold criteria when measured value, threshold value, and threshold operator are present and computable.
- **FR-005**: System MUST set `pass_mismatch = true` whenever populated `expected_pass` does not match populated `passed`.
- **FR-006**: System MUST set `blocked_signal = true` for failed required criteria that stop signal generation.
- **FR-007**: System MUST populate `first_blocker`, `all_blockers`, and `blocking_layer` for skipped or rejected opportunities unless the skip is genuinely non-blocking and documented.
- **FR-008**: System MUST include trend classification blockers in blocker fields even when all threshold criteria passed.
- **FR-009**: System MUST populate summary-level `top_blockers` whenever the report contains skipped or blocked opportunities with known blockers.
- **FR-010**: System MUST keep emitted, rejected, skipped, and indeterminate counts separate.
- **FR-011**: System MUST count engine errors, API timeouts, missing candle data, missing candle time, and incomplete diagnostics as indeterminate.
- **FR-012**: System MUST count strategy logic failures as skipped or rejected, not indeterminate.
- **FR-013**: System MUST preserve existing JSON export compatibility while adding new diagnostic fields.
- **FR-014**: System MUST expose threshold-version-change warnings and counts by threshold version where practical.
- **FR-015**: System MUST document how to interpret`no_trend_reason`, `trend_decision`, `first_blocker`, `all_blockers`, `blocking_layer`, and `top_blockers`.
- **FR-016**: System MUST NOT optimize parameters, loosen thresholds, alter entry rules, make trading more frequent, or add forward outcome labels unless already available as a simple exposure.

### Key Entities

- **Trend Decision Diagnostic**: Explanation of how trend-strength checks, linear regression directions, agreement checks, and final classification produced a trend or no-trend outcome.
- **Criterion Result**: A threshold or boolean evaluation with measured value, threshold value, operator, recorded pass result, expected pass result, mismatch flag, requirement flag, blocker flag, and data quality.
- **Evaluated Opportunity**: One strategy evaluation containing final decision, decision reason, trend result, direction, criteria, blockers, data quality, and trend diagnostics.
- **Diagnostic Summary**: Aggregated report that separates emitted, rejected, skipped, and indeterminate counts and ranks actual blockers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of no-trend opportunities with all three trend-strength checks passed and conflicting directions show`no_trend_reason = direction_conflict`.
- **SC-002**: 100% of no-trend opportunities with a failed 15m strength check show `insufficient_strength_15m` or `multiple_insufficient_strength`.
- **SC-003**: 100% of computable threshold-based criteria export non-null `expected_pass`.
- **SC-004**: 100% of expected/actual pass inconsistencies export `pass_mismatch = true`.
- **SC-005**: 100% of failed required criteria that block signal generation export `blocked_signal = true`.
- **SC-006**: Reports with skipped opportunities that have known blockers export non-empty `top_blockers`.
- **SC-007**: Indeterminate counts contain only data, API, engine, or incomplete diagnostic failures in test fixtures.
- **SC-008**: Existing JSON export consumers can still parse the export with the new fields present.

## Assumptions

- The primary user is the strategy owner/operator using exported diagnostics for strategy tuning decisions.
- Current thresholds, entry behavior, signal gating, risk behavior, and trading frequency remain unchanged.
- Linear regression values and existing criterion results are sufficient to diagnose trend classification causes.
- Missing or malformed market data is a data-quality problem, not a strategy rejection.
- Follow-on optimization should wait until diagnostics are trustworthy and a clean data collection window exists.
