# Feature Specification: Signal Setup Outcomes

**Feature Branch**: `011-signal-setup-outcomes`  
**Created**: 2026-05-14  
**Status**: Draft  
**Input**: User description: "Add signal journal evaluation fields that separate emitted signal outcome from tradable setup outcome. Required fields: setup_group_id groups same symbol + direction + strategy signals within a configurable time window, default 10 minutes; is_duplicate_setup true when signal belongs to an existing active setup group; entry_valid_at_signal true when the signal price is still within an acceptable distance of the recommended entry; entry_miss_distance absolute and ATR-normalized distance from suggested entry at signal time; signal_age_bars number of M5 bars since the setup condition first became true; late_signal true when signal fired after price already moved beyond the valid entry tolerance; usable_for_strategy_stats false for duplicates, missed entries, stale signals, and manually invalidated signals; trade_grade TP_HIT, SL_HIT, BE, MISSED_ENTRY, LATE_SIGNAL, DUPLICATE, INVALID, PENDING. Do not count emitted signals as trade opportunities unless usable_for_strategy_stats is true."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Identify Tradable Setups (Priority: P1)

An operator reviewing Signal Journal evidence can distinguish a raw emitted signal from a unique tradable setup, so repeated alerts from the same market condition do not inflate opportunity counts.

**Why this priority**: Strategy statistics become misleading when every emitted signal is treated as an independent trade opportunity.

**Independent Test**: Create or inspect multiple same-symbol, same-direction, same-strategy signals inside the configured grouping window and verify they share one setup group while duplicate records are clearly marked.

**Acceptance Scenarios**:

1. **Given** a first signal for a symbol, direction, and strategy has no active setup group in the grouping window, **When** it is journaled, **Then** it starts a new setup group and is not marked as a duplicate.
2. **Given** another signal with the same symbol, direction, and strategy occurs inside the active setup grouping window, **When** it is journaled, **Then** it receives the same setup group and is marked as a duplicate setup.
3. **Given** another signal with the same symbol, direction, and strategy occurs after the grouping window has expired, **When** it is journaled, **Then** it starts a separate setup group.

---

### User Story 2 - Classify Entry Usability at Signal Time (Priority: P1)

An operator can tell whether a signal was still actionable at the moment it fired, including how far price had moved from the suggested entry.

**Why this priority**: A signal that arrives after price has already moved too far should not be evaluated like a valid trade opportunity.

**Independent Test**: Compare journal records for signals within entry tolerance, beyond entry tolerance, and at the tolerance boundary, then verify entry validity, miss distance, and late-signal status are recorded consistently.

**Acceptance Scenarios**:

1. **Given** signal-time price is within the acceptable distance of the recommended entry, **When** the signal is journaled, **Then** it records entry validity as true.
2. **Given** signal-time price is beyond the acceptable distance of the recommended entry, **When** the signal is journaled, **Then** it records entry validity as false, records the miss distance, and marks the signal as late when the move already exceeded valid entry tolerance.
3. **Given** ATR is available at signal time, **When** miss distance is recorded, **Then** the journal includes both absolute and ATR-normalized distance.
4. **Given** ATR is unavailable or unsuitable, **When** miss distance is recorded, **Then** the journal still records absolute distance and leaves the ATR-normalized value blank or unavailable.

---

### User Story 3 - Protect Strategy Statistics (Priority: P2)

An operator using strategy statistics can trust that opportunity counts only include usable setups, not duplicates, missed entries, stale signals, or manually invalidated records.

**Why this priority**: Optimization and diagnostics depend on separating signal emissions from real opportunities.

**Independent Test**: Review strategy statistics with a mix of usable, duplicate, missed, stale, and manually invalidated signals, then verify only records marked usable for strategy stats are counted as trade opportunities.

**Acceptance Scenarios**:

1. **Given** a signal is a duplicate setup, missed entry, late signal, stale signal, or manually invalidated signal, **When** strategy opportunity statistics are calculated, **Then** the signal is excluded.
2. **Given** a signal is eligible and not otherwise excluded, **When** strategy opportunity statistics are calculated, **Then** the signal may be counted as one trade opportunity.
3. **Given** an operator manually invalidates a previously usable signal, **When** statistics are refreshed, **Then** the signal no longer contributes to trade opportunity counts.

---

### User Story 4 - Record Normalized Trade Grades (Priority: P3)

An operator can review each journaled signal or setup using one normalized trade grade that separates resolved outcomes from duplicate, invalid, late, missed, and pending states.

**Why this priority**: Consistent grades make filtering, export, review, and later analysis less ambiguous.

**Independent Test**: Inspect journal records across all supported outcome states, including a break-even review action, and verify each uses exactly one allowed grade value.

**Acceptance Scenarios**:

1. **Given** a setup reaches take profit, stop loss, or break-even, **When** its outcome is recorded, **Then** its trade grade is `TP_HIT`, `SL_HIT`, or `BE`.
2. **Given** a signal is duplicate, missed, late, invalid, or unresolved, **When** its state is recorded, **Then** its trade grade is `DUPLICATE`, `MISSED_ENTRY`, `LATE_SIGNAL`, `INVALID`, or `PENDING`.
3. **Given** a journal record has a trade grade, **When** it is filtered, exported, or used for analysis, **Then** the grade value remains one of the allowed normalized values.

### Edge Cases

- The setup grouping window is changed from the default 10 minutes.
- The same symbol, direction, and strategy emits signals exactly at the grouping-window boundary.
- Signals have matching symbol and direction but different strategy identities.
- Signal-time price is exactly at the acceptable entry tolerance boundary.
- The suggested entry price is missing or unavailable.
- ATR is missing, zero, stale, or otherwise unsuitable for normalization.
- The setup condition first became true before the journal began tracking it.
- A signal is manually invalidated after previously being counted as usable.
- A pending signal later resolves to a TP hit, SL hit, break-even, missed entry, late signal, duplicate, or invalid state.
- Legacy journal records do not have the new evaluation fields.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Signal Journal MUST record `setup_group_id` for each new journaled signal.
- **FR-002**: `setup_group_id` MUST group signals with the same symbol, direction, and strategy when they occur within the active setup grouping window.
- **FR-003**: The setup grouping window MUST be configurable and MUST default to 10 minutes.
- **FR-004**: The Signal Journal MUST record `is_duplicate_setup` as true when a signal belongs to an existing active setup group rather than starting a new setup group.
- **FR-005**: The Signal Journal MUST record `entry_valid_at_signal` as true only when signal-time price is within the acceptable distance of the recommended entry.
- **FR-006**: The Signal Journal MUST record `entry_miss_distance` as both absolute distance from suggested entry and ATR-normalized distance when ATR is available.
- **FR-007**: The Signal Journal MUST record `signal_age_bars` as the number of M5 bars since the setup condition first became true.
- **FR-008**: The Signal Journal MUST record `late_signal` as true when a signal fired after price already moved beyond the valid entry tolerance.
- **FR-009**: The Signal Journal MUST record `usable_for_strategy_stats` as false for duplicate setups, missed entries, stale signals, manually invalidated signals, and late signals that are not usable trade opportunities.
- **FR-010**: Strategy statistics MUST NOT count emitted signals as trade opportunities unless `usable_for_strategy_stats` is true.
- **FR-011**: The Signal Journal MUST record `trade_grade` using only these values: `TP_HIT`, `SL_HIT`, `BE`, `MISSED_ENTRY`, `LATE_SIGNAL`, `DUPLICATE`, `INVALID`, or `PENDING`.
- **FR-012**: Duplicate setup signals MUST use `trade_grade` value `DUPLICATE`.
- **FR-013**: Signals whose entry was no longer valid at signal time MUST use `MISSED_ENTRY` or `LATE_SIGNAL` according to the recorded entry validity and lateness classification.
- **FR-014**: Manually invalidated signals MUST use `trade_grade` value `INVALID` and MUST have `usable_for_strategy_stats` set to false.
- **FR-015**: Unresolved eligible signals MUST use `trade_grade` value `PENDING` until a terminal outcome or invalidation is recorded.
- **FR-016**: The journal MUST preserve enough information for review and export to explain why `usable_for_strategy_stats` is false.
- **FR-017**: Existing Signal Journal records MUST remain readable even when they do not contain the new evaluation fields.
- **FR-018**: The feature MUST NOT retune strategy thresholds, change signal generation rules, or mutate historical signal evidence except where an operator explicitly invalidates a record.
- **FR-019**: Practical tests MUST cover setup grouping, grouping-window boundaries, duplicate classification, entry validity, absolute and ATR-normalized miss distance, signal age, late-signal classification, trade grade values, manual invalidation, legacy records, and strategy-stat opportunity counts.

### Key Entities *(include if feature involves data)*

- **Emitted Signal**: A signal event produced by strategy evaluation, regardless of whether it remains tradable.
- **Setup Group**: A logical group of same-symbol, same-direction, same-strategy signals emitted within the configured grouping window.
- **Tradable Setup**: A signal or setup group that remains entry-valid and is eligible to be counted as a trade opportunity.
- **Entry Validity Evaluation**: The signal-time assessment of current price against recommended entry tolerance, including absolute and ATR-normalized miss distance.
- **Signal Age**: The number of M5 bars between the setup condition first becoming true and the signal being emitted.
- **Strategy Stats Eligibility**: The journal decision that determines whether a signal contributes to opportunity counts.
- **Trade Grade**: The normalized outcome value assigned to a journaled signal or setup.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In validation data, 100% of same-symbol, same-direction, same-strategy signals inside the configured grouping window share one setup group.
- **SC-002**: In validation data, 100% of duplicate setup signals after the first active setup are marked `is_duplicate_setup` true and `usable_for_strategy_stats` false.
- **SC-003**: In validation data, 100% of missed, late, stale, and manually invalidated signals have `usable_for_strategy_stats` false.
- **SC-004**: Strategy opportunity counts include 0 emitted signals where `usable_for_strategy_stats` is false.
- **SC-005**: 100% of new journaled signals include values for setup group, duplicate status, entry validity, signal age, late-signal status, stats eligibility, and trade grade, with only ATR-normalized miss distance allowed to be blank when ATR is unavailable.
- **SC-006**: 100% of recorded trade grades use one of the eight allowed values.
- **SC-007**: Existing journal review and export workflows can read legacy records without failing when the new fields are absent.

## Assumptions

- Signal Journal operators are authenticated users who already have access to view strategy diagnostics and journal records.
- The setup grouping window defaults to 10 minutes unless the operator or environment config changes it.
- "Same strategy" means the strategy identity already recorded for the emitted signal.
- Existing strategy or journal context defines acceptable entry tolerance, stale-signal thresholds, recommended entry, and ATR availability; this feature records and applies those values without retuning them.
- Signal-time price is the market price captured with the emitted signal, falling back to the signal entry price only when no separate current price is available.
- Valid entry tolerance is configuration-driven and defaults to an ATR-based tolerance from existing journal or strategy context; implementation must document the exact source.
- Stale signal threshold is configuration-driven and must default conservatively without changing signal firing rules.
- If suggested entry is unavailable, `entry_valid_at_signal` is unknown or blank, `usable_for_strategy_stats` is false, and `stats_exclusion_reason` is `missing_entry_context`.
- A signal exactly at the acceptable entry tolerance boundary is considered entry-valid.
- When ATR is unavailable or unsuitable, absolute entry miss distance is still recorded and the ATR-normalized value may be blank.
- Legacy records may display blank values for fields that did not exist when they were created.
