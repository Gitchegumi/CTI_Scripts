# Research: Prime Signal Suppression

## Decision: Persist Prime State on Journal Entries

**Decision**: Store prime activity and suppression evidence directly on Signal Journal entries with additive fields.

**Rationale**: The journal is the source of truth for emitted signal evidence, already survives restart, and is guarded by a module-level lock for read/write mutations. Keeping prime state on entries avoids a separate registry that could drift from manual grading, reset, purge, or export behavior.

**Alternatives considered**:

- In-memory per-symbol map: rejected because restart recovery is required.
- Separate prime state file/table: rejected because it adds synchronization risk with existing journal lifecycle operations.

## Decision: Active Prime Means Unresolved, Prime-Active, and Same Symbol

**Decision**: The active prime lookup should scan persisted entries for the newest same-symbol entry whose `prime_active` is true and whose normalized journal outcome remains unresolved.

**Rationale**: This matches the user requirement that primes are symbol-specific and remain active only until inferred TP/SL, manual resolution, stale/expired resolution, invalidation, reset/purge semantics, or other existing resolution flows deactivate them.

**Alternatives considered**:

- Same symbol and same direction only: rejected because opposite-direction follow-on signals must also be suppressed.
- Existing setup group identity: rejected because current setup grouping includes direction and time-window semantics, while prime suppression is symbol-only and outcome-state-based.

## Decision: Infer Outcome from Candle High/Low Between Prime and New Signal

**Decision**: Evaluate candle highs/lows between the prime signal timestamp and the follow-on signal timestamp using the prime's original symbol, direction, entry, stop, target, and timestamp.

**Rationale**: The required behavior is outcome-state-based, not cooldown-based. Candle high/low checks are deterministic enough to determine whether the prior setup was theoretically resolved before the later signal.

**Alternatives considered**:

- Compare only latest price: rejected because it misses intervening target/stop touches.
- Use broker trade history: rejected because alert-only and unexecuted journal signals still need theoretical outcome inference.

## Decision: Conservative Stop on Ambiguous Same-Candle Touch

**Decision**: If target and stop are both touched in the same candle and order cannot be known, close the prime as inferred stop and mark the close ambiguous.

**Rationale**: This matches the explicit requirement and keeps analysis conservative.

**Alternatives considered**:

- Prefer target: rejected as optimistic and contrary to requested behavior.
- Leave prime unresolved: rejected because it would keep suppressing even though both bounds were touched.

## Decision: Use Existing Journal Lock for Race Protection

**Decision**: Run active-prime lookup, inference result application, suppression update, old-prime close update, and new-prime insertion while holding the existing journal lock.

**Rationale**: Current append, grade, reset, purge, and read paths already use `_lock` around JSONL access. Reusing that lock prevents rapid same-symbol appends from both becoming prime and avoids a wider concurrency model change.

**Alternatives considered**:

- No lock beyond append write: rejected because lookup and write must be atomic.
- Per-symbol locks: rejected as unnecessary complexity for a local single-process journal file.

## Decision: Store Total Suppressed Count and Latest Timestamp First

**Decision**: Implement required total suppression fields and latest suppressed timestamp; include same/opposite direction counters when they fit cleanly in the entry update path.

**Rationale**: The feature requires total count and auditability. Directional counts are valuable and low-risk if stored as integers, but full suppressed signal payload storage may bloat CSV and dashboard views.

**Alternatives considered**:

- Store full suppressed signal snapshots for every suppression: deferred unless JSON-only metadata can stay compact.
- Omit directional counts entirely: acceptable fallback but less useful for chop analysis.

## Decision: Metrics Are Derived from Journal Prime Fields

**Decision**: Prime suppression metrics should aggregate from journal prime fields and be exposed alongside existing metrics/export paths without changing strategy opportunity counting semantics.

**Rationale**: Suppressed signals intentionally do not create opportunities. Deriving counts from journal evidence preserves the distinction between emitted signals, actionable trade opportunities, and suppressed noise.

**Alternatives considered**:

- Record suppressed signals as metrics opportunities with `usable_for_strategy_stats=false`: rejected for v1 because suppressed signals should not create duplicate rows or require grading.

## Decision: Legacy Records Remain Non-Blocking Unless Explicitly Prime-Active

**Decision**: Missing prime fields on legacy records should not make those records active primes.

**Rationale**: Legacy records lack enough persisted state to prove active unresolved prime status and must remain readable without surprise suppression after upgrade.

**Alternatives considered**:

- Treat every unresolved pending legacy signal as active prime: rejected because it could unexpectedly suppress future signals after deployment.
