"""A module for implementing a trading strategy based on Keltner Channels,
ATR, Stochastic RSI, and MACD indicators.

Returns:
    None
"""

import os
import logging as log
import time
import json
import csv
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

forex_pairs = ["EURUSD", "USDJPY", "USDCAD", "GBPJPY", "NZDUSD", "AUDUSD"]
index_symbols = ["US500", "US30"]
crypto_pairs = ["BTCUSDC"]

jpy_symbols = [pair for pair in forex_pairs if "JPY" in pair]
standard_symbols = [pair for pair in forex_pairs if pair not in jpy_symbols]

trading_symbols = forex_pairs + index_symbols + crypto_pairs

ny_timezone = timezone("America/New_York")

forex_market_hours = [
    {"start": "Monday 00:00:00", "end": "Monday 16:30:00"},
    {"start": "Monday 18:00:00", "end": "Tuesday 16:30:00"},
    {"start": "Tuesday 18:00:00", "end": "Wednesday 16:30:00"},
    {"start": "Wednesday 18:00:00", "end": "Thursday 16:30:00"},
    {"start": "Thursday 18:00:00", "end": "Friday 16:30:00"},
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
    "start": "15:55:00",
    "end": "16:30:00",
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
    # log.info("Symbol hours for %s: %s", symbol, json.dumps(symbol_hours, indent=2))

    if not symbol_hours:
        return True  # No specific trading hours, assume always open

    # Only allow Monday (weekday=0) through Friday (weekday=4) if closed on weekend.
    if symbol in forex_pairs + index_symbols and (
        now.weekday() < 0
        or now.weekday() > 4
        or (
            now.weekday() == 4
            and (now.hour > 16 or (now.hour == 17 and now.minute >= 00))
        )
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
    aroon_length=50,
):
    """Get the current trend for the given symbol.

    Args:
        login_manager (LoginManager): The login manager instance.
        symbol (str): The trading symbol to check.

    Returns:
        str: The current trend ("up", "down", or "none").
    """
    aroon_threshold = 40

    supertrend = Indicators.calculate_super_trend(
        df, length=st_length, multiplier=st_multiplier
    )
    ema_50 = Indicators.calculate_ema(df, length=ema_length)
    aroon = Indicators.calculate_aroon(df, length=aroon_length)
    stoch_rsi = Indicators.calculate_stoch_rsi(df)
    keltner_channels = Indicators.calculate_keltner_channels(df)
    current_price = df["c"].iloc[-1]
    current_high = df["h"].iloc[-1]
    current_low = df["l"].iloc[-1]
    last_10_highs = df["h"].iloc[-11:-1]
    last_10_highs_max = last_10_highs.max()
    last_10_highs_index = last_10_highs.idxmax()
    last_10_highs_pos = df.index.get_loc(last_10_highs_index)
    last_10_lows = df["l"].iloc[-11:-1]
    last_10_lows_min = last_10_lows.min()
    last_10_lows_index = last_10_lows.idxmin()
    last_10_lows_pos = df.index.get_loc(last_10_lows_index)
    decimal_places = (
        5 if symbol in standard_symbols else 3 if symbol in jpy_symbols else 2
    )

    super_trend = round(
        supertrend[f"SUPERT_{st_length}_{st_multiplier}"].iloc[-1], decimal_places
    )
    ema_50_value = round(ema_50.iloc[-1], decimal_places)
    aroon_osc = round(aroon[f"AROONOSC_{aroon_length}"].iloc[-1], 2)
    rsi_d = round(stoch_rsi["STOCHRSId_14_14_3_3"].iloc[-1], 2)
    rsi_k = round(stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-1], 2)
    rsi_k_last_5_max = round(max(stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-5:]), 2)
    rsi_k_last_5_min = round(min(stoch_rsi["STOCHRSIk_14_14_3_3"].iloc[-5:]), 2)
    keltner_upper_at_max = round(
        keltner_channels["KCUe_20_1.5"].iloc[last_10_highs_pos], decimal_places
    )
    keltner_lower_at_min = round(
        keltner_channels["KCLe_20_1.5"].iloc[last_10_lows_pos], decimal_places
    )
    keltner_basis = round(keltner_channels["KCBe_20_1.5"].iloc[-1], decimal_places)

    if current_price > super_trend:
        log.info(
            "%s: Price (%s) is above the SuperTrend (%s) looking for BUY signal.",
            symbol,
            current_price,
            super_trend,
        )
        if current_price > ema_50_value:
            log.info(
                "%s: Price (%s) is above the EMA50 (%s). Continuing ...",
                symbol,
                current_price,
                ema_50_value,
            )
            if last_10_highs_max > keltner_upper_at_max:
                log.info(
                    "%s: Recent high (%s) is above the Keltner Upper (%s). Continuing...",
                    symbol,
                    last_10_highs_max,
                    keltner_upper_at_max,
                )
                if current_low <= keltner_basis:
                    log.info(
                        "%s: Current low (%s) is below the Keltner Basis (%s). Continuing ...",
                        symbol,
                        current_low,
                        keltner_basis,
                    )
                    if aroon_osc >= aroon_threshold:
                        log.info(
                            "%s: Aroon Oscillator (%s) is above the threshold (%s). Continuing ...",
                            symbol,
                            aroon_osc,
                            aroon_threshold,
                        )
                        if rsi_k_last_5_min < 30 and rsi_d < rsi_k:
                            log.info(
                                "%s: Stochastic RSI k (%s) is below 30 is over RSI d (%s).",
                                symbol,
                                round(rsi_k_last_5_min, decimal_places),
                                round(rsi_d, decimal_places),
                            )
                            log.info("%s: Trade signal identified: BUY", symbol)
                            return "BUY"
                        log.info(
                            "%s: Stochastic RSIk (%s) is above 30 or RSIk (%s) \
    is below RSId (%s). No BUY signal.",
                            symbol,
                            round(rsi_k_last_5_min, decimal_places),
                            round(rsi_k, decimal_places),
                            round(rsi_d, decimal_places),
                        )
                    else:
                        log.info(
                            "%s: Aroon Oscillator (%s) is below %s. No BUY signal.",
                            symbol,
                            aroon_osc,
                            aroon_threshold,
                        )
                else:
                    log.info(
                        "%s: Price (%s) did not pull back to Keltner Basis: %s. No BUY signal.",
                        symbol,
                        current_low,
                        keltner_basis,
                    )
            else:
                log.info(
                    "%s: Recent high (%s) is below the Keltner Upper (%s). No BUY signal.",
                    symbol,
                    last_10_highs_max,
                    keltner_upper_at_max,
                )
        else:
            log.info(
                "%s: Price (%s) is below the EMA50: %s. No BUY signal.",
                symbol,
                current_price,
                ema_50_value,
            )

    elif current_price < super_trend:
        log.info(
            "%s: Price (%s) is below the SuperTrend (%s) looking for SELL signal.",
            symbol,
            current_price,
            super_trend,
        )
        if current_price < ema_50_value:
            log.info(
                "%s: Price (%s) is below the EMA50 (%s). Continuing ...",
                symbol,
                current_price,
                ema_50_value,
            )
            if last_10_lows_min < keltner_lower_at_min:
                log.info(
                    "%s: Recent low (%s) is below the Keltner Lower (%s). Continuing...",
                    symbol,
                    last_10_lows_min,
                    keltner_lower_at_min,
                )
                if current_high >= keltner_basis:
                    log.info(
                        "%s: Current high (%s) is above the Keltner Basis (%s). Continuing ...",
                        symbol,
                        current_high,
                        keltner_basis,
                    )
                    if aroon_osc <= -aroon_threshold:
                        log.info(
                            "%s: Aroon Oscillator (%s) is below the threshold (%s). Continuing ...",
                            symbol,
                            aroon_osc,
                            -aroon_threshold,
                        )
                        if rsi_k_last_5_max > 70 and rsi_d > rsi_k:
                            log.info(
                                "%s: Stochastic RSI k (%s) is above 70 and is below RSI d (%s).",
                                symbol,
                                round(rsi_k_last_5_max, decimal_places),
                                round(rsi_d, decimal_places),
                            )
                            log.info("%s: Trade signal identified: SELL", symbol)
                            return "SELL"
                        log.info(
                            "%s: Stochastic RSI k (%s) is below 70 or RSIk (%s) \
is above RSId (%s). No SELL signal.",
                            symbol,
                            round(rsi_k_last_5_max, decimal_places),
                            round(rsi_k, decimal_places),
                            round(rsi_d, decimal_places),
                        )
                    else:
                        log.info(
                            "%s: Aroon Oscillator (%s) is above %s. No SELL signal.",
                            symbol,
                            aroon_osc,
                            -aroon_threshold,
                        )
                else:
                    log.info(
                        "%s: Price (%s) did not rally to Keltner Basis: %s. No SELL signal.",
                        symbol,
                        current_high,
                        keltner_basis,
                    )
            else:
                log.info(
                    "%s: Recent low (%s) is above the Keltner Lower (%s). No SELL signal.",
                    symbol,
                    last_10_lows_min,
                    keltner_lower_at_min,
                )
        else:
            log.info(
                "%s: Price (%s) is above the EMA50: %s. No SELL signal.",
                symbol,
                current_price,
                ema_50_value,
            )
    else:
        log.info(
            "%s: Price (%s) is above the SuperTrend: %s. No SELL signal.",
            symbol,
            current_price,
            super_trend,
        )
    return None


def calc_take_profit(direction, current_price, stop_loss, rr_value=2):
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


def calc_volume(login_manager, symbol, stop_loss, risk_per_trade=0.0025):
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
    current_atr = atr.iloc[-1]
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
            volume = (account_balance * risk_per_trade) / stop_loss_pip_value / 100000
        elif symbol in jpy_symbols:
            volume = (account_balance * risk_per_trade) / stop_loss_pip_value / 1000
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


def update_stop_loss(
    login_manager,
    position_id,
    symbol,
    side,
    volume,
    stop_loss,
    take_profit,
):
    """Update the stop loss for open positions based on the new value.

    Args:
        login_manager (LoginManager): The login manager instance.
        open_positions (list): A list of open positions.
        new_stop_loss (float): The new stop loss value.
    """
    price_data = PriceData()
    ohlc = price_data.fetch_market_data(login_manager, symbol, 5)
    df = pd.DataFrame(ohlc).set_index("t")
    new_stop_loss = Indicators.calculate_super_trend(df, length=50, multiplier=3.0)[
        "SUPERT_50_3.0"
    ].iloc[-1]

    decimal_places = abs(Decimal(str(df["c"].iloc[-1])).as_tuple().exponent)
    new_stop_loss = round(new_stop_loss, decimal_places)

    # log.info(
    #     "New stop loss for %s: %s(%s)", symbol, new_stop_loss, type(new_stop_loss)
    # )

    if (
        side == "BUY"
        and new_stop_loss > stop_loss
        or side == "SELL"
        and new_stop_loss < stop_loss
    ):
        log.info(
            "Updating stop loss for %s: %s -> %s",
            symbol,
            stop_loss,
            round(new_stop_loss, decimal_places),
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
        utils.print_boxed_message(f"Stop loss for {symbol} is already set. Skipping.")


def run_strategy():
    """Run the trading strategy based on weekday entries."""
    while True:
        st_length = 50
        st_multiplier = 3.0
        ema_length = 50
        aroon_length = 24
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
        closed_positions_response = utils.fetch_closed_positions(login_manager)
        closed_positions = (
            closed_positions_response.get("operations", [])
            if closed_positions_response
            else []
        )
        open_position_symbols = [pos["symbol"] for pos in open_positions]
        price_data = PriceData()

        # check for csv file
        if not os.path.exists(utils.CSV_FILE):
            utils.initialize_csv()

        # check csv file for recently closed trades
        for position in closed_positions:
            with open(utils.CSV_FILE, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["trade_id"] == position["id"] and not row["close_date_time"]:
                        log.info("Trade without close time found: %s", row["trade_id"])
                        utils.update_csv(
                            trade_id=position["id"],
                            close_date_time=position["time"],
                            swap=position["swap"],
                            profit=position["netProfit"],
                            close_reason=position["closeReason"],
                        )

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
                        "open time": position_data.get("openTime"),
                        "volume": position_data.get("volume"),
                        "side": position_data.get("side"),
                        "stopLoss": position_data.get("stopLoss"),
                        "takeProfit": position_data.get("takeProfit"),
                        "netProfit": position_data.get("netProfit"),
                        "commission": position_data.get("commission"),
                        "swap": position_data.get("swap"),
                    }
                    utils.print_boxed_message(
                        f"Trade already open for {symbol}. Checking Stop Loss",
                    )
                    utils.print_boxed_message(json.dumps(filtered_data, indent=2))
                    position_id = position_data.get("id")
                    side = position_data.get("side")
                    volume = position_data.get("volume")
                    stop_loss = position_data.get("stopLoss")
                    take_profit = position_data.get("takeProfit")
                    update_stop_loss(
                        login_manager,
                        position_id,
                        symbol,
                        side,
                        volume,
                        stop_loss,
                        take_profit,
                    )

            else:
                ohlc = price_data.fetch_market_data(login_manager, symbol, 5)
                df = pd.DataFrame(ohlc).set_index("t")
                current_price = df["c"].iloc[-1]
                spread = utils.check_spread(login_manager, symbol)
                atr = Indicators.calculate_atr(df, length=14).iloc[-1]
                if spread is not None and spread < atr * 1.2:
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
                            df, length=st_length, multiplier=st_multiplier
                        )[f"SUPERT_{st_length}_{st_multiplier}"].iloc[-1]
                        if symbol == "BTCUSDC":
                            if direction == "BUY":
                                take_profit = current_price + (0.75) / abs(
                                    current_price - stop_loss
                                )
                            elif direction == "SELL":
                                take_profit = current_price - (0.75) / abs(
                                    current_price - stop_loss
                                )
                        else:
                            take_profit = calc_take_profit(
                                direction, current_price, stop_loss, 2.8
                            )
                        if symbol == "BTCUSDC":
                            volume = 0.01
                        else:
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
                else:
                    utils.print_boxed_message(
                        f"Spread is None or too high for {symbol}. Skipping."
                    )
        time.sleep(60)


if __name__ == "__main__":
    run_strategy()
