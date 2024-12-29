"""A module for implementing a trading strategy based on weekday entries.

Returns:
    None
"""

import logging as log
import time
import json
from datetime import datetime
import requests
import pandas as pd
import pandas_ta as ta  # pylint: disable=import-error
from pytz import timezone
from trading_scripts.api import utils  # pylint: disable=import-error
from trading_scripts.api.login import (  # pylint: disable=import-error
    LoginManager,
)
from trading_scripts.api.price_data import PriceData  # pylint: disable=import-error
from trading_scripts.api.atr_data import (  # pylint: disable=import-error
    calculate_atr_from_market_data,
)

ny_timezone = timezone("America/New_York")

trading_hours = {
    "EURUSD": {
        "market_hours": {
            "start": "Monday 00:00:00",
            "end": "Friday 23:59:59",
        },
        "daily_swap": {
            "start": "16:55:00",
            "end": "17:05:00",
        },
    },
    "US500": {
        "market_hours": {
            "start": "08:30:00",
            "end": "16:30:00",
        }
    },
    "US30": {
        "market_hours": {
            "start": "08:30:00",
            "end": "16:30:00",
        }
    },
    "BTCUSDC": {
        "daily_swap": {
            "start": "17:55:00",
            "end": "18:05:00",
        }
    },
}

trading_symbols = ["BTCUSDC"]


def is_within_trading_hours(symbol):
    """Check if the current time is within the trading hours for the given symbol.

    Args:
        symbol (str): The trading symbol to check.

    Returns:
        bool: True if within trading hours, False otherwise.
    """
    now = datetime.now(ny_timezone)
    symbol_hours = trading_hours.get(symbol, {}).get("market_hours")
    if not symbol_hours:
        return True  # No specific trading hours, assume always open

    start_str = symbol_hours["start"]
    end_str = symbol_hours["end"]

    if " " in start_str:
        start = datetime.strptime(start_str, "%A %H:%M:%S").time()
        end = datetime.strptime(end_str, "%A %H:%M:%S").time()
    else:
        start = datetime.strptime(start_str, "%H:%M:%S").time()
        end = datetime.strptime(end_str, "%H:%M:%S").time()

    if start < end:
        return start <= now.time() <= end
    return now.time() >= start or now.time() <= end


def is_within_daily_swap(symbol):
    """Check if the current time is within the daily swap time for the given symbol.

    Args:
        symbol (str): The trading symbol to check.

    Returns:
        bool: True if within daily swap time, False otherwise.
    """
    now = datetime.now(ny_timezone)
    symbol_swap = trading_hours.get(symbol, {}).get("daily_swap")
    if not symbol_swap:
        return False

    start = datetime.strptime(symbol_swap["start"], "%H:%M:%S").time()
    end = datetime.strptime(symbol_swap["end"], "%H:%M:%S").time()

    return start <= now.time() <= end


def close_trades_during_swap(login_manager, open_positions):
    """Close trades for symbols during the daily swap time.

    Args:
        login_manager (LoginManager): The login manager instance.
        open_positions (list): A list of open positions.
    """
    for position in open_positions:
        symbol = position["symbol"]
        if is_within_daily_swap(symbol):
            log.info("Closing trade for %s during daily swap time", symbol)
            utils.close_position(
                login_manager,
                position["id"],
                symbol,
                position["side"],
                position["volume"],
            )


def calc_linear_regression(symbol, timeframe):
    """Calculate the linear regression for the given symbol and timeframe.

    Args:
        symbol (str): The trading symbol.
        timeframe (str): The timeframe for the linear regression.
    """
    price_data = PriceData(LoginManager())
    ohlc = price_data.fetch_market_data(symbol, timeframe)
    df = pd.DataFrame(ohlc)
    df.set_index("t", inplace=True)
    df.ta.linreg(close="c", length=14, append=True)
    return df["LR_14"].iloc[-1] - df["LR_14"].iloc[-2]


def get_trend(symbol):
    """Get the trend for the given symbol based on linear regression.

    Args:
        symbol (str): The trading symbol.

    Returns:
        str: The trend direction ("buy", "sell", or None).
    """
    regression_1h = calc_linear_regression(symbol, 60)
    regression_15m = calc_linear_regression(symbol, 15)

    if regression_1h > 0 and regression_15m > 0:
        return "buy"
    elif regression_1h < 0 and regression_15m < 0:
        return "sell"
    return None


def calc_rsi(symbol):
    """Calculate the RSI values for the specified symbol.

    Args:
        symbol (str): The trading symbol.
    """
    price_data = PriceData(LoginManager())
    ohlc = price_data.fetch_market_data(symbol, 5)
    df = pd.DataFrame(ohlc).set_index("time")
    df["RSI"] = ta.rsi(df["close"], length=14)
    return df["RSI"].iloc[-1]


def calc_macd(symbol):
    """Calculate the MACD values for the specified symbol.

    Args:
        symbol (str): The trading symbol.
    """
    price_data = PriceData(LoginManager())
    ohlc = price_data.fetch_market_data(symbol, 5)
    df = pd.DataFrame(ohlc).set_index("time")
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    return macd["MACDh_12_26_9"].iloc[-1] if "MACDh_12_26_9" in macd.columns else 0


def calc_keltner_channel(symbol):
    """Calculate the Keltner Channel values for the specified symbol.

    Args:
        symbol (str): The trading symbol.
    """
    # Calculate Keltner Channel values for the specified symbol
    price_data = PriceData(LoginManager())
    ohlc = price_data.fetch_market_data(symbol, 5)
    df = pd.DataFrame(ohlc).set_index("time")
    kc = df.ta.kc()
    df["KC_Lower"] = kc["KCL_20_2.0"]
    df["KC_Upper"] = kc["KCU_20_2.0"]
    result = {
        "price": df["close"].iloc[-1],
        "lower_band": df["KC_Lower"].iloc[-1],
        "upper_band": df["KC_Upper"].iloc[-1],
        "candlestick": "engulfing",  # Simplified placeholder
    }
    return result


def identify_trade_signal(symbol, trend):
    """Identify the trade signal based on RSI, MACD, and Keltner Channel.

    Args:
        symbol (str): The trading symbol.
        trend (str): The trend direction ("buy" or "sell").

    Returns:
       str : The trade signal ("buy", "sell", or None).
    """
    # Identify trade signal based on RSI, MACD, and Keltner Channel
    rsi = calc_rsi(symbol)
    macd_histogram = calc_macd(symbol)
    kc_values = calc_keltner_channel(symbol)

    # BUY signal conditions
    if (
        trend == "buy"
        and rsi < 30  # RSI is oversold
        and macd_histogram > 0  # MACD shows weakening bearish
        and kc_values["price"] < kc_values["lower_band"]  # Price below lower KC band
        and kc_values["candlestick"]
        in ["pinbar", "engulfing"]  # Pinbar or engulfing toward bullish
    ):
        return "buy"

    # SELL signal conditions
    if (
        trend == "sell"
        and rsi > 70  # RSI is overbought
        and macd_histogram < 0  # MACD shows weakening bullish
        and kc_values["price"] > kc_values["upper_band"]  # Price above upper KC band
        and kc_values["candlestick"]
        in ["pinbar", "engulfing"]  # Pinbar or engulfing toward bearish
    ):
        return "sell"

    return None


def calc_stop_loss(login_manager, symbols):
    """Calculate the stop loss for the given symbol.

    Args:
        symbol (str): The trading symbol.

    Returns:
        float: The stop loss value.
    """
    price_data = PriceData(login_manager)
    for symbol in symbols:
        trend = get_trend(symbol)
        side = identify_trade_signal(symbol, trend)
        market_watch = price_data.fetch_market_watch(symbol)
        atr = calculate_atr_from_market_data(login_manager, symbol)
        if side == "buy":
            stop_loss = market_watch["bid"] - (atr * 3)
            return stop_loss
        if side == "sell":
            stop_loss = market_watch["ask"] + (atr * 3)
            return stop_loss
    return None


def calc_take_profit(login_manager, symbols):
    """Calculate the stop loss for the given symbol.

    Args:
        symbol (str): The trading symbol.

    Returns:
        float: The stop loss value.
    """
    price_data = PriceData(login_manager)
    for symbol in symbols:
        trend = get_trend(symbol)
        side = identify_trade_signal(symbol, trend)
        market_watch = price_data.fetch_market_watch(symbol)
        atr = calculate_atr_from_market_data(login_manager, symbol)
        if side == "buy":
            take_profit = market_watch["bid"] + (atr * 9)
            return take_profit
        if side == "sell":
            take_profit = market_watch["ask"] - (atr * 9)
            return take_profit
    return None


def calc_volume(login_manager, symbol):
    """Calculate the volume for the given symbol based on account balance.

    Args:
        symbol (str): The trading symbol.

    Returns:
        float: The volume to trade.
    """
    # Calculate volume based on account balance
    risk_per_trade = 0.0025  # 0.25% risk per trade
    account_balance = PriceData.fetch_account_balance(login_manager)
    current_price = PriceData.fetch_market_watch(login_manager, symbol)
    stop_loss = calc_stop_loss(login_manager, symbol)
    volume = (account_balance * risk_per_trade) / abs(current_price - stop_loss)
    return volume


def enter_trade(login_manager, symbol, direction, volume, stop_loss, take_profit):
    """Enter a trade for the given symbol with the specified parameters.

    Args:
        symbol (str): The trading symbol.
        direction (str): The trade direction ("buy" or "sell").
        volume (float): The volume to trade.
        stop_loss (float): The stop loss value.
        take_profit (float): The take profit value.
    """
    # Logic to enter trade for the given symbol
    url = f"{utils.PLATFORM_URL}/mtr-api/{login_manager.system_uuid}/position/open"
    payload = json.dumps(
        {
            "instrument": symbol,
            "orderSide": direction.upper(),
            "volume": volume,
            "slPrice": stop_loss,
            "tpPrice": take_profit,
            "isMobile": False,
        }
    )
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Auth-trading-api": login_manager.auth_trading_api,
        "Cookie": f"co-auth={login_manager.cookie}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    session = requests.Session()
    session.headers.update(headers)
    try:
        response = session.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        log.info("Successfully opened position for %s: %s", symbol, direction)
    except requests.RequestException as e:
        log.error("Failed to open position for %s: %s", symbol, e)


def run_strategy():
    """Run the trading strategy based on weekday entries."""
    login_manager = LoginManager()
    open_positions = []
    symbols = trading_symbols
    while True:
        login_manager.login()
        open_positions_response = utils.fetch_open_positions_once(login_manager)
        open_positions = open_positions_response.get("positions", []) if open_positions_response else []
        close_trades_during_swap(login_manager, open_positions)
        for symbol in symbols:
            if not is_within_trading_hours(symbol):
                log.info(
                    "Skipping trades for %s as it is outside trading hours", symbol
                )
                continue

            if symbol in open_positions:
                log.info("Position already open for %s", symbol)
            else:
                stop_loss = calc_stop_loss(login_manager, symbol)
                take_profit = calc_take_profit(login_manager, symbol)
                volume = calc_volume(login_manager, symbol)
                direction = identify_trade_signal(symbol, get_trend(symbol))
                if direction:
                    enter_trade(
                        login_manager,
                        symbol,
                        direction,
                        volume,
                        stop_loss,
                        take_profit,
                    )
                else:
                    log.info("No trade signal found for %s", symbol)
        time.sleep(5)  # Adjust sleep interval as needed


if __name__ == "__main__":
    run_strategy()
