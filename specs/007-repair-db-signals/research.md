# Research: Repair DB-backed page performance and signal pipeline progression

## Decision: Measure before optimizing DB-backed pages

**Rationale**: The problem statement identifies several candidate slow pages and endpoints, but the slowest path must be proven locally before changing queries. Lightweight timings and query-plan checks reduce the chance of optimizing the wrong path.

**Alternatives considered**:
- Optimize all database access immediately: rejected because it risks broad churn and response-shape changes.
- Add a heavy profiling dependency: rejected because this feature needs low-friction local and Docker-compatible diagnostics.

## Decision: Preserve response shape by default

**Rationale**: Existing dashboard pages and exports depend on current response shapes. Performance fixes should improve boundedness, indexes, batching, and duplicate loads without forcing frontend contract churn unless a pathological unbounded response is the root cause.

**Alternatives considered**:
- Redesign dashboard data contracts: rejected as too broad for a production repair.
- Change defaults silently: rejected unless documented as necessary for performance.

## Decision: Prefer additive SQLite indexes and idempotent schema setup

**Rationale**: The project stores metrics and manual trades in SQLite files. Additive indexes can speed common filters and orderings while keeping existing rows and schema consumers compatible.

**Alternatives considered**:
- Replace SQLite: rejected as outside scope.
- Require manual DB rebuilds: rejected because local and Docker workflows should keep working with existing files.

## Decision: Bound default history reads

**Rationale**: Dashboard pages generally need recent/default views first, not full historical exports. Bounded default reads prevent full-table scans and large serialization costs while explicit exports can remain available.

**Alternatives considered**:
- Fetch all data and filter client-side: rejected because it causes slow page loads and frontend memory pressure.
- Remove export/full-history support: rejected because it changes useful operator workflows.

## Decision: Centralize deterministic candle boundary helpers

**Rationale**: Signal correctness depends on selecting the last fully closed M5 candle and treating before/exact/after close consistently. A helper makes the timing behavior testable and avoids scattered timezone math.

**Alternatives considered**:
- Inline boundary logic at call sites: rejected because it is harder to test and easier to drift.
- Use naive datetimes: rejected because timezone ambiguity is a known suspicious area.

## Decision: Treat insufficient signal data as a diagnostic state, not an exception

**Rationale**: Missing candles or indicator windows are expected market/data conditions. They should produce precise diagnostics such as missing input and required/available counts without raising `IndexError` or preventing other candidates from being evaluated.

**Alternatives considered**:
- Broad try/except around signal evaluation: rejected because it can mask real defects.
- Fill missing candles with synthetic data: rejected because it could alter strategy decisions.

## Decision: Pre-close gate decisions must not permanently block candidates

**Rationale**: A candidate evaluated before close should remain eligible when the candle closes. Recording a permanent blocked decision explains the current zero pass count failure mode and prevents normal signal progression.

**Alternatives considered**:
- Let pre-close decisions remain final: rejected because metrics show gate pass count stuck at zero.
- Force gate pass before close: rejected because it violates signal integrity.

## Decision: Canonical diagnostic key is `signal_engine_data`

**Rationale**: Metrics must aggregate consistently. Any legacy `singal_engine_data` misspelling should be normalized or handled during reads so diagnostics do not fragment.

**Alternatives considered**:
- Keep both names as separate states: rejected because it hides true counts.
- Drop legacy data: rejected because existing metrics may still contain the misspelling.
