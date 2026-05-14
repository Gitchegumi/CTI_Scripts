# Tasks: Signal Journal Export

**Input**: Design documents from `specs/010-signal-journal-export/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included because the feature request explicitly asks for backend export, frontend response handling, filter/range parameter, and selected-range coverage.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm current export surface and validation commands before changing behavior.

- [X] T001 Inspect current Signal Journal export implementation in `src/tradegumi/journal.py`, `src/tradegumi/api_server.py`, `dashboard/src/app/api/journal/export/route.ts`, and `dashboard/src/app/journal/page.tsx`
- [X] T002 [P] Confirm existing dashboard export patterns in `dashboard/src/app/manual-trades/page.tsx` and `dashboard/src/app/strategy-metrics/page.tsx`
- [X] T003 [P] Confirm focused backend test conventions in `src/tradegumi/tests/test_journal.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared export-selection primitives needed by all export stories.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 Add `SignalJournalExportSelection` and `SignalJournalExportResult` helpers with useful docstrings in `src/tradegumi/journal.py`
- [X] T005 Add timestamp parsing and per-record analysis timestamp selection helpers with useful docstrings in `src/tradegumi/journal.py`
- [X] T006 Add deterministic CSV cell normalization for nested/list/dict values in `src/tradegumi/journal.py`
- [X] T007 [P] Update Signal Journal export scope type definitions in `dashboard/src/types/index.ts`

**Checkpoint**: Export helper can represent scope, timestamps, and deterministic CSV values.

---

## Phase 3: User Story 1 - Download a Signal Journal CSV (Priority: P1) MVP

**Goal**: Successful Signal Journal exports produce a real browser-downloaded CSV file with server-provided file metadata.

**Independent Test**: Trigger export for existing records and verify the browser downloads a CSV attachment with a Signal Journal filename.

### Tests for User Story 1

- [X] T008 [P] [US1] Add backend export result/header-focused unit tests in `src/tradegumi/tests/test_journal.py`
- [X] T009 [P] [US1] Add dashboard export handler checks for Blob download and filename parsing in `dashboard/src/app/journal/page.tsx` if local test infrastructure exists; otherwise document manual coverage in `specs/010-signal-journal-export/quickstart.md`

### Implementation for User Story 1

- [X] T010 [US1] Update `export_journal_csv` or equivalent helper in `src/tradegumi/journal.py` to return CSV plus matching-record count and filename metadata
- [X] T011 [US1] Update `/api/journal/export` in `src/tradegumi/api_server.py` to return `Content-Type`, `Content-Disposition`, and `Content-Length` for CSV attachments
- [X] T012 [US1] Update `dashboard/src/app/api/journal/export/route.ts` to forward upstream file status, body, `Content-Type`, and `Content-Disposition`
- [X] T013 [US1] Update `exportJournal` in `dashboard/src/app/journal/page.tsx` to prefer the `Content-Disposition` filename, create a Blob download, and revoke the object URL after click

**Checkpoint**: User Story 1 is functional and testable independently.

---

## Phase 4: User Story 2 - Export a Selected Time Range (Priority: P2)

**Goal**: Operators can export only a selected evaluated/created timestamp range.

**Independent Test**: Export a range that includes recent records and excludes older records, then verify all CSV rows are in range.

### Tests for User Story 2

- [X] T014 [P] [US2] Add backend range-filter tests for `evaluated_at`, `created_at`, and legacy `signal_timestamp` fallback in `src/tradegumi/tests/test_journal.py`
- [X] T015 [P] [US2] Add invalid-range and no-records tests in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 2

- [X] T016 [US2] Implement inclusive `start`/`end` filtering in `src/tradegumi/journal.py`
- [X] T017 [US2] Update `/api/journal/export` query handling in `src/tradegumi/api_server.py` for `start` and `end`, including invalid-range errors and no-records JSON response
- [X] T018 [US2] Add date/time export controls and local invalid-range guard in `dashboard/src/app/journal/page.tsx`
- [X] T019 [US2] Send selected `start` and `end` parameters from `dashboard/src/app/journal/page.tsx` through `dashboard/src/app/api/journal/export/route.ts`
- [X] T020 [US2] Ensure empty export results display a clear message and do not create a download link in `dashboard/src/app/journal/page.tsx`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Export Current Journal Filters (Priority: P3)

**Goal**: Export scope matches current visible Signal Journal filters, starting with the existing grade filter and preserving room for additional visible filters later.

**Independent Test**: Apply the visible grade filter, export, and verify all CSV rows match the selected grade plus selected date/time range.

### Tests for User Story 3

- [X] T021 [P] [US3] Add combined grade-plus-range export tests in `src/tradegumi/tests/test_journal.py`
- [X] T022 [P] [US3] Add deterministic field-order and required optimization-column tests in `src/tradegumi/tests/test_journal.py`

### Implementation for User Story 3

- [X] T023 [US3] Extend `src/tradegumi/journal.py` export fields to include required optimization-analysis columns while preserving deterministic extra fields
- [X] T024 [US3] Ensure `dashboard/src/app/journal/page.tsx` sends the existing grade filter with range parameters and does not alter grading, reset, purge, grouping, or pagination behavior
- [X] T025 [US3] Ensure `dashboard/src/app/api/journal/export/route.ts` forwards all current and reserved export filter query parameters without dropping file headers

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and final quality checks.

- [X] T026 [P] Update Signal Journal export documentation in `docs/signal-journal.md`
- [X] T027 Review changed Python code for intention-revealing names, simple control flow, and useful docstrings in `src/tradegumi/journal.py` and `src/tradegumi/api_server.py`
- [X] T028 Review changed dashboard UI for responsive controls, non-overlapping text, and preservation of existing Signal Journal workflows in `dashboard/src/app/journal/page.tsx`
- [X] T029 Run focused backend tests with `python -m pytest src/tradegumi/tests/test_journal.py`
- [X] T030 Run dashboard lint with `npm run lint` from `dashboard/`
- [X] T031 Run dashboard build with `npm run build` from `dashboard/`
- [ ] T032 Run manual quickstart validation from `specs/010-signal-journal-export/quickstart.md`
- [ ] T033 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion; blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational; MVP for file download behavior.
- **User Story 2 (Phase 4)**: Depends on Foundational and integrates with US1 response behavior.
- **User Story 3 (Phase 5)**: Depends on Foundational and benefits from US1/US2 export plumbing.
- **Polish (Phase 6)**: Depends on all implemented stories.

### User Story Dependencies

- **US1**: No dependency on US2 or US3 after Foundational.
- **US2**: Can be implemented after Foundational, but final UI behavior uses US1's file/no-file response handling.
- **US3**: Can be implemented after Foundational, but final validation combines grade filters with US2 range selection.

### Parallel Opportunities

- T002 and T003 can run in parallel.
- T007 can run in parallel with T004-T006.
- T008 and T009 can run in parallel.
- T014 and T015 can run in parallel.
- T021 and T022 can run in parallel.
- T026 can run in parallel with final code review tasks once behavior is stable.

## Parallel Example: User Story 2

```text
Task: "Add backend range-filter tests for evaluated_at, created_at, and legacy signal_timestamp fallback in src/tradegumi/tests/test_journal.py"
Task: "Add invalid-range and no-records tests in src/tradegumi/tests/test_journal.py"
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup and Foundational tasks.
2. Implement US1 backend/proxy/header/browser download behavior.
3. Validate that a CSV file downloads for matching records.

### Incremental Delivery

1. US1 fixes the broken download contract.
2. US2 adds date/time range selection and empty-result behavior.
3. US3 aligns exports with visible filters and required optimization columns.
4. Polish updates docs and runs backend/dashboard validation.

## Notes

- Do not edit strategy, risk, signal generation, or broker execution code.
- Do not purge, rewrite, or migrate existing Signal Journal data.
- Mark each completed task as `[X]` in this file during implementation.
