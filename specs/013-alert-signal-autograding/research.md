# Research: Alert Signal Auto-Grading

## Shared Live Price Observations

**Decision**: Introduce a provider-neutral `PriceObservation` model and rolling in-memory service fed by the existing one-second `client.get_pricing(scan_symbols)` loop in `main.py`.

**Rationale**: The main loop already fetches bid/ask prices for all scanned watchlist symbols every second. Publishing those ticks into a shared service lets the dashboard and evaluator consume the same observations and avoids a second polling loop.

**Alternatives considered**:

- Add evaluator-specific Oanda polling: rejected because it duplicates market-data traffic and violates the feature constraints.
- Use dashboard browser polling as the source of truth: rejected because backend grading should not depend on a browser session being open.
- Persist all observations: rejected for v1 because in-memory rolling history is enough and avoids retention growth.

## Dashboard Price Reuse

**Decision**: Treat the backend price ticker as the shared dashboard price path. Add a lightweight read API or adapt existing position/watchlist responses only where practical, but keep the evaluator subscribed to backend observations rather than dashboard client state.

**Rationale**: The dashboard currently polls API/data endpoints, while backend `main.py` already performs the one-second pricing fetch. Sharing at the backend observation layer gives both consumers the same market facts without coupling UI rendering to grading.

**Alternatives considered**:

- Move all dashboard pricing into `/api/positions`: rejected as insufficient because alert-only signals may exist without open broker positions.
- Push grading from Next.js routes: rejected because it would depend on dashboard traffic and mix UI proxy concerns with signal state mutation.

## Bid/Ask and Midpoint Grading

**Decision**: Grade BUY signals using bid for both target and stop touches; grade SELL signals using ask for both target and stop touches. Permit midpoint-only grading only when bid/ask are absent and the recorded outcome source explicitly identifies midpoint grading.

**Rationale**: Bid/ask rules match the requested execution-quality semantics. Midpoint results can be useful for historical or fallback data but must not be presented as true executable bid/ask grading.

**Alternatives considered**:

- Always use midpoint: rejected because it misstates executable outcomes.
- Refuse midpoint-only data entirely: rejected because historical/manual backfill may only provide midpoint and can still be useful if clearly labeled.

## Rolling History Retention

**Decision**: Keep bounded in-memory history per symbol, with configurable or conservative defaults based on count and/or age. Do not persist observations in v1 unless implementation discovers an existing bounded pattern.

**Rationale**: Live grading uses each new ordered observation, and unresolved signal evaluation does not require an unbounded tick database. Bounded history supports excursion metrics and future fallback without storage growth.

**Alternatives considered**:

- Store every tick in JSONL or SQLite: rejected because it increases retention and cleanup complexity.
- Keep only latest tick: rejected because excursion metrics and same-cycle ambiguity handling benefit from short history.

## Journal Outcome Fields

**Decision**: Add additive fields to existing Signal Journal JSONL entries and export headers, defaulting missing legacy values safely. Keep existing `grade`/`trade_grade` behavior compatible while adding richer status/outcome/source fields for auto-grading.

**Rationale**: The journal is already the owner of signal review state, manual grading, reset, purge, export, and prime fields. Additive fields preserve compatibility and simplify dashboard/API updates.

**Alternatives considered**:

- Create a separate outcomes database: rejected because it fragments signal review state and complicates export/dashboard behavior.
- Replace existing grade fields: rejected because current manual grading and dashboard filters depend on them.

## Manual Override Preservation

**Decision**: Manual grades and manually locked records are never overwritten by the evaluator. Reset-to-pending clears auto outcome fields and may make the entry eligible again unless manual lock remains.

**Rationale**: Analysts need an escape hatch and audit trail. Existing grade/reset flows already define the right ownership boundary for human edits.

**Alternatives considered**:

- Let latest automated result overwrite manual grades: rejected because it destroys analyst intent.
- Permanently exclude reset entries: rejected because reset is explicitly intended to reopen eligibility unless locked.

## Prime Suppression Integration

**Decision**: Make prime-suppression checks consult the journal outcome/status state before blocking same-symbol follow-on signals. If the prime has auto-closed by target or stop, deactivate old prime state and allow the new signal; if unresolved, keep current blocking/invalidation behavior and increment invalidated-by-prime evidence.

**Rationale**: The active-prime rule must agree with the evaluator’s state or it can leave resolved opportunities blocked. Existing prime fields in `journal.py` remain the source of prime activity.

**Alternatives considered**:

- Maintain a separate prime registry: rejected because persisted journal fields already recover active prime state after restart.
- Ignore auto outcomes in prime suppression: rejected because it would block valid follow-on signals after TP/SL.

## Streaming Readiness

**Decision**: Implement streaming as a future publisher of the same `PriceObservation` interface, not as part of this feature.

**Rationale**: The current supported polling behavior can ship first. Designing the evaluator around observations rather than Oanda calls keeps the future streaming replacement small.

**Alternatives considered**:

- Implement Oanda streaming now: rejected because it expands scope and is not necessary for first delivery.
- Build evaluator directly on `OandaClient`: rejected because it violates execution abstraction and future streaming goals.
