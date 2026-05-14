# Feature Specification: Signal Journal Export

**Feature Branch**: `010-signal-journal-export`  
**Created**: 2026-05-14  
**Status**: Draft  
**Input**: User description: "Fix the Signal Journal export button so clicking it downloads a CSV file, add export range selection so stale signals from old broken strategy runs are excluded unless selected, reuse existing visible filters where available, avoid strategy logic or data mutation changes, and add practical tests."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Download a Signal Journal CSV (Priority: P1)

An operator viewing the Signal Journal can click export and receive an actual CSV file download containing the journal records that match the export scope.

**Why this priority**: The current export action reports success but does not produce a file, so the primary workflow is broken.

**Independent Test**: From the Signal Journal page, trigger export for records known to exist and verify that the browser downloads a CSV file with a meaningful Signal Journal filename and readable rows.

**Acceptance Scenarios**:

1. **Given** the Signal Journal contains matching records, **When** the operator clicks export, **Then** a CSV file is downloaded in the browser.
2. **Given** the export completes successfully, **When** the operator inspects the downloaded file, **Then** the filename identifies the Signal Journal and selected range or current selection.
3. **Given** a successful export request occurs, **When** the browser receives the export response, **Then** the response is handled as a downloadable file rather than as ordinary page data.

---

### User Story 2 - Export a Selected Time Range (Priority: P2)

An operator can choose a date/time range before exporting so optimization analysis can focus on the intended period and exclude stale signals from old broken strategy runs.

**Why this priority**: Reliable optimization analysis depends on exporting the relevant signal window rather than mixing current data with obsolete or broken-run signals.

**Independent Test**: Choose a date/time range that includes some records and excludes older records, export the CSV, and verify every exported row falls within the selected range.

**Acceptance Scenarios**:

1. **Given** the Signal Journal contains records inside and outside a selected evaluated/created timestamp range, **When** the operator exports that range, **Then** only records within the selected range appear in the CSV.
2. **Given** a selected range has both start and end values, **When** the export completes, **Then** the downloaded filename includes the selected date boundaries.
3. **Given** a selected range matches no records, **When** the operator exports, **Then** the page shows a clear no-records message and no empty or broken file is downloaded.

---

### User Story 3 - Export Current Journal Filters (Priority: P3)

An operator can export records matching the Signal Journal filters already used to inspect data, such as symbol, status, final decision, strategy, mode, date range, and graded or pending state when those filters are available.

**Why this priority**: Matching exports to visible journal filters reduces surprises and makes later analysis reproducible.

**Independent Test**: Apply visible filters to the Signal Journal, export, and verify the CSV contains only records matching those filters.

**Acceptance Scenarios**:

1. **Given** one or more Signal Journal filters are active, **When** the operator exports the current filtered set, **Then** the CSV contains only records matching those filters.
2. **Given** no optional filters are active, **When** the operator exports a selected date/time range, **Then** only the date/time range constrains the exported records.
3. **Given** filter criteria exclude all records, **When** the operator exports, **Then** the page shows a clear no-records message and no file is downloaded.

### Edge Cases

- The selected start timestamp is after the selected end timestamp.
- The selected range has only a start or only an end timestamp.
- The journal contains records with an evaluated timestamp and records with only a created timestamp.
- The journal contains nested diagnostics, blockers, or criteria that must be represented without making the primary CSV unreadable.
- A download-capable response succeeds but the browser cannot create or save the file.
- Existing table filtering, grading, pending-state behavior, and pagination are active while export is triggered.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST download a CSV file when the Signal Journal export action succeeds and matching records exist.
- **FR-002**: The exported file MUST use a meaningful filename that identifies the Signal Journal and either the selected date range or selected/current filtered range.
- **FR-003**: The export result MUST be delivered with file download metadata so browsers can recognize it as a CSV attachment.
- **FR-004**: The Signal Journal page MUST provide date/time range controls for export.
- **FR-005**: Export range filtering MUST use the signal timestamp most relevant for journal analysis, preferring evaluated timestamp when present and falling back to created timestamp otherwise.
- **FR-006**: The export MUST include only records matching the selected export range.
- **FR-007**: The export SHOULD include records matching the same visible Signal Journal filters when those filters exist, including symbol, status, final decision, strategy, mode, date range, and graded or pending state.
- **FR-008**: The system MUST show a clear user-facing message when an export selection matches no records and MUST NOT download an empty or broken file in that case.
- **FR-009**: The CSV MUST include fields needed for later optimization analysis: signal or opportunity ID, symbol, timeframe, strategy, mode, direction, trend, final decision, decision reason, confidence, failed criteria count, near miss flag and reason, first blocker, all blockers, blocking layer, evaluated timestamp, created timestamp, signal status, grade or pending state when present, trade result fields when present, and profit/loss fields when present.
- **FR-010**: Nested criteria or diagnostics included in existing journal data MUST be represented in a deterministic flat CSV column when practical.
- **FR-011**: The feature MUST preserve existing Signal Journal table filtering, grading, pending-state behavior, and pagination.
- **FR-012**: The feature MUST NOT change strategy logic, signal generation rules, or existing signal data.
- **FR-013**: Export behavior MUST be deterministic: the same export selection over unchanged data must produce the same records and stable column structure.
- **FR-014**: Practical tests MUST cover file download behavior, download metadata, range/filter parameter use, selected-range record inclusion, and no-records handling.

### Key Entities *(include if feature involves data)*

- **Signal Journal Record**: A journal entry representing a signal or opportunity, including identifiers, market context, strategy metadata, decision details, blockers, timestamps, status, grading state, and optional trade result or profit/loss data.
- **Export Selection**: The operator-selected scope for the export, including date/time boundaries and any applicable current Signal Journal filters.
- **CSV Export File**: A deterministic flat-file representation of matching Signal Journal records with stable column names and a meaningful filename.
- **No-Records Result**: A user-facing outcome for valid export selections that match zero records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In manual verification, 100% of successful Signal Journal exports with matching records produce a browser-downloaded CSV file.
- **SC-002**: For a selected date/time range, 100% of exported rows have their evaluated timestamp, or created timestamp when evaluated timestamp is absent, within the selected boundaries.
- **SC-003**: For a filtered export, 100% of exported rows match the active export filters that were selected or visible at export time.
- **SC-004**: Empty export selections show a visible message within 2 seconds and produce no downloaded file.
- **SC-005**: The CSV includes all mandatory optimization-analysis columns for every exported row, with blank values allowed only where the underlying journal data is absent.
- **SC-006**: Existing Signal Journal browsing, filtering, grading, pending-state behavior, and pagination continue to pass their current validation checks after the export change.

## Assumptions

- Signal Journal operators are authenticated users who already have access to view the journal.
- CSV is the required export format for this feature; additional formats are out of scope.
- Row selection export is optional unless the existing UI already has row selection available.
- Existing signal data must remain unchanged, including stale or broken-run records.
- Export date/time controls may default to the current visible journal date range when one is already active.
- The feature is limited to Signal Journal export and does not alter signal generation, strategy thresholds, trading decisions, or risk behavior.
