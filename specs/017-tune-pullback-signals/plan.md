# Implementation Plan: High-Value KC Band Pullbacks

**Branch**: `017-tune-pullback-signals` | **Date**: 2026-06-05 | **Spec**: [spec.md](file:///e:/GitHub/CTI_Scripts/specs/017-tune-pullback-signals/spec.md)
**Input**: Feature specification from `/specs/017-tune-pullback-signals/spec.md`

## Summary

Implement the high-value Keltner Channel (KC) band pullback strategy. This requires updating the `_pullback_keltner_sequence` method and the core pullback evaluation logic in `src/tradegumi/signal_engine.py` to identify shallow pullbacks that begin outside the KC outer band, satisfy Stoch RSI/structure/trigger candle checks, but do not reach the midline (or even return inside the outer band), provided trend momentum (MACD histogram) is intact. These signals will be classified with `signal_type="high_value_pullback"`.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: pandas, numpy, ta-lib, pytest  
**Storage**: SQLite (via `strategy_metrics.py`), local state files (`signals.json`, `loop_state.json`)  
**Testing**: pytest  
**Target Platform**: Windows / Linux  
**Project Type**: Algorithmic Trading Signal Engine  
**Performance Goals**: Engine evaluation cycles under 200ms per symbol  
**Constraints**: Zero hardcoded credentials, broker-agnostic, maintains all existing L2 metrics and scoreboards.  
**Scale/Scope**: Tier 1 and Tier 2 watchlist symbols  

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Signal Integrity**: PASS. The new `high_value_pullback` classification uses standard Stoch RSI, trigger candle shape, and structure gates. To compensate for not reaching the midline, it adds a mandatory MACD histogram direction gate to confirm trend momentum is intact.
- **Execution Layer Abstraction**: PASS. No execution code is touched. Signals remain broker-agnostic.
- **Risk-First**: PASS. Standard risk checks and position sizing rules are non-bypassable and automatically apply to the new signal type.
- **Observable by Default**: PASS. All evaluations, whether passing or blocked, will be written to JSON state files, logged, and output to Discord with `signal_type="high_value_pullback"`.
- **Configuration-Driven Operations**: PASS. Utilizes existing configurable parameters (lookbacks, thresholds).
- **Security & Credential Hygiene**: PASS. No credentials or secrets are used or committed.
- **Code Quality & Documentation**: PASS. All code changes will use intention-revealing names and include required docstrings.
- **Pull Request Policy**: PASS. Reviewer will be requested as identified by the user or project context (e.g. Gitchegumi) before merge.

## Project Structure

### Documentation (this feature)

```text
specs/017-tune-pullback-signals/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
src/
└── tradegumi/
    ├── signal_engine.py # Main signal logic
    └── tests/
        └── test_signal_engine.py # Testing suite
```

**Structure Decision**: Single project layout under `src/tradegumi`.

## Complexity Tracking

*No violations.*
