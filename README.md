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

```
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

| Component | Interval | Purpose |
|---|---|---|
| Price ticker | 1 second | Live bid/ask for all watchlist symbols (1 API call) |
| Signal engine | 5 seconds | Indicators, LR slopes, signal detection |
| Loop state write | 1 second | Dashboard data (prices, trends, LR values) |
| Watchlist re-rank | 30 minutes | Re-evaluate tiers during market hours |
| Pre-session scan | 02:00 ET daily | Full re-scan + instrument availability check |

API budget: ~4 calls/sec (well within Oanda's 120/sec limit).

## Dashboard

The dashboard is a Next.js app that reads data from the bot's JSON files and API endpoints.

### Sections

| Section | Column | Polls | Data Source |
|---|---|---|---|
| 💳 Account Metrics | Left | 30s | `watchlist.json` |
| ⚙️ Settings | Left | 5s | `GET /api/status`, `POST /api/config/*` |
| ⚡ Active Signals | Left | 30s | `signals.json` |
| 📊 Open Trades | Left | 5s (open) / 60s (closed) | `GET /api/positions` |
| 📊 Watchlist | Right | 30s (open) / 60s (closed) | `watchlist.json` + `loop_state.json` |
| 📜 Trade History | Right | 30s (open) / 60s (closed) | `GET /api/trades` |

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

| Endpoint | Description |
|---|---|
| `GET /api/status` | Current mode, program, phase, runtime state |
| `GET /api/data/loop_state` | Live prices, trends, LR values |
| `GET /api/data/watchlist` | Ranked watchlist with tiers |
| `GET /api/data/signals` | Active signals |
| `GET /api/positions` | Open positions from Oanda |
| `GET /api/trades?count=N` | Closed trade history |

### POST

| Endpoint | Body | Description |
|---|---|---|
| `POST /api/config/mode` | `{"mode": "alert_only"\|"demo"\|"live"}` | Switch trading mode |
| `POST /api/config/program` | `{"program": "challenge"\|"instant"}` | Switch CTI program |
| `POST /api/config/phase` | `{"phase": 1\|2\|3}` | Switch CTI phase |
| `POST /api/action/rescan` | `{}` | Trigger immediate watchlist re-scan |

All endpoints include CORS headers for dashboard access.

## Webhook Callbacks

When `TRADEGUMI_CALLBACK_URL` is set, the bot POSTs structured events to that URL:

| Event | When | Payload |
|---|---|---|
| `signal` | Every trade signal | symbol, direction, confidence, strategy, LR values, mode |
| `mode_change` | Mode switched via API | new mode, previous mode |
| `rescan` | Watchlist re-scan completes | trigger type (full/periodic) |
| `closed_market` | All markets close | day name, message |
| `trade_open` | Position opened (future) | trade details |
| `trade_close` | Position closed (future) | trade details |

Webhook receiver runs on DockeGumi at `:8198` for automated orchestration.

## Run Modes

| Mode | Signals | Execution | Use When |
|---|---|---|---|
| `alert_only` | ✅ Discord only | ❌ None | Initial testing — see what fires without risk |
| `demo` | ✅ Discord | ✅ Oanda demo account | Forward testing — real market, fake money |
| `live` | ✅ Discord | ✅ MatchTrader prop account | Stage 2 — live prop firm trading |

**Start with `alert_only`.** Run it for 1-2 weeks. Review signal quality and Layer 2 confidence scores. Then switch to `demo` from the dashboard.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OANDA_API_KEY` | *(required)* | Oanda v20 API token |
| `OANDA_ACCOUNT_ID` | *(required)* | Oanda account ID |
| `OANDA_BASE_URL` | `https://api-fxpractice.oanda.com` | Practice URL (change for live) |
| `DISCORD_WEBHOOK_URL` | *(required)* | Discord webhook for trade alerts |
| `TRADEGUMI_MODE` | `alert_only` | alert_only / demo / live |
| `TRADEGUMI_CALLBACK_URL` | *(optional)* | DockeGumi webhook URL for orchestration |
| `TRADEGUMI_API_PORT` | `8199` | API server port |
| `MAX_OPEN_POSITIONS` | `5` | Max simultaneous positions |
| `CTI_PROGRAM` | `challenge` | challenge (2-step) or instant (instant funding) |
| `CTI_PHASE` | `1` | 1 = Phase 1 (10%), 2 = Phase 2 (5%), 3 = Funded (10%) |
| `CTI_DAILY_LOSS_PCT` | `0.05` | 5% daily loss limit |
| `CTI_MAX_DD_PCT` | `0.10` | 10% max drawdown |
| `RISK_PER_TRADE` | `0.0025` | 0.25% account risk per trade |
| `SL_ATR_MULTIPLIER` | `3` | Stop loss = 3× ATR |
| `TP_ATR_MULTIPLIER` | `12` | Take profit = 12× ATR (1:4 R:R) |

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
| Indicator | Parameters | BUY Condition | SELL Condition |
|---|---|---|---|
| **StochRSI** | 14,14,3,3 | k prev-3 min < 30, k > d | k prev-3 max > 70, k < d |
| **MACD** | 12,26,9 | Histogram > prev-5 min | Histogram < prev-5 max |
| **Keltner Channel** | 20, 1.5× EMA | Last-5 low ≤ KC middle min | Last-5 high ≥ KC middle max |
| **Candlestick** *(optional)* | — | Engulfing, Hammer | Shooting Star, Engulfing |

Each indicator also produces a **0-1 strength score** (Layer 2 quality scoring). The weighted sum becomes the signal confidence percentage.

### Layer 3 — Risk Management
- Position size = 0.25% account risk ÷ (ATR × SL multiplier × lot size)
- SL = 3× ATR from entry
- TP = 12× ATR from entry (1:4 risk:reward)
- Trailing SL: 4-tier system that tightens as profit grows (3× → 2× → 1.5× → 1× ATR at 0R → 1.5R → 3R → 5R)
- Max 5 open positions

## Session Rules

| Asset Class | Trading Hours (ET) | Notes |
|---|---|---|
| Forex | Mon–Fri 00:00–16:30 | 16:30–19:00 break (swap blackout) |
| Indices | Mon–Fri 00:00–16:30 | 16:30–18:30 break |
| Crypto | 24/7 | Low priority — doesn't fit session model |
| All | — | No new entries during swap blackout |

## File Structure

```
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

## Docker Deployment (Planned)

TradeGumi is designed to run containerized on TrueNAS or any Docker host. The bot + dashboard + API server will be a single `docker-compose` stack. Webhook callbacks enable DockeGumi orchestration even when running on a separate machine.

```yaml
# Planned docker-compose.yml
services:
  tradegumi-bot:
    build: .
    ports:
      - "8199:8199"  # API server
    env_file: .env
    volumes:
      - tradegumi-data:/app/data

  tradegumi-dashboard:
    build: ./dashboard
    ports:
      - "3000:3000"  # Dashboard
    environment:
      - NEXT_PUBLIC_API_URL=http://tradegumi-bot:8199
    depends_on:
      - tradegumi-bot
```

## Oanda Setup

1. **Create a demo account**: [Oanda fxTrade Practice](https://fxtrade.oanda.com/your_account/fxtrade/register/gate)
2. **Generate API token**: Log in → Account Management Portal → "Manage API Access" → Generate token
3. **Find your account ID**: Shown in the Oanda dashboard or API response
4. **Add to `.env`**: `OANDA_API_KEY` and `OANDA_ACCOUNT_ID`

Oanda API reference: https://developer.oanda.com/rest-live-v20/introduction/

## Stage 2 Roadmap

- [ ] MatchTrader REST client implementation
- [ ] `TRADEGUMI_MODE=live` unlock
- [ ] Docker Compose deployment for TrueNAS
- [ ] Tiered risk table (from Risk_Management_Rules.docx) replacing flat 0.25%
- [ ] Dynamic position sizing (Layer 3 — after positive expectancy validated)
- [ ] Automated daily performance reporting to Discord