"""Configuration for TradeGumi.

All values sourced from environment variables or .env file. No hardcoded secrets.
"""
import os
from pathlib import Path

# Load .env file from project root (CTI_Scripts/.env)
_project_root = Path(__file__).resolve().parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        # python-dotenv not installed — manual fallback
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

# ── Oanda ──────────────────────────────────────────────────────────────────────
OANDA_API_KEY = os.getenv("OANDA_API_KEY", "")
OANDA_ACCOUNT_ID = os.getenv("OANDA_ACCOUNT_ID", "")
OANDA_BASE_URL = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com").rstrip("/")
OANDA_STREAM_URL = os.getenv("OANDA_STREAM_URL", "https://stream-fxpractice.oanda.com").rstrip("/")

# ── Discord ─────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN   = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_USER_ID     = os.getenv("DISCORD_USER_ID", "")

# ── Signal Journal ───────────────────────────────────────────────────────────
# Token required to access the /journal page on the dashboard.
JOURNAL_TOKEN = os.getenv("JOURNAL_TOKEN", "")

# ── Volatility Shock Filter ─────────────────────────────────────────────────
VOLATILITY_SHOCK_ENABLED = os.getenv("VOLATILITY_SHOCK_ENABLED", "true").lower() in ("true", "1", "yes")
SHOCK_CANDLE_ATR_MULTIPLE = float(os.getenv("SHOCK_CANDLE_ATR_MULTIPLE", "3.0"))
SHOCK_2_BAR_ATR_MULTIPLE = float(os.getenv("SHOCK_2_BAR_ATR_MULTIPLE", "4.0"))
SHOCK_3_BAR_ATR_MULTIPLE = float(os.getenv("SHOCK_3_BAR_ATR_MULTIPLE", "5.0"))
SHOCK_SUPPRESSION_CANDLES = int(os.getenv("SHOCK_SUPPRESSION_CANDLES", "3"))
SHOCK_LOOKBACK_CANDLES = int(os.getenv("SHOCK_LOOKBACK_CANDLES", "3"))
SHOCK_M5_TRUE_RANGE_ATR_MULTIPLE = float(os.getenv("SHOCK_M5_TRUE_RANGE_ATR_MULTIPLE", "4.0"))
SHOCK_M15_TRUE_RANGE_ATR_MULTIPLE = float(os.getenv("SHOCK_M15_TRUE_RANGE_ATR_MULTIPLE", "3.5"))
SHOCK_BODY_ATR_MULTIPLE = float(os.getenv("SHOCK_BODY_ATR_MULTIPLE", "3.0"))
SHOCK_BODY_RANGE_ATR_MULTIPLE = float(os.getenv("SHOCK_BODY_RANGE_ATR_MULTIPLE", "3.5"))
SHOCK_M5_SUPPRESSION_CANDLES = int(os.getenv("SHOCK_M5_SUPPRESSION_CANDLES", "4"))
SHOCK_M15_SUPPRESSION_CANDLES = int(os.getenv("SHOCK_M15_SUPPRESSION_CANDLES", "3"))

# Strategy diagnostics
STRATEGY_METRICS_RETENTION_DAYS = int(os.getenv("STRATEGY_METRICS_RETENTION_DAYS", "90"))
STRATEGY_METRICS_DEFAULT_DAYS = int(os.getenv("STRATEGY_METRICS_DEFAULT_DAYS", "7"))
STRATEGY_METRICS_MAX_OPPORTUNITIES = int(os.getenv("STRATEGY_METRICS_MAX_OPPORTUNITIES", "1000"))
SIGNAL_SETUP_GROUP_WINDOW_MINUTES = int(os.getenv("SIGNAL_SETUP_GROUP_WINDOW_MINUTES", "10"))
SIGNAL_ENTRY_TOLERANCE_ATR = float(os.getenv("SIGNAL_ENTRY_TOLERANCE_ATR", "0.25"))
SIGNAL_STALE_BARS = int(os.getenv("SIGNAL_STALE_BARS", "3"))

# TradeGumi loop cadence and lightweight performance logging.
# Defaults preserve fast live observation and intrabar signal evaluation.
TRADEGUMI_PRICE_POLL_SECONDS = float(os.getenv("TRADEGUMI_PRICE_POLL_SECONDS", "1"))
TRADEGUMI_SIGNAL_ENGINE_SECONDS = float(os.getenv("TRADEGUMI_SIGNAL_ENGINE_SECONDS", "5"))
TRADEGUMI_LOOP_STATE_WRITE_SECONDS = float(os.getenv("TRADEGUMI_LOOP_STATE_WRITE_SECONDS", "5"))
TRADEGUMI_WATCHLIST_RELOAD_SECONDS = float(os.getenv("TRADEGUMI_WATCHLIST_RELOAD_SECONDS", "60"))
TRADEGUMI_PERF_LOG_SECONDS = float(os.getenv("TRADEGUMI_PERF_LOG_SECONDS", "60"))
TRADEGUMI_PERF_ENABLED = os.getenv("TRADEGUMI_PERF_ENABLED", "true").lower() in ("true", "1", "yes")

# Market data provider mode. Streaming is the default for Oanda, with REST
# polling kept as the fallback path when streaming is unavailable or disabled.
TRADEGUMI_MARKET_DATA_MODE = os.getenv("TRADEGUMI_MARKET_DATA_MODE", "streaming").strip().lower()
TRADEGUMI_STREAM_RECONNECT_SECONDS = float(os.getenv("TRADEGUMI_STREAM_RECONNECT_SECONDS", "5"))
TRADEGUMI_STREAM_HEARTBEAT_TIMEOUT_SECONDS = float(os.getenv("TRADEGUMI_STREAM_HEARTBEAT_TIMEOUT_SECONDS", "15"))
TRADEGUMI_STREAM_BACKOFF_MAX_SECONDS = float(os.getenv("TRADEGUMI_STREAM_BACKOFF_MAX_SECONDS", "60"))
TRADEGUMI_STREAM_MAX_RECONNECT_ATTEMPTS = int(os.getenv("TRADEGUMI_STREAM_MAX_RECONNECT_ATTEMPTS", "5"))

# ── Database / Cache ────────────────────────────────────────────────────────
# Postgres is required (durable source of truth); there is no SQLite fallback.
TRADEGUMI_DATABASE_URL = os.getenv("TRADEGUMI_DATABASE_URL", "")
TRADEGUMI_REDIS_URL = os.getenv("TRADEGUMI_REDIS_URL", "")
TRADEGUMI_POSTGRES_PASSWORD = os.getenv("TRADEGUMI_POSTGRES_PASSWORD", "")

# ── Webhook Callback (DockeGumi / external orchestrator) ────────────────────
# TradeGumi POSTs structured signal data here on every signal event.
# Set to DockeGumi's endpoint (e.g. http://10.0.0.210:8198/api/tradegumi/webhook)
CALLBACK_URL = os.getenv("TRADEGUMI_CALLBACK_URL", "") 

# ── Mode ─────────────────────────────────────────────────────────────────────
# alert_only | demo | live
TRADEGUMI_MODE = os.getenv("TRADEGUMI_MODE", "alert_only").lower()

# ── Execution ────────────────────────────────────────────────────────────────
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "5"))
RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.0025"))  # 0.25%

# ── ATR / SL / TP ───────────────────────────────────────────────────────────
SL_ATR_MULTIPLIER = float(os.getenv("SL_ATR_MULTIPLIER", "3"))
TP_ATR_MULTIPLIER = float(os.getenv("TP_ATR_MULTIPLIER", "12"))

# ── CTI-v1.1 Dual-Path Thresholds ──────────────────────────────────────────
# Continuation path (CTI-v1.1-continuation-test)
CONTINUATION_KC_PROXIMITY_ATR = float(os.getenv("CONTINUATION_KC_PROXIMITY_ATR", "0.25"))
CONTINUATION_STRUCTURE_BARS = int(os.getenv("CONTINUATION_STRUCTURE_BARS", "5"))
CONTINUATION_MANAGEMENT_ENABLED = os.getenv("CONTINUATION_MANAGEMENT_ENABLED", "true").lower() in ("true", "1", "yes")
CONTINUATION_MANAGEMENT_BE_TRIGGER_R = float(os.getenv("CONTINUATION_MANAGEMENT_BE_TRIGGER_R", "1.0"))
CONTINUATION_MANAGEMENT_PROFIT_PROTECT_TRIGGER_R = float(os.getenv("CONTINUATION_MANAGEMENT_PROFIT_PROTECT_TRIGGER_R", "1.5"))
CONTINUATION_MANAGEMENT_PROFIT_PROTECT_OFFSET_R = float(os.getenv("CONTINUATION_MANAGEMENT_PROFIT_PROTECT_OFFSET_R", "0.1"))
CONTINUATION_MANAGEMENT_TP_EXTENSION_MULTIPLE_R = float(os.getenv("CONTINUATION_MANAGEMENT_TP_EXTENSION_MULTIPLE_R", "0.5"))
CONTINUATION_MANAGEMENT_MAX_TP_EXTENSIONS = int(os.getenv("CONTINUATION_MANAGEMENT_MAX_TP_EXTENSIONS", "2"))
CONTINUATION_MANAGEMENT_MAX_TARGET_R = float(os.getenv("CONTINUATION_MANAGEMENT_MAX_TARGET_R", "4.0"))
# Pullback path relaxed thresholds
PULLBACK_KC_PROXIMITY_ATR = float(os.getenv("PULLBACK_KC_PROXIMITY_ATR", "0.25"))
PULLBACK_STOCH_RSI_RELAXED = os.getenv("PULLBACK_STOCH_RSI_RELAXED", "true").lower() in ("true", "1", "yes")
PULLBACK_ENABLED = os.getenv("PULLBACK_ENABLED", "true").lower() in ("true", "1", "yes")
PULLBACK_15M_MEMORY_CANDLES = int(os.getenv("PULLBACK_15M_MEMORY_CANDLES", "4"))
PULLBACK_15M_STRONG_OPPOSITE_MULTIPLIER = float(os.getenv("PULLBACK_15M_STRONG_OPPOSITE_MULTIPLIER", "1.25"))
PULLBACK_REQUIRE_1H_ALIGNMENT = os.getenv("PULLBACK_REQUIRE_1H_ALIGNMENT", "true").lower() in ("true", "1", "yes")
PULLBACK_STRUCTURE_LOOKBACK_BARS = int(os.getenv("PULLBACK_STRUCTURE_LOOKBACK_BARS", "12"))
PULLBACK_KC_BREAK_LOOKBACK_BARS = int(os.getenv("PULLBACK_KC_BREAK_LOOKBACK_BARS", "10"))
PULLBACK_KC_MIDLINE_TOLERANCE_ATR = float(os.getenv("PULLBACK_KC_MIDLINE_TOLERANCE_ATR", "0.35"))
PULLBACK_KC_MIDLINE_TOLERANCE_CHANNEL_WIDTH = float(os.getenv("PULLBACK_KC_MIDLINE_TOLERANCE_CHANNEL_WIDTH", "0.25"))
PULLBACK_STOCH_OVERSOLD = float(os.getenv("PULLBACK_STOCH_OVERSOLD", "25"))
PULLBACK_STOCH_OVERSOLD_RECENT = float(os.getenv("PULLBACK_STOCH_OVERSOLD_RECENT", "30"))
PULLBACK_STOCH_OVERBOUGHT = float(os.getenv("PULLBACK_STOCH_OVERBOUGHT", "75"))
PULLBACK_STOCH_OVERBOUGHT_RECENT = float(os.getenv("PULLBACK_STOCH_OVERBOUGHT_RECENT", "70"))
PULLBACK_TRIGGER_MAX_BODY_RANGE_RATIO = float(os.getenv("PULLBACK_TRIGGER_MAX_BODY_RANGE_RATIO", "0.33"))
PULLBACK_TRIGGER_MIN_REJECTION_WICK_RANGE_RATIO = float(os.getenv("PULLBACK_TRIGGER_MIN_REJECTION_WICK_RANGE_RATIO", "0.25"))
PULLBACK_TRIGGER_MIN_REJECTION_WICK_BODY_RATIO = float(os.getenv("PULLBACK_TRIGGER_MIN_REJECTION_WICK_BODY_RATIO", "1.0"))
PULLBACK_STOCH_MEMORY_BARS = int(os.getenv("PULLBACK_STOCH_MEMORY_BARS", "4"))
PULLBACK_MACD_HARD_BLOCK_ENABLED = os.getenv("PULLBACK_MACD_HARD_BLOCK_ENABLED", "false").lower() in ("true", "1", "yes")
# Trend bias: 1H+15M agreement only (continuation) vs full 3-TF (pullback)
CONTINUATION_TREND_REQUIRE_5M = os.getenv("CONTINUATION_TREND_REQUIRE_5M", "false").lower() in ("true", "1", "yes")

# ── Symbols ─────────────────────────────────────────────────────────────────
FOREX_MAJORS = ["EURUSD", "GBPUSD", "NZDUSD", "AUDUSD", "USDCHF", "USDCAD", "USDJPY"]
FOREX_MINORS = [
    "EURNZD", "GBPNZD", "AUDNZD", "AUDCHF", "CADCHF", "EURAUD", "GBPAUD", "NZDCHF",
    "AUDCAD", "CADJPY", "EURCHF", "GBPCHF", "NZDCAD", "AUDJPY", "CHFJPY", "EURCAD",
    "GBPCAD", "NZDJPY", "EURJPY", "GBPJPY", "EURGBP",
]
COMMODITIES = ["XAUUSD", "XAGUSD", "OIL"]
INDICES = [
    "US500", "NAS100", "US30", "DAX", "FTSE100", "F40", "JP225", "EUR50", "AUS200",
    "CHC50", "ES35", "N25", "SWI20", "RUS2000",
]
CRYPTO = ["BTCUSD", "ETHUSD", "LTCUSD", "XRPUSD"]  # SOLUSD, ADAUSD not on Oanda

ALL_SYMBOLS = FOREX_MAJORS + FOREX_MINORS + COMMODITIES + INDICES + CRYPTO

# Pre-session scanner determines daily watchlist — no hardcoded symbol restrictions
EXECUTION_SYMBOLS = ALL_SYMBOLS

JPY_SYMBOLS = [s for s in ALL_SYMBOLS if "JPY" in s]
STANDARD_SYMBOLS = [s for s in ALL_SYMBOLS if s not in JPY_SYMBOLS]

# ── Symbol Mapping (CTI → Oanda) ──────────────────────────────────────────────
# Oanda v20 instrument names per https://developer.oanda.com/rest-live-v20/instrument-ep/
# Corrected per task spec — verify CFD indices on practice account if they 400.
OANDA_SYMBOL_MAP = {
    # Indices — Oanda CFD instrument names
    "US500":    "SPX500_USD",
    "NAS100":   "NAS100_USD",
    "US30":     "US30_USD",
    "DAX":      "DE30_EUR",
    "FTSE100":  "UK100_GBP",
    "F40":      "FR40_EUR",
    "JP225":    "JP225_USD",
    "EUR50":    "EU50_EUR",
    "AUS200":   "AU200_AUD",
    "CHC50":    "CHF50_CHF",
    "ES35":     "ESP35_EUR",
    "N25":      "NL25_EUR",
    "SWI20":    "CH20_CHF",
    "RUS2000":  "RUS200_USD",
    # Commodities
    "XAUUSD": "XAU_USD",
    "XAGUSD": "XAG_USD",
    "OIL":    "WTICO_USD",   # WTI Crude; BCO_USD = Brent Crude
    # Crypto — Oanda uses underscore format
    "BTCUSD": "BTC_USD",
    "ETHUSD": "ETH_USD",
    "LTCUSD": "LTC_USD",
    "XRPUSD": "XRP_USD",
    # SOLUSD, ADAUSD — NOT offered on Oanda; excluded from CRYPTO list above
}

# Reverse map: Oanda instrument → CTI symbol
CTI_SYMBOL_MAP = {v: k for k, v in OANDA_SYMBOL_MAP.items()}

# Oanda instruments confirmed unavailable on this account
# Populated at startup by querying GET /v3/accounts/{id}/instruments
UNAVAILABLE_INSTRUMENTS: set[str] = set()


def to_oanda_symbol(symbol: str) -> str:
    """Convert CTI symbol to Oanda v20 format.

    Uses explicit mapping table first, then falls back to 3-char split.
    EURUSD → EUR_USD, US500 → SPX500_USD, XAUUSD → XAU_USD
    """
    if symbol in OANDA_SYMBOL_MAP:
        return OANDA_SYMBOL_MAP[symbol]
    # Default: split after first 3 chars (works for standard forex: EURUSD, GBPJPY, etc.)
    return symbol[:3] + "_" + symbol[3:]


def from_oanda_symbol(oanda_sym: str) -> str:
    """Convert Oanda v20 format back to CTI symbol.

    EUR_USD → EURUSD, SPX500_USD → US500, XAU_USD → XAUUSD
    """
    if oanda_sym in CTI_SYMBOL_MAP:
        return CTI_SYMBOL_MAP[oanda_sym]
    return oanda_sym.replace("_", "")


# ── Chop / Regime Filter ────────────────────────────────────────────────────
CHOP_FILTER_ENABLED = os.getenv("CHOP_FILTER_ENABLED", "true").lower() in ("true", "1", "yes")
CHOP_OPPOSITE_SIGNAL_SUPPRESSION_CANDLES = int(os.getenv("CHOP_OPPOSITE_SIGNAL_SUPPRESSION_CANDLES", "6"))
CHOP_DIRECTION_FLIP_LOOKBACK_CANDLES = int(os.getenv("CHOP_DIRECTION_FLIP_LOOKBACK_CANDLES", "6"))
CHOP_MAX_DIRECTION_FLIPS = int(os.getenv("CHOP_MAX_DIRECTION_FLIPS", "1"))
CHOP_REQUIRE_15M_STRENGTH_MULTIPLIER = float(os.getenv("CHOP_REQUIRE_15M_STRENGTH_MULTIPLIER", "1.25"))
CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES = int(os.getenv("CHOP_REQUIRE_TREND_PERSISTENCE_CANDLES", "1"))
# When true, the 15M LR must point in the same direction as the 1H trend for the
# chop filter to treat it as a healthy bridge. A soft/opposing 15M during a
# normal pullback still gets checked, but an aligned (or flat) 15M is not blocked.
CHOP_REQUIRE_15M_DIRECTION_ALIGNMENT = os.getenv("CHOP_REQUIRE_15M_DIRECTION_ALIGNMENT", "true").lower() in ("true", "1", "yes")

# ── CTI Challenge Rules ────────────────────────────────────────────────────
# CTI_CHALLENGE_TYPE env var:
#   1-step = 1-Step Challenge (8% profit target, single phase)
#   2-step = 2-Step Challenge (Phase 1: 10%, Phase 2: 5%)
#   instant = Instant Funding (10% profit target)
#
# CTI_PHASE env var:
#   1 = Phase 1
#   2 = Phase 2
#   3 = Funded (only for 2-step; instant uses phase 3 for "Funded")
#
# Tier auto-detection (from balance):
#   Challenge 1-Step / 2-Step tiers: $2,500 | $3,750 | $5,000 | $7,500 | $10,000 | $15,000 | $20,000 | $25,000 | $37,500 | $50,000 | $75,000 | $100,000 | $112,500 | $125,000 | $150,000 | $175,000 | $200,000
#   Instant tiers: $5,000 | $10,000 | $20,000 | $40,000 | $80,000 | $160,000 | $320,000 | $640,000 | $1,000,000 | $2,000,000
#
# All accounts: 5% daily loss limit, 10% max DD, 1:30 leverage

CTI_CHALLENGE_TYPE = os.getenv("CTI_CHALLENGE_TYPE", "2-step").lower()  # "1-step", "2-step", or "instant"
CTI_PHASE = int(os.getenv("CTI_PHASE", "1"))  # 1=Phase 1, 2=Phase 2, 3=Funded
CTI_PROGRAM = os.getenv("CTI_PROGRAM", "challenge").lower()  # "challenge" or "instant"

CTI_DAILY_LOSS_PCT = float(os.getenv("CTI_DAILY_LOSS_PCT", "0.05"))    # 5%
CTI_MAX_DD_PCT = float(os.getenv("CTI_MAX_DD_PCT", "0.10"))             # 10%

# Optional: Override auto-detected funding tier with a fixed value
# Format: comma-separated list like "50000,100000,150000" or single value like "100000"
CTI_FUNDING_TIER_ENV = os.getenv("CTI_FUNDING_TIER", "")

# Tier lookup tables
CTI_CHALLENGE_TIERS = [2500, 3750, 5000, 7500, 10000, 15000, 20000, 25000, 37500, 50000, 75000, 100000, 112500, 125000, 150000, 175000, 200000]
CTI_INSTANT_TIERS  = [5000, 10000, 20000, 40000, 80000, 160000, 320000, 640000, 1000000, 2000000]


def _detect_tier_from_balance(balance: float) -> int:
    """Auto-detect funding tier from current balance."""
    if CTI_CHALLENGE_TYPE == "instant":
        tiers = CTI_INSTANT_TIERS
    else:
        tiers = CTI_CHALLENGE_TIERS
    return next((t for t in tiers if balance <= t), tiers[-1])


def get_cti_tier(balance: float) -> dict:
    """Get CTI parameters based on account balance and configured challenge type.

    Tier is auto-detected from balance by default. Can be overridden with
    CTI_FUNDING_TIER env var for fixed funding tier regardless of balance.
    Dollar amounts are calculated dynamically: e.g. daily loss = 5% of tier.
    """
    # Auto-detect tier from balance, or use configured funding tier
    if CTI_FUNDING_TIER_ENV:
        # Use configured funding tier (comma-separated list or single value)
        try:
            tier_values = [int(t.strip()) for t in CTI_FUNDING_TIER_ENV.split(",")]
            tier_dollars = tier_values[0] if len(tier_values) == 1 else max(tier_values)
        except ValueError:
            # Fallback to auto-detection if parsing fails
            tier_dollars = _detect_tier_from_balance(balance)
    else:
        tier_dollars = _detect_tier_from_balance(balance)
    
    tier_name = f"${tier_dollars:,.0f}"

    if CTI_CHALLENGE_TYPE == "instant":
        phase_label = "Instant Funded" if CTI_PHASE == 3 else "Instant"
        active_target_pct = 0.10  # 10% for all instant accounts
    elif CTI_CHALLENGE_TYPE == "1-step":
        phase_label = "1-Step Funded" if CTI_PHASE == 3 else "1-Step Challenge"
        active_target_pct = 0.08  # 8% for 1-step
    elif CTI_PHASE == 1:
        phase_label = "Phase 1"
        active_target_pct = 0.10  # 10%
    elif CTI_PHASE == 2:
        phase_label = "Phase 2"
        active_target_pct = 0.05  # 5%
    else:  # Phase 3 = Funded
        phase_label = "Funded"
        active_target_pct = 0.10  # 10% first payout target

    return {
        "challenge_type": CTI_CHALLENGE_TYPE,
        "program": "challenge" if CTI_CHALLENGE_TYPE != "instant" else "instant",
        "phase": CTI_PHASE,
        "phase_label": phase_label,
        "tier_dollars": tier_dollars,
        "tier_name": tier_name,
        "active_target_pct": active_target_pct,
        "daily_loss_pct": CTI_DAILY_LOSS_PCT,
        "max_dd_pct": CTI_MAX_DD_PCT,
    }


# ── Validate ─────────────────────────────────────────────────────────────────
def validate_config():
    """Raise if required config is missing for the current mode."""
    errors = []
    if not OANDA_API_KEY:
        errors.append("OANDA_API_KEY is required")
    if not OANDA_ACCOUNT_ID:
        errors.append("OANDA_ACCOUNT_ID is required")
    if TRADEGUMI_MODE not in ("alert_only", "demo", "live"):
        errors.append(f"Invalid TRADEGUMI_MODE={TRADEGUMI_MODE}")
    if TRADEGUMI_MARKET_DATA_MODE not in ("streaming", "polling"):
        errors.append(f"Invalid TRADEGUMI_MARKET_DATA_MODE={TRADEGUMI_MARKET_DATA_MODE}")
    if not TRADEGUMI_DATABASE_URL:
        errors.append(
            "TRADEGUMI_DATABASE_URL is required — Postgres is the durable store "
            "and there is no SQLite fallback"
        )
    if errors:
        raise ValueError("Config errors: " + "; ".join(errors))
