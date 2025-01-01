"""A module for implementing a trading strategy based on Keltner Channels,
ATR, Stochastic RSI, and MACD indicators.

Returns:
    None
"""

import logging as log
import time
import json
from decimal import Decimal
from datetime import datetime
import pandas as pd
import pandas_ta as ta  # pylint: disable=import-error, unused-import
from pytz import timezone
from trading_scripts.api import utils  # pylint: disable=import-error
from trading_scripts.api.login import (  # pylint: disable=import-error
    LoginManager,
)
from trading_scripts.api.price_data import PriceData  # pylint: disable=import-error
from trading_scripts.api.indicators import (  # pylint: disable=import-error
    Indicators,
)

forex_pairs = [] # ["EURUSD", "USDJPY", "USDCAD", "GBPJPY", "NZDUSD", "AUDUSD"]
index_symbols = [] # ["US500", "US30"]
crypto_pairs = ["BTCUSDC"]

jpy_symbols = [pair for pair in forex_pairs if "JPY" in pair]
standard_symbols = [pair for pair in forex_pairs if pair not in jpy_symbols]

trading_symbols = forex_pairs + index_symbols + crypto_pairs

ny_timezone = timezone("America/New_York")

forex_market_hours = [
    {"start": "Monday 00:00:00", "end": "Monday 16:30:00"},
    {"start": "Monday 19:00:00", "end": "Tuesday 16:30:00"},
    {"start": "Tuesday 19:00:00", "end": "Wednesday 16:30:00"},
    {"start": "Wednesday 19:00:00", "end": "Thursday 16:30:00"},
    {"start": "Thursday 19:00:00", "end": "Friday 16:30:00"},
]

forex_daily_swap = {
    "start": "16:55:00",
    "end": "17:05:00",
}

index_market_hours = [
    {"start": "Monday 00:00:00", "end": "Monday 16:30:00"},
    {"start": "Monday 18:30:00", "end": "Tuesday 16:30:00"},
    {"start": "Tuesday 18:30:00", "end": "Wednesday 16:30:00"},
    {"start": "Wednesday 18:30:00", "end": "Thursday 16:30:00"},
    {"start": "Thursday 18:30:00", "end": "Friday 16:30:00"},
]

index_daily_swap = {
    "start": "16:55:00",
    "end": "18:29:00",
}

crypto_daily_swap = {
    "start": "16:55:00",
    "end": "17:30:00",
}

trading_hours = {}

for pair in forex_pairs:
    trading_hours[pair] = {
        "market_hours": forex_market_hours,
        "daily_swap": forex_daily_swap,
    }

for index in index_symbols:
    trading_hours[index] = {
        "market_hours": index_market_hours,
        "daily_swap": index_daily_swap,
    }

for pair in crypto_pairs:
    trading_hours[pair] = {
        "daily_swap": crypto_daily_swap,
    }

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

def identify_trade_signal(
        df,
        symbol,
        current_price,
        st_length=50,
        st_multiplier=3.0,
        ema_length=50,
        aroon_length=50
    ):
    """Get the current trend for the given symbol.

    Args:
        login_manager (LoginManager): The login manager instance.
        symbol (str): The trading symbol to check.

    Returns:
        str: The current trend ("up", "down", or "none").
    """
    aroon_threshold = 50

    supertrend = Indicators.calculate_super_trend(
        df,
        length=st_length,
        multiplier=st_multiplier
    )
    ema_50 = Indicators.calculate_ema(df, length=ema_length)
    aroon = Indicators.calculate_aroon(df, length=aroon_length)
    stoch_rsi = Indicators.calculate_stoch_rsi(df)
    current_price = df["c"].iloc[-1]
    decimal_places = abs(Decimal(str(current_price)).as_tuple().exponent)

    super_trend = round(
        supertrend[f'SUPERT_{st_length}_{st_multiplier}'].iloc[-1],
        decimal_places
    )
    ema_50_value = round(ema_50.iloc[-1], decimal_places)
    aroon_osc = aroon[f"AROONOSC_{aroon_length}"].iloc[-1]
    rsi_d = stoch_rsi["STOCHRSId_14_14_3_3"].iloc[-1]
    rsi_k = stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-1]
    rsi_k_last_5_max = max(stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-5:])
    rsi_k_last_5_min = min(stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-5:])

    if current_price > super_trend:
        log.info(
            "%s: Price (%s) is above the SuperTrend (%s) looking for BUY signal.",
            symbol,
            current_price,
            super_trend
        )
        if current_price > ema_50_value:
            log.info(
                "%s: Price (%s) is above the EMA50 (%s) checking Aroon Oscillator.",
                symbol, current_price,
                ema_50_value
            )
            if aroon_osc >= aroon_threshold:
                log.info(
                    "%s: Aroon Oscillator (%s) is above %s, checking RSI",
                        symbol,
                        aroon_osc,
                        aroon_threshold
                    )
                if rsi_k_last_5_min < 30 and rsi_d < rsi_k:
                    log.info(
                        "%s: Stochastic RSI k (%s) is below 30 is over RSI d (%s).",
                        symbol,
                        round(rsi_k_last_5_min, decimal_places),
                        round(rsi_d, decimal_places)
                    )
                    log.info(
                        "%s: Trade signal identified: BUY",
                        symbol
                    )
                    return "BUY"
                log.info(
                    "%s: Stochastic RSIk (%s) is above 30 or RSIk (%s) \
is above RSId (%s). No BUY signal.",
                    symbol,
                    round(rsi_k_last_5_min, decimal_places),
                    round(rsi_k, decimal_places),
                    round(rsi_d, decimal_places)
                )
            else:
                log.info(
                    "%s: Aroon Oscillator (%s) is below %s. No BUY signal.",
                    symbol,
                    aroon_osc,
                    aroon_threshold
                )
        else:
            log.info(
                "%s: Price (%s) is below the EMA50: %s. No BUY signal.",
                symbol,
                current_price,
                ema_50_value
            )
    else:
        log.info(
            "%s: Price (%s) is below the SuperTrend: %s. No BUY signal.",
            symbol,
            current_price,
            super_trend
        )

    if current_price < super_trend:
        log.info(
            "%s: Price (%s) is below the SuperTrend (%s) looking for SELL signal.",
            symbol,
            current_price,
            super_trend
        )
        if current_price < ema_50_value:
            log.info(
                "%s: Price (%s) is below the EMA50 (%s) checking Aroon Oscillator.",
                symbol,
                current_price,
                ema_50_value
            )
            if aroon_osc <= -aroon_threshold:
                log.info(
                    "%s: Aroon Oscillator (%s) is below %s, checking RSI",
                        symbol,
                        aroon_osc,
                        -aroon_threshold
                    )
                if rsi_k_last_5_max > 70 and rsi_d > rsi_k:
                    log.info(
                        "%s: Stochastic RSI k (%s) is above 70 and is below RSI d (%s).",
                        symbol,
                        round(rsi_k_last_5_max, decimal_places),
                        round(rsi_d, decimal_places)
                    )
                    log.info(
                        "%s: Trade signal identified: SELL",
                        symbol
                    )
                    return "SELL"
                log.info(
                    "%s: Stochastic RSI k (%s) is below 70 or RSIk (%s) \
is not below RSId (%s). No SELL signal.",
                    symbol,
                    round(rsi_k_last_5_max, decimal_places),
                    round(rsi_k, decimal_places),
                    round(rsi_d, decimal_places)
                )
            else:
                log.info(
                    "%s: Aroon Oscillator (%s) is above %s. No SELL signal.",
                    symbol,
                    aroon_osc,
                    -aroon_threshold
                )
        else:
            log.info(
                "%s: Price (%s) is above the EMA50: %s. No SELL signal.",
                symbol,
                current_price,
                ema_50_value
            )
    else:
        log.info(
            "%s: Price (%s) is above the SuperTrend: %s. No SELL signal.",
            symbol,
            current_price,
            super_trend
        )
    return None

def calc_take_profit(
        direction,
        current_price,
        stop_loss,
        rr_value=2
    ):
    """Calculate the take profit for the given symbol.

    Args:
        symbol (str): The trading symbol.
        direction (str): The trade direction ("BUY" or "SELL").
        current_price (float): The current price of the symbol.
        stop_loss (float): The stop loss price.

    Returns:
        float: The take profit price.
    """
    if direction == "BUY":
        return current_price + ((current_price - stop_loss) * rr_value)
    if direction == "SELL":
        return current_price - ((stop_loss - current_price) * rr_value)
    return None

def calc_volume(
        login_manager,
        symbol, stop_loss,
        risk_per_trade = 0.0025
    ):
    """Calculate the volume for the given symbol based on account balance.

    Args:
        symbol (str): The trading symbol.

    Returns:
        float: The volume to trade.
    """
    # Calculate volume based on account balance
    log.info("Calculating volume for %s", symbol)
    price_data = PriceData()
    account_balance_data = price_data.fetch_account_balance(login_manager)
    account_balance = float(account_balance_data["balance"])
    ohlc = price_data.fetch_market_data(login_manager, symbol, 5)
    df = pd.DataFrame(ohlc).set_index("t")
    current_price = df["c"].iloc[-1]
    atr = Indicators.calculate_atr(df, length=14)
    current_atr = atr["ATR_14"].iloc[-1]
    stop_loss_pip_value = abs(current_price - stop_loss)
    min_stop_loss = current_atr * 1.5

    if stop_loss is None:
        log.error("Stop loss calculation failed for %s", symbol)
        return None

    if stop_loss_pip_value < min_stop_loss:
        log.error(
            "Stop loss too close to current price for %s: %s, %s",
            symbol,
            stop_loss_pip_value,
            min_stop_loss,
        )
        return None

    try:
        if symbol in standard_symbols:
            volume = (
                (account_balance * risk_per_trade) / stop_loss_pip_value / 100000
            )
        elif symbol in jpy_symbols:
            volume = (
                (account_balance * risk_per_trade) / stop_loss_pip_value / 1000
            )
        else:
            volume = (account_balance * risk_per_trade) / stop_loss_pip_value
            if symbol in index_symbols and volume < 0.1:
                volume = 0.1
                if ((volume * stop_loss_pip_value) / account_balance) < 0.0075:
                    return round(volume, 1)
                else:
                    log.error("Risk per trade too high for %s: %s", symbol, volume)

    except ZeroDivisionError:
        log.error(
            "Division by zero error for %s: bid_price=%s, stop_loss=%s",
            symbol,
            current_price,
            stop_loss,
        )
        return None

    return round(volume, 2)

def update_stop_loss(login_manager, open_positions, new_stop_loss):
    """Update the stop loss for open positions based on the new value.

    Args:
        login_manager (LoginManager): The login manager instance.
        open_positions (list): A list of open positions.
        new_stop_loss (float): The new stop loss value.
    """
    for position in open_positions:
        symbol = position["symbol"]
        side = position["side"]
        stop_loss = position["stopLoss"]
        position_id = position["id"]
        volume = position["volume"]
        take_profit = position["takeProfit"]

        if side == "BUY" and new_stop_loss > stop_loss:
            log.info(
                "Updating stop loss for %s: %s -> %s",
                symbol,
                stop_loss,
                new_stop_loss,
            )
            utils.edit_sl_position(
                login_manager,
                position_id,
                symbol,
                side,
                volume,
                new_stop_loss,
                take_profit,
            )

        elif side == "SELL" and new_stop_loss < stop_loss:
            log.info(
                "Updating stop loss for %s: %s -> %s",
                symbol,
                stop_loss,
                new_stop_loss,
            )
            utils.edit_sl_position(
                login_manager,
                position_id,
                symbol,
                side,
                volume,
                new_stop_loss,
                take_profit,
            )
        else:
            utils.print_boxed_message(
                f"Stop loss for {symbol} is already set. Skipping."
            )

def run_strategy():
    """Run the trading strategy based on weekday entries."""
    while True:
        st_length=50
        st_multiplier=3.0
        ema_length=50
        aroon_length=50
        login_manager = LoginManager()
        open_positions = []
        utils.setup_logging()
        utils.print_boxed_message("Looking for trade opportunities")
        login_manager.login()
        open_positions_response = utils.fetch_open_positions_once(login_manager)
        open_positions = (
            open_positions_response.get("positions", [])
            if open_positions_response
            else []
        )
        open_position_symbols = [pos["symbol"] for pos in open_positions]
        price_data = PriceData()

        log.info("Open position symbols: %s", open_position_symbols)
        close_trades_during_swap(login_manager, open_positions)
        for symbol in trading_symbols:
            ohlc = price_data.fetch_market_data(login_manager, symbol, 5)
            df = pd.DataFrame(ohlc).set_index("t")
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
                position_data = next(
                    (pos for pos in open_positions if pos["symbol"] == symbol), None
                )
                if position_data:
                    filtered_data = {
                        "id": position_data.get("id"),
                        "volume": position_data.get("volume"),
                        "side": position_data.get("side"),
                        "stopLoss": position_data.get("stopLoss"),
                        "takeProfit": position_data.get("takeProfit"),
                        "netProfit": position_data.get("netProfit"),
                        "commission": position_data.get("commission"),
                    }
                    utils.print_boxed_message(
                        f"Trade already open for {symbol}. Checking Stop Loss",
                    )
                    utils.print_boxed_message(json.dumps(filtered_data, indent=2))
                    new_stop_loss = Indicators.calculate_super_trend(
                        df,
                        length=st_length,
                        multiplier=st_multiplier
                    )[f'SUPERT_{st_length}_{st_multiplier}'].iloc[-1]
                    update_stop_loss(login_manager, open_positions, new_stop_loss)

            else:
                ohlc = price_data.fetch_market_data(login_manager, symbol, 5)
                df = pd.DataFrame(ohlc).set_index("t")
                current_price = df["c"].iloc[-1]
                direction = identify_trade_signal(
                    df,
                    symbol,
                    current_price,
                    st_length,
                    st_multiplier,
                    ema_length,
                    aroon_length,
                    )
                if direction:
                    log.info("Setting stop loss and take profit for %s", symbol)
                    stop_loss = Indicators.calculate_super_trend(
                        df,
                        length=st_length,
                        multiplier=st_multiplier
                    )[f'SUPERT_{st_length}_{st_multiplier}'].iloc[-1]
                    take_profit = calc_take_profit(
                        direction,
                        current_price,
                        stop_loss,
                        2.5
                    )
                    volume = calc_volume(login_manager, symbol, stop_loss)
                    if stop_loss and take_profit and volume:
                        log.info("Entering trade for %s", symbol)
                        utils.enter_trade(
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
        time.sleep(60)

if __name__ == "__main__":
    run_strategy()
