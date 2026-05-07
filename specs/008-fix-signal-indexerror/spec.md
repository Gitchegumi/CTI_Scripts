# Feature Specification: Fix Signal Stack IndexError

**Feature Branch**: `008-fix-signal-indexerror`  
**Created**: 2026-05-07  
**Status**: Draft  
**Input**: User description: "Fix signal stack IndexError caused by missing last closed candle or insufficient indicator window"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Defer Signal Evaluation When Data Is Not Ready (Priority: P1)

As an operator reviewing strategy metrics diagnostics, I need signal evaluation to classify missing M5 candle or indicator inputs as a data-not-ready condition instead of failing with an indexing error, so I can distinguish normal warmup/readiness gaps from strategy rejection or broken signal logic.

**Why this priority**: This is the current blocker surfaced by diagnostics. Without this behavior, valid directional trend candidates cannot be reliably traced through the signal stack.

**Independent Test**: Can be fully tested by evaluating signal-stack inputs with empty, one-row, open-only, and indicator-warmup-short M5 data and confirming each result is a structured data-not-ready diagnostic with no raw indexing failure.

**Acceptance Scenarios**:

1. **Given** an empty M5 candle list, **When** the signal stack is evaluated, **Then** the result is deferred or indeterminate with a structured data-not-ready diagnostic and no raw indexing error.
2. **Given** M5 candles that do not include a fully closed candle, **When** the signal stack is evaluated, **Then** the open candle is not treated as the last closed candle and the result explains that closed-candle input is unavailable.
3. **Given** too few M5 candles for required indicator warmup, **When** the signal stack is evaluated, **Then** the result explains the missing indicator window and does not classify the candidate as a strategy rejection.

---

### User Story 2 - Preserve Normal Signal Rule Evaluation When Inputs Are Ready (Priority: P2)

As an operator monitoring trend-valid candidates, I need candidates with enough closed-candle and indicator data to continue past signal-engine data readiness into the existing candle-close gate and signal rule evaluation, so diagnostics show whether the strategy rules accepted or rejected the candidate.

**Why this priority**: The fix must not hide valid candidates behind overly broad missing-data classification or change entry behavior.

**Independent Test**: Can be tested by providing valid aligned M5 candle and indicator data and confirming signal-engine data is not marked missing before the existing rule evaluation path runs.

**Acceptance Scenarios**:

1. **Given** sufficient closed M5 candle and indicator data, **When** the signal stack is evaluated, **Then** evaluation proceeds to the existing candle-close gate and signal rules.
2. **Given** sufficient data where the existing strategy rules reject the candidate, **When** diagnostics are produced, **Then** the rejection is reported as strategy rejection rather than signal-engine data missing.

---

### User Story 3 - Report Complete Readiness Diagnostics (Priority: P3)

As a maintainer analyzing metrics JSON and signal journal output, I need data-not-ready diagnostics to include counts, readiness requirements, blockers, and backward-compatible fields, so repeated failures can be debugged without reading logs or reproducing the run manually.

**Why this priority**: Complete diagnostics reduce ambiguity after the immediate failure is stopped and keep existing metric consumers working.

**Independent Test**: Can be tested by inspecting metrics output for readiness failures and confirming it contains required, available, blocker, and signal-engine fields while preserving existing JSON consumers.

**Acceptance Scenarios**:

1. **Given** missing last-closed-candle input, **When** metrics JSON is generated, **Then** it includes stage, timeframe, missing input, data-not-ready type, required and available counts, decision reason, first blocker, all blockers, blocking layer, and blocked-signal status.
2. **Given** missing indicator-window input, **When** metrics JSON is generated, **Then** it includes the same readiness fields with indicator-window counts.
3. **Given** existing metrics JSON readers, **When** new readiness fields are present, **Then** existing fields remain available and compatible.

### Edge Cases

- Empty M5 candle list.
- One-candle M5 list.
- M5 candle list containing only currently forming candles.
- Closed candle count below the signal stack's minimum requirement.
- Indicator output with zero usable rows after warmup.
- Indicator output shorter than the candle list after warmup trimming or null removal.
- Indicator data whose final usable timestamp does not align with the selected closed candle timestamp.
- Valid trend candidate that has enough signal data but is later rejected by existing strategy rules.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST validate signal-stack input readiness before evaluating M5 signal rules for a trend-valid candidate.
- **FR-002**: The readiness validation MUST cover raw M5 candle count, closed M5 candle count, last fully closed candle availability, required indicator window length, available usable indicator window length, and indicator availability for the selected closed candle.
- **FR-003**: The system MUST NOT treat a currently forming M5 candle as the last closed candle.
- **FR-004**: The system MUST document whether it defers evaluation when the latest candle is open or evaluates against the previous fully closed candle, consistent with existing strategy intent.
- **FR-005**: The system MUST verify candle and indicator alignment after any warmup trimming or null removal before using positional values for signal evaluation.
- **FR-006**: The system MUST NOT allow a raw indexing error to escape from normal signal-stack operation when M5 candle or indicator data is absent or insufficient.
- **FR-007**: When required signal-stack data is missing, the system MUST return a structured data-not-ready diagnostic with `stage`, `timeframe`, `missing_input`, `error_type`, required counts, available counts, and a human-readable message.
- **FR-008**: The structured diagnostic for missing last-closed-candle or indicator-window input MUST use `stage` of `signal_stack`, `timeframe` of `M5`, `missing_input` of `last_closed_candle_or_indicator_window`, and `error_type` of `DataNotReady`.
- **FR-009**: When data is not ready, the final decision MUST be deferred or indeterminate according to the existing decision model and MUST include a specific decision reason such as `signal_stack_data_not_ready`.
- **FR-010**: When data is not ready and signal-engine data is required, diagnostics MUST populate `first_blocker`, `all_blockers`, `blocking_layer`, and a signal-engine criterion with `blocked_signal = true`.
- **FR-011**: The system MUST distinguish data-not-ready outcomes from strategy-rule rejections in diagnostics and metrics summaries.
- **FR-012**: When required signal-stack data is available and aligned, the candidate MUST proceed to the existing candle-close gate and signal rule evaluation without being marked as missing signal-engine data.
- **FR-013**: The system MUST request or retain enough M5 history to satisfy the signal stack's largest required indicator window plus any closed-candle requirement.
- **FR-014**: The feature MUST preserve existing strategy thresholds, entry criteria, trend logic, and profitability behavior.
- **FR-015**: Metrics JSON and signal-journal outputs MUST remain backward-compatible while allowing additional readiness fields.
- **FR-016**: Automated tests MUST cover empty candles, one candle, no closed candle, insufficient indicator window, shortened indicator output, missing last closed candle, missing indicator window, valid data progression, blocker population, and backward-compatible metrics output.

### Key Entities

- **M5 Candle Set**: The raw and closed candles available to the signal stack for one candidate, including counts and timestamps needed to select a fully closed candle.
- **Last Closed Candle**: The selected M5 candle that is fully complete and eligible for signal-rule evaluation.
- **Indicator Window**: The usable indicator values available after warmup and null filtering, including the window length and timestamp alignment with the selected closed candle.
- **Readiness Diagnostic**: A structured record explaining why signal-stack evaluation was skipped before strategy-rule evaluation.
- **Signal Decision Metadata**: The decision reason, blockers, blocking layer, and signal-engine criterion status that classify a candidate as data-not-ready, strategy-rejected, deferred, or evaluated.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of normal data-not-ready M5 candle and indicator cases complete without a raw indexing failure.
- **SC-002**: 100% of data-not-ready signal-stack outcomes include a structured diagnostic identifying the missing input and available-versus-required counts.
- **SC-003**: 100% of valid aligned signal-stack inputs proceed past signal-engine data readiness to the existing candle-close gate and signal rule evaluation.
- **SC-004**: 100% of covered data-not-ready outcomes populate decision reason, first blocker, all blockers, blocking layer, and blocked-signal status when signal-engine data is required.
- **SC-005**: Existing metrics JSON consumers remain compatible, with no required existing field removed or renamed.
- **SC-006**: Automated regression tests cover all acceptance criteria listed for missing inputs and valid data progression.

## Assumptions

- The target operator is the existing local or Docker-hosted strategy metrics user reviewing diagnostics and signal journals.
- Existing decision states already include a deferred or indeterminate outcome that can represent data-not-ready conditions.
- The existing strategy intent is to evaluate only fully closed M5 candles; if the latest candle is open, the system will either defer or use the previous fully closed candle based on current project behavior discovered during implementation.
- Indicator requirements can be derived from the signal stack's current rules and should not be changed for tuning purposes.
- Diagnostics may add fields but must not remove, rename, or change the meaning of fields already consumed by existing metrics workflows.
