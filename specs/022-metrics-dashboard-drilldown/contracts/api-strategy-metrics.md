# Contract: Strategy Metrics API (additive changes)

These are the **only** backend/API contract changes. Everything else (summary, compare, export shapes; auth proxy behavior) is **unchanged**. FR-024 requires the existing JSON export contract stay byte-compatible for an equivalent report.

All endpoints are reached by the dashboard through the authenticated proxy (`/api/strategy-metrics/*` → `proxyMetrics` → backend `:8199`). Auth is unchanged (Authentik forwarded headers or `tg_journal_auth` cookie / `X-API-Key`).

## 1. `GET /api/strategy-metrics/opportunities` — add `criterion` filter

**Change**: add one optional query parameter. No change to response item shape.

### Query parameters
| Param | Type | Required | Notes |
|-------|------|----------|-------|
| `start` | date `YYYY-MM-DD` | yes | unchanged |
| `end` | date `YYYY-MM-DD` | yes | unchanged |
| `symbol` | string | no | unchanged |
| `decision` | `emitted\|rejected\|skipped\|indeterminate` | no | unchanged |
| `strategy` | string | no | unchanged |
| `signal_type` | string | no | unchanged |
| `first_blocker` | string | no | unchanged — *decisive* blocker only |
| `near_miss` | `true\|false` | no | unchanged |
| **`criterion`** | string | **no (NEW)** | returns opportunities where the named criterion was evaluated with `passed = false` (failed), regardless of whether it was the decisive blocker. Combinable with all other filters. |
| `limit` | int | no | unchanged (default 100; UI uses 200) |
| `offset` | int | no | unchanged |

### Semantics
- When `criterion` is provided, results are restricted to opportunities containing a `CriterionResult` with `criterion_name == criterion` and `passed == false`, implemented via `EXISTS`/JOIN on the already-persisted criteria rows (no full-set scan, no schema change). Results SHOULD order failed-first to match the drilldown (FR-013).
- When `criterion` is omitted, behavior is identical to today.
- Unknown `criterion` value ⇒ empty result set (not an error).

### Response
Unchanged: `StrategyMetricOpportunity[]` (each with full `criteria[]` carrying `measured_value`, `threshold_value`, `threshold_operator`, `passed`, `margin`, `data_quality`).

### Backend touch points
- `tradegumi.strategy_metrics._opportunity_filter_clauses(...)` / `get_opportunities(...)` / `_get_opportunities_db(...)` — thread `criterion` through.
- `tradegumi.api_server` opportunities handler (~line 346) — read `criterion = self._get_query_param("criterion")`, pass through.

## 2. `GET /api/strategy-metrics/summary` — additive response fields

**Change**: response gains fields the backend **already computes** but did not previously serialize into the TS contract, plus `layer` on each criterion summary. `DiagnosticSummary.to_dict()` already emits most of these via `asdict`; verify and expose. No new query params.

### Added/clarified response fields
| Field | Type | Status |
|-------|------|--------|
| `criterion_summaries[].layer` | string | **NEW** (R5) — add to `CriterionSummary` dataclass + populate |
| `pipeline_funnel` | `Record<string, number>` | EXPOSE (already computed) |
| `near_miss_reason_counts` | `Record<string, number>` | EXPOSE (already computed) |
| `signal_type_counts` | `Record<string, number>` | EXPOSE (already computed) |
| `strategy_counts` | `Record<string, number>` | EXPOSE (already computed) |

### Availability contract (R6)
- A summary metric that is genuinely **not computable** for the requested range MUST be serialized as `null` (or omitted), which the client renders as *unavailable*.
- A metric whose true value is `0` MUST be serialized as `0` and rendered as a real zero.
- The client MUST NOT invent or hardcode any displayed metric; every card maps to a field here (FR-007/FR-008/FR-009).

## 3. Unchanged contracts (regression-guarded)
- `GET /api/strategy-metrics/compare` — no change.
- `GET /api/strategy-metrics/export` (with/without `include_opportunities`) — **no change**; FR-024 / SC-007 require identical output for an equivalent report. Add/keep a test asserting export parity.

## Contract tests (backend, pytest)
1. `criterion` filter returns only opportunities where that criterion failed; failed-first ordering; respects `limit/offset`; combinable with `symbol`/`near_miss`.
2. Omitting `criterion` reproduces current results exactly.
3. Unknown `criterion` ⇒ `[]`, HTTP 200.
4. `criterion_summaries[].layer` present and correct for known criteria.
5. `summary` payload includes `pipeline_funnel`, `near_miss_reason_counts`, `signal_type_counts`, `strategy_counts`.
6. `export` output unchanged vs golden for a fixed range (parity test).
