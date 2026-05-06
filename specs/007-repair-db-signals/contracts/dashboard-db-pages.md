# Contract: Dashboard DB-backed pages

## Contract Goals

- Preserve current response shapes for DB-backed dashboard routes unless a documented exception is required for performance.
- Bound default reads to the data needed for the visible page.
- Keep export/full-history behavior explicit.
- Provide repeatable measurement hooks or commands for before/after timing.

## Pages and Route Families

| Page | Route family | Contract expectation |
| --- | --- | --- |
| Strategy metrics | `dashboard/src/app/api/strategy-metrics/*` | Summary, opportunities, compare, and export keep existing fields; default reads avoid unnecessary full-history work. |
| Signal journal | `dashboard/src/app/api/journal/*` | Journal reads, export, purge/reset maintain existing behavior while avoiding duplicate or unbounded default fetches. |
| Manual trade journal | `dashboard/src/app/api/manual-trades/*` | History and stats remain compatible; default result sets are bounded or filtered where needed. |
| Dashboard trade history | `dashboard/src/app/api/trades/history/route.ts` | Trade history loads only the rows required for the visible history view by default. |

## Request Expectations

- Existing query parameters continue to work.
- New optional parameters may be added for pagination, limit, date range, or measurement, but existing callers must not break.
- Default behavior should match current visible behavior unless changed and documented.

## Response Expectations

- Existing top-level fields remain present.
- Existing item field names remain present.
- If pagination or bounds metadata is added, it must be additive.
- Errors remain user-safe and must not include secrets or raw credential-bearing data.

## Performance Expectations

- Route handlers should avoid repeated backend/database calls for the same page state.
- Server-side filtering and ordering should replace client-side full-history filtering where it reduces latency.
- Query/index changes should be validated with local timing and correctness checks.
