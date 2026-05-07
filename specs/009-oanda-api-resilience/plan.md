# Implementation Plan: OANDA API Resilience

**Branch**: `009-oanda-api-resilience` | **Date**: 2026-05-07 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/009-oanda-api-resilience/spec.md`

## Summary

Harden the OANDA v20 integration so transient provider failures, especially candle-fetch 504 Gateway Timeout responses, retry before signal evaluation and surface precise indeterminate API/data diagnostics when exhausted. The implementation will audit and correct OANDA paths, normalize base URLs, add bounded request timeouts and retry/backoff for transient statuses, preserve provider candle completion status, ensure signal inputs use only complete candles, and fix order/position path and response parsing without changing strategy thresholds or entry rules.

## Technical Context

**Language/Version**: Python 3.13 package under `src/`  
**Primary Dependencies**: `requests` session client, Python stdlib `time`/logging/dataclasses, pytest  
**Storage**: Existing strategy metrics SQLite/JSON records; no schema replacement planned  
**Testing**: pytest under `src/tradegumi/tests/`, with OANDA session/request test doubles  
**Target Platform**: Local operator service and Docker-hosted TradeGumi backend using OANDA practice/demo and live REST integrations  
**Project Type**: Python trading backend with broker-agnostic execution client interface  
**Performance Goals**: Bounded retries must not hang the signal loop; successful transient recovery should complete within a small multiple of the configured request timeout  
**Constraints**: Do not change signal thresholds, trend thresholds, MACD rules, entry criteria, risk rules, or profitability behavior; do not log API tokens/secrets; preserve broker abstraction  
**Scale/Scope**: OANDA REST client paths, request wrapper, candle model completion flag, signal-engine upstream failure diagnostics, focused docs/tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Resilience repairs data delivery and diagnostics without bypassing trend, signal, confidence, or risk layers. |
| II. Execution Layer Abstraction | PASS | OANDA-specific behavior stays in the OANDA client; shared `Candle.complete` remains provider-neutral. |
| III. Risk-First | PASS | No risk sizing, drawdown, order-placement criteria, or execution guardrails are loosened. |
| IV. Observable by Default | PASS | Provider failures become explicit diagnostics with method/path/status/retry context. |
| V. Configuration-Driven Operations | PASS | Timeouts/retry constants may be config-backed or module constants; no strategy parameters are retuned. |
| Security & Credential Hygiene | PASS | Logs and diagnostics must omit authorization headers, tokens, and raw secret-bearing payloads. |
| Code Quality & Documentation | PASS | New Python helpers require useful docstrings, clear names, and focused tests. |
| Pull Request Policy | PASS | `tasks.md` must end with submitting a PR with DockeGumi as reviewer. |

No gate violations.

## Project Structure

### Documentation (this feature)

```text
specs/009-oanda-api-resilience/
|-- spec.md
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
|   |-- oanda-v20-endpoints.md
|   `-- diagnostics.md
|-- checklists/
|   `-- requirements.md
`-- tasks.md
```

### Source Code (repository root)

```text
src/tradegumi/
|-- api/
|   |-- base_client.py              # add provider-neutral candle completion flag
|   `-- oanda_client.py             # URL normalization, timeout, retry, endpoint paths, response parsing
|-- config.py                       # OANDA base/stream URL defaults and optional resilience config
|-- signal_engine.py                # complete-candle filtering and upstream OANDA failure diagnostics
|-- strategy_metrics.py             # ensure API/data failures classify as indeterminate/passive diagnostics
`-- tests/
    |-- test_oanda_client.py        # endpoint, URL, retry, response parser, candle completion tests
    |-- test_signal_engine.py       # complete-candle and failed-candle diagnostic regression tests
    `-- test_strategy_metrics.py    # passive metrics/API failure classification tests

docs/
|-- strategy-metrics.md             # OANDA/API failure diagnostic notes
`-- signal-journal.md               # update only if signal journal docs mention provider diagnostics
```

**Structure Decision**: Keep changes inside the existing OANDA client, shared execution models, signal diagnostics, and tests. Do not introduce a replacement HTTP library, new broker abstraction layer, or strategy-rule changes.

## Phase 0: Research

See [research.md](research.md) for endpoint audit decisions and retry/diagnostic design.

## Phase 1: Design & Contracts

See [data-model.md](data-model.md) for request attempts, failure diagnostics, provider candles, complete candle windows, and order transaction responses.

See [contracts/oanda-v20-endpoints.md](contracts/oanda-v20-endpoints.md) and [contracts/diagnostics.md](contracts/diagnostics.md) for external endpoint and diagnostic contracts.

See [quickstart.md](quickstart.md) for local validation steps.

## Post-Design Constitution Check

| Principle | Status | Notes |
| --- | --- | --- |
| I. Signal Integrity | PASS | Complete data proceeds to existing rules; failures become indeterminate and never emit signals. |
| II. Execution Layer Abstraction | PASS | OANDA path/retry logic does not leak into strategy or risk rules. |
| III. Risk-First | PASS | Order parsing/path fixes do not bypass risk checks or alter risk configuration. |
| IV. Observable by Default | PASS | Diagnostics include provider failure categories and safe request context. |
| V. Configuration-Driven Operations | PASS | Existing OANDA environment defaults remain env-driven and normalized. |
| Security & Credential Hygiene | PASS | Request diagnostics explicitly exclude API keys and authorization headers. |
| Code Quality & Documentation | PASS | Plan requires docstrings and tests for new helpers/exceptions. |
| Pull Request Policy | PASS | Final task list includes PR submission with DockeGumi review. |

No post-design gate violations.
