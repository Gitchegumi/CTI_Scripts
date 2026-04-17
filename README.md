# TradeGumi — CTI Signal Engine

Pure Python signal engine for the City Traders Imperium (CTI) prop firm strategy. Uses Oanda v20 REST API for market data and demo execution. Discord alerts for all signals. Designed to swap to MatchTrader for live prop firm execution with zero signal logic changes.

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

Copy the template and fill in your credentials:

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
# alert_only = signals only, no execution (start here)
# demo = signals + Oanda execution on demo account
# live = signals + MatchTrader execution (Stage 2, not yet implemented)
TRADEGUMI_MODE=alert_only
```

> **`.env` is gitignored.** Your keys will never be committed to the repo.

### 3. Run it

```bash
cd src
poetry run python -m tradegumi.main
```

Or without Poetry:

```bash
cd src
python -m tradegumi.main
```

The engine will:
1. Run the **pre-session scanner** to rank all CTI-allowed symbols into Tier 1 (trade), Tier 2 (alert only), or Below Threshold (skip)
2. Post the ranked watchlist to Discord
3. Start the main loop — checking each Tier 1 symbol every 60 seconds during trading hours
4. Post every signal to Discord (even blocked ones, with the block reason logged)
5. Manage trailing stops on open positions (demo/live modes)

## Run Modes

| Mode | Signals | Execution | Use When |
|---|---|---|---|
| `alert_only` | ✅ Discord only | ❌ None | Initial testing — see what fires without risk |
| `demo` | ✅ Discord | ✅ Oanda demo account | Forward testing — real market, fake money |
| `live` | ✅ Discord | ✅ MatchTrader prop account | Stage 2 — live prop firm trading |

**Start with `alert_only`.** Run it for 1-2 weeks. Review signal quality and Layer 2 confidence scores. Then switch to `demo`.

## Configuration

All settings are in `.env` or environment variables. Defaults are sane for CTI strategy:

| Variable | Default | Description |
|---|---|---|
| `OANDA_API_KEY` | *(required)* | Your Oanda v20 API token |
| `OANDA_ACCOUNT_ID` | *(required)* | Your Oanda account ID |
| `OANDA_BASE_URL` | `https://api-fxpractice.oanda.com` | Practice URL (change for live) |
| `DISCORD_WEBHOOK_URL` | *(required)* | Discord webhook for trade alerts |
| `TRADEGUMI_MODE` | `alert_only` | alert_only / demo / live |
| `MAX_OPEN_POSITIONS` | `5` | Max simultaneous positions |
| `CTI_PROGRAM` | `challenge` | `challenge` (2-step) or `instant` (instant funding) |
| `CTI_PHASE` | `1` | `1` = Phase 1 (10% target), `2` = Phase 2 (5% target), `3` = Funded (10% target) |
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
Runs at startup and every morning at 06:30 ET. Ranks all symbols by:
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

## Architecture

```
CTI_Scripts/
├── .env.example            # Template for your API keys
├── requirements.txt        # pip deps (Poetry preferred)
├── README.md
└── src/
    ├── pyproject.toml      # Poetry project (both packages)
    ├── tradegumi/           # Signal engine (active development)
    │   ├── main.py          # Entry point, mode switch, 60s main loop
    │   ├── config.py        # .env loader + all configuration
    │   ├── api/
    │   │   ├── base_client.py    # Abstract ExecutionClient interface
    │   │   ├── oanda_client.py    # Oanda v20 REST implementation
    │   │   └── matchtrader_client.py  # Stub (Stage 2)
    │   ├── indicators.py    # pandas_ta wrappers + Layer 2 scoring
    │   ├── signal_engine.py  # Trend filter + 4-layer stack + confidence
    │   ├── pre_session_scanner.py  # Morning ranked watchlist (Layer 1)
    │   ├── alerts.py        # Discord webhook alerter
    │   ├── risk.py          # Position sizing, daily drawdown checks
    │   ├── session_rules.py # Trading hours, swap blackout, DOW bias
    │   └── trailing_sl.py   # 4-tier ATR trailing stop manager
    ├── trading_scripts/     # Legacy MT5/MetaTrader scripts (reference)
    └── backtesting/         # Historical data + backtest notebooks
```

**Provider swap:** Oanda and MatchTrader both implement the same `ExecutionClient` interface. Stage 2 = swap the client, keep the signal engine.

## Oanda Setup

1. **Create a demo account**: [Oanda fxTrade Practice](https://fxtrade.oanda.com/your_account/fxtrade/register/gate)
2. **Generate API token**: Log in → Account Management Portal → "Manage API Access" → Generate token
3. **Find your account ID**: Shown in the Oanda dashboard or API response
4. **Add to `.env`**: `OANDA_API_KEY` and `OANDA_ACCOUNT_ID`

Oanda API reference: https://developer.oanda.com/rest-live-v20/introduction/

## Discord Webhook Setup

1. Open your Discord server settings → Integrations → Webhooks
2. Create a webhook in the channel where you want trade alerts
3. Copy the webhook URL into `DISCORD_WEBHOOK_URL` in your `.env`

## Dependencies

**Poetry (recommended):**
```bash
cd src && poetry install
```

**pip:**
```bash
pip install -r requirements.txt
```

Core: pandas, pandas_ta, requests, python-dotenv, pytz

## Stage 2 Roadmap

- [ ] MatchTrader REST client implementation
- [ ] `TRADEGUMI_MODE=live` unlock
- [ ] Tiered risk table (from Risk_Management_Rules.docx) replacing flat 0.25%
- [ ] Dynamic position sizing (Layer 3 — after positive expectancy validated)
- [ ] Automated daily performance reporting to Discord