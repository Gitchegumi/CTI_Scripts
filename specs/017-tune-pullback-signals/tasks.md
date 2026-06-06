# Tasks: High-Value KC Band Pullbacks

**Input**: Design documents from `/specs/017-tune-pullback-signals/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md

**Tests**: Tests are requested in the specification (FR-023) and will be implemented first (TDD approach).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single project structure: `src/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify dependencies and test environment readiness

- [ ] T001 Verify virtual environment and dev dependencies (pytest) in src/pyproject.toml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ensure the existing test suite compiles and runs before changes

- [ ] T002 Verify existing test suite runs successfully via pytest

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Partial Retracement Outside Midline (Priority: P1) 🎯 MVP

**Goal**: Detect pullback when price has broken outside outer band, triggers valid trigger candle, retraces inside outer band but does not reach midline, with MACD histogram aligned.

**Independent Test**: Replay scenario where price breaks below lower band, retraces up to cross the band but turns back down before midline, with negative MACD histogram and bearish trigger. Verifies SELL `high_value_pullback` is emitted.

### Tests for User Story 1
- [ ] T003 [P] [US1] Write test cases in src/tradegumi/tests/test_signal_engine.py verifying BUY and SELL high_value_pullback signals for partial retracements inside outer band but before midline
- [ ] T004 [US1] Verify T003 tests fail as expected without implementation in src/tradegumi/tests/test_signal_engine.py

### Implementation for User Story 1
- [ ] T005 [US1] Update _pullback_keltner_sequence to accept macd_current parameter and evaluate high-value pullback conditions for partial retracements in src/tradegumi/signal_engine.py
- [ ] T006 [US1] Update core pullback signal evaluation in _get_signal to pass macd_current to _pullback_keltner_sequence and classify signal_type as "high_value_pullback" in src/tradegumi/signal_engine.py
- [ ] T007 [US1] Verify T003 tests pass after implementation in src/tradegumi/tests/test_signal_engine.py

**Checkpoint**: At this point, User Story 1 is fully functional and testable independently.

---

## Phase 4: User Story 2 - Rejection Remaining Completely Outside Outer KC Band (Priority: P1)

**Goal**: Recognize extremely strong continuation pullbacks when price breaks outside the outer band, triggers trigger candle, but does not return inside the outer KC band, with MACD histogram aligned.

**Independent Test**: Replay trend period where price breaks below lower KC band, forms trigger candle whose high remains below lower KC band, negative MACD histogram, verify SELL `high_value_pullback` is emitted.

### Tests for User Story 2
- [ ] T008 [P] [US2] Write test cases in src/tradegumi/tests/test_signal_engine.py verifying BUY and SELL high_value_pullback signals where price remains completely outside the outer KC band
- [ ] T009 [US2] Verify T008 tests fail as expected without implementation in src/tradegumi/tests/test_signal_engine.py

### Implementation for User Story 2
- [ ] T010 [US2] Extend _pullback_keltner_sequence high-value sequence evaluation logic to cover the case where price remains outside the outer band in src/tradegumi/signal_engine.py
- [ ] T011 [US2] Verify T008 tests pass successfully in src/tradegumi/tests/test_signal_engine.py

**Checkpoint**: At this point, User Stories 1 and 2 work independently.

---

## Phase 5: User Story 3 - MACD Momentum Verification Gate (Priority: P1)

**Goal**: Reject shallow, aggressive pullbacks if momentum shows signs of fading (MACD histogram >= 0 for Downtrend/shorts, <= 0 for Uptrend/longs).

**Independent Test**: Replay trend period where price remains outside outer band, but MACD histogram is >= 0 for a short. Verify no signal is emitted.

### Tests for User Story 3
- [ ] T012 [P] [US3] Write test cases in src/tradegumi/tests/test_signal_engine.py verifying that high-value pullback setups are rejected when the MACD histogram is not aligned with the trend direction
- [ ] T013 [US3] Verify T012 tests fail as expected without implementation in src/tradegumi/tests/test_signal_engine.py

### Implementation for User Story 3
- [ ] T014 [US3] Ensure MACD histogram check is strictly enforced for the high_value_pullback path in src/tradegumi/signal_engine.py
- [ ] T015 [US3] Verify T012 tests pass successfully in src/tradegumi/tests/test_signal_engine.py

**Checkpoint**: Momentum verification logic is fully functional and testable.

---

## Phase 6: User Story 4 - Existing Pullback Behavior Remains Intact (Priority: P2)

**Goal**: Deep-retracement pullbacks to the midline continue to trigger standard pullback signals.

**Independent Test**: Replay standard midline pullback and verify it is classified as `signal_type="pullback"`.

### Tests and Implementation for User Story 4
- [ ] T016 [P] [US4] Write regression tests in src/tradegumi/tests/test_signal_engine.py ensuring standard midline pullbacks are still classified with signal_type="pullback"
- [ ] T017 [US4] Verify all regression tests pass successfully in src/tradegumi/tests/test_signal_engine.py

**Checkpoint**: All user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Code cleanup, documentation, and PR submission

- [ ] T018 Review changed code in src/tradegumi/signal_engine.py for intention-revealing names, simple control flow, and no unexplained magic values
- [ ] T019 Add or update Python docstrings for modified helper functions in src/tradegumi/signal_engine.py
- [ ] T020 Run the entire test suite via pytest to verify no regression
- [ ] T021 Submit PR with the user/context-identified reviewer, or ask the user to identify the reviewer before opening the PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1).
- **User Stories (Phase 3+)**: All depend on Foundational (Phase 2).
  - Can be developed sequentially in priority order: US1 -> US2 -> US3 -> US4.
- **Polish (Phase 7)**: Depends on all desired user stories being complete.

### Within Each User Story
- Tests written and verified failing before implementation.
- Core logic implemented.
- Tests verified passing.

### Parallel Opportunities
- Test writing tasks marked [P] can be written in parallel.
- Polish phase tasks can be executed in sequence.
