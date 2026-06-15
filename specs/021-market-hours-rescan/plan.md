# Implementation Plan: Forex Market Hours Rescan

**Branch**: `022-market-hours-rescan` | **Date**: 2026-06-15 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/021-market-hours-rescan/spec.md`

## Summary

Correct forex session classification so forex instruments are considered open across the full trading week from Sunday 16:00 Central / 17:00 Eastern through Friday 16:00 Central / 17:00 Eastern, including the Sunday 21:40 Central case reported by the operator. Keep forced rescans from collapsing the whole watchlist into unavailable status by separating global forex-session state from per-symbol broker availability and surfacing clear diagnostics for both.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16.2.4 / React 19.2.4 dashboard under `dashboard/`  
**Primary Dependencies**: Python stdlib `datetime`, `zoneinfo`/existing timezone utilities, existing execution-client abstraction, existing Redis/runtime-state command flow, existing dashboard fetch hooks; pytest; Next ESLint/TypeScript checks if UI/types change  
**Storage**: Existing JSON state files under `src/tradegumi/data/` (`loop_state.json`, `watchlist.json`) and Redis runtime snapshot; no new durable store planned  
**Testing**: pytest in `src/tradegumi/tests/` for session boundaries, scan eligibility, command/rescan behavior, and loop-state diagnostics; dashboard checks via `npm run lint` and `npm run build` only if UI/types change  
**Target Platform**: Windows / Linux local operator environment, Docker Compose deployment, TradeGumi API on port 8199 with Next dashboard proxy  
**Project Type**: Python trading signal backend plus Next.js dashboard  
**Performance Goals**: Keep per-symbol session checks effectively constant-time; forced rescan remains responsive for the configured watchlist and does not add operator-visible delay beyond existing broker/data calls  
**Constraints**: Do not bypass signal layers, alter risk checks, add broker-specific imports to session logic, hardcode secrets, or change watchlist membership outside normal scan scoring and symbol availability rules  
**Scale/Scope**: Forex execution symbols in the existing watchlist, weekly forex open/close boundaries, forced rescan path, loop-state/watchlist diagnostics, focused tests and docs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The feature corrects forex session eligibility before existing Layer 1/2/3 evaluation; no signal layer is bypassed or weakened. |
| II. Execution Layer Abstraction | PASS | Forex session rules remain broker-neutral and symbol-category based; broker availability stays behind the existing execution client. |
| III. Risk-First | PASS | No order placement or risk logic changes are planned; risk checks remain mandatory for any actionable signal. |
| IV. Observable by Default | PASS | Forex market-open, market-closed, and symbol-unavailable reasons will remain visible through loop/watchlist state, logs, and rescan callbacks. |
| V. Configuration-Driven Operations | PASS | Existing symbol lists and runtime rescan command flow are reused; no operator must edit code to trigger the corrected behavior. |
| Security & Credential Hygiene | PASS | No new secrets, credentials, external auth surfaces, or credential-bearing logs are introduced. |
| Code Quality & Documentation | PASS | Session-boundary helpers and diagnostics require intention-revealing names, docstrings, and regression tests around timezone boundaries. |
| Pull Request Policy | PASS | No reviewer was identified in the feature context; task generation must include a final task to ask the user for the reviewer before opening the PR. |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/021-market-hours-rescan/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- market-session-status.md
|   |-- forced-rescan-result.md
|   `-- loop-state-diagnostics.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- session_rules.py              # forex weekly open/close boundaries and timezone-safe session helpers
|-- main.py                       # forced-rescan gating, loop-state reasons, closed-market notifications
|-- pre_session_scanner.py        # scan result availability/diagnostic fields if needed
|-- callback.py                   # rescan/closed-market callback payload compatibility if fields are added
|-- api_server.py                 # existing rescan command endpoint remains the control path
`-- tests/
    |-- test_session_rules.py     # Sunday open, weekday open, Friday close, weekend closed, DST-aware behavior
    |-- test_commands.py          # existing rescan command semantics remain intact
    |-- test_main_market_data.py  # loop/rescan eligibility helpers if extracted
    `-- test_pre_session_scanner.py # forced-rescan availability diagnostics if scanner output changes

dashboard/src/
|-- hooks/useData.ts              # market-open derivation if loop-state diagnostic shape changes
|-- components/SettingsPanel.tsx  # rescan affordance/status copy only if existing UI cannot show result
`-- types/index.ts                # shared diagnostic field types only if new fields are exposed
```

**Structure Decision**: Keep the fix in existing session-rule and scan orchestration boundaries. Add small structured diagnostic fields to existing state/result payloads only where needed; avoid a new scheduler, database table, or broker-specific calendar service.

## Phase 0: Research

See [research.md](research.md) for decisions on forex weekly session semantics, timezone handling, symbol categories, forced-rescan availability separation, and diagnostics compatibility.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for forex market session status, symbol availability, and forced rescan result entities.

See [contracts/market-session-status.md](contracts/market-session-status.md), [contracts/forced-rescan-result.md](contracts/forced-rescan-result.md), and [contracts/loop-state-diagnostics.md](contracts/loop-state-diagnostics.md) for session, rescan, and dashboard-visible state contracts.

See [quickstart.md](quickstart.md) for validation steps.

Agent context was updated in [AGENTS.md](../../AGENTS.md) to point at this plan.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Design only corrects whether forex symbols are eligible to reach normal evaluation during an open market session. |
| II. Execution Layer Abstraction | PASS | Session contracts are broker-neutral; account-specific tradability remains a client availability concern. |
| III. Risk-First | PASS | Rescan and session changes do not place orders and do not affect risk enforcement. |
| IV. Observable by Default | PASS | Contracts require distinct forex market session and symbol availability reasons in operator-visible outputs. |
| V. Configuration-Driven Operations | PASS | Existing runtime rescan command and configured symbol categories remain the operator control surface. |
| Security & Credential Hygiene | PASS | No credential fields are added to payloads or logs. |
| Code Quality & Documentation | PASS | Quickstart and planned tests cover non-obvious timezone/session boundaries. |
| Pull Request Policy | PASS | Task generation must include final reviewer ask-back before PR creation unless a reviewer is identified later. |

No post-design gate violations.

## Complexity Tracking

*No violations.*
