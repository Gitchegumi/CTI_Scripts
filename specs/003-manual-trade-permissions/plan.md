# Implementation Plan: Manual Trade Permissions

**Branch**: `003-manual-trade-permissions` | **Date**: 2026-05-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/003-manual-trade-permissions/spec.md`

## Summary

Unify the manual trades interface with the main dashboard Trade History so both views show the same current-mode historical trade set, while enforcing mode-specific edit permissions. `alert_only` mode allows full-field corrections on all displayed trades, with non-manual historical trades stored as local overrides and only manually created trades deletable. All other modes keep trade facts read-only and allow only notes/tags. Trade records, overrides, notes, and tags are isolated by bot mode, with legacy unmodeled data classified as `alert_only`. The collected data must also be exportable as LLM-friendly structured evidence for AI-assisted strategy evaluation and adjustment workflows.

The implementation will extend the existing Python `manual_trades.py` SQLite store into a mode-scoped trade history/annotation/override store, add unified history and export endpoints to `api_server.py`, update the Next.js proxy and dashboard hooks to consume unified history, and adapt `/manual-trades` controls to current-mode permissions and agent-ready export.

## Technical Context

**Language/Version**: Python 3.11 backend; TypeScript / Next.js 14+ dashboard  
**Primary Dependencies**: Python stdlib HTTP server and SQLite; existing `ExecutionClient` trade history retrieval; React hooks/components and Next.js route handlers  
**Storage**: Existing local SQLite store under `src/tradegumi/data/`, extended with bot-mode fields plus annotation/override data and structured JSON export generation; existing broker/source trade history remains source-owned  
**Testing**: pytest for Python storage, merge, mode isolation, permission enforcement, and export schema/content; dashboard validation through available lint/typecheck plus quickstart manual checks  
**Target Platform**: Docker-hosted TradeGumi service plus authenticated web dashboard  
**Project Type**: Web application with Python trading backend and Next.js frontend  
**Performance Goals**: Unified trade history loads within the existing 30-second dashboard polling cycle and returns 50-100 recent trades in under 2 seconds for a single operator  
**Constraints**: No external database; no broker-specific logic inside trade storage/permission code; existing auth via `JOURNAL_TOKEN`; no secrets added; mode changes remain config-driven  
**Scale/Scope**: Single operator, three bot modes (`alert_only`, `demo`, `live`), local history/annotation/override data, dashboard and manual-trades views

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Feature affects trade-history presentation and manual record maintenance only; no signal generation criteria or firing paths are changed. |
| II. Execution Layer Abstraction | PASS | Source trade history is consumed through existing execution-client/API boundaries; the new merge/override layer stores generic trade fields and must not import broker clients directly. |
| III. Risk-First | PASS | No order placement or risk bypass is introduced. `alert_only` edits are record corrections only and do not create executable trades. |
| IV. Observable by Default | PASS | Main dashboard and manual trades page both become observable views of the same current-mode history; export provides agent-readable evidence; permission errors are surfaced to users instead of silent mutation. |
| V. Configuration-Driven Operations | PASS | Current bot mode remains read from existing config/status behavior; permissions and mode isolation derive from that mode without hardcoded environment changes. |
| Security & Credential Hygiene | PASS | Existing `JOURNAL_TOKEN` authentication is reused; no new credentials or external services are introduced. |
| Code Quality & Documentation | PASS | Python storage/merge/permission helpers must have module/function docstrings and intention-revealing names. |
| Pull Request Policy | PENDING | Generated task list must include "Submit PR with DockeGumi as reviewer" as the final task. |

No gates failed. No complexity violations to track.

## Project Structure

### Documentation (this feature)

```text
specs/003-manual-trade-permissions/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- manual-trades-api.md
|   |-- dashboard-ui.md
|   `-- agent-export.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- manual_trades.py             # UPDATE: mode-scoped unified storage, overrides, annotations, permission checks
|-- api_server.py                # UPDATE: unified trade history/export endpoints and mode-aware mutation handling
|-- config.py                    # READ: current TRADEGUMI_MODE; update only if helper/defaults are needed
`-- tests/
    `-- test_manual_trades.py    # NEW/UPDATE: storage, merge, mode isolation, legacy default, permissions, export

dashboard/src/
|-- app/
|   |-- manual-trades/
|   |   `-- page.tsx             # UPDATE: unified history table and mode-aware edit/delete controls
|   `-- api/
|       `-- manual-trades/
|           |-- [[...id]]/route.ts # UPDATE: proxy unified list/create/update/delete requests
|           |-- stats/route.ts     # UPDATE: proxy current-mode summary stats
|           `-- export/route.ts    # NEW: proxy current-mode agent export requests
|-- components/
|   `-- TradeHistory.tsx         # UPDATE: render unified dashboard history fields including notes/tags if exposed
|-- hooks/
|   `-- useData.ts               # UPDATE: fetch unified current-mode trade history
|-- lib/
|   `-- api.ts                   # UPDATE: unified trade history client methods/types
`-- types/
    `-- index.ts                 # UPDATE: mode-scoped unified trade, annotation, and permission types
```

**Structure Decision**: Keep the existing Python backend plus Next.js dashboard/proxy layout. Extend the current manual-trades module and endpoints rather than introducing a new service, database server, or broker-specific dashboard path.

## Phase 0: Research

See [research.md](research.md) for decisions and alternatives.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for entity design.

See [contracts/manual-trades-api.md](contracts/manual-trades-api.md), [contracts/dashboard-ui.md](contracts/dashboard-ui.md), and [contracts/agent-export.md](contracts/agent-export.md) for API, UI, and export contracts.

See [quickstart.md](quickstart.md) for validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Contracts only touch history, annotations, overrides, and dashboard presentation; signal logic remains out of scope. |
| II. Execution Layer Abstraction | PASS | Data model uses canonical trade identity/source fields and avoids Oanda-specific schema; source trades are read via existing API/client boundary. |
| III. Risk-First | PASS | Full edits in `alert_only` are local history corrections; no execution or risk enforcement path is modified. |
| IV. Observable by Default | PASS | Both dashboard and manual-trades views display current-mode unified history; agent exports provide structured evidence for offline analysis; rejected/ignored mutation attempts return explicit errors or warnings. |
| V. Configuration-Driven Operations | PASS | Mode isolation and permissions are derived from `TRADEGUMI_MODE` surfaced by existing config/status endpoints. |
| Security & Credential Hygiene | PASS | Existing journal auth is required for mutation and protected reads; no secret-bearing contract fields are added. |
| Code Quality & Documentation | PASS | Plan scopes Python helper changes that require docstrings and tests around non-obvious merge/permission behavior. |
| Pull Request Policy | PENDING | Must be enforced in `/speckit-tasks`. |

No post-design gates failed.
