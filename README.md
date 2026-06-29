# TradeGumi — CTI Signal Engine & Dashboard

Real-time signal engine for the City Traders Imperium (CTI) prop firm strategy, with a live dashboard for monitoring, configuration, and trade management. Uses Oanda v20 REST API for market data and demo execution. Discord alerts for all signals. Designed to swap to MatchTrader for live prop firm execution with zero signal logic changes.

## Features

- **4-Layer Signal Stack** — StochRSI + MACD + Keltner Channel + Candlestick confirmation
- **Live Dashboard** — Real-time prices, watchlist rankings, open trades, trade history, account metrics
- **Dashboard Config** — Switch mode (alert_only/demo/live), program (challenge/instant), phase, trigger re-scans — all from the browser
- **Weekend Throttling** — Dashboard auto-throttles polling from 2s → 60s when markets are closed
- **Webhook Callbacks** — TradeGumi sends structured events to DockeGumi for automated orchestration
- **30-Min Re-Ranking** — Watchlist re-scans every 30 minutes during market hours to track range evolution
- **Discord Alerts** — Every signal, blocked signal, and watchlist update posted to Discord

## Strategy Metrics

TradeGumi records diagnostics for every evaluated opportunity so no-signal periods can be reviewed without changing signal behavior. The dashboard route `/strategy-metrics` shows date-range summaries, near-misses, criterion pass/fail rates, blocker rankings, period comparison, and JSON export.

Diagnostic history is stored in Postgres (the durable source of truth), with a compact latest summary written to `src/tradegumi/data/strategy_metrics.json` for dashboard observability. By default, diagnostic retention is 90 days and can be adjusted with `STRATEGY_METRICS_RETENTION_DAYS`.

Signal journal exports separate emitted signal outcomes from tradable setup outcomes. A signal only counts as a strategy-stat trade opportunity when `usable_for_strategy_stats` is true; duplicates, missed entries, late signals, stale signals, and manual invalidations are excluded. Tune setup grouping and entry validity with `SIGNAL_SETUP_GROUP_WINDOW_MINUTES`, `SIGNAL_ENTRY_TOLERANCE_ATR`, and `SIGNAL_STALE_BARS`.

## Strategy Folders

Strategies are **self-contained, executable plugin folders** under `strategies/`.
TradeGumi core is the runtime framework (market data, trend/chop/shock filters,
cooldown, diagnostics, risk sizing); each strategy folder owns its *decision*
logic and is discovered and loaded at runtime without any change to core code.
Two reference strategies are tracked: `strategies/example-strategy/` (the full
CTI pullback strategy with continuation management) and
`strategies/macd-momentum/` (a minimal strategy proving the contract with only
the two required files). Backtesting and strategy research are **not** part of
TradeGumi — they live in QuantPipe.

See [`docs/strategy-plugins.md`](docs/strategy-plugins.md) for the full folder
contract and interface reference.

### Folder layout

```text
strategies/
├── example-strategy/       # Tracked — full reference implementation
│   ├── strategy.json       #   metadata (id, label, description, signal_type, entrypoint)
│   ├── strategy.py         #   get_strategy() -> BaseStrategy; owns the signal decision
│   ├── indicators.py       #   strategy-specific indicators / structure helpers
│   ├── management.py       #   trade-management (manage_open_trade), risk/exit, confidence
│   └── README.md           #   per-strategy notes
├── macd-momentum/          # Tracked — minimal reference (two required files only)
│   ├── strategy.json
│   ├── strategy.py
│   └── README.md
└── my-strategy/            # Gitignored — your own strategy (local only)
    └── strategy.py
```

Only `strategy.json` and `strategy.py` are required; `indicators.py`,
`management.py`, `config.py`, `tests/`, and any other files are optional and up to
the strategy.

### `strategy.json` fields

| Field         | Required | Description                                          |
| ------------- | -------- | ---------------------------------------------------- |
| `id`          | Yes      | Unique strategy identifier (used in dropdown values) |
| `label`       | No       | Display name in the dashboard dropdown                |
| `description` | No       | Short description shown in tooltips/metadata         |
| `signal_type` | No       | Strategy variant tag (e.g. `pullback`, `continuation`) |
| `entrypoint`  | No       | Strategy module filename (informational; defaults to `strategy.py`) |

### How the runtime discovers and loads strategies

`tradegumi.strategy_loader.load_strategy()` resolves a folder under the configured
strategies directory (`STRATEGIES_DIR`, default `./strategies`) by folder name or by
`strategy.json` `id`, imports its `strategy.py` as an isolated synthetic package
(so `from .indicators import …` works even with a hyphenated folder name), and
calls the module-level `get_strategy()` factory, which must return a
`tradegumi.strategy_loader.BaseStrategy`. `SignalEngine` loads its strategy once at
construction — the bundled `example-strategy` by default, overridable with the
`TRADEGUMI_STRATEGY` env var (folder name or `id`) — and calls
`strategy.evaluate(engine, ctx)` for each evaluation, plus the optional
`strategy.bridge_trend(...)` and `strategy.manage_open_trade(ctx)` hooks. The last
owns continuation / open-trade management: core detects a continuation against an
active trade and persists the outcome, but the strategy decides the SL/TP changes
(the default declines, so management is opt-in). The separate strategy *registry*
scans `strategies/` for `strategy.json` to populate the dashboard dropdown, and
`strategy_loader.discover_strategies()` validates that each folder actually
implements the interface — the worker logs the result at startup.

### Adding a new strategy

1. Copy the example folder: `cp -r strategies/example-strategy strategies/my-strategy`
2. Edit `strategies/my-strategy/strategy.json` (unique `id`) and the logic in
   `strategy.py` / `indicators.py` / `management.py`.
3. Point the runtime at it with `TRADEGUMI_STRATEGY=my-strategy` (or its `id`) and
   restart the API server / worker.

Your new folder is **not tracked by git** — only the bundled reference strategies
(`example-strategy`, `macd-momentum`) are committed. All other sibling folders are
gitignored so your private strategies stay local. The built-in `CTI-v1` entry is
always available in the dropdown regardless of folder contents.

If a folder is missing `strategy.json` or contains malformed JSON, it still appears
in the dropdown with a warning badge (⚠️) so you know something needs fixing.

### `.gitignore` policy

```gitignore
# Strategy folders — only the bundled reference strategies are tracked.
# Sibling folders (your own strategies) are ignored so they stay local.
strategies/*
!strategies/example-strategy/
!strategies/macd-momentum/
```

## Quick Start

### 1. Install dependencies

```bash
cd src && poetry install
```

Or without Poetry:

```bash
pip install -r requirements.txt
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` with your values:

```ini
# Oanda API — get these from https://www.oanda.com/account/tpa/personal_token
OANDA_API_KEY=your_oanda_api_key_here
OANDA_ACCOUNT_ID=your_account_id_here

# Oanda URLs — defaults to practice (demo) account
# Change to https://api-fxtrade.oanda.com for live
OANDA_BASE_URL=https://api-fxpractice.oanda.com

# Discord webhook — create one in your Discord server settings
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/your_webhook_here

# Run mode: alert_only | demo | live
TRADEGUMI_MODE=alert_only

# CTI program and phase
CTI_PROGRAM=challenge   # challenge (2-step) or instant (instant funding)
CTI_PHASE=1              # 1 = Phase 1, 2 = Phase 2, 3 = Funded

# Webhook callback URL (optional — for DockeGumi orchestration)
# Set to http://your-nuc-ip:8198/api/tradegumi/webhook when running remotely
TRADEGUMI_CALLBACK_URL=
```

> **`.env` is gitignored.** Your keys will never be committed to the repo.

### 3. Run the services

The runtime is split into three independent processes — **worker** (trading
loop, no HTTP port), **api** (analytics + control on `:8199`), and **dashboard**
(Next.js on `:3000`). See `specs/019-split-runtime-containers`.

For local development, run each in its own terminal:

```bash
# Worker — trading loop
cd src && poetry run python -m tradegumi.main --mode alert_only

# API — analytics + control server
cd src && poetry run python -m tradegumi.api_main

# Dashboard
cd dashboard && npm install && npm run build && NEXT_PUBLIC_API_URL=http://localhost:8199 npm start
```

For production, Docker Compose runs all three as separate services (plus Postgres
and Redis):

```bash
docker compose up -d --build
```

Dashboard: `http://localhost:3000` · API: `http://localhost:8199`.

## Architecture

The runtime is split into three independently deployable services that share
state through **Redis** (hot state, operator commands, worker heartbeat) and
**Postgres** (durable analytics). A failure or restart of any one service does
not affect the other two.

```text
   ┌──────────────────┐                         ┌──────────────────┐
   │ tradegumi-worker │                         │  tradegumi-api   │
   │ 4-layer loop     │── snapshot/heartbeat ──▶ │  HTTP :8199      │
   │ (no public port) │◀──── commands ───────── │  analytics+ctrl  │
   └────────┬─────────┘     (Redis)             └────────┬─────────┘
            │ durable writes                             │ read-only broker
            ▼                                            ▼ client (no orders)
   ┌──────────────────────────────────────────────────────────┐
   │  Redis (hot state · commands · heartbeat)                  │
   │  Postgres (durable analytics · journal)                    │
   └──────────────────────────────────────────────────────────┘
                                                         ▲
                                              ┌──────────┴───────────┐
                                              │ tradegumi-dashboard  │
                                              │ Next.js :3000        │
                                              │ → calls the API only │
                                              └──────────────────────┘
```

**Data flow:**

- **Worker** runs the 4-layer signal engine, writes durable analytics to
  Postgres, and publishes a hot-state snapshot + liveness heartbeat to Redis. No
  public HTTP port.
- **API** serves the dashboard: hot state from the worker's Redis snapshot,
  durable analytics from Postgres, and account/positions/trade-history from its
  own read-only broker client. It never places orders (Risk-First).
- **Dashboard** (Next.js) reads and writes exclusively through the API.
- **Config changes** (mode/program/phase/challenge_type, re-scan) flow
  API → worker over the Redis command channel; the worker applies them without a
  restart and reflects them in its snapshot. A command issued while the worker is
  down is applied on its next startup (durable desired-config).
- **Callback webhook** sends structured events (signals, worker start/stop,
  command applied) to DockeGumi.

### Main Loop Cadence

| Component         | Interval       | Purpose                                             |
| ----------------- | -------------- | --------------------------------------------------- |
| Price ticker      | 1 second       | Live bid/ask for all watchlist symbols (1 API call) |
| Signal engine     | 5 seconds      | Indicators, LR slopes, signal detection             |
| Loop state write  | 1 second       | Dashboard data (prices, trends, LR values)          |
| Watchlist re-rank | 30 minutes     | Re-evaluate tiers during market hours               |
| Pre-session scan  | 02:00 ET daily | Full re-scan + instrument availability check        |

API budget: ~4 calls/sec (well within Oanda's 120/sec limit).

## Dashboard

The dashboard is a Next.js app that reads and writes exclusively through the API service (`tradegumi-api`); it holds no direct connection to the worker, Redis, or Postgres.

### Sections

| Section            | Column | Polls                     | Data Source                             |
| ------------------ | ------ | ------------------------- | --------------------------------------- |
| 💳 Account Metrics | Left   | 30s                       | `watchlist.json`                        |
| ⚙️ Settings        | Left   | 5s                        | `GET /api/status`, `POST /api/config/*` |
| ⚡ Active Signals  | Left   | 30s                       | `signals.json`                          |
| 📊 Open Trades     | Left   | 5s (open) / 60s (closed)  | `GET /api/positions`                    |
| 📊 Watchlist       | Right  | 30s (open) / 60s (closed) | `watchlist.json` + `loop_state.json`    |
| 📜 Trade History   | Right  | 30s (open) / 60s (closed) | `GET /api/trades`                       |

### Weekend Mode

When all symbols are closed (weekend/after-hours), the dashboard:

- Throttles all polling from 2-5s → 60s
- Shows a yellow banner: "🌙 Markets closed — polling throttled to 60s"
- API status still polls at 5s (config changes take effect immediately)
- Auto-resumes fast polling when any market opens

### Settings Panel

Switch between `alert_only` → `demo` → `live`, change program (challenge/instant), phase (1/2/Funded), and trigger manual re-scans — all from the dashboard. Changes are delivered to the worker over the Redis command channel and applied within a loop iteration (no restart). They are also recorded as durable "desired config" in Redis, which the worker reconciles on startup — so a change made while the worker is down is applied when it returns. Note: while set, desired-config overrides the matching `.env` value across restarts (clear the Redis `desired_config` key to fall back to `.env`).

When program is set to "Instant", the phase selector dynamically hides (instant accounts don't have phases).

## API Endpoints

### GET

| Endpoint                   | Description                                 |
| -------------------------- | ------------------------------------------- |
| `GET /api/status`          | Current mode, program, phase, runtime state |
| `GET /api/data/loop_state` | Live prices, trends, LR values              |
| `GET /api/data/watchlist`  | Ranked watchlist with tiers                 |
| `GET /api/data/signals`    | Active signals                              |
| `GET /api/positions`       | Open positions from Oanda                   |
| `GET /api/trades?count=N`  | Closed trade history                        |

### POST

| Endpoint                   | Body                                     | Description                         |
| -------------------------- | ---------------------------------------- | ----------------------------------- |
| `POST /api/config/mode`    | `{"mode": "alert_only"\|"demo"\|"live"}` | Switch trading mode                 |
| `POST /api/config/program` | `{"program": "challenge"\|"instant"}`    | Switch CTI program                  |
| `POST /api/config/phase`   | `{"phase": 1\|2\|3}`                     | Switch CTI phase                    |
| `POST /api/action/rescan`  | `{}`                                     | Trigger immediate watchlist re-scan |

Config/action POSTs are delivered to the worker over the Redis command channel.
They return `{"status": "accepted", "command_id": ...}` (or `400` for an invalid
value, `503` if the command channel is unavailable — never a silent success).
The worker applies the command within a loop iteration; poll `GET /api/status` to
observe the change.

All endpoints include CORS headers for dashboard access.

## Webhook Callbacks

When `TRADEGUMI_CALLBACK_URL` is set, the bot POSTs structured events to that URL:

| Event           | When                        | Payload                                                  |
| --------------- | --------------------------- | -------------------------------------------------------- |
| `signal`        | Every trade signal          | symbol, direction, confidence, strategy, LR values, mode |
| `mode_change`   | Mode switched via API       | new mode, previous mode                                  |
| `rescan`        | Watchlist re-scan completes | trigger type (full/periodic)                             |
| `closed_market` | All markets close           | day name, message                                        |
| `trade_open`    | Position opened (future)    | trade details                                            |
| `trade_close`   | Position closed (future)    | trade details                                            |

Webhook receiver runs on DockeGumi at `:8198` for automated orchestration.

## Run Modes

| Mode         | Signals         | Execution                   | Use When                                      |
| ------------ | --------------- | --------------------------- | --------------------------------------------- |
| `alert_only` | ✅ Discord only | ❌ None                     | Initial testing — see what fires without risk |
| `demo`       | ✅ Discord      | ✅ Oanda demo account       | Forward testing — real market, fake money     |
| `live`       | ✅ Discord      | ✅ MatchTrader prop account | Stage 2 — live prop firm trading              |

**Start with `alert_only`.** Run it for 1-2 weeks. Review signal quality and Layer 2 confidence scores. Then switch to `demo` from the dashboard.

## Configuration

| Variable                 | Default                            | Description                                           |
| ------------------------ | ---------------------------------- | ----------------------------------------------------- |
| `OANDA_API_KEY`          | _(required)_                       | Oanda v20 API token                                   |
| `OANDA_ACCOUNT_ID`       | _(required)_                       | Oanda account ID                                      |
| `OANDA_BASE_URL`         | `https://api-fxpractice.oanda.com` | Practice URL (change for live)                        |
| `DISCORD_WEBHOOK_URL`    | _(required)_                       | Discord webhook for trade alerts                      |
| `TRADEGUMI_MODE`         | `alert_only`                       | alert_only / demo / live                              |
| `TRADEGUMI_CALLBACK_URL` | _(optional)_                       | DockeGumi webhook URL for orchestration               |
| `TRADEGUMI_API_PORT`     | `8199`                             | API server port                                       |
| `MAX_OPEN_POSITIONS`     | `5`                                | Max simultaneous positions                            |
| `CTI_PROGRAM`            | `challenge`                        | challenge (2-step) or instant (instant funding)       |
| `CTI_PHASE`              | `1`                                | 1 = Phase 1 (10%), 2 = Phase 2 (5%), 3 = Funded (10%) |
| `CTI_DAILY_LOSS_PCT`     | `0.05`                             | 5% daily loss limit                                   |
| `CTI_MAX_DD_PCT`         | `0.10`                             | 10% max drawdown                                      |
| `RISK_PER_TRADE`         | `0.0025`                           | 0.25% account risk per trade                          |
| `SL_ATR_MULTIPLIER`      | `3`                                | Stop loss = 3× ATR                                    |
| `TP_ATR_MULTIPLIER`      | `12`                               | Take profit = 12× ATR (1:4 R:R)                       |

## Strategy: CTI 4-Layer Signal Stack

Every signal passes through all four layers. All must agree for a signal to fire:

### Layer 0 — Trend Filter

- Linear Regression slope on 15m (length=50) AND 5m (length=14)
- Both timeframes must agree on direction. No counter-trend trades.

### Layer 1 — Pre-Session Scanner

Runs at startup, every morning at 06:30 ET, and every 30 minutes during market hours. Ranks all symbols by:

- **ADR consumption** — how much daily range is already used
- **Volatility regime** — 5d ATR vs 20d ATR (expanding vs contracting)
- **Breakout probability** — % of recent sessions with >1× ATR moves during London/NY overlap
- **Day-of-week bias** — historical directional tendency

Output: Tier 1 (trade), Tier 2 (watch/alert), Below Threshold (skip). No hardcoded symbol restrictions — the data decides daily.

### Layer 2 — Signal Stack

| Indicator                    | Parameters   | BUY Condition              | SELL Condition              |
| ---------------------------- | ------------ | -------------------------- | --------------------------- |
| **StochRSI**                 | 14,14,3,3    | k prev-3 min < 30, k > d   | k prev-3 max > 70, k < d    |
| **MACD**                     | 12,26,9      | Histogram > prev-5 min     | Histogram < prev-5 max      |
| **Keltner Channel**          | 20, 1.5× EMA | Last-5 low ≤ KC middle min | Last-5 high ≥ KC middle max |
| **Candlestick** _(optional)_ | —            | Engulfing, Hammer          | Shooting Star, Engulfing    |

Each indicator also produces a **0-1 strength score** (Layer 2 quality scoring). The weighted sum becomes the signal confidence percentage.

### Layer 3 — Risk Management

- Position size = 0.25% account risk ÷ (ATR × SL multiplier × lot size)
- SL = 3× ATR from entry
- TP = 12× ATR from entry (1:4 risk:reward)
- Trailing SL: 4-tier system that tightens as profit grows (3× → 2× → 1.5× → 1× ATR at 0R → 1.5R → 3R → 5R)
- Max 5 open positions

## Session Rules

| Asset Class | Trading Hours (ET)  | Notes                                    |
| ----------- | ------------------- | ---------------------------------------- |
| Forex       | Mon–Fri 00:00–16:30 | 16:30–19:00 break (swap blackout)        |
| Indices     | Mon–Fri 00:00–16:30 | 16:30–18:30 break                        |
| Crypto      | 24/7                | Low priority — doesn't fit session model |
| All         | —                   | No new entries during swap blackout      |

## File Structure

```bash
CTI_Scripts/
├── .env.example                 # Template for API keys
├── .env                         # Your config (gitignored)
├── dashboard/                   # Next.js dashboard
│   ├── src/
│   │   ├── app/page.tsx          # Main layout
│   │   ├── components/
│   │   │   ├── AccountCard.tsx   # 💳 Account metrics + progress bars
│   │   │   ├── SettingsPanel.tsx  # ⚙️ Mode/program/phase + re-scan
│   │   │   ├── SignalsSection.tsx # ⚡ Active signals cards
│   │   │   ├── OpenTrades.tsx    # 📋 Open positions table
│   │   │   ├── WatchlistSection.tsx # 📊 Ranked symbols with live prices
│   │   │   ├── TradeHistory.tsx  # 📜 Closed trades (filterable, sortable)
│   │   │   ├── Header.tsx        # Live clock, mode badge, provider
│   │   │   └── Footer.tsx        # CTI program info
│   │   ├── hooks/useData.ts     # Data hooks with weekend throttling
│   │   ├── lib/api.ts            # API client (config, positions, trades)
│   │   └── types/index.ts        # TypeScript interfaces
│   └── public/data/             # Symlink to bot data directory
├── src/
│   ├── pyproject.toml            # Poetry project
│   └── tradegumi/
│       ├── main.py               # Entry point, dual-cadence loop
│       ├── config.py             # .env loader + all configuration
│       ├── api_server.py          # HTTP API (:8199) for dashboard
│       ├── callback.py           # Webhook sender for DockeGumi
│       ├── webhook_receiver.py   # Webhook receiver (:8198) for orchestration
│       ├── api/
│       │   ├── base_client.py    # Abstract ExecutionClient interface
│       │   └── oanda_client.py   # Oanda v20 REST implementation
│       ├── indicators.py         # pandas_ta wrappers + Layer 2 scoring
│       ├── signal_engine.py       # Trend filter + 4-layer stack + confidence
│       ├── pre_session_scanner.py # Morning ranked watchlist (Layer 1)
│       ├── alerts.py             # Discord webhook alerter + signal persistence
│       ├── risk.py               # Position sizing, daily drawdown checks
│       ├── session_rules.py      # Trading hours, swap blackout, DOW bias
│       └── trailing_sl.py       # 4-tier ATR trailing stop manager
└── src/tradegumi/data/           # Runtime JSON data (loop_state, watchlist, signals)
```

## Docker Deployment

TradeGumi runs as a single `docker-compose` stack with Postgres (durable analytics) + Redis (hot runtime cache).

```yaml
services:
  tradegumi:
    image: ghcr.io/gitchegumi/cti-scripts:latest
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8199:8199"  # API server
      - "3000:3000"  # Dashboard
    env_file:
      - .env
    volumes:
      - tradegumi-data:/app/src/tradegumi/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8199/api/status"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: postgres:17-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: tradegumi
      POSTGRES_PASSWORD: ${TRADEGUMI_POSTGRES_PASSWORD:-tradegumi}
      POSTGRES_DB: tradegumi
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tradegumi -d tradegumi"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
      start_period: 5s

volumes:
  tradegumi-data:
  postgres-data:
  redis-data:
```

### Required `.env` variables

```ini
TRADEGUMI_DATABASE_URL=postgresql://tradegumi:your_password@postgres:5432/tradegumi
TRADEGUMI_REDIS_URL=redis://redis:6379/0
```

Postgres is **required** — it is the durable source of truth for strategy metrics (evaluated opportunities and criterion results) **and the signal journal** (`journal_entries`). There is no SQLite fallback: if `TRADEGUMI_DATABASE_URL` is unset or Postgres is unreachable, the bot fails fast at startup rather than silently writing elsewhere. The application reads and writes the journal through Postgres; the append-only `signal_journal.jsonl` file is legacy — kept as a best-effort export/backup snapshot and importable into a fresh database via `journal.backfill_from_jsonl`, but never read for queries. Redis caches hot runtime state (latest loop state / dashboard view) and short-lived strategy-summary responses, and is safe to lose.

### Dashboard auth behind Authentik

By default the dashboard is gated by the `JOURNAL_TOKEN` cookie. When you deploy behind an [Authentik](https://goauthentik.io/) outpost, the proxy injects forwarded identity headers (`x-authentik-*`) after it authenticates the request. To trust those headers instead of the cookie, set:

```ini
AUTHENTIK_TRUST_PROXY_HEADERS=true
```

**Only enable this when both conditions hold:**

1. The dashboard is unreachable except through the Authentik proxy (e.g. it is not exposed directly on `:3000`).
2. The proxy is configured to **strip any client-supplied `x-authentik-*` headers** before forwarding.

Without those guarantees a caller could forge `x-authentik-username` and bypass authentication entirely. When the flag is `false` or unset, the `x-authentik-*` headers are ignored and the `JOURNAL_TOKEN` cookie check is used.

## Oanda Setup

1. **Create a demo account**: [Oanda fxTrade Practice](https://fxtrade.oanda.com/your_account/fxtrade/register/gate)
2. **Generate API token**: Log in → Account Management Portal → "Manage API Access" → Generate token
3. **Find your account ID**: Shown in the Oanda dashboard or API response
4. **Add to `.env`**: `OANDA_API_KEY` and `OANDA_ACCOUNT_ID`

Oanda API reference: [https://developer.oanda.com/rest-live-v20/introduction/](https://developer.oanda.com/rest-live-v20/introduction/)

## Stage 2 Roadmap

- [ ] MatchTrader REST client implementation
- [ ] `TRADEGUMI_MODE=live` unlock
- [x] Docker Compose deployment with Postgres + Redis
- [ ] Tiered risk table (from Risk_Management_Rules.docx) replacing flat 0.25%
- [ ] Dynamic position sizing (Layer 3 — after positive expectancy validated)
- [ ] Automated daily performance reporting to Discord
