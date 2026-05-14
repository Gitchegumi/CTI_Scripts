# Implementation Plan: Signal Journal Export

**Branch**: `010-signal-journal-export` | **Date**: 2026-05-14 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/010-signal-journal-export/spec.md`

## Summary

Repair the Signal Journal CSV export so a successful export request produces a real browser download, then add scoped export selection by date/time range and existing visible journal grade filter. The implementation will keep strategy and signal generation untouched while extending the journal export helper, backend response metadata, Next.js proxy header forwarding, and dashboard export controls/error handling.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16.2.4 / React 19.2.4 dashboard under `dashboard/`  
**Primary Dependencies**: Python stdlib `http.server`, `csv`, `json`, `datetime`; dashboard `fetch`, `NextResponse`, React hooks; pytest; Next ESLint/TypeScript checks  
**Storage**: Existing append-only Signal Journal JSONL at `src/tradegumi/data/signal_journal.jsonl`; no mutation or schema migration planned  
**Testing**: pytest in `src/tradegumi/tests/`; dashboard lint/build checks via `npm run lint` and `npm run build`  
**Target Platform**: Local operator TradeGumi API on port 8199 with Docker/Next dashboard proxy  
**Project Type**: Python trading backend plus Next.js dashboard  
**Performance Goals**: Export 1,000 journal records in under 2 seconds for one operator; empty-result feedback visible within 2 seconds  
**Constraints**: Do not change strategy thresholds, signal generation, risk logic, purge behavior, or existing signal data; preserve journal filtering, grading, pending reset, and pagination/display behavior  
**Scale/Scope**: Signal Journal CSV export helper, `/api/journal/export` backend route, dashboard `/api/journal/export` proxy route, Signal Journal page export controls, tests, and docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Export reads journal evidence only; it does not generate, unblock, or mutate signals. |
| II. Execution Layer Abstraction | PASS | No broker or execution-client code is touched. |
| III. Risk-First | PASS | No risk sizing, drawdown, position, or order-placement behavior changes. |
| IV. Observable by Default | PASS | User-facing empty/error states are part of the export flow; existing journal records remain machine-readable. |
| V. Configuration-Driven Operations | PASS | No strategy or operational configuration constants are retuned. |
| Security & Credential Hygiene | PASS | Existing journal auth remains in place; no token or secret is exported or logged. |
| Code Quality & Documentation | PASS | Python helper changes require clear names, docstrings, and focused tests. |
| Pull Request Policy | PASS | `tasks.md` will include the required DockeGumi reviewer PR task. |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/010-signal-journal-export/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- signal-journal-export-api.md
|   `-- signal-journal-export-ui.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- journal.py                  # update CSV scope/filtering, filename metadata support, empty-result signaling
|-- api_server.py               # update /api/journal/export headers and query handling
`-- tests/
    `-- test_journal.py         # update export field, range, empty, and deterministic filtering tests

dashboard/src/app/
|-- journal/page.tsx            # add export range controls and response/empty handling
`-- api/journal/export/route.ts # forward file response headers and query params

docs/
`-- signal-journal.md           # document range-scoped CSV export behavior
```

**Structure Decision**: Keep the change inside the existing Signal Journal JSONL helper, lightweight Python API route, Next dashboard proxy, and page component. Do not introduce a new export service, database migration, queue, or signal-data maintenance action.

## Phase 0: Research

See [research.md](research.md) for response header, range-filter, empty-result, and CSV column decisions.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for export selection, journal record timestamp selection, CSV fields, and empty-result behavior.

See [contracts/signal-journal-export-api.md](contracts/signal-journal-export-api.md) and [contracts/signal-journal-export-ui.md](contracts/signal-journal-export-ui.md) for backend/proxy and dashboard contracts.

See [quickstart.md](quickstart.md) for validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design only reads and serializes existing journal records. |
| II. Execution Layer Abstraction | PASS | Broker abstraction remains untouched. |
| III. Risk-First | PASS | Risk and order placement remain outside scope. |
| IV. Observable by Default | PASS | Empty export and failure states are explicitly visible to the operator. |
| V. Configuration-Driven Operations | PASS | No strategy/runtime config semantics change. |
| Security & Credential Hygiene | PASS | Existing auth is preserved through proxy and backend; no secret fields added to CSV. |
| Code Quality & Documentation | PASS | New/modified Python helpers will carry docstrings and focused pytest coverage. |
| Pull Request Policy | PASS | Task plan includes final PR submission with DockeGumi as reviewer. |

No post-design gate violations.
