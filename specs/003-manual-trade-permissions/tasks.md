# Tasks: Manual Trade Permissions

**Input**: Design documents from `/specs/003-manual-trade-permissions/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Python tests are included because the plan and quickstart require coverage for schema migration, legacy defaulting, mode filtering, duplicate merge, local overrides, annotation persistence, permission enforcement, and agent export schema/content.

**Organization**: Tasks are grouped by user story so each story can be implemented and validated independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel because it touches different files and has no dependency on incomplete tasks.
- **[Story]**: User story label for story phases only.
- Every task includes exact file paths.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Prepare existing backend/frontend files and test entry points for the feature.

- [ ] T001 Inspect existing manual-trade schema and test isolation patterns in `src/tradegumi/manual_trades.py` and `src/tradegumi/tests/`
- [ ] T002 [P] Inspect current dashboard trade-history data flow in `dashboard/src/hooks/useData.ts`, `dashboard/src/lib/api.ts`, and `dashboard/src/components/TradeHistory.tsx`
- [ ] T003 [P] Inspect current manual trades UI and proxy behavior in `dashboard/src/app/manual-trades/page.tsx` and `dashboard/src/app/api/manual-trades/[[...id]]/route.ts`
- [ ] T004 [P] Create or update Python manual-trade test module scaffold in `src/tradegumi/tests/test_manual_trades.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add shared mode-scoped storage primitives, canonical identity, and API data shapes needed by every story.

**CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 Add bot-mode, source identity, tags, annotation, and override schema support with legacy `alert_only` defaults in `src/tradegumi/manual_trades.py`
- [ ] T006 Add canonical trade identity and normalization helpers for manual and source trade records in `src/tradegumi/manual_trades.py`
- [ ] T007 Add permission calculation helper for `can_edit_all_fields`, `can_edit_notes_tags`, and `can_delete` in `src/tradegumi/manual_trades.py`
- [ ] T008 Add backend response serialization for unified historical trades matching `contracts/manual-trades-api.md` in `src/tradegumi/manual_trades.py`
- [ ] T009 Add agent export schema constants and field metadata helpers matching `contracts/agent-export.md` in `src/tradegumi/manual_trades.py`
- [ ] T010 Update TypeScript trade history, permission, and agent export types in `dashboard/src/types/index.ts`
- [ ] T011 Update API client types and unified trade-history/export method signatures in `dashboard/src/lib/api.ts`

**Checkpoint**: Foundation ready - user story implementation can now begin.

---

## Phase 3: User Story 1 - Review Complete History in Manual Trades (Priority: P1) MVP

**Goal**: `/manual-trades` and the main dashboard Trade History show the same complete, de-duplicated current-mode history.

**Independent Test**: Populate dashboard-visible historical trades, open `/manual-trades`, and confirm all matching current-mode trades appear once with correct empty/error behavior.

### Tests for User Story 1

- [ ] T012 [P] [US1] Add Python test for current-mode filtering and legacy `alert_only` defaulting in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T013 [P] [US1] Add Python test for duplicate canonical identity merge in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T014 [P] [US1] Add Python test for unified summary stats scoped to current mode in `src/tradegumi/tests/test_manual_trades.py`

### Implementation for User Story 1

- [ ] T015 [US1] Implement unified current-mode history query and merge logic in `src/tradegumi/manual_trades.py`
- [ ] T016 [US1] Implement current-mode summary stats over unified history in `src/tradegumi/manual_trades.py`
- [ ] T017 [US1] Update `GET /api/trades/manual`, `GET /api/trades/manual/stats`, and unified dashboard `GET /api/trades/history` handling in `src/tradegumi/api_server.py`
- [ ] T018 [US1] Update Next.js manual-trades proxy query forwarding and response handling in `dashboard/src/app/api/manual-trades/[[...id]]/route.ts`
- [ ] T019 [US1] Update Next.js manual-trades stats proxy response handling in `dashboard/src/app/api/manual-trades/stats/route.ts`
- [ ] T020 [US1] Add Next.js proxy route for unified dashboard trade history in `dashboard/src/app/api/trades/history/route.ts`
- [ ] T021 [US1] Update `useTradeHistory` to fetch unified current-mode history through `dashboard/src/lib/api.ts` in `dashboard/src/hooks/useData.ts`
- [ ] T022 [US1] Update `/manual-trades` loading, empty, error, filtering, and table rendering for unified history in `dashboard/src/app/manual-trades/page.tsx`
- [ ] T023 [US1] Update main dashboard `TradeHistory` field mapping for unified history records in `dashboard/src/components/TradeHistory.tsx`

**Checkpoint**: User Story 1 is fully functional and testable as the MVP.

---

## Phase 4: User Story 2 - Edit Historical Trades in Alert-Only Mode (Priority: P2)

**Goal**: In `alert_only`, every displayed trade can be fully edited, non-manual edits are stored as local overrides, and only manually created trades can be deleted.

**Independent Test**: Set mode to `alert_only`, edit every exposed field on manual and non-manual historical trades, confirm both views show saved values, and confirm delete is available only for manual trades.

### Tests for User Story 2

- [ ] T024 [P] [US2] Add Python test for full-field manual trade updates in `alert_only` in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T025 [P] [US2] Add Python test for non-manual trade local overrides and merged display in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T026 [P] [US2] Add Python test preventing deletion of non-manual historical trades in `src/tradegumi/tests/test_manual_trades.py`

### Implementation for User Story 2

- [ ] T027 [US2] Implement `alert_only` full-field update behavior for manual trades in `src/tradegumi/manual_trades.py`
- [ ] T028 [US2] Implement local override create/update and merge behavior for non-manual trades in `src/tradegumi/manual_trades.py`
- [ ] T029 [US2] Implement manual-only delete enforcement in `src/tradegumi/manual_trades.py`
- [ ] T030 [US2] Update `PUT /api/trades/manual/{id}` and `DELETE /api/trades/manual/{id}` handling for `alert_only` permissions in `src/tradegumi/api_server.py`
- [ ] T031 [US2] Update `/manual-trades` edit form to support all exposed unified trade fields in `dashboard/src/app/manual-trades/page.tsx`
- [ ] T032 [US2] Update `/manual-trades` delete action visibility to allow only manual records in `alert_only` in `dashboard/src/app/manual-trades/page.tsx`
- [ ] T033 [US2] Add local override indicator in `/manual-trades` for corrected non-manual records in `dashboard/src/app/manual-trades/page.tsx`

**Checkpoint**: User Stories 1 and 2 both work independently.

---

## Phase 5: User Story 3 - Restrict Edits Outside Alert-Only Mode (Priority: P3)

**Goal**: In every non-`alert_only` mode, only notes and tags are editable, protected trade facts cannot change, and all mode data remains isolated.

**Independent Test**: Switch to `demo` or `live`, confirm only notes/tags are editable, attempt protected field changes, confirm zero protected changes persist, and confirm mode switches do not leak data.

### Tests for User Story 3

- [ ] T034 [P] [US3] Add Python test for notes/tags-only updates outside `alert_only` in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T035 [P] [US3] Add Python test rejecting protected field changes outside `alert_only` in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T036 [P] [US3] Add Python test for annotation, override, and trade isolation across modes in `src/tradegumi/tests/test_manual_trades.py`

### Implementation for User Story 3

- [ ] T037 [US3] Implement notes and tags persistence for all modes in `src/tradegumi/manual_trades.py`
- [ ] T038 [US3] Implement protected-field rejection for non-`alert_only` updates in `src/tradegumi/manual_trades.py`
- [ ] T039 [US3] Update API error responses for protected-field updates and disallowed creates/deletes in `src/tradegumi/api_server.py`
- [ ] T040 [US3] Update `/manual-trades` form to render read-only trade facts and editable notes/tags outside `alert_only` in `dashboard/src/app/manual-trades/page.tsx`
- [ ] T041 [US3] Hide Add Trade and Delete controls outside `alert_only` in `dashboard/src/app/manual-trades/page.tsx`
- [ ] T042 [US3] Surface protected-field save errors from the proxy/API in `dashboard/src/app/manual-trades/page.tsx`
- [ ] T043 [US3] Ensure dashboard and manual-trades refresh paths refetch after mode switches in `dashboard/src/hooks/useData.ts`

**Checkpoint**: All user stories are independently functional.

---

## Phase 6: User Story 4 - Export Agent-Ready Strategy Data (Priority: P4)

**Goal**: Export current-mode trade history, corrections, annotations, and metadata as structured JSON for LLM and agentic workflows.

**Independent Test**: Export the current-mode dataset and confirm the JSON includes schema version, generated timestamp, scope, summary, field metadata, analysis context, and records with source/override details.

### Tests for User Story 4

- [ ] T044 [P] [US4] Add Python test for Agent Export top-level schema, schema name, chunking metadata, and metadata in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T045 [P] [US4] Add Python test for Agent Export mode isolation and legacy `alert_only` defaulting in `src/tradegumi/tests/test_manual_trades.py`
- [ ] T046 [P] [US4] Add Python test for exported override/source/displayed values and optional linked strategy/signal context in `src/tradegumi/tests/test_manual_trades.py`

### Implementation for User Story 4

- [ ] T047 [US4] Implement current-mode Agent Export generation, including optional linked strategy/signal context when already available, in `src/tradegumi/manual_trades.py`
- [ ] T048 [US4] Add `GET /api/trades/manual/export` handling in `src/tradegumi/api_server.py`
- [ ] T049 [US4] Create Next.js export proxy route in `dashboard/src/app/api/manual-trades/export/route.ts` and verify it is not captured by `dashboard/src/app/api/manual-trades/[[...id]]/route.ts`
- [ ] T050 [US4] Add manual-trades Agent Export client method in `dashboard/src/lib/api.ts`
- [ ] T051 [US4] Add current-mode Agent Export action and error handling in `dashboard/src/app/manual-trades/page.tsx`

**Checkpoint**: Agent-ready exports are available and mode-isolated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validate the full feature and satisfy project quality gates.

- [ ] T052 [P] Update developer-facing notes for mode-isolated manual trade history and Agent Export in `src/tradegumi/manual_trades.py`
- [ ] T053 Run Python tests for manual trade behavior with pytest from `src/tradegumi/tests/test_manual_trades.py`
- [ ] T054 Run available dashboard lint/typecheck validation from `dashboard/package.json`
- [ ] T055 Run the manual validation flow in `specs/003-manual-trade-permissions/quickstart.md`
- [ ] T056 Review changed Python code for required module, public function, public method, and non-trivial helper docstrings in `src/tradegumi/manual_trades.py` and `src/tradegumi/api_server.py`
- [ ] T057 Review changed code for intention-revealing names, simple control flow, and no unexplained magic values across `src/tradegumi/` and `dashboard/src/`
- [ ] T058 Submit PR with DockeGumi as reviewer

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion and blocks all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion and is the MVP.
- **User Story 2 (Phase 4)**: Depends on Foundational completion and benefits from US1 unified read behavior.
- **User Story 3 (Phase 5)**: Depends on Foundational completion and benefits from US1 unified read behavior.
- **User Story 4 (Phase 6)**: Depends on Foundational completion and benefits from US1 unified read behavior.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **US1 Review Complete History**: Can start after Phase 2; no dependency on US2 or US3.
- **US2 Edit Historical Trades in Alert-Only Mode**: Can start after Phase 2; uses shared unified identity/permissions and can be validated after US1 read path exists.
- **US3 Restrict Edits Outside Alert-Only Mode**: Can start after Phase 2; uses shared permission enforcement and can be validated after US1 read path exists.
- **US4 Export Agent-Ready Strategy Data**: Can start after Phase 2; uses shared unified history and can be validated after US1 read path exists.

### Within Each User Story

- Write tests before implementation tasks in the same story.
- Backend storage and permission behavior before API handler updates.
- API contract behavior before dashboard proxy/UI integration.
- UI state and controls after TypeScript types and API clients are updated.

### Parallel Opportunities

- T002, T003, and T004 can run in parallel during setup.
- T012, T013, and T014 can run in parallel for US1 tests.
- T024, T025, and T026 can run in parallel for US2 tests.
- T034, T035, and T036 can run in parallel for US3 tests.
- T044, T045, and T046 can run in parallel for US4 tests.
- US2 and US3 backend tests can be drafted in parallel after Phase 2 if separate workers coordinate on `src/tradegumi/tests/test_manual_trades.py`.

---

## Parallel Example: User Story 1

```bash
Task: "T012 [US1] Add Python test for current-mode filtering and legacy alert_only defaulting in src/tradegumi/tests/test_manual_trades.py"
Task: "T013 [US1] Add Python test for duplicate canonical identity merge in src/tradegumi/tests/test_manual_trades.py"
Task: "T014 [US1] Add Python test for unified summary stats scoped to current mode in src/tradegumi/tests/test_manual_trades.py"
```

## Parallel Example: User Story 2

```bash
Task: "T024 [US2] Add Python test for full-field manual trade updates in alert_only in src/tradegumi/tests/test_manual_trades.py"
Task: "T025 [US2] Add Python test for non-manual trade local overrides and merged display in src/tradegumi/tests/test_manual_trades.py"
Task: "T026 [US2] Add Python test preventing deletion of non-manual historical trades in src/tradegumi/tests/test_manual_trades.py"
```

## Parallel Example: User Story 3

```bash
Task: "T034 [US3] Add Python test for notes/tags-only updates outside alert_only in src/tradegumi/tests/test_manual_trades.py"
Task: "T035 [US3] Add Python test rejecting protected field changes outside alert_only in src/tradegumi/tests/test_manual_trades.py"
Task: "T036 [US3] Add Python test for annotation, override, and trade isolation across modes in src/tradegumi/tests/test_manual_trades.py"
```

## Parallel Example: User Story 4

```bash
Task: "T044 [US4] Add Python test for Agent Export top-level schema, schema name, chunking metadata, and metadata in src/tradegumi/tests/test_manual_trades.py"
Task: "T045 [US4] Add Python test for Agent Export mode isolation and legacy alert_only defaulting in src/tradegumi/tests/test_manual_trades.py"
Task: "T046 [US4] Add Python test for exported override/source/displayed values and optional linked strategy/signal context in src/tradegumi/tests/test_manual_trades.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 setup.
2. Complete Phase 2 foundational schema, identity, permissions, and shared types.
3. Complete Phase 3 to make `/manual-trades` and main dashboard Trade History show the same current-mode history.
4. Stop and validate US1 independently with the quickstart history-visibility checks.

### Incremental Delivery

1. Deliver US1 for unified current-mode history visibility.
2. Deliver US2 for `alert_only` full editing, local overrides, and manual-only deletion.
3. Deliver US3 for non-`alert_only` annotation-only editing and mode isolation enforcement.
4. Deliver US4 for LLM/agent-ready structured export.
5. Run polish validation, quickstart, and PR review steps.

### Parallel Team Strategy

1. One developer completes shared backend storage primitives in `src/tradegumi/manual_trades.py`.
2. One developer updates frontend types/client/proxy files after backend response shape is stable.
3. Story-specific UI work proceeds after foundational types and endpoints are available.

---

## Notes

- [P] tasks touch different files or independent test cases and can run in parallel with coordination.
- `src/tradegumi/tests/test_manual_trades.py` is shared by many test tasks; parallel workers should avoid editing the same section simultaneously.
- Backend permission checks are authoritative even when UI controls are hidden or disabled.
- Do not change signal generation, risk enforcement, or broker-specific execution logic for this feature.
