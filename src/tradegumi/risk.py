"""Risk management: position sizing, SL/TP, daily drawdown checks."""
from typing import Optional

from tradegumi import config
from tradegumi.api.base_client import ExecutionClient


def calc_stop_loss_price(entry_price: float, atr: float, side: str) -> float:
    """Calculate SL price.

    Args:
        entry_price: Entry price (bid for BUY, ask for SELL)
        atr: Current ATR value
        side: "BUY" or "SELL"

    Returns:
        SL price rounded to appropriate precision.
    """
    mult = config.SL_ATR_MULTIPLIER
    if side == "BUY":
        sl = entry_price - (atr * mult)
    else:
        sl = entry_price + (atr * mult)
    return round(sl, _price_decimals(entry_price))


def calc_take_profit_price(entry_price: float, atr: float, side: str) -> float:
    """Calculate TP price.

    Args:
        entry_price: Entry price
        atr: Current ATR value
        side: "BUY" or "SELL"

    Returns:
        TP price rounded to appropriate precision.
    """
    mult = config.TP_ATR_MULTIPLIER
    if side == "BUY":
        tp = entry_price + (atr * mult)
    else:
        tp = entry_price - (atr * mult)
    return round(tp, _price_decimals(entry_price))


def calc_position_units(
    account_balance: float,
    entry_price: float,
    stop_loss_price: float,
    symbol: str,
) -> int:
    """Calculate Oanda position size in units (not lots).

    For Oanda, 1 unit = 1 unit of the base currency.
    A "lot" of 0.05 = 5,000 units (not 100,000).

    Risk = account_balance * RISK_PER_TRADE
    Units = Risk / (SL distance in account currency per unit)

    For USD-quote pairs (EUR/USD): loss per unit = SL distance (in USD)
    For USD-base pairs (USD/JPY): loss per unit = SL distance / entry_price (converted to USD)

    Args:
        account_balance: Current account balance
        entry_price: Price at entry
        stop_loss_price: Calculated SL price
        symbol: Symbol for pip/point value selection

    Returns:
        Position size in units (rounded to whole units).
    """
    risk_amount = account_balance * config.RISK_PER_TRADE
    sl_distance = abs(entry_price - stop_loss_price)
    if sl_distance == 0:
        raise ValueError(f"SL distance is zero for {symbol}")

    # For USD-base pairs (USDJPY, USDCHF, USDCAD), convert SL distance to USD terms
    if symbol.startswith("USD"):
        # SL distance is in quote currency; convert to USD
        units = risk_amount * entry_price / sl_distance
    else:
        # SL distance is directly in USD (for EUR/USD, GBP/USD, etc.)
        units = risk_amount / sl_distance

    return max(1, int(round(units)))


def calc_lot_size(
    account_balance: float,
    entry_price: float,
    stop_loss_price: float,
    symbol: str,
) -> float:
    """Calculate lot size for a trade.

    Risk = account_balance * RISK_PER_TRADE
    Lot size = Risk / (entry_price - stop_loss_price) / lot_divisor

    Args:
        account_balance: Current account balance
        entry_price: Price at entry
        stop_loss_price: Calculated SL price
        symbol: Symbol for lot divisor selection

    Returns:
        Volume in lots.
    """
    risk_amount = account_balance * config.RISK_PER_TRADE
    sl_distance = abs(entry_price - stop_loss_price)
    if sl_distance == 0:
        raise ValueError(f"SL distance is zero for {symbol}")

    if symbol in config.JPY_SYMBOLS:
        divisor = 1000
    elif symbol in config.STANDARD_SYMBOLS:
        divisor = 100_000
    else:
        divisor = 1

    lots = risk_amount / (sl_distance * divisor)
    return max(0.01, round(lots, 2))  # minimum 0.01 lots


def _price_decimals(price: float) -> int:
    """Infer decimal places from price magnitude."""
    if price >= 1000:
        return 2
    elif price >= 100:
        return 3
    elif price >= 10:
        return 4
    elif price >= 1:
        return 5
    else:
        return 6


def check_drawdown(
    client: ExecutionClient,
    daily_limit: float = 0.05,
    session_limit: float = 0.03,
) -> tuple[bool, str]:
    """Check if account is within drawdown limits.

    Args:
        client: ExecutionClient for balance lookup
        daily_limit: Max daily drawdown as fraction (0.05 = 5%)
        session_limit: Max session drawdown as fraction

    Returns:
        (is_allowed, reason) tuple
    """
    balance = client.get_account_balance()
    # TODO: load peak_balance from persistent state
    # For now: always pass (will be wired to real state in Stage 2)
    return True, ""


def can_open_position(
    client: ExecutionClient,
    max_positions: Optional[int] = None,
) -> tuple[bool, str]:
    """Check if a new position can be opened.

    Args:
        client: ExecutionClient
        max_positions: Override for MAX_OPEN_POSITIONS

    Returns:
        (can_open, reason) tuple
    """
    max_pos = max_positions or config.MAX_OPEN_POSITIONS
    positions = client.get_open_positions()
    if len(positions) >= max_pos:
        return False, f"At max positions ({max_pos})"
    return True, ""