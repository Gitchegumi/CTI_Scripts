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
OANDA_BASE_URL = os.getenv("OANDA_BASE_URL", "https://api-fxpractice.oanda.com")
OANDA_STREAM_URL = os.getenv("OANDA_STREAM_URL", "https://stream-fxpractice.oanda.com")

# ── Discord ─────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN   = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_USER_ID     = os.getenv("DISCORD_USER_ID", "")

# ── Signal Journal ───────────────────────────────────────────────────────────
# Token required to access the /journal page on the dashboard.
JOURNAL_TOKEN = os.getenv("JOURNAL_TOKEN", "")

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


# ── CTI Challenge Rules ────────────────────────────────────────────────────
# All CTI accounts use the same percentages regardless of size.
# The bot reads balance from Oanda API and calculates dollar amounts dynamically.
# No hardcoded tier sizes — everything derives from live balance.
#
# CTI_PHASE env var:
#   1 = Phase 1 (10% profit target)
#   2 = Phase 2 (5% profit target)
#   3 = Funded (5% first payout target, then scaling)
#
# CTI_PROGRAM env var:
#   challenge = 2-Step Challenge (default)
#   instant = Instant Funding
#
# Both programs: 5% daily loss limit, 10% max DD, 1:30 leverage

CTI_PROGRAM = os.getenv("CTI_PROGRAM", "challenge").lower()  # "challenge" or "instant"
CTI_PHASE = int(os.getenv("CTI_PHASE", "1"))  # 1=Phase 1, 2=Phase 2, 3=Funded

CTI_DAILY_LOSS_PCT = float(os.getenv("CTI_DAILY_LOSS_PCT", "0.05"))    # 5%
CTI_MAX_DD_PCT = float(os.getenv("CTI_MAX_DD_PCT", "0.10"))             # 10%


def get_cti_tier(balance: float) -> dict:
    """Get CTI parameters based on account balance and configured phase.

    All CTI accounts use the same percentages. Balance comes from Oanda API.
    Dollar amounts are calculated dynamically: e.g. daily loss = 5% of balance.

    When CTI issues a new (scaled) account, the balance changes automatically
    and the bot picks up the correct dollar amounts.
    """
    if CTI_PROGRAM == "instant":
        phase_label = "Instant Funded"
        active_target_pct = 0.10  # 10% for all instant accounts
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
        "program": CTI_PROGRAM,
        "phase": CTI_PHASE,
        "phase_label": phase_label,
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
    if errors:
        raise ValueError("Config errors: " + "; ".join(errors))
