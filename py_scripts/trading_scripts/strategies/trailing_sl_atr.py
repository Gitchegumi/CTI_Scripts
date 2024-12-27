"""A trailing stop loss strategy that uses the Trading API to fetch and update open positions."""

import os
import sys
import logging as log
from decimal import Decimal
import threading
import time
from trading_scripts.api import utils  # pylint: disable=import-error
from trading_scripts.api.login import (  # pylint: disable=import-error
    LoginManager,
)

from trading_scripts.api.atr_data import (  # pylint: disable=import-error
    calculate_atr_from_market_data,
)
from trading_scripts.api.price_data import (  # pylint: disable=import-error
    PriceData,
)


def calculate_new_sl(position, atr_value, swing_values, initial_r_value):
    """Calculate the new stop loss based on 3xATR."""
    symbol = position["symbol"]
    side = position["side"]
    atr_multiplier = 3

    # Calculate RR value
    current_price = (
        swing_values[symbol]["high"] if side == "BUY" else swing_values[symbol]["low"]
    )
    rr_value = round(abs(current_price - position["openPrice"]) / initial_r_value, 2)

    if 1.5 < rr_value <= 3 and (
        (side == "BUY" and position["currentPrice"] > position["openPrice"])
        or (side == "SELL" and position["currentPrice"] < position["openPrice"])
    ):
        atr_multiplier = 2
    elif 3 < rr_value <= 5 and (
        (side == "BUY" and position["currentPrice"] > position["openPrice"])
        or (side == "SELL" and position["currentPrice"] < position["openPrice"])
    ):
        atr_multiplier = 1.5
    elif 5 < rr_value and (
        (side == "BUY" and position["currentPrice"] > position["openPrice"])
        or (side == "SELL" and position["currentPrice"] < position["openPrice"])
    ):
        atr_multiplier = 1

    log.info("ATR Multiplier %s: %s", position["symbol"], atr_multiplier)
    log.info("RR Value %s: %s", position["symbol"], rr_value)

    # Determine decimal precision
    example_value = position["openPrice"]  # Take example value
    decimal_places = abs(Decimal(str(example_value)).as_tuple().exponent)

    if side == "BUY":
        new_sl_calc = swing_values[symbol]["high"] - (atr_value * atr_multiplier)
        new_sl = round(new_sl_calc, decimal_places)
    elif side == "SELL":
        new_sl_calc = swing_values[symbol]["low"] + (atr_value * atr_multiplier)
        new_sl = round(new_sl_calc, decimal_places)
    else:
        log.error("Unknown position side: %s", side)
        return None
    return new_sl


def update_stop_loss(
    login_manager,
    positions,
    atr_values,
    swing_values,
    atr_lock,
    swing_lock,
    initial_r_values,
    interval=30,
):
    """Update the stop loss for each position based on RR."""
    price_data = PriceData(login_manager)
    account_balance = price_data.fetch_account_balance()
    total_balance = float(account_balance.get("balance", 0))

    if total_balance == 0:
        log.error("Account balance is zero or could not be fetched.")
        return

    for position in positions:
        symbol = position["symbol"]
        side = position["side"]
        stop_loss = position["stopLoss"]
        position_id = position["id"]
        volume = position["volume"]

        with atr_lock:
            atr_value = atr_values.get(symbol)
        if atr_value is None:
            log.warning("No ATR value found for symbol: %s", symbol)
            continue

        with swing_lock:
            initial_r_value = initial_r_values.get(position_id)
            new_sl = calculate_new_sl(
                position, atr_value, swing_values, initial_r_value
            )
        if new_sl is not None:
            symbol_data = price_data.fetch_symbol_data(symbol)
            pointvalue = symbol_data.get("pointvalue", 1)
            pricescale = symbol_data.get("pricescale", 1)
            if pricescale == 100:
                pricescale = 1
            open_price = position["openPrice"]
            take_profit = None
            if side == "BUY":
                if new_sl > stop_loss:
                    log.info(
                        "Updating stop loss for %s: %s -> %s", symbol, stop_loss, new_sl
                    )
                    take_profit = open_price + (
                        (total_balance * 0.01 / (volume * pointvalue)) / pricescale
                    )
                    # Update stop loss using the Trading API
                    utils.edit_sl_position(
                        login_manager,
                        position_id,
                        symbol,
                        side,
                        volume,
                        new_sl,
                        take_profit,
                    )
                else:
                    log.info(
                        "New stop loss (%s) is not greater than current stop loss (%s) for %s. \
Nothing Changed.",
                        new_sl,
                        stop_loss,
                        symbol,
                    )
            elif side == "SELL":
                if new_sl < stop_loss:
                    log.info(
                        "Updating stop loss for %s: %s -> %s", symbol, stop_loss, new_sl
                    )
                    take_profit = open_price - (
                        (total_balance * 0.01 / (volume * pointvalue)) / pricescale
                    ) 
                    # Update stop loss using the Trading API
                    utils.edit_sl_position(
                        login_manager,
                        position_id,
                        symbol,
                        side,
                        volume,
                        new_sl,
                        take_profit,
                    )
                else:
                    log.info(
                        "New stop loss (%s) is not less than current stop loss (%s) for %s. \
Nothing Changed.",
                        new_sl,
                        stop_loss,
                        symbol,
                    )
            else:
                log.error("Unknown position side: %s", side)
        time.sleep(interval)


def update_positions(
    login_manager,
    positions,
    symbols,
    initial_r_values,
    interval=10,
):
    """Update positions every specified interval."""
    while True:
        try:
            new_positions = utils.fetch_open_positions_once(login_manager)
            if not new_positions or not isinstance(new_positions, (dict, list)):
                log.warning("No valid positions returned from fetch.")
            else:
                new_positions = (
                    new_positions.get("positions", [])
                    if isinstance(new_positions, dict)
                    else new_positions
                )
                lock = threading.Lock()
                with lock:
                    # Update symbols list in place to avoid issues in threads
                    positions.clear()
                    positions.extend(new_positions)
                    symbols.clear()
                    symbols.extend(pos["symbol"] for pos in new_positions)

                    # Calculate and store initial R value for new positions
                    for position in new_positions:
                        if position["id"] not in initial_r_values:
                            atr_value = calculate_atr_from_market_data(
                                login_manager, position["symbol"]
                            )
                            sample = position["openPrice"]
                            decimal_places = abs(
                                Decimal(str(sample)).as_tuple().exponent
                            )
                            if atr_value is not None:
                                initial_r_value = (
                                    round(
                                        abs(
                                            position["openPrice"]
                                            - (position["openPrice"] - atr_value * 3)
                                        ),
                                        decimal_places,
                                    )
                                    if position["side"] == "BUY"
                                    else round(
                                        abs(
                                            position["openPrice"]
                                            - (position["openPrice"] + atr_value * 3)
                                        ),
                                        decimal_places,
                                    )
                                )
                                initial_r_values[position["id"]] = initial_r_value
                            else:
                                log.warning(
                                    "ATR value is None for position %s. Skipping R-value \
    calculation.",
                                    position["id"],
                                )

                            log.info(
                                "%s updated - Net Profit: %s, Initial R: %s",
                                position["symbol"],
                                position["netProfit"],
                                initial_r_value,
                            )
        except (ConnectionError, KeyError) as e:
            log.error("A connection or key error occurred: %s", e)
        time.sleep(interval)


def update_atr_values(login_manager, symbols, atr_values, atr_lock, interval=60):
    """Update ATR values every specified interval."""
    while True:
        current_symbols = {
            pos["symbol"]
            for pos in utils.fetch_open_positions_once(login_manager)["positions"]
        }
        with atr_lock:
            # Remove old orders from atr_values
            for symbol in list(atr_values.keys()):
                if symbol not in current_symbols:
                    log.info("Removing old order %s from ATR values.", symbol)
                    del atr_values[symbol]
        for symbol in symbols:
            atr_value = calculate_atr_from_market_data(login_manager, symbol)
            with atr_lock:
                if atr_value is not None:
                    atr_values[symbol] = atr_value
            log.info("ATR values updated for %s: %s", symbol, atr_values[symbol])
        time.sleep(interval)


def update_swing_values(
    login_manager, price_data, symbols, swing_values, swing_lock, interval=30
):
    """Update high/low values every specified interval."""
    while True:
        current_symbols = {
            pos["symbol"]
            for pos in utils.fetch_open_positions_once(login_manager)["positions"]
        }
        with swing_lock:
            # Remove old orders from swing_values
            for symbol in list(swing_values.keys()):
                if symbol not in current_symbols:
                    log.info("Removing old order %s from swing values.", symbol)
                    del swing_values[symbol]
        for symbol in symbols:
            log.info("Updating swing values for symbol: %s", symbol)
            price_data.update_swing_values(symbol)
            with swing_lock:
                swing_values[symbol] = price_data.get_stored_values().get(symbol, {})
            log.info(
                "Swing values updated for %s: high=%s low=%s",
                symbol,
                swing_values[symbol].get("high"),
                swing_values[symbol].get("low"),
            )
        time.sleep(interval)


def tail(file, lines=20):
    """Print the last `lines` lines of a file.

    Args:
        file (.log): The log file to read.
        lines (int, optional): The number of lines to read. Defaults to 20.
    """
    with open(file, "r", encoding="utf-8") as f:
        return f.readlines()[-lines:]


def restart_for_time():
    """Restart the strategy after a specified time interval."""
    restart_intervals = [
        ("Restarting strategy in 15 minutes.", 60 * 10),
        ("Restarting strategy in 5 minutes.", 60 * 4),
        ("Restarting strategy in 1 minute.", 60),
    ]

    for message, sleep_time in restart_intervals:
        log.warning(message)
        time.sleep(sleep_time)
    os.execv(sys.executable, [sys.executable] + sys.argv)


def run_strategy():
    """Main entry point for the trailing stop loss strategy."""
    utils.setup_logging()
    log.info("************ Running Trailing SL by ATR Strategy ************")

    max_empty_checks = 3
    empty_check_count = 0

    while True:
        # Initialize the Login Manager
        login_manager = LoginManager()

        try:
            log.info("Attempting to log in...")
            login_manager.login()
            rt_token = login_manager.rt_token

            # Start the token refresh process in a separate thread

            refresh_thread = threading.Thread(
                target=login_manager.refresh_token, args=(rt_token,)
            )
            refresh_thread.start()

            threading.Thread(target=restart_for_time).start()

            # Fetch and update market data for open positions
            positions = []
            symbols = []
            price_data = PriceData(login_manager)
            atr_values = {}
            swing_values = {}
            initial_r_values = {}

            # Create locks for ATR and swing values
            atr_lock = threading.Lock()
            swing_lock = threading.Lock()

            # Start threads for updating positions, ATR values, and swing values
            positions_thread = threading.Thread(
                target=update_positions,
                args=(
                    login_manager,
                    positions,
                    symbols,
                    initial_r_values,
                ),
            )
            positions_thread.start()

            threading.Thread(
                target=update_atr_values,
                args=(
                    login_manager,
                    symbols,
                    atr_values,
                    atr_lock,
                ),
            ).start()

            threading.Thread(
                target=update_swing_values,
                args=(login_manager, price_data, symbols, swing_values, swing_lock),
            ).start()

            # Main loop to update stop loss
            while True:
                if not positions:
                    empty_check_count += 1
                    log.warning(
                        "Positions list is empty. Empty check count: %s",
                        empty_check_count,
                    )
                    time.sleep(5)

                    if empty_check_count >= max_empty_checks:
                        log.error(
                            "Empty check count exceeded. Restarting the strategy."
                        )
                        os.execv(
                            sys.executable,
                            [sys.executable] + sys.argv,
                        )
                else:
                    empty_check_count = 0

                log_lines = tail("logs/debug.log", 5)
                if any("401 " in line for line in log_lines):
                    log.error("Data fetch error detected. Restarting the strategy.")
                    os.execv(
                        sys.executable,
                        [sys.executable] + sys.argv,
                    )

                # log.info("positions from run_strategy: %s", positions)
                # log.info("symbols from run_strategy: %s", symbols)
                if positions and atr_values and swing_values:
                    update_stop_loss(
                        login_manager,
                        positions,
                        atr_values,
                        swing_values,
                        atr_lock,
                        swing_lock,
                        initial_r_values,
                    )

        except (ConnectionError, KeyError) as e:
            log.error("A connection or key error occurred: %s", e)
        except ValueError as e:
            log.error("A value error occurred: %s", e)
        except RuntimeError as e:
            log.error("A runtime error occurred: %s", e)


if __name__ == "__main__":
    run_strategy()
