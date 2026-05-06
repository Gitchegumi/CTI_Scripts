# Feature Specification: Journal and Dashboard Controls

**Feature Branch**: `005-journal-dashboard-controls`  
**Created**: 2026-05-05  
**Status**: Draft  
**Input**: User description: "Fix strategy metrics date range inclusion, add signal journal export and maintenance controls, allow Developing-mode manual P&L correction, display alert_only as Developing, and restore dashboard trade history loading without noisy console failures."

## Clarifications

### Session 2026-05-05

- No critical ambiguities required user input before planning; conservative defaults from the request were accepted for filtered Signal Journal export, filtered-or-all purge scope, reset-to-pending semantics, preserving internal `alert_only`, optional trade-correlation fallback, and no destructive migrations.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review Strategy Metrics Through Selected End Date (Priority: P1)

A strategy reviewer selects a start and end date on the Strategy Metrics page and sees all evaluations that occurred from the start of the start date through the end of the selected end date.

**Why this priority**: Date range trust is foundational for every tuning decision. If the selected end date excludes same-day data, every summary, export, and comparison can be misleading.

**Independent Test**: Can be fully tested by creating evaluations on the selected end date, selecting that date as the end date, and verifying that summary totals and opportunity rows include those evaluations.

**Acceptance Scenarios**:

1. **Given** evaluations exist at 2026-05-06 00:00, noon, and 23:59:59 local/application time, **When** the reviewer selects end date 05/06/2026, **Then** all three evaluations are included.
2. **Given** evaluations exist on 2026-05-07, **When** the reviewer selects end date 05/06/2026, **Then** 2026-05-07 evaluations are excluded.
3. **Given** the system uses an exclusive internal end boundary, **When** the reviewer selects 05/06/2026, **Then** the system converts it to an internal boundary at the start of 05/07/2026 and keeps the displayed selection as 05/06/2026.

---

### User Story 2 - Export Signal Journal Data for Optimization (Priority: P1)

A strategy reviewer exports Signal Journal records into a portable file that contains signal identity, emitted signal details, diagnostics, grading state, outcomes when available, notes, and timestamps needed for optimization analysis.

**Why this priority**: The current signal journal contains useful forward-testing evidence, but optimization work requires a repeatable export path rather than manual copying.

**Independent Test**: Can be tested by applying a journal filter, exporting, and verifying that the file contains the filtered signal records with the required optimization fields.

**Acceptance Scenarios**:

1. **Given** journal entries exist for multiple grades, **When** the reviewer filters to Pending and exports, **Then** the export includes only Pending entries and records the export scope.
2. **Given** a journal entry has signal details, diagnostics, grade, notes, and timestamps, **When** it is exported, **Then** those fields are present in the exported record.
3. **Given** optional diagnostic or outcome fields are missing from older records, **When** the export is generated, **Then** the record remains exportable and missing fields are explicitly blank or null rather than causing failure.

---

### User Story 3 - Purge Stale Signal Journal Entries Safely (Priority: P1)

A strategy reviewer removes stale Signal Journal entries generated under old strategy parameters after confirming the destructive action.

**Why this priority**: Old signal records can pollute current optimization analysis. The action is destructive, so it needs a clear confirmation path.

**Independent Test**: Can be tested by creating journal entries, initiating purge, cancelling once, confirming once, and verifying that only Signal Journal entries in the chosen scope are removed.

**Acceptance Scenarios**:

1. **Given** Signal Journal entries exist, **When** the reviewer chooses Purge and cancels the confirmation, **Then** no entries are removed.
2. **Given** Signal Journal entries exist and the reviewer confirms purge, **When** the purge completes, **Then** the page refreshes and shows the cleared state for the selected scope.
3. **Given** manual trade journal entries exist, **When** Signal Journal entries are purged, **Then** manual trade journal entries remain unchanged.

---

### User Story 4 - Reset Accidentally Graded Signals to Pending (Priority: P2)

A reviewer can reset an accidentally graded Signal Journal entry back to Pending while preserving the original emitted signal and diagnostic evidence.

**Why this priority**: Accidental grading can distort outcome statistics before a trade has completed. Resetting avoids deleting useful signal records.

**Independent Test**: Can be tested by grading an entry, resetting it to Pending, and verifying that signal details and notes remain while grade-completion fields no longer make it appear graded.

**Acceptance Scenarios**:

1. **Given** a signal is graded TP Hit, SL Hit, Manual Close, or Expired, **When** the reviewer resets it to Pending, **Then** its grade/status is Pending.
2. **Given** a reset entry had original signal prices, confidence, strategy, and diagnostics, **When** reset completes, **Then** those original fields are unchanged.
3. **Given** a reset entry had reviewer notes, **When** reset completes, **Then** the notes remain unless they are explicitly outcome-only fields.

---

### User Story 5 - Correct Manual Trade P&L in Developing Mode (Priority: P2)

An operator in Developing mode can correct the P&L of manually tracked trades because the bot did not execute those trades automatically.

**Why this priority**: Developing-mode trade history is used for evaluation, and inaccurate P&L prevents reliable strategy review.

**Independent Test**: Can be tested by setting mode to alert_only, editing a manual trade P&L field, and verifying that the correction is accepted and reflected in the trade table and summary while the same protected edit is rejected outside Developing mode.

**Acceptance Scenarios**:

1. **Given** the current mode is alert_only, **When** the operator edits a manual trade P&L, **Then** the updated P&L is saved and displayed.
2. **Given** the current mode is demo or live, **When** the operator attempts to edit protected trade facts including P&L, **Then** the edit is rejected or hidden and only allowed annotation fields remain editable.
3. **Given** a P&L override is saved, **When** the trade appears in dashboard history or export, **Then** the displayed value and override status are clear.

---

### User Story 6 - See Developing Label Instead of Alert Only (Priority: P3)

An operator sees the user-facing mode label "Developing" anywhere the application currently presents "Alert Only", while existing stored values and configuration remain stable.

**Why this priority**: The label explains why full manual correction is allowed without forcing a risky internal mode migration.

**Independent Test**: Can be tested by setting mode to alert_only and verifying all user-facing mode badges, controls, filters, and documentation display "Developing" while API and stored values still use alert_only.

**Acceptance Scenarios**:

1. **Given** the stored mode is alert_only, **When** the dashboard renders mode labels, **Then** users see "Developing".
2. **Given** existing records contain alert_only, **When** records are loaded, filtered, exported, or edited, **Then** they continue to work without migration.
3. **Given** an API response exposes the raw mode value for compatibility, **When** the UI displays it, **Then** the display layer maps it to "Developing".

---

### User Story 7 - Restore Main Dashboard Trade History (Priority: P1)

An operator opens the main dashboard and sees manual trade journal records in Trade History without repeated failing requests or hydration errors.

**Why this priority**: The dashboard is the primary operating surface. A failing trade-history panel hides current performance and creates noisy console errors that obscure real failures.

**Independent Test**: Can be tested by creating manual trade records, opening the dashboard, and verifying that Trade History displays them while `/api/trades/history?count=50` returns a valid response and missing correlation data does not break rendering.

**Acceptance Scenarios**:

1. **Given** manual trade records exist, **When** `/api/trades/history?count=50` is requested with valid access, **Then** it returns a valid trade-history response instead of a 500.
2. **Given** manual trade records exist and broker/source trade history is unavailable or fails, **When** the dashboard loads, **Then** manual records still populate Trade History.
3. **Given** trade correlation data is missing, **When** the dashboard loads, **Then** correlation fields fall back to empty values without repeated noisy 404 errors.
4. **Given** the dashboard renders dates and client-only data, **When** the page hydrates, **Then** React hydration error #418 no longer occurs.

### Edge Cases

- Selected strategy metrics ranges that start or end on daylight-saving transition days must not omit records from the selected calendar date.
- Empty Signal Journal export must return a valid file with metadata and an empty records list.
- Malformed legacy Signal Journal lines must not prevent valid neighboring lines from exporting, purging, or resetting.
- Purge must be idempotent when the selected scope already has no Signal Journal entries.
- Reset to Pending must be safe when the entry is already Pending.
- Manual trade P&L edits must handle zero, positive, and negative values.
- Dashboard trade history must remain available when broker/source trade history fails but local manual trade history is readable.
- Missing optional optimization fields must be represented consistently without hiding the record.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Strategy Metrics date filtering MUST include the full selected end date in summaries, opportunity lists, comparisons, and exports.
- **FR-002**: Strategy Metrics date filtering MUST exclude records after the selected end date.
- **FR-003**: Strategy Metrics date handling MUST document whether internal ranges are inclusive or exclusive and must keep UI behavior intuitive for calendar-date selections.
- **FR-004**: Signal Journal MUST provide an export action from the Signal Journal page.
- **FR-005**: Signal Journal export MUST include signal identity, symbol, direction, signal timestamp, strategy/version/parameter identifiers when available, emitted signal details, criteria or diagnostics when available, grade/status, outcome data when available, user notes, and relevant timestamps.
- **FR-006**: Signal Journal export MUST produce CSV as the minimum supported format; JSON MAY be added as an additional format if it follows existing export patterns.
- **FR-007**: Signal Journal export MUST respect active Signal Journal filters and record the export scope in metadata or filename.
- **FR-008**: Signal Journal MUST provide a confirmed purge action that deletes Signal Journal entries in the chosen scope only after user confirmation.
- **FR-009**: Signal Journal purge MUST NOT delete manual trade journal entries.
- **FR-010**: Signal Journal purge MUST refresh the page state after completion and show an accurate empty or filtered state.
- **FR-011**: Signal Journal MUST provide a row-level action to reset graded or completed entries to Pending.
- **FR-012**: Resetting a Signal Journal entry to Pending MUST preserve original signal and diagnostic fields.
- **FR-013**: Resetting a Signal Journal entry to Pending MUST clear grade-completion fields that would keep the entry classified as graded, while preserving user notes by default.
- **FR-014**: Manual trade P&L MUST be editable when the current mode is alert_only, displayed to users as Developing.
- **FR-015**: Protected manual trade facts including P&L MUST remain non-editable outside alert_only/Developing mode, except for allowed annotation fields.
- **FR-016**: User-facing UI labels MUST display "Developing" instead of "Alert Only" while preserving internal alert_only values and existing stored records.
- **FR-017**: Dashboard Trade History MUST load manual trade journal records through the dashboard trade-history path.
- **FR-018**: `/api/trades/history?count=50` MUST return a valid response for valid requests when manual trades exist, even if broker/source trade history is unavailable.
- **FR-019**: Missing trade correlation data MUST use an intentional empty fallback and MUST NOT produce repeated noisy 404 console errors.
- **FR-020**: React hydration mismatch error #418 MUST be investigated and resolved or isolated behind client-only rendering for unstable client-derived content.
- **FR-021**: Errors MUST be fixed at the root cause or handled through intentional fallbacks; the implementation MUST NOT merely hide failures that remain operationally important.
- **FR-022**: Existing diagnostics useful for optimization MUST be preserved in journal records, metrics records, exports, and dashboard display where already available.
- **FR-023**: All destructive journal maintenance actions MUST require confirmation and expose success or failure feedback.
- **FR-024**: Existing stored manual trade and Signal Journal records MUST remain readable without a destructive migration.

### Key Entities

- **Strategy Metrics Range**: User-selected start and end calendar dates, normalized to an internal query range and applied consistently to summaries, opportunities, comparisons, and exports.
- **Signal Journal Entry**: A recorded emitted signal with identity, symbol, direction, strategy context, emitted prices, diagnostics, grade/status, notes, timestamps, and optional outcome fields.
- **Signal Journal Export**: A portable optimization data file with export metadata, scope, schema/version indicator, and journal records.
- **Signal Journal Purge Scope**: The set of journal entries selected for deletion, derived from active filters by default.
- **Manual Trade Record**: A manually tracked or corrected trade with mode, source, P&L, notes, tags, permissions, and optional override status.
- **Display Mode Label**: User-facing mapping from internal mode value to display label, especially alert_only to Developing.
- **Dashboard Trade History Record**: A dashboard-ready trade-history item normalized from manual and optional broker/source records.
- **Trade Correlation Data**: Optional confidence/correlation metadata associated with trade history records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A selected Strategy Metrics end date includes records through 23:59:59.999 of that calendar date in 100% of date range tests.
- **SC-002**: Signal Journal export completes successfully for empty, filtered, and mixed legacy/current journal data sets.
- **SC-003**: Confirmed Signal Journal purge removes only the selected Signal Journal scope and never removes manual trade journal records in validation tests.
- **SC-004**: Resetting graded Signal Journal entries to Pending preserves original signal details and notes in validation tests.
- **SC-005**: Manual trade P&L edits succeed in alert_only/Developing mode and fail or remain unavailable in demo/live mode in validation tests.
- **SC-006**: All user-facing alert_only labels in affected screens display "Developing" while stored/API compatibility with alert_only remains intact.
- **SC-007**: Dashboard Trade History displays existing manual trade records and `/api/trades/history?count=50` no longer returns 500 for valid manual-history requests.
- **SC-008**: Missing trade correlation data causes zero repeated visible or console 404 failures during normal dashboard polling.
- **SC-009**: React hydration error #418 is absent during dashboard load validation.
- **SC-010**: Each issue in this specification has either automated test coverage or a documented manual verification step.

## Assumptions

- The application remains a single-operator dashboard; no new multi-user permission model is introduced.
- Internal mode values remain `alert_only`, `demo`, and `live`; only display labels change for this feature.
- Signal Journal export respects the active grade filter because the page already exposes grade filtering and filtered export is safer for optimization workflows.
- Signal Journal purge defaults to the active grade filter when a filter is selected; otherwise it purges all Signal Journal entries after confirmation.
- Resetting a signal to Pending clears grade/status completion markers such as grade timestamp and outcome-specific classification fields, while preserving free-form notes.
- No destructive migration is planned; compatibility fixes should read existing JSONL and SQLite records in place.
- Missing trade correlation data is optional for display and should fall back to an empty correlation list.
- Strategy Metrics selected calendar dates use the application's current local/operator time semantics unless an existing backend timestamp already includes a timezone; internal storage timestamps remain unchanged.
