# Contract: UI Report-Execution & Drilldown Behavior

This is the front-end behavioral contract for the controlled-execution and drilldown experience. It is verified with Vitest + @testing-library/react. It exists because the *when* of fetching (US1) and the drilldown affordances (US2) are the heart of this feature and must be testable independently of styling.

## A. Controlled report execution (`useStrategyMetricsReport` + `ReportControls`)

1. **No fetch on edit** — Changing `start`, then `end`, then any filter issues **zero** network requests. (FR-001, SC-001)
2. **Apply triggers exactly one fetch** — Activating "Apply Filters" issues exactly one `summary` + one `opportunities` request for the current draft. (FR-002)
3. **Range validation** — If `start > end`, Apply is blocked and a visible validation message appears; no fetch occurs. (FR-006)
4. **Loading state** — While a fetch is in flight, a loading indication is shown and the Apply control is disabled (or repeat activations are ignored). (FR-003, FR-004)
5. **In-flight guard** — Calling `run()` again while loading does not start a second concurrent fetch. Rapid double-activation results in a single fetch. (FR-004)
6. **Keep-last-on-success** — Previously rendered report stays visible until the new report resolves (no blank intermediate). (FR-005)
7. **Keep-last-on-error** — If a fetch rejects, `status` becomes `error`, an error indication shows, and the prior `summary`/`opportunities` **remain rendered** (never cleared). (FR-005, SC-009)
8. **Stale-response drop** — If two runs overlap, only the latest run's response is applied (sequence guard). 
9. **Dirty indication** — When draft ≠ applied, the UI marks filters as pending/unapplied. (FR-035)

## B. Executive summary availability (`ExecutiveSummary` + `metrics-availability`)

10. **Real zero rendered** — A metric with value `0` renders as `0`. (FR-009)
11. **Unavailable rendered distinctly** — A metric with value `null`/absent is hidden or marked "unavailable", visually distinct from `0`. (FR-008, FR-009, SC-003)
12. **No hardcoded cards** — Every rendered card is bound to a `summary` field; a card with no backing field does not exist. (FR-007, SC-002)

## C. Criterion drilldown (`CriterionDrilldown`)

13. **Open/close preserves context** — Selecting a criterion opens an overlay/drawer/expandable region; closing returns to the same report and scroll position without refetching the whole report. (FR-011, FR-030, SC-013)
14. **Header stats** — Detail shows name, layer, evaluated/pass/fail counts, pass/fail rate, near-miss contribution, average failure margin, incomplete count. (FR-012)
15. **Failed-first list** — Failed opportunities are listed before others. (FR-013)
16. **Per-failure detail** — Each failed opportunity shows measured value, threshold value, threshold operator, expected-vs-actual pass, and blocker context when available. (FR-014)
17. **Inner filters** — Filtering inside the drilldown by symbol / decision / signal type / near-miss / blocker narrows the list without re-running the whole report. (FR-015)
18. **Expand to opportunity** — A failed opportunity expands to its full evaluated-opportunity detail incl. its complete criteria list. (FR-016)
19. **No-data state** — A criterion with `evaluated_count === 0` shows an explicit "no data" message, not zeros implying evaluation. (FR-017)
20. **Bounded load** — Opening a criterion loads a bounded page of failures (not the whole set), via the `criterion`-scoped endpoint. (FR-023, SC-006)

## D. Opportunity explorer (`OpportunityExplorer`)

21. **Pagination/bounded load** — Explorer loads opportunities in pages; the full evaluated set is never fetched at once. (FR-021, SC-006)
22. **Search/filter narrows** — Search/filter narrows the listed opportunities. (FR-021)
23. **Expand detail** — A row expands to full detail + criteria list. (FR-022)

## E. Accessibility & presentation (cross-cutting; targeted tests + manual checklist)

24. **Keyboard operable** — Filters, Apply, criterion rows, drilldown open/close, and pagination are reachable/operable by keyboard with visible focus. (FR-033, SC-012)
25. **Status not by color alone** — Pass/fail/near-miss/blocker/unavailable each pair color with a label/icon/shape. (FR-026, SC-011)
26. **Reduced motion** — With `prefers-reduced-motion`, non-essential animation is suppressed; all info/interactions remain. (FR-034, SC-015)
27. **Section order** — controls → executive summary → failure diagnosis → criterion drilldown → opportunity explorer. (FR-018)

> Items 24–27 mix automated (focus order, reduced-motion class, section order in DOM, presence of non-color cues) with a short manual a11y/visual pass recorded in quickstart.
