# Research: Continuation Management Events

## Active Trade Identity

**Decision**: Treat the active pullback-originated journal record as the managed trade identity and assign/retain a stable `trade_id` for lifecycle linkage.

**Rationale**: Feature 012 already made journal records the durable prime state for unresolved signals. Reusing that state keeps lifecycle evidence visible, exportable, and restart-safe without adding a parallel registry.

**Alternatives considered**:

- Separate lifecycle database only: stronger relational modeling, but creates a second source of truth and complicates journal export compatibility.
- Signal ID only as trade ID: simple, but a dedicated `trade_id` leaves room for future aggregation or migration while still linking to `entry_signal_id`.

## Continuation Routing

**Decision**: Preserve continuation detection in `signal_engine.py`, but route emitted continuation evidence through lifecycle management before it becomes a journaled trade entry.

**Rationale**: The issue explicitly says not to remove continuation logic. Routing after signal evaluation keeps signal integrity intact while preventing continuation from dominating entry rows.

**Alternatives considered**:

- Disable continuation emission: removes useful management evidence and violates the issue guidance.
- Lower continuation confidence thresholds: does not address the lifecycle mismatch.

## Baseline Management Rules

**Decision**: Use configurable R-based defaults: allow break-even movement after sufficient favorable movement, allow profit-protect tightening only when it improves risk, and allow TP extension only when continuation evidence remains strong and extension caps have not been reached.

**Rationale**: R-based rules align with the spec's desired 1R/1.5R examples and the existing stop-loss distance semantics. Configurable defaults satisfy constitution requirements and make forward testing adjustable.

**Alternatives considered**:

- ATR-only progress thresholds: useful later, but R-based accounting maps directly to outcome metrics and risk.
- Always extend TP on continuation: can create runaway targets and violates the requested cap.

## Profit-Protected Outcome Accounting

**Decision**: Classify final outcomes from current managed SL/TP relative to entry and direction, not from the exit mechanism alone.

**Rationale**: A stop-loss hit beyond entry is economically a win. Outcome labels must reflect captured profit, break-even, or loss so metrics match trader reality.

**Alternatives considered**:

- Keep all SL hits as losses: preserves legacy labels but directly conflicts with the feature.
- Store profit-protected exits as manual wins only: hides automated lifecycle behavior and weakens metrics.

## Storage Shape

**Decision**: Add lifecycle fields to journal entries for entry state and compact linked management-event evidence, and add additive metrics storage fields or tables only where summary/export performance requires them.

**Rationale**: JSONL is already the permanent Signal Journal surface and supports legacy compatibility through default normalization. Strategy metrics SQLite can aggregate lifecycle counters for dashboard export without making the journal unreadable.

**Alternatives considered**:

- Store every management event as a full independent actionable row: easy export, but reintroduces duplicate-entry noise.
- Store only metrics counters: loses auditability of old/new SL/TP changes and rejection reasons.

## Opposite-Direction Continuation Handling

**Decision**: Record opposite-direction continuation during an active trade as warning or exit-management evidence and do not automatically open a new trade while the active trade remains unresolved.

**Rationale**: The spec calls this out directly, and it prevents churn while preserving useful diagnostic evidence.

**Alternatives considered**:

- Reverse immediately on opposite continuation: changes trade model and risk behavior beyond scope.
- Drop opposite continuations silently: violates observability and loses warning evidence.

## Dashboard and Export Exposure

**Decision**: Expose lifecycle role, management-event acceptance, old/new SL/TP values, managed outcome category, and lifecycle counters in existing journal export, strategy metrics export, journal dashboard, and strategy metrics dashboard.

**Rationale**: The current problem was discovered through Discord/journal/metrics exports. The fix must be visible in the same operator workflow.

**Alternatives considered**:

- Backend-only lifecycle: would fix accounting but leave the operator unable to verify behavior.
- New separate page only: adds navigation cost and hides lifecycle context from existing journal review.

## Legacy Compatibility

**Decision**: Missing lifecycle fields default to non-managed legacy behavior. Existing continuation rows remain readable but do not become active pullback-originated trades retroactively unless an explicit migration/replay tool is later requested.

**Rationale**: Exported historical data must remain usable, and retroactive reinterpretation could change metrics unexpectedly.

**Alternatives considered**:

- Migrate all historical continuations into management events: impossible to do reliably without active pullback state.
- Reject legacy rows in exports: breaks current analysis workflows.
