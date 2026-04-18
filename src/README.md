<div align="center">

# TradeGumi — CTI Signal Engine

<img src="https://api.dicebear.com/9.x/icons/svg?seed=Midnight&backgroundColor[]&icon=lightbulb" height="100" alt="avatar" />

[Overview](#-overview) •
[Features](#-features) •
[Getting Started](#-getting-started) •
[Usage](#-usage) •
[Architecture](#-architecture) •
[API](#-api) •
[Configuration](#-configuration)

</div>

---

## 🎯 Overview

TradeGumi is a real-time CTI signal engine for the City Traders Imperium (CTI) prop firm strategy. It runs a dual-cadence main loop — 1-second price ticker and 5-second signal engine — against the Oanda v20 REST API, with Discord alerts, a live dashboard, and a REST API for remote configuration.

Designed to swap to MatchTrader for live prop firm execution with zero signal logic changes (same `ExecutionClient` interface).

## ✨ Features

- **4-Layer Signal Stack** — StochRSI + MACD + Keltner Channel + Candlestick confirmation
- **Dual-Cadence Loop** — 1s price ticker for live bid/ask, 5s signal engine for indicators
- **30-Min Re-Ranking** — Watchlist re-scans every 30 min during market hours
- **Pre-Session Scanner** — Daily ranked watchlist based on ADR, volatility, breakout probability
- **Trailing Stop Manager** — 4-tier ATR trailing SL that tightens as profit grows
- **CTI Risk Rules** — 0.25% risk per trade, 5% daily loss limit, 10% max DD
- **Discord Alerts** — Every signal, blocked signal, and watchlist update
- **REST API** — Change mode, program, phase, trigger re-scans from the dashboard
- **Webhook Callbacks** — Structured events sent to DockeGumi for orchestration
- **Live Dashboard** — Next.js dashboard with real-time prices, signals, trades, and config

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- Poetry (recommended) or pip
- Oanda practice account + API key
- Discord webhook URL

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/Gitchegumi/CTI_Scripts.git
   cd CTI_Scripts/src
   ```

2. Install dependencies:

   ```bash
   poetry install
   ```

3. Create your `.env` file:

   ```bash
   cp ../.env.example ../.env
   ```

   Fill in your Oanda API key, account ID, and Discord webhook URL.

4. Run it:

   ```bash
   poetry run python -m tradegumi.main --mode alert_only
   ```

### Dashboard

```bash
cd ../dashboard
npm install
npm run build
npm start
```

Dashboard runs on `http://localhost:3000`. API server on `http://localhost:8199`.

## 📘 Usage

### Command Line

```bash
# Alert-only mode (signals only, no execution)
poetry run python -m tradegumi.main --mode alert_only

# Demo mode (signals + Oanda practice execution)
poetry run python -m tradegumi.main --mode demo

# Live mode (signals + MatchTrader execution — Stage 2)
poetry run python -m tradegumi.main --mode live
```

### Main Loop

The bot runs two loops in one process:

| Component | Interval | Purpose |
|---|---|---|
| Price ticker | 1 second | Live bid/ask for all watchlist symbols |
| Signal engine | 5 seconds | Indicators, LR slopes, signal detection |
| Loop state write | 1 second | Dashboard data (prices, trends, LR values) |
| Watchlist re-rank | 30 minutes | Re-evaluate tiers during market hours |
| Pre-session scan | 02:00 ET daily | Full re-scan + instrument availability |

### Run Modes

| Mode | Signals | Execution | Use When |
|---|---|---|---|
| `alert_only` | ✅ Discord only | ❌ None | Testing — see what fires |
| `demo` | ✅ Discord | ✅ Oanda demo | Forward testing |
| `live` | ✅ Discord | ✅ MatchTrader | Live prop firm (Stage 2) |

Mode can be changed at runtime via the dashboard or API.

## 🏗 Architecture

```
tradegumi/
├── main.py                # Entry point, dual-cadence loop, API server start
├── config.py              # .env loader + all configuration
├── api_server.py           # HTTP API (:8199) for dashboard
├── callback.py            # Webhook sender for DockeGumi orchestration
├── webhook_receiver.py    # Webhook receiver (:8198) for incoming events
├── api/
│   ├── base_client.py     # Abstract ExecutionClient interface
│   └── oanda_client.py    # Oanda v20 REST implementation
├── indicators.py          # pandas_ta wrappers + Layer 2 scoring
├── signal_engine.py       # Trend filter + 4-layer stack + confidence
├── pre_session_scanner.py # Morning ranked watchlist (Layer 1)
├── alerts.py              # Discord webhook alerter + signal persistence
├── risk.py                # Position sizing, daily drawdown checks
├── session_rules.py       # Trading hours, swap blackout, DOW bias
└── trailing_sl.py        # 4-tier ATR trailing stop manager
```

**Provider swap:** Oanda and MatchTrader both implement `ExecutionClient`. Stage 2 = swap the client, keep the signal engine.

## 📚 API

### GET Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/status` | Current mode, program, phase, runtime state |
| `GET /api/data/loop_state` | Live prices, trends, LR values |
| `GET /api/data/watchlist` | Ranked watchlist with tiers |
| `GET /api/data/signals` | Active signals |
| `GET /api/positions` | Open positions from Oanda |
| `GET /api/trades?count=N` | Closed trade history |

### POST Endpoints

| Endpoint | Body | Description |
|---|---|---|
| `POST /api/config/mode` | `{"mode": "alert_only"\|"demo"\|"live"}` | Switch trading mode |
| `POST /api/config/program` | `{"program": "challenge"\|"instant"}` | Switch CTI program |
| `POST /api/config/phase` | `{"phase": 1\|2\|3}` | Switch CTI phase |
| `POST /api/action/rescan` | `{}` | Trigger immediate watchlist re-scan |

### Webhook Callbacks

Set `TRADEGUMI_CALLBACK_URL` to receive structured events:

| Event | When | Key Payload Fields |
|---|---|---|
| `signal` | Every trade signal | symbol, direction, confidence, strategy, LR values |
| `mode_change` | Mode switched via API | mode, previous_mode |
| `rescan` | Watchlist re-scan completes | trigger (full/periodic) |
| `closed_market` | All markets close | day, message |

## ⚙️ Configuration

All settings are in `.env` or environment variables:

| Variable | Default | Description |
|---|---|---|
| `OANDA_API_KEY` | *(required)* | Oanda v20 API token |
| `OANDA_ACCOUNT_ID` | *(required)* | Oanda account ID |
| `OANDA_BASE_URL` | `https://api-fxpractice.oanda.com` | Practice (change for live) |
| `DISCORD_WEBHOOK_URL` | *(required)* | Discord webhook for alerts |
| `TRADEGUMI_MODE` | `alert_only` | alert_only / demo / live |
| `TRADEGUMI_CALLBACK_URL` | *(optional)* | DockeGumi webhook URL |
| `TRADEGUMI_API_PORT` | `8199` | API server port |
| `MAX_OPEN_POSITIONS` | `5` | Max simultaneous positions |
| `CTI_PROGRAM` | `challenge` | challenge or instant |
| `CTI_PHASE` | `1` | 1, 2, or 3 |
| `CTI_DAILY_LOSS_PCT` | `0.05` | 5% daily loss limit |
| `CTI_MAX_DD_PCT` | `0.10` | 10% max drawdown |
| `RISK_PER_TRADE` | `0.0025` | 0.25% risk per trade |
| `SL_ATR_MULTIPLIER` | `3` | Stop loss = 3× ATR |
| `TP_ATR_MULTIPLIER` | `12` | Take profit = 12× ATR |

## Strategy: CTI 4-Layer Signal Stack

Every signal passes through all four layers. All must agree:

1. **Layer 0 — Trend Filter**: LR slope on 15m + 5m must agree on direction
2. **Layer 1 — Pre-Session Scanner**: Daily ranking by ADR consumption, volatility, breakout probability
3. **Layer 2 — Signal Stack**: StochRSI + MACD + Keltner Channel + Candlestick (all must confirm)
4. **Layer 3 — Risk Management**: Position sizing, daily loss limits, trailing SL

Confidence score = weighted sum of Layer 2 indicator strengths (0–100%).

## Stage 2 Roadmap

- [ ] MatchTrader REST client implementation
- [ ] `TRADEGUMI_MODE=live` unlock
- [ ] Docker Compose deployment
- [ ] Tiered risk table replacing flat 0.25%
- [ ] Dynamic position sizing after positive expectancy validated
- [ ] Automated daily performance reporting