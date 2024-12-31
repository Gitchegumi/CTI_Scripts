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
import pandas_ta as ta  # pylint: disable=import-error, unused-import
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
        "market_hours": [
            {"start": "Monday 00:00:00", "end": "Monday 16:30:00"},
            {"start": "Monday 19:00:00", "end": "Tuesday 16:30:00"},
            {"start": "Tuesday 19:00:00", "end": "Wednesday 16:30:00"},
            {"start": "Wednesday 19:00:00", "end": "Thursday 16:30:00"},
            {"start": "Thursday 19:00:00", "end": "Friday 16:30:00"},
        ],
        "daily_swap": {
            "start": "16:55:00",
            "end": "17:05:00",
        },
    },
    "US500": {
        "market_hours": [
            {"start": "Monday 00:00:00", "end": "Monday 16:30:00"},
            {"start": "Monday 19:00:00", "end": "Tuesday 16:30:00"},
            {"start": "Tuesday 19:00:00", "end": "Wednesday 16:30:00"},
            {"start": "Wednesday 19:00:00", "end": "Thursday 16:30:00"},
            {"start": "Thursday 19:00:00", "end": "Friday 16:30:00"},
        ],
        "daily_swap": {
            "start": "16:55:00",
            "end": "18:59:00",
        },
    },
    "US30": {
        "market_hours": [
            {"start": "Monday 00:00:00", "end": "Monday 16:30:00"},
            {"start": "Monday 19:00:00", "end": "Tuesday 16:30:00"},
            {"start": "Tuesday 19:00:00", "end": "Wednesday 16:30:00"},
            {"start": "Wednesday 19:00:00", "end": "Thursday 16:30:00"},
            {"start": "Thursday 19:00:00", "end": "Friday 16:30:00"},
        ],
        "daily_swap": {
            "start": "16:55:00",
            "end": "18:59:00",
        },
    },
     "BTCUSDC": {
        "daily_swap": {
            "start": "16:55:00",
            "end": "17:30:00",
        },
    }
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
    log.info("Symbol hours for %s: %s", symbol, json.dumps(symbol_hours, indent=2))

    if not symbol_hours:
        return True  # No specific trading hours, assume always open

    # If it's EURUSD, only allow Monday (weekday=0) through Friday (weekday=4).
    if symbol in ["EURUSD", "US500", "US30"] and (
        now.weekday() < 0 or now.weekday() > 4
    ):
        return False

    for period in symbol_hours:
        start = ny_timezone.localize(
            datetime.strptime(period["start"], "%A %H:%M:%S").replace(
                year=now.year, month=now.month, day=now.day
            )
        )
        end = ny_timezone.localize(
            datetime.strptime(period["end"], "%A %H:%M:%S").replace(
                year=now.year, month=now.month, day=now.day
            )
        )

        if start < end:
            if start <= now <= end:
                return True
        else:
            if now >= start or now <= end:
                return True

    return False


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

    if regression_1h > 0.1 and regression_15m > 0.02:
        log.info("Trend identified: Uptrend")
        return "Uptrend"
    elif regression_1h < -0.1 and regression_15m < -0.02:
        log.info("Trend identified: Downtrend")
        return "Downtrend"
    utils.print_boxed_message(f"No trend identified for {symbol}")
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
    stoch_rsi = df.ta.stochrsi(high="h", low="l", close="c")
    return stoch_rsi


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
    return macd


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

    # log.info("Keltner Channel values: %s", kc.tail())

    df["KC_Lower"] = kc["KCLe_20_1.5"]
    df["KC_Middle"] = kc["KCBe_20_1.5"]
    df["KC_Upper"] = kc["KCUe_20_1.5"]
    result = {
        "price": df["c"].iloc[-1],
        "high": df["h"].iloc[-1],
        "last_5_high": df["h"].iloc[-6:-1].max(),
        "low": df["l"].iloc[-1],
        "last_5_low": df["l"].iloc[-6:-1].min(),
        "lower_band": df["KC_Lower"].iloc[-1],
        "middle_band": df["KC_Middle"].iloc[-1],
        "upper_band": df["KC_Upper"].iloc[-1],
        "last_5_middle_min": df["KC_Middle"].iloc[-6:-1].min(),
        "last_5_middle_max": df["KC_Middle"].iloc[-6:-1].max(),
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
    price_data = PriceData()
    ohlc = price_data.fetch_market_data(login_manger, symbol, 5)
    df = pd.DataFrame(ohlc).set_index("t")
    candlestick = df.ta.cdl_pattern(
        open="o",
        high="h",
        low="l",
        close="c",
        name=["engulfing", "shootingstar", "hammer"],
    )
    recent_candles = candlestick.iloc[-5:].dropna(how="all")
    recent_candle_patterns = recent_candles[(recent_candles != 0).any(axis=1)]
    recent_candle_patterns = recent_candle_patterns.loc[
        :, (recent_candle_patterns != 0).any(axis=0)
    ]
    identified_patterns = recent_candle_patterns.columns[
        (recent_candle_patterns != 0).any(axis=0)
    ]
    log.info("Current candle patterns: %s", json.dumps(identified_patterns.tolist()))

    stoch_rsi = calc_rsi(login_manger, symbol)
    rsi = stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-1]
    rsi_d = stoch_rsi["STOCHRSId_14_14_3_3"].iloc[-1]
    rsi_prev_3_max = stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-4:].max()
    rsi_prev_3_min = stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-4:].min()
    macd = calc_macd(login_manger, symbol)
    kc_values = calc_keltner_channel(login_manger, symbol)
    # log.info("kc_values: %s", kc_values)
    # kc_middle_prev_5 = kc_values["middle_band"].iloc[-6:-1]
    macd_hist_current = macd["MACDh_12_26_9"].iloc[-1]
    macd_hist_prev_5_max = macd["MACDh_12_26_9"].iloc[-6:-1].max()
    macd_hist_prev_5_min = macd["MACDh_12_26_9"].iloc[-6:-1].min()

    # BUY signal conditions
    if trend == "Uptrend":
        log.info("Checking RSI for oversold condition")
        log.info("RSI prev 3 min: %s", rsi_prev_3_min)
        if rsi_prev_3_min < 30:  # RSI is oversold
            log.info("RSI is oversold: %s, checking MACD", rsi)
            if rsi > rsi_d:  # RSI is bullish
                log.info("RSI is bullish: %s, %s, checking MACD", rsi, rsi_d)
                if (
                    macd_hist_current > macd_hist_prev_5_min
                ):  # MACD shows bullish pressure
                    log.info(
                        "MACD histogram is bullish: %s, %s, checking KC",
                        macd_hist_current,
                        macd_hist_prev_5_min,
                    )
                    if (
                        kc_values["last_5_low"] <= kc_values["last_5_middle_min"]
                    ):  # Price below lower KC band
                        log.info(
                            "Price is below middle KC band: %s, %s",
                            kc_values["last_5_low"],
                            kc_values["last_5_middle_min"],
                        )
                        if (
                            "CDL_ENGULFING" in identified_patterns
                            or "CDL_HAMMER" in identified_patterns
                        ):
                            log.info(
                                "RSI: %s, MACD: %s, KC: %s, patterns: %s",
                                rsi,
                                macd_hist_current,
                                kc_values,
                                json.dumps(identified_patterns.tolist()),
                            )
                            log.info("Trade signal identified: BUY")
                            return "BUY"
                        else:
                            log.error(
                                "Failed candlestick check for BUY: %s",
                                json.dumps(identified_patterns.tolist()),
                            )
                    else:
                        log.error(
                            "Failed Keltner check for BUY: price=%s, middle_band=%s",
                            kc_values["last_5_low"],
                            kc_values["last_5_middle_min"],
                        )
                else:
                    log.error(
                        "Failed MACD check for BUY: macd_current=%s, macd_previous=%s",
                        macd_hist_current,
                        macd_hist_prev_5_min,
                    )
            else:
                log.error(
                    "Failed RSI check for BUY: RSI %s is not greater than RSId %s",
                    round(rsi, 2),
                    round(rsi_d, 2),
                )
        else:
            log.error(
                "Failed RSI check for BUY: RSI %s is not less than 30", round(rsi, 2)
            )

    # SELL signal conditions
    if trend == "Downtrend":
        log.info("Checking RSI for overbought condition")
        log.info("RSI prev 3 max: %s", rsi_prev_3_max)
        if rsi_prev_3_max > 70:  # RSI is overbought
            log.info("RSI is overbought: %s, checking MACD", rsi)
            if rsi < rsi_d:  # RSI is bearish
                log.info("RSI is bearish: %s, %s, checking MACD", rsi, rsi_d)
                if (
                    macd_hist_current < macd_hist_prev_5_max
                ):  # MACD shows weakening bullish
                    log.info(
                        "MACD histogram is bearish: %s, %s, checking KC",
                        macd_hist_current,
                        macd_hist_prev_5_max,
                    )
                    if (
                        kc_values["last_5_high"] >= kc_values["last_5_middle_max"]
                    ):  # Price above upper KC band
                        log.info(
                            "Price is above upper KC band: %s, %s",
                            kc_values["last_5_high"],
                            kc_values["last_5_middle_max"],
                        )
                        if (
                            "CDL_ENGULFING" in identified_patterns
                            or "CDL_SHOOTINGSTAR" in identified_patterns
                            or "CDL_SPINNINGTOP" in identified_patterns
                        ):
                            log.info(
                                "RSI: %s, MACD: %s, KC: %s, patterns: %s",
                                rsi,
                                macd_hist_current,
                                kc_values,
                                json.dumps(identified_patterns.tolist()),
                            )
                            log.info("Trade signal identified: SELL")
                            return "SELL"
                        else:
                            log.error(
                                "Failed candlestick check for SELL: %s",
                                json.dumps(identified_patterns.tolist()),
                            )
                    else:
                        log.error(
                            "Failed Keltner check for SELL: price=%s, middle_band=%s",
                            kc_values["last_5_high"],
                            kc_values["last_5_middle_max"],
                        )
                else:
                    log.error(
                        "Failed MACD check for SELL: macd_current=%s, macd_previous=%s",
                        macd_hist_current,
                        macd_hist_prev_5_max,
                    )
            else:
                log.error(
                    "Failed RSI check for SELL: RSI %s is not less than RSId %s",
                    round(rsi, 2),
                    round(rsi_d, 2),
                )
        else:
            log.error(
                "Failed RSI check for SELL: RSI %s is not greater than 70",
                round(rsi, 2),
            )
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
    market_watch_data = price_data.fetch_market_watch(login_manager, symbol)

    # log.info(
    #     "market watch data for stop_loss: %s",
    #     json.dumps(market_watch_data, indent=2)
    # )

    if not market_watch_data or not isinstance(market_watch_data, list):
        log.error(
            "Market watch data is missing or not in expected format for symbol: %s",
            symbol,
        )
        return None

    market_watch = next(
        (item for item in market_watch_data if item["symbol"] == symbol), None
    )

    # log.info(
    #     "market watch dict for stop_loss: %s",
    #     json.dumps(market_watch, indent=2)
    # )

    if not market_watch or "ask" not in market_watch:
        log.error(
            "Market watch data is missing or 'ask' key not found for symbol: %s", symbol
        )
        return None

    atr = calculate_atr_from_market_data(login_manager, symbol)
    if side == "BUY":
        stop_loss = float(market_watch["bid"]) - (atr * 3)
        return stop_loss
    if side == "SELL":
        stop_loss = float(market_watch["ask"]) + (atr * 3)
        return stop_loss
    return None


def calc_take_profit(login_manager, symbol):
    """Calculate the take profit for the given symbol.

    Args:
        symbol (str): The trading symbol.

    Returns:
        float: The take profit value.
    """
    log.info("Calculating take profit for %s", symbol)
    price_data = PriceData()
    trend = get_trend(login_manager, symbol)
    side = identify_trade_signal(login_manager, symbol, trend)
    market_watch_data = price_data.fetch_market_watch(login_manager, symbol)

    # log.info(
    #     "market watch data for take_profit: %s",
    #     json.dumps(market_watch_data, indent=2)
    # )

    if not market_watch_data or not isinstance(market_watch_data, list):
        log.error(
            "Market watch data is missing or not in expected format for symbol: %s",
            symbol,
        )
        return None

    market_watch = next(
        (item for item in market_watch_data if item["symbol"] == symbol), None
    )

    # log.info(
    #     "market watch dict for take_profit: %s",
    #     json.dumps(market_watch, indent=2)
    # )

    if not market_watch or "ask" not in market_watch:
        log.error(
            "Market watch data is missing or 'ask' key not found for symbol: %s", symbol
        )
        return None

    atr = calculate_atr_from_market_data(login_manager, symbol)
    if side == "BUY":
        take_profit = float(market_watch["bid"]) + (atr * 9)
        return take_profit
    if side == "SELL":
        take_profit = float(market_watch["ask"]) - (atr * 9)
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
    market_watch_data = price_data.fetch_market_watch(login_manager, symbol)

    # log.info(
    #     "market watch data for calc_volume: %s",
    #     json.dumps(market_watch_data, indent=2)
    # )

    if not market_watch_data or not isinstance(market_watch_data, list):
        log.error(
            "Market watch data is missing or not in expected format for symbol: %s",
            symbol,
        )
        return None

    current_price = next(
        (item for item in market_watch_data if item["symbol"] == symbol), None
    )

    # log.info(
    #     "current price for calc_volume: %s",
    #     json.dumps(current_price, indent=2)
    # )

    if not current_price or "bid" not in current_price:
        log.error(
            "Market watch data is missing or 'ask' key not found for symbol: %s", symbol
        )
        return None

    stop_loss = calc_stop_loss(login_manager, symbol)
    if stop_loss is None:
        log.error("Stop loss calculation failed for %s", symbol)
        return None

    try:
        bid_price = float(current_price["bid"])
    except (ValueError, TypeError):
        log.error("Invalid bid price for %s: %s", symbol, current_price["bid"])
        return None

    try:
        if symbol == "EURUSD":
            volume = (
                (account_balance * risk_per_trade) / abs(bid_price - stop_loss) / 100000
            )
        else:
            volume = (account_balance * risk_per_trade) / abs(bid_price - stop_loss)
    except ZeroDivisionError:
        log.error(
            "Division by zero error for %s: bid_price=%s, stop_loss=%s",
            symbol,
            bid_price,
            stop_loss,
        )
        return None

    # log.info(
    #         "%s * %s / abs(%s - %s) = %s",
    #         account_balance,
    #         risk_per_trade,
    #         bid_price,
    #         stop_loss,
    #         ((account_balance * risk_per_trade) / abs(bid_price - stop_loss)),
    #     )
    return round(volume, 2)


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
        utils.print_boxed_message("Looking for trade opportunities")
        login_manager.login()
        open_positions_response = utils.fetch_open_positions_once(login_manager)
        open_positions = (
            open_positions_response.get("positions", [])
            if open_positions_response
            else []
        )
        open_position_symbols = [pos["symbol"] for pos in open_positions]
        log.info("Open position symbols: %s", open_position_symbols)
        close_trades_during_swap(login_manager, open_positions)
        for symbol in trading_symbols:
            utils.print_boxed_message(f"Checking trade opportunities for {symbol}")
            if not is_within_trading_hours(symbol):
                log.info(
                    "Skipping trades for %s as it is outside trading hours", symbol
                )
                continue

            if is_within_daily_swap(symbol):
                log.info(
                    "Skipping trades for %s as it is during the daily swap time", symbol
                )
                continue

            if symbol in open_position_symbols:
                utils.print_boxed_message(f"Trade already open for {symbol}. Skipping.")
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
                    utils.print_boxed_message(
                        f"No trade signal identified for {symbol}. Skipping."
                    )
        time.sleep(60)  # Adjust sleep interval as needed


if __name__ == "__main__":
    run_strategy()
