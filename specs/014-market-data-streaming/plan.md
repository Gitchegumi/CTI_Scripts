# Implementation Plan: Provider-Agnostic Market Data Streaming

**Branch**: `014-market-data-streaming` | **Date**: 2026-05-30 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/014-market-data-streaming/spec.md`

## Summary

Add a provider-neutral market data layer that publishes normalized `PriceObservation` objects from either a streaming provider or the existing polling path. Oanda pricing streaming is the first streaming implementation, using a persistent authenticated stream and converting price payloads into shared observations with `OANDA_PRICING_STREAM`; REST polling remains available as the fallback. The main loop keeps the existing 5-second signal engine cadence, while Signal Journal outcome evaluation moves to immediate observation handling for streaming and continues polling behavior when fallback is active.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`; Next.js 16 / React 19 dashboard under `dashboard/`
**Primary Dependencies**: Python stdlib threading/queue/time/json/dataclasses; existing `requests` session for Oanda HTTP; existing `ExecutionClient`, `PriceTick`, `PriceObservation`, `RollingPriceHistory`, `evaluate_price_observation`, and runtime API state helpers
**Storage**: In-memory rolling price history; existing JSONL Signal Journal; existing compact `loop_state.json` and runtime API state; no new durable market data store
**Testing**: pytest in `src/tradegumi/tests/`; dashboard lint/build only if dashboard types or UI behavior are changed
**Target Platform**: Docker Compose TradeGumi container on a low-power TrueNAS host; local backend API on port 8199; dashboard proxy
**Project Type**: Python trading backend plus Next.js dashboard
**Performance Goals**: Reduce REST pricing calls by at least 90% while streaming is healthy; preserve TP/SL journal update within 2 seconds of observation receipt in tests; preserve 5-second signal-engine cadence; avoid more than one active Oanda price stream for TradeGumi watchlist prices
**Constraints**: Do not change trading strategy thresholds, risk enforcement, execution behavior, or MatchTrader scope; keep polling fallback; obey Oanda limits of 120 REST requests/s/IP, 20 active streams/IP, and no more than 2 new connections/s; keep per-observation logs at DEBUG
**Scale/Scope**: One active TradeGumi process observing the current scan symbol set, typically tens of symbols; Oanda streaming provider plus polling provider/fallback; future MatchTrader provider enabled by interface but not implemented

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The feature only changes market data delivery into existing observation consumers; it does not modify signal gates, thresholds, or generation logic. |
| II. Execution Layer Abstraction | PASS | Core design introduces a provider-neutral market data interface so Oanda stream objects do not leak into journal, dashboard, or signal code. |
| III. Risk-First | PASS | No order placement, risk sizing, drawdown, or position-limit behavior is changed. |
| IV. Observable by Default | PASS | Plan includes stream health summaries, fallback logs, liveness state, and dashboard state continuity. JSON state remains available. |
| V. Configuration-Driven Operations | PASS | New behavior is controlled by env vars and preserves polling mode. |
| Security & Credential Hygiene | PASS | Oanda bearer token use stays in provider code; logs must omit tokens and account secrets. |
| Code Quality & Documentation | PASS | Planned Python modules/classes/helpers require docstrings and focused tests for lifecycle, parsing, fallback, and shutdown. |
| Pull Request Policy | PASS | Final task list includes DockeGumi reviewer PR task. |

## Project Structure

### Documentation (this feature)

```text
specs/014-market-data-streaming/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- market-data-provider.md
|   |-- oanda-pricing-stream.md
|   |-- polling-market-data.md
|   `-- runtime-state.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- market_data.py                 # Provider-neutral lifecycle, health, and orchestration abstractions
|-- price_observations.py          # Existing PriceObservation/RollingPriceHistory; add stream publish helper only if needed
|-- main.py                        # Wire provider lifecycle, resubscribe on scan_symbols changes, consume latest observations for state
|-- config.py                      # Add market data mode, reconnect, heartbeat timeout, backoff env vars
|-- api_server.py                  # Expose runtime market-data health if dashboard/API needs it
|-- signal_outcomes.py             # Continue using evaluate_price_observation from observation callbacks
|-- signal_engine.py               # Continue using latest shared observations for live trigger prices
|-- api/
|   `-- oanda_client.py            # Keep REST execution client; optionally share auth/base details with stream provider
`-- tests/
    |-- test_market_data.py
    |-- test_oanda_market_data.py
    |-- test_price_observations.py
    |-- test_signal_outcomes.py
    `-- test_main_market_data.py

dashboard/src/
|-- hooks/useData.ts               # Only if loop-state/health response shape changes
`-- types/index.ts                 # Only if market-data health becomes a typed dashboard field

docs/
`-- signal-journal.md              # Update only if operator-facing streaming/fallback behavior needs documentation here
```

**Structure Decision**: Keep market data separate from execution clients and signal logic. `ExecutionClient` remains for orders, account state, candles, positions, and polling fallback. New provider-neutral market data ownership belongs in `market_data.py`; Oanda streaming implementation may live there initially or in a focused provider module if it grows, but consumers receive only `PriceObservation` and health state.

## Phase 0: Research

See [research.md](research.md) for Oanda documentation findings, provider lifecycle decisions, fallback policy, resubscribe strategy, health summary design, and testing approach.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for market data provider entities, subscription state, stream health, observation flow, and fallback transitions.

See [contracts/market-data-provider.md](contracts/market-data-provider.md), [contracts/oanda-pricing-stream.md](contracts/oanda-pricing-stream.md), [contracts/polling-market-data.md](contracts/polling-market-data.md), and [contracts/runtime-state.md](contracts/runtime-state.md) for provider lifecycle, Oanda stream parsing, polling fallback, and dashboard/API state contracts.

See [quickstart.md](quickstart.md) for validation scenarios.

Agent context was updated in [AGENTS.md](../../AGENTS.md) to point at this plan.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | The design does not change signal thresholds or decision gates; streaming only changes live price observation delivery. |
| II. Execution Layer Abstraction | PASS | Oanda-specific parsing is isolated behind a market data provider contract; core consumers use normalized observations. |
| III. Risk-First | PASS | No execution/risk behavior is changed. |
| IV. Observable by Default | PASS | Health summaries, fallback state, reconnect counts, heartbeat age, and active symbol count are specified. |
| V. Configuration-Driven Operations | PASS | Streaming, polling, heartbeat timeout, reconnect, and backoff settings are env-var driven. |
| Security & Credential Hygiene | PASS | Auth tokens remain bearer headers only and must be redacted from logs. |
| Code Quality & Documentation | PASS | Tasks require docstrings and code quality review for new Python modules and helpers. |
| Pull Request Policy | PASS | Tasks include DockeGumi reviewer PR task. |

## Complexity Tracking

No constitution violations or complexity exceptions are required.
