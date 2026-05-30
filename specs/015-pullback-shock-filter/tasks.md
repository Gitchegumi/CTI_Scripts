# Tasks: Pullback Signal Bridge and Shock Suppression

**Input**: Design documents from `/specs/015-pullback-shock-filter/`
**Prerequisites**: plan.md, spec.md, test-plan.md, rollback-observability.md

**Tests**: Required. Write or update tests before implementation changes.

## Phase 1: Setup

- [ ] T001 Review `specs/015-pullback-shock-filter/spec.md`, `plan.md`, `test-plan.md`, and `rollback-observability.md` after approval.
- [ ] T002 Confirm no unrelated worktree changes will be modified.

## Phase 2: Foundational Tests

- [ ] T003 [P] Add pullback allowed-case tests in `src/tradegumi/tests/test_signal_engine.py` for hammer, bullish engulfing, shooting star, and bearish engulfing pullbacks.
- [ ] T004 [P] Add pullback reject-case tests in `src/tradegumi/tests/test_signal_engine.py` for strong opposite M15, structure break, missing KC break, invalid trigger, generic candlestick, missing Stoch RSI exhaustion, and MACD soft-only behavior.
- [ ] T005 [P] Add continuation regression tests in `src/tradegumi/tests/test_signal_engine.py` verifying strategy `CTI-v1.1-continuation-test`.
- [ ] T006 [P] Add shock threshold and suppression tests in `src/tradegumi/tests/test_volatility_shock.py`.
- [ ] T007 [P] Add strategy metrics tests in `src/tradegumi/tests/test_strategy_metrics.py` for strategy/signal_type preservation, pullback blockers, and threshold hash changes.
- [ ] T008 [P] Add Signal Journal export tests in `src/tradegumi/tests/test_journal.py` for pullback/shock fields and version distinction.

## Phase 3: Configuration and Versioning

- [ ] T009 Add pullback bridge, structure, KC sequence, Stoch RSI, trigger, and shock threshold env vars in `src/tradegumi/config.py`.
- [ ] T010 Update `.env.example` with the new configuration keys and conservative defaults.
- [ ] T011 Update `src/tradegumi/signal_engine.py:get_threshold_version()` to include new pullback and shock behavior thresholds.
- [ ] T012 Add explicit continuation and pullback strategy constants in `src/tradegumi/signal_engine.py`.

## Phase 4: Pullback Path

- [ ] T013 Refactor `src/tradegumi/signal_engine.py:_get_signal()` into shared indicator context plus explicit continuation and pullback evaluators.
- [ ] T014 Implement M15 pullback trend memory bridge in `src/tradegumi/signal_engine.py`.
- [ ] T015 Implement M5 HH/HL and LH/LL pullback structure validation in `src/tradegumi/signal_engine.py`.
- [ ] T016 Implement prior outer-band break plus midline retracement Keltner sequence in `src/tradegumi/signal_engine.py`.
- [ ] T017 Implement approved direction-specific trigger candle validation in `src/tradegumi/signal_engine.py` and `src/tradegumi/indicators.py` if helper normalization is needed.
- [ ] T018 Implement pullback Stoch RSI exhaustion gates and MACD soft score diagnostics in `src/tradegumi/signal_engine.py`.
- [ ] T019 Ensure pullback `Signal` objects emit strategy `CTI-v1.2-pullback` and signal type `pullback`.

## Phase 5: Shock Suppression

- [ ] T020 Update `src/tradegumi/volatility_shock.py` for M5/M15 true-range thresholds and body/range rule.
- [ ] T021 Update `src/tradegumi/volatility_shock.py` suppression-window calculation for M5 and M15 defaults.
- [ ] T022 Update `src/tradegumi/signal_engine.py:check_symbol()` so active shock suppression blocks all continuation and pullback entries for the symbol.
- [ ] T023 Preserve and test no-raw-LR fallback when shock filtering leaves insufficient clean candles.

## Phase 6: Metrics, Journal, and Alerts

- [ ] T024 Update `src/tradegumi/signal_engine.py:SignalDiagnostic` and `to_opportunity()` so emitted strategy and signal type are persisted correctly.
- [ ] T025 Update `src/tradegumi/strategy_metrics.py` with pullback blocker summaries and strategy/signal_type grouping if not already available.
- [ ] T026 Update `src/tradegumi/journal.py` to store/export pullback bridge, trigger, and shock suppression fields carried by signals.
- [ ] T027 Verify `src/tradegumi/alerts.py` and `src/tradegumi/main.py` callback payloads preserve strategy and signal type.

## Phase 7: Validation

- [ ] T028 Run `python -m pytest src/tradegumi/tests/test_signal_engine.py -q`.
- [ ] T029 Run `python -m pytest src/tradegumi/tests/test_volatility_shock.py -q`.
- [ ] T030 Run `python -m pytest src/tradegumi/tests/test_strategy_metrics.py -q`.
- [ ] T031 Run `python -m pytest src/tradegumi/tests/test_journal.py -q`.
- [ ] T032 Review changed Python code for intention-revealing names, simple control flow, and no unexplained magic values.
- [ ] T033 Add or update Python module, class, function, method, and non-trivial helper docstrings.
- [ ] T034 Submit PR with DockeGumi as reviewer.

## Dependencies & Execution Order

- Tests T003-T008 should be written before implementation tasks T009-T027.
- Configuration/versioning T009-T012 should land before path-specific implementation.
- Pullback path T013-T019 and shock path T020-T023 can proceed in parallel after config is ready.
- Metrics/journal tasks T024-T027 depend on signal objects carrying the new fields.
- Validation T028-T034 runs after implementation.
