# Implementation Plan: Strategy Metrics Dashboard Usability & Criterion Drilldown

**Branch**: `024-metrics-dashboard-drilldown` | **Date**: 2026-06-16 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/022-metrics-dashboard-drilldown/spec.md`

## Summary

Redesign the existing Strategy Metrics dashboard page (`dashboard/src/app/strategy-metrics/page.tsx`) from an auto-refreshing wall of data into a controlled, polished analysis tool. Three things change: (1) **report execution becomes explicit** — filters and dates are edited as draft state and only fetched on an "Apply Filters" action, with a loading state, in-flight guard, and the last successful report kept on screen; (2) **a criterion drilldown** lets the operator click any criterion to inspect its failed opportunities with measured value / threshold / operator / blocker context; (3) **the page is reorganized** into controls → executive summary → failure diagnosis → drilldown → opportunity explorer, with restrained charts, and given a cohesive, accessible visual treatment using **shadcn/ui** (Radix-based, accessible by default) plus **MagicUI** for subtle motion, both extending the existing Tailwind v4 dark theme.

Research of the backend revealed that most diagnosis data the spec asks for **already exists server-side and is simply not exposed**: `DiagnosticSummary` already computes `pipeline_funnel`, `near_miss_reason_counts`, `signal_type_counts`, and `strategy_counts`, and the opportunities endpoint already supports `limit/offset` pagination plus `symbol/decision/strategy/signal_type/first_blocker/near_miss` filters. The work is therefore **predominantly frontend**, with two small, additive backend changes: an optional `criterion` filter on the opportunities endpoint (to list *all* failures of a criterion, not just where it was the decisive blocker) and a `layer` field on `CriterionSummary`. No grading, signal, risk, or execution logic changes.

## Technical Context

**Language/Version**: TypeScript 5 (frontend), Python 3.11+ (backend)
**Primary Dependencies**: Next.js 16.2.9 (App Router), React 19.2, Tailwind CSS v4 (CSS-first `@theme`, no `tailwind.config.js`); **to add**: shadcn/ui (Radix UI primitives, `class-variance-authority`, `tailwind-merge`, `lucide-react`), MagicUI components, and a charting lib (Recharts via shadcn Chart). Backend: stdlib `http.server`-style handler + `tradegumi.strategy_metrics` + `tradegumi.persistence` (SQLite/Postgres backend).
**Storage**: Existing metrics persistence (`tradegumi.persistence.get_db()`); no schema changes required for the core feature (criterion filter uses an EXISTS/JOIN on the already-persisted criteria rows).
**Testing**: Frontend — Vitest + @testing-library/react (jsdom). Backend — pytest (`src/tradegumi/tests/test_strategy_metrics*.py`).
**Target Platform**: Web (desktop/laptop primary), served by the dashboard container; backend API on `:8199` reached through the Next.js proxy (`/api/strategy-metrics/*` → `proxyMetrics`).
**Project Type**: Web application (Next.js frontend + Python backend), single repo.
**Performance Goals**: Apply-to-render perceived as immediate; one network round per Apply; criterion drilldown and explorer load bounded pages (default 200 opportunities/page, already in place) rather than the full set.
**Constraints**: Must extend (not replace) the existing dark theme/token system (`dashboard/src/app/globals.css` `@theme inline`); WCAG AA contrast and full keyboard operability; honor reduced-motion; existing JSON export behavior unchanged. NOTE: `dashboard/AGENTS.md` warns this Next.js version has breaking changes — consult `node_modules/next/dist/docs/` before writing App Router code.
**Scale/Scope**: Single-operator internal analysis tool; one page redesign plus ~8–12 new presentational components, one hook refactor, one api-client param addition, and two additive backend changes.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| **I. Signal Integrity** | PASS (no impact) | No change to the four-layer signal evaluation. This feature only *reads and presents* already-recorded evaluation diagnostics; no criterion thresholds, layer order, or pass/fail logic are altered. |
| **II. Execution Layer Abstraction** | PASS (no impact) | No execution/broker code touched. No imports of any broker client. |
| **III. Risk-First** | PASS (no impact) | No risk-enforcement code touched. |
| **IV. Observable by Default** | PASS (reinforces) | Feature strengthens observability. Existing JSON state/export remain machine-readable; FR-024 mandates the export contract is unchanged. New backend fields are additive; absent/`null` is used to signal a genuinely unavailable metric (distinct from real `0`), so the dashboard never shows a misleading silent value. |
| **V. Configuration-Driven Operations** | PASS | No magic numbers in signal logic. UI page sizes/animation durations are presentation constants, not strategy parameters. No new env vars needed. |
| **Security & Credential Hygiene** | PASS | New `criterion` query param flows through the existing authenticated proxy (`proxyMetrics`, Authentik/cookie). No secrets added; no credentials in logs or client code. |
| **Code Quality & Documentation** | PASS (enforced in tasks) | New Python (criterion filter, `layer` on summary) gets docstrings stating purpose/params/constraints. New TS components/hooks use intention-revealing names; non-obvious behavior (in-flight guard, draft-vs-applied state, availability semantics) gets tests. |
| **Pull Request Policy** | PENDING → resolved in tasks | `tasks.md` MUST end with a Polish-phase PR task naming the reviewer. Per the established dual-account workflow ([pr-reviewer] memory: DockeGumi authors / Gitchegumi reviews, or per the feature's PR task), the final task will request review from the designated reviewer account; if the author/reviewer pairing is ambiguous at task time, the task instructs the implementer to ask the user before opening the PR. |

**Result**: No violations. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/022-metrics-dashboard-drilldown/
├── plan.md              # This file
├── research.md          # Phase 0 output — library + decoupling + availability decisions
├── data-model.md        # Phase 1 output — entities, contract field additions
├── quickstart.md        # Phase 1 output — setup (shadcn/MagicUI) + verification steps
├── contracts/           # Phase 1 output — API + UI-state contracts
│   ├── api-strategy-metrics.md
│   └── ui-report-state.md
└── checklists/
    └── requirements.md  # Created by /speckit-specify
```

### Source Code (repository root)

```text
dashboard/                                  # Next.js 16 + React 19 + Tailwind v4 frontend
├── components.json                         # NEW — shadcn config (Tailwind v4 / RSC aware)
├── src/
│   ├── app/
│   │   ├── globals.css                      # EXTEND — add shadcn design tokens into existing @theme
│   │   └── strategy-metrics/
│   │       └── page.tsx                     # REWRITE — compose sections; draft-vs-applied filters
│   ├── components/
│   │   ├── ui/                              # NEW — shadcn primitives (button, card, sheet/dialog,
│   │   │                                    #        table, badge, skeleton, tabs, chart, …)
│   │   └── strategy-metrics/                # NEW — feature components:
│   │       ├── ReportControls.tsx           #   filters + Apply (draft state, validation)
│   │       ├── ExecutiveSummary.tsx         #   stat cards w/ availability handling
│   │       ├── FailureDiagnosis.tsx         #   top blockers, pass/fail table, near-miss, funnel
│   │       ├── CriterionDrilldown.tsx       #   sheet/dialog: failed opps, measured vs threshold
│   │       ├── OpportunityExplorer.tsx      #   paginated, searchable, expandable
│   │       └── charts/                       #   PassFailByCriterion, TopBlockers, PipelineFunnel
│   ├── hooks/
│   │   └── useData.ts                       # EDIT — useStrategyMetricsReport: manual-trigger,
│   │                                        #        in-flight guard, keep-last-on-error
│   ├── lib/
│   │   ├── api.ts                            # EDIT — add `criterion` param to opportunities call
│   │   └── metrics-availability.ts          # NEW — real-zero vs unavailable helpers
│   └── types/
│       └── index.ts                         # EDIT — expose pipeline_funnel, near_miss_reason_counts,
│                                            #        signal_type_counts; add layer to criterion summary
└── (vitest tests colocated / under __tests__)

src/tradegumi/
├── strategy_metrics.py                      # EDIT — add `criterion` filter to get_opportunities;
│                                            #        add `layer` to CriterionSummary
├── api_server.py                            # EDIT — read & pass `criterion` query param
└── tests/
    ├── test_strategy_metrics.py             # EDIT/ADD — criterion filter + layer coverage
    └── test_strategy_metrics_backend.py     # EDIT/ADD — endpoint param coverage
```

**Structure Decision**: Web-application layout, reusing the existing `dashboard/` (frontend) and `src/tradegumi/` (backend) trees. The feature is scoped to the strategy-metrics page and its data path. New presentational components live under `dashboard/src/components/strategy-metrics/`; shadcn primitives land in the conventional `dashboard/src/components/ui/`. Backend edits are confined to `strategy_metrics.py` and the strategy-metrics request handlers in `api_server.py`.

## Complexity Tracking

> No constitution violations. Table intentionally omitted.
