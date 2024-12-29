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

trading_symbols = ["US500", "US30", "EURUSD", "BTCUSDC"]


def is_within_trading_hours(symbol):
    """Check if the current time is within the trading hours for the given symbol.

    Args:
        symbol (str): The trading symbol to check.

    Returns:
        bool: True if within trading hours, False otherwise.
    """
    now = datetime.now(ny_timezone)
    log.info("Current time: %s", now)
    symbol_hours = trading_hours.get(symbol, {}).get("market_hours")
    log.info("Symbol hours for %s: %s", symbol, symbol_hours)

    if not symbol_hours:
        return True  # No specific trading hours, assume always open

    # If it's EURUSD, only allow Monday (weekday=0) through Friday (weekday=4).
    if (
        symbol == "EURUSD"
        or "US500"
        or "US30"
        and (now.weekday() < 0 or now.weekday() > 4)
    ):
        return False

    # If the config includes full weekday names
    if " " in symbol_hours["start"]:
        start = symbol_hours["start"]  # e.g. "Monday 00:00:00"
        end = symbol_hours["end"]  # e.g. "Friday 23:59:59"
        # If you still want to parse the specific times, you can do so here,
        # but the weekday check above will prevent Sunday trades for EURUSD.
        return True
    else:
        # Fallback for times given with no weekday
        start = datetime.strptime(symbol_hours["start"], "%H:%M:%S").time()
        end = datetime.strptime(symbol_hours["end"], "%H:%M:%S").time()

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


def calc_linear_regression(login_manager, symbol, timeframe):
    """Calculate the linear regression for the given symbol and timeframe.

    Args:
        symbol (str): The trading symbol.
        timeframe (str): The timeframe for the linear regression.
    """
    log.info("Calculating linear regression for %s", symbol)
    price_data = PriceData()
    ohlc = price_data.fetch_market_data(login_manager, symbol, timeframe)
    log.info("Fetched market data for %s", symbol)  # Log the fetched data

    if not ohlc or "t" not in ohlc:
        log.error("Market data for %s does not contain 't' key", symbol)
        return None

    df = pd.DataFrame(ohlc)
    df.set_index("t", inplace=True)
    # log.info("Dataframe for %s: %s", symbol, df.head())

    df.ta.linreg(close="c", length=14, append=True)
    # log.info("Linear regression Dataframe for %s: %s", symbol, df.tail())

    if "LR_14" not in df.columns:
        log.error("Linear Regression calculation failed for %s", symbol)
        return None

    lr_diff = df["LR_14"].iloc[-1] - df["LR_14"].iloc[-2]
    current_price = df["c"].iloc[-1]

    if current_price == 0:
        log.error("Current price is 0 for %s", symbol)
        return None

    lr_precentage = (lr_diff / current_price) * 100
    # log.info("Linear Regression percentage for %s: %s", symbol, lr_precentage)

    return lr_precentage


def get_trend(login_manager, symbol):
    """Get the trend for the given symbol based on linear regression.

    Args:
        symbol (str): The trading symbol.

    Returns:
        str: The trend direction ("BUY", "SELL", or None).
    """
    log.info("Calculating trend for %s", symbol)
    regression_1h = calc_linear_regression(login_manager, symbol, 60)
    log.info("1H Linear Regression percentage for %s: %s", symbol, regression_1h)
    regression_15m = calc_linear_regression(login_manager, symbol, 15)
    log.info("15M Linear Regression percentage for %s: %s", symbol, regression_15m)

    if regression_1h > 0.1 and regression_15m > 0.05:
        log.info("Trend identified: Uptrend")
        return "Uptrend"
    elif regression_1h < -0.1 and regression_15m < -0.05:
        log.info("Trend identified: Downtrend")
        return "Downtrend"
    log.info("No trend identified")
    return None


def calc_rsi(login_manager, symbol):
    """Calculate the RSI values for the specified symbol.

    Args:
        symbol (str): The trading symbol.
    """
    log.info("Calculating RSI for %s", symbol)
    price_data = PriceData()
    ohlc = price_data.fetch_market_data(login_manager, symbol, 5)
    df = pd.DataFrame(ohlc).set_index("t")
    df["RSI"] = ta.rsi(df["c"], length=14)
    return df["RSI"].iloc[-1]


def calc_macd(login_manager, symbol):
    """Calculate the MACD values for the specified symbol.

    Args:
        symbol (str): The trading symbol.
    """
    log.info("Calculating MACD for %s", symbol)
    price_data = PriceData()
    ohlc = price_data.fetch_market_data(login_manager, symbol, 5)
    df = pd.DataFrame(ohlc).set_index("t")
    macd = df.ta.macd(close="c", fast=12, slow=26, signal=9)
    return macd["MACDh_12_26_9"].iloc[-1] if "MACDh_12_26_9" in macd.columns else 0


def calc_keltner_channel(login_manager, symbol):
    """Calculate the Keltner Channel values for the specified symbol.

    Args:
        symbol (str): The trading symbol.
    """
    # Calculate Keltner Channel values for the specified symbol
    log.info("Calculating Keltner Channel for %s", symbol)
    price_data = PriceData()
    ohlc = price_data.fetch_market_data(login_manager, symbol, 5)
    df = pd.DataFrame(ohlc).set_index("t")
    kc = df.ta.kc(close="c", high="h", low="l", length=20, scalar=1.5, mamode="ema")

    # log.info("Keltner Channel values: %s", kc)

    df["KC_Lower"] = kc["KCLe_20_1.5"]
    df["KC_Middle"] = kc["KCBe_20_1.5"]
    df["KC_Upper"] = kc["KCUe_20_1.5"]
    result = {
        "price": df["c"].iloc[-1],
        "lower_band": df["KC_Lower"].iloc[-1],
        "upper_band": df["KC_Upper"].iloc[-1],
        "candlestick": "engulfing",  # Simplified placeholder
    }
    return result


def identify_trade_signal(login_manger, symbol, trend):
    """Identify the trade signal based on RSI, MACD, and Keltner Channel.

    Args:
        symbol (str): The trading symbol.
        trend (str): The trend direction ("Uptrend" or "Downtrend").

    Returns:
       str : The trade signal ("BUY", "SELL", or None).
    """
    log.info("Identifying trade signal for %s", symbol)
    # Identify trade signal based on RSI, MACD, and Keltner Channel
    rsi = calc_rsi(login_manger, symbol)
    macd_histogram = calc_macd(login_manger, symbol)
    kc_values = calc_keltner_channel(login_manger, symbol)

    # BUY signal conditions
    if trend == "Uptrend":
        log.info("Checking RSI for oversold condition")
        if rsi < 30:  # RSI is oversold
            log.info("RSI is oversold: %s, checking MACD", rsi)
            macd_current = macd_histogram.iloc[-1]
            macd_previous = macd_histogram.iloc[-2]
            if macd_current > macd_previous:  # MACD shows bullish pressure
                log.info(
                    "MACD histogram is bullish: %s, %s, checking KC",
                    macd_current,
                    macd_previous,
                )
                if (
                    kc_values["price"] < kc_values["lower_band"]
                ):  # Price below lower KC band
                    log.info(
                        "Price is below lower KC band: %s, %s",
                        kc_values["price"],
                        kc_values["lower_band"],
                    )
                    if kc_values["candlestick"] in [
                        "pinbar",
                        "engulfing",
                    ]:  # Pinbar or engulfing toward bullish
                        log.info(
                            "RSI: %s, MACD: %s, KC: %s", rsi, macd_histogram, kc_values
                        )
                        log.info("Trade signal identified: BUY")
                        return "BUY"

    # SELL signal conditions
    if trend == "Downtrend":
        log.info("Checking RSI for overbought condition")
        if rsi > 70:  # RSI is overbought
            log.info("RSI is overbought: %s, checking MACD", rsi)
            macd_current = macd_histogram.iloc[-1]
            macd_previous = macd_histogram.iloc[-2]
            if macd_current < macd_previous:  # MACD shows weakening bullish
                log.info(
                    "MACD histogram is bearish: %s, %s, checking KC",
                    macd_current,
                    macd_previous,
                )
                if (
                    kc_values["price"] > kc_values["upper_band"]
                ):  # Price above upper KC band
                    log.info(
                        "Price is above upper KC band: %s, %s",
                        kc_values["price"],
                        kc_values["upper_band"],
                    )
                    if kc_values["candlestick"] in [
                        "pinbar",
                        "engulfing",
                    ]:  # Pinbar or engulfing toward bearish
                        log.info(
                            "RSI: %s, MACD: %s, KC: %s", rsi, macd_histogram, kc_values
                        )
                        log.info("Trade signal identified: SELL")
                        return "SELL"

    log.info("No trade signal identified")
    return None


def calc_stop_loss(login_manager, symbol):
    """Calculate the stop loss for the given symbol.

    Args:
        symbol (str): The trading symbol.

    Returns:
        float: The stop loss value.
    """
    log.info("Calculating stop loss for %s", symbol)
    price_data = PriceData()
    trend = get_trend(login_manager, symbol)
    side = identify_trade_signal(login_manager, symbol, trend)
    market_watch = price_data.fetch_market_watch(login_manager, symbol)
    atr = calculate_atr_from_market_data(login_manager, symbol)
    if side == "BUY":
        stop_loss = market_watch["bid"] - (atr * 3)
        return stop_loss
    if side == "SELL":
        stop_loss = market_watch["ask"] + (atr * 3)
        return stop_loss
    return None


def calc_take_profit(login_manager, symbol):
    """Calculate the stop loss for the given symbol.

    Args:
        symbol (str): The trading symbol.

    Returns:
        float: The stop loss value.
    """
    log.info("Calculating take profit for %s", symbol)
    price_data = PriceData()
    trend = get_trend(login_manager, symbol)
    side = identify_trade_signal(login_manager, symbol, trend)
    market_watch = price_data.fetch_market_watch(login_manager, symbol)
    atr = calculate_atr_from_market_data(login_manager, symbol)
    if side == "BUY":
        take_profit = market_watch["bid"] + (atr * 9)
        return take_profit
    if side == "SELL":
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
    log.info("Calculating volume for %s", symbol)
    risk_per_trade = 0.0025  # 0.25% risk per trade
    price_data = PriceData()
    account_balance_data = price_data.fetch_account_balance(login_manager)
    account_balance = float(account_balance_data["balance"])
    current_price = price_data.fetch_market_watch(login_manager, symbol)
    stop_loss = calc_stop_loss(login_manager, symbol)
    volume = (account_balance * risk_per_trade) / abs(current_price - stop_loss)
    return volume


def enter_trade(login_manager, symbol, direction, volume, stop_loss, take_profit):
    """Enter a trade for the given symbol with the specified parameters.

    Args:
        symbol (str): The trading symbol.
        direction (str): The trade direction ("BUY" or "SELL").
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
    utils.setup_logging()
    while True:
        login_manager.login()
        open_positions_response = utils.fetch_open_positions_once(login_manager)
        open_positions = (
            open_positions_response.get("positions", [])
            if open_positions_response
            else []
        )
        close_trades_during_swap(login_manager, open_positions)
        for symbol in trading_symbols:
            log.info("Checking trades for %s", symbol)
            if not is_within_trading_hours(symbol):
                log.info(
                    "Skipping trades for %s as it is outside trading hours", symbol
                )
                continue

            if symbol in open_positions:
                log.info("Position already open for %s", symbol)
            else:
                trend = get_trend(login_manager, symbol)
                direction = identify_trade_signal(login_manager, symbol, trend)
                if direction:
                    stop_loss = calc_stop_loss(login_manager, symbol)
                    take_profit = calc_take_profit(login_manager, symbol)
                    volume = calc_volume(login_manager, symbol)
                    log.info("Entering trade for %s", symbol)
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
        time.sleep(60)  # Adjust sleep interval as needed


if __name__ == "__main__":
    run_strategy()
