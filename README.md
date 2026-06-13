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

### 3. Run the bot

```bash
cd src
poetry run python -m tradegumi.main --mode alert_only
```

### 4. Run the dashboard

```bash
cd dashboard
npm install
npm run build
npm start
```

Dashboard runs on `http://localhost:3000`. The bot's API server runs on port `8199`.

## Architecture

```text
┌─────────────────────────────────────────────────────┐
│  TradeGumi Bot (Python)                            │
│                                                    │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ Main Loop     │  │ API Server    │               │
│  │ (1s prices,  │  │ (:8199)      │               │
│  │  5s signals)  │  │  GET/POST    │               │
│  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                         │
│  ┌──────┴───────┐  ┌─────┴────────┐               │
│  │ Signal Engine │  │ Callback      │               │
│  │ (4-layer)     │  │ (webhook)    │               │
│  └──────────────┘  └──────┬────────┘               │
│                           │                        │
└───────────────────────────┼────────────────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
    ┌─────┴──────┐  ┌──────┴───────┐  ┌──────┴──────┐
    │ Dashboard   │  │ Discord     │  │ DockeGumi   │
    │ (Next.js    │  │ Webhook     │  │ (NUC :8198) │
    │  :3000)     │  │ Alerts      │  │ Orchestration│
    └─────────────┘  └─────────────┘  └─────────────┘
```

**Data flow:**

- Bot writes `loop_state.json` (1s), `watchlist.json` (30min), `signals.json` (on signal)
- Dashboard reads JSON files + API endpoints for live data
- API server (`:8199`) accepts config changes (mode, program, phase, re-scan)
- Callback webhook sends structured events to DockeGumi for automated action

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

The dashboard is a Next.js app that reads data from the bot's JSON files and API endpoints.

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

Switch between `alert_only` → `demo` → `live`, change program (challenge/instant), phase (1/2/Funded), and trigger manual re-scans — all from the dashboard. Changes persist to `.env` and take effect immediately.

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

Postgres is **required** — it is the durable source of truth for strategy metrics and the signal journal. There is no SQLite fallback: if `TRADEGUMI_DATABASE_URL` is unset or Postgres is unreachable, persistence operations fail rather than silently writing elsewhere. Redis caches hot runtime state (latest prices, active signals, watchlist, strategy summary) and is safe to lose — the source of truth remains Postgres.

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
