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
