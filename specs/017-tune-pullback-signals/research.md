# Research: High-Value KC Band Pullbacks

## Decision 1: High-Value Pullback Sequence Detection

**Decision**: Modify `_pullback_keltner_sequence` to accept `macd_current` as an optional parameter. When provided, evaluate if the setup qualifies as a high-value pullback.

**Rationale**:
By evaluating this logic inside `_pullback_keltner_sequence`, we can reuse the existing `prior_break` check (which verifies that price broke outside the outer Keltner Channel band) and the `midline` calculation. This keeps the logic encapsulated within the Keltner sequence evaluation function.

**Alternatives Considered**:
- *Evaluating high-value pullback conditions directly in `_get_signal`*: Rejected because it duplicates KC logic (midline, prior break, upper/lower band cols) outside of `_pullback_keltner_sequence` and makes the core signal evaluation method less readable.

---

## Decision 2: Defining "Price Has Not Reached Midline"

**Decision**: Express the "price has not reached midline" condition as `trigger_close < midline` for Downtrends and `trigger_close > midline` for Uptrends.

**Rationale**:
A downtrend pullback consists of price pulling back upwards from below the lower KC band. If price crosses above the midline, it has reached and crossed it. Therefore, remaining below the midline (while having broken the lower KC band previously) is the exact mathematical definition of not fully returning to the midline. This single condition elegantly covers both cases where price remains entirely outside the lower band, and where it enters the band but stays below the midline.

---

## Decision 3: Classification and Signal Type

**Decision**: Classify these signals as `signal_type="high_value_pullback"` when the high-value sequence conditions are met and the standard sequence check fails.

**Rationale**:
This provides clear observability of the strategy performance in JSON logs, metrics outputs, and Discord notifications, allowing the user to distinguish between standard midline pullbacks and aggressive high-value pullbacks.
Using a separate value for `signal_type` also ensures that downstream components (like database loggers and Discord formatters) can correctly display and track these signals.
