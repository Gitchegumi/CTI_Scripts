# Research: Fix signal stack IndexError

## Decision: Validate readiness before any positional indicator access

**Rationale**: The recurring diagnostic points to list or dataframe indexing after trend candidates reach the signal stack. A single readiness checkpoint before StochRSI, MACD, Keltner, and recent-candle slicing makes normal warmup/short-data cases deterministic and testable.

**Alternatives considered**:

- Catch `IndexError` around the whole signal stack: rejected because it hides which input was missing and can misclassify malformed data.
- Add guards at every `.iloc` or list index: rejected as harder to audit and easier to regress.

## Decision: Use only the latest fully closed M5 candle and the closed window ending at that candle

**Rationale**: The project requires candle-close-gated signal evaluation. Selecting a closed window before indicator calculation avoids mixing the currently forming candle into indicator rows or last-five candle checks.

**Alternatives considered**:

- Always defer when the latest candle is open: rejected unless existing behavior has no previous closed candle, because a valid previous closed candle can preserve current strategy intent.
- Treat the latest candle as usable if close time is near: rejected because it risks mid-candle signal changes.

## Decision: Report data-not-ready through existing signal-engine criterion and blocker fields

**Rationale**: Existing metrics already classify `signal_engine_data` missing states and dashboard consumers rely on those fields. Adding readiness counts and `DataNotReady` type keeps compatibility while making diagnostics more precise.

**Alternatives considered**:

- Add a separate top-level metrics format: rejected as broader and more likely to break consumers.
- Keep `IndexError` in diagnostic payloads: rejected because normal warmup should not be an exception-classified failure.

## Decision: Verify indicator usability and timestamp alignment after warmup

**Rationale**: Indicator outputs can drop or null early rows, and positional array endings are only safe if the final usable row corresponds to the selected closed candle. Alignment prevents the final candle from being paired with stale or shifted indicator values.

**Alternatives considered**:

- Assume indicator outputs remain one-to-one with candle inputs: rejected because warmup/null removal can break that assumption.
- Require exact dataframe length equality: rejected because valid warmup behavior can produce shorter usable output.

## Decision: Request enough M5 history for the largest signal-stack window

**Rationale**: Readiness validation can only pass if the upstream candle request retains enough history for all indicators and last-five checks. The request count should remain comfortably above the signal stack minimum.

**Alternatives considered**:

- Lower indicator windows or strategy requirements: rejected as out-of-scope strategy tuning.
- Retry with more candles after failure: deferred as unnecessary if the current request already exceeds the documented minimum.
