<!--
  SYNC IMPACT REPORT
  ==================
  Version change: 1.1.0 → 1.2.0 (MINOR: task list final-task rule added to Pull Request Policy)
  Modified principles: None
  Added sections: "Submit PR" final-task rule within Pull Request Policy
  Removed sections: None
  Templates requiring updates:
    ✅ .specify/templates/plan-template.md — Constitution Check gate unchanged; no update needed
    ✅ .specify/templates/spec-template.md — no impact; no update needed
    ✅ .specify/templates/tasks-template.md — UPDATED: added "Submit PR with DockeGumi as reviewer"
      as final task in Phase N Polish section
    ✅ .specify/templates/commands/ — no command files present; nothing to update
  Follow-up TODOs:
    - TODO(RATIFICATION_DATE): Using 2026-04-28 (first fill date) as ratification date.
      If an earlier governance adoption date exists, update this field.
    - MatchTrader live execution client is not yet implemented; Principle II
      should be re-verified once it ships to confirm abstraction holds.
-->

# TradeGumi CTI Signal Engine Constitution

## Core Principles

### I. Signal Integrity (NON-NEGOTIABLE)

A trade signal MUST pass all four layers before it fires. No partial signals, manual
overrides, or layer bypasses are permitted under any circumstance.

Layer execution order is fixed:

- **Layer 0 — Trend Filter**: 15m + 5m LR slopes must agree on direction.
- **Layer 1 — Pre-Session Scanner**: Symbol must be Tier 1 (or explicitly Tier 2 with
  justification). Below-threshold symbols MUST be skipped.
- **Layer 2 — Signal Stack**: StochRSI + MACD + Keltner Channel must all confirm.
  Candlestick confirmation is optional but counted in confidence scoring.
- **Layer 3 — Risk Management**: Position size, daily loss limit, and max drawdown checks
  must pass before an order is placed.

**Rationale**: CTI prop firm rules carry real financial penalty for violations. A single
rogue signal that breaches drawdown limits can void an entire challenge. Integrity is the
only acceptable default.

### II. Execution Layer Abstraction

Signal logic MUST be broker-agnostic. All execution is routed through a common
`ExecutionClient` interface (`src/tradegumi/api/base_client.py`). No signal, risk, or
session-rules code may import or reference a specific broker (Oanda, MatchTrader, etc.)
directly.

Swapping execution targets (Oanda demo → MatchTrader live) MUST require only a config
change, not a code change.

**Rationale**: The project's explicit design goal is zero signal logic changes when
migrating from Oanda demo to MatchTrader live execution. Leaking broker specifics into
signal code breaks this guarantee.

### III. Risk-First (NON-NEGOTIABLE)

Every trade entry MUST enforce all three risk constraints without exception:

| Constraint | Default | Configurable? |
| --- | --- | --- |
| Risk per trade | 0.25% of account | Yes — via env var only |
| Daily loss limit | 5% of account | Yes — via env var only |
| Max drawdown | 10% of account | Yes — via env var only |
| Max open positions | 5 | Yes — via env var only |

Risk parameters are env-var driven, but the enforcement code MUST NOT be bypassable.
`alert_only` mode is exempt from order placement, but risk checks MUST still run and log.

**Rationale**: CTI challenge phases have hard breach limits. Exceeding them terminates the
account. Risk enforcement is the last line of defense.

### IV. Observable by Default

Every significant event MUST be posted to Discord AND written to the JSON state files.
Silent failures are not permitted.

Events that MUST be observable:

- Signal fired (with symbol, direction, confidence %, all layer states)
- Signal blocked (with reason — which layer failed)
- Watchlist re-rank completed (with tier changes)
- Mode/program/phase config change
- Market open / market close / swap blackout entry
- Any execution error or API failure

JSON state files (`loop_state.json`, `watchlist.json`, `signals.json`) MUST remain
current and machine-readable for dashboard consumption.

**Rationale**: The dashboard and DockeGumi orchestration depend entirely on these outputs.
A silent bug in signal detection is indistinguishable from a correctly quiet market unless
every decision is logged.

### V. Configuration-Driven Operations

Mode (`alert_only` / `demo` / `live`), CTI program (`challenge` / `instant`), and phase
(1 / 2 / Funded) changes MUST take effect via the `/api/config/*` endpoints or `.env`
edits — without code changes or process restarts where possible.

All strategy parameters (ATR multipliers, LR lengths, indicator periods, risk percentages)
MUST be env-var configurable. No magic numbers may be hardcoded in signal logic.

**Rationale**: Iterating on strategy parameters or switching between challenge phases
must not require code deployments. Config-driven operations are essential for rapid
forward-testing cycles.

## Security & Credential Hygiene

All secrets (API keys, webhook URLs, account IDs) MUST be stored in `.env` only.
The `.env` file is gitignored and MUST never be committed.

Rules:

- `.env.example` MUST contain all required variable names with placeholder values and
  inline documentation — it is the canonical configuration reference.
- No secret or credential value MUST appear in any source file, log output, or Discord
  message.
- Webhook URLs and Oanda tokens in logs MUST be redacted or omitted.
- Docker deployments MUST use `env_file` or mounted secrets, never hardcoded env values
  in `docker-compose.yml` or Dockerfiles.

## Development Workflow

All signal logic changes MUST follow this promotion ladder before reaching a funded
account:

1. **alert_only** — Run for at minimum 1 week of market sessions. Review signal quality,
   Layer 2 confidence scores, and Discord alert accuracy. No capital at risk.
2. **demo** — Run until positive expectancy is demonstrated over a statistically
   meaningful sample (≥30 closed trades). Real market conditions, simulated capital.
3. **live** — Only after demo validation. Requires explicit manual mode switch via API
   or dashboard. No automated promotion.

Backtesting data in `src/backtesting/` is advisory only — live forward testing on demo
is the authoritative validation gate.

Docker Compose is the production deployment standard. Direct `python -m` invocation is
for local development only.

## Governance

This constitution supersedes all other development practices and documentation for the
TradeGumi project. When any other doc conflicts with this constitution, this document wins.

Amendment procedure:

1. Propose change in a PR with rationale and impact analysis.
2. Update this file with the new content and bump `CONSTITUTION_VERSION` per semver rules.
3. Update `LAST_AMENDED_DATE` to the amendment date.
4. Run `/speckit-constitution` to propagate changes to dependent templates.
5. Complexity violations (deviations from principles) MUST be documented in the
   `Complexity Tracking` table of the relevant `plan.md`.

Versioning policy:

- **MAJOR** — Principle removed, redefined, or enforcement relaxed.
- **MINOR** — New principle or section added, or guidance materially expanded.
- **PATCH** — Wording clarification, typo fix, non-semantic refinement.

All PRs touching signal logic, risk code, or execution clients MUST pass the Constitution
Check gate in `plan.md` before Phase 0 research begins.

### Pull Request Policy

All PRs MUST request **DockeGumi** as a reviewer before merging. No PR may be merged
without DockeGumi's review approval.

Every task list generated for a feature MUST include **"Submit PR with DockeGumi as
reviewer"** as the final task. This task is non-optional and MUST appear in the Polish
phase of every `tasks.md`.

**Version**: 1.2.0 | **Ratified**: 2026-04-28 | **Last Amended**: 2026-04-28
