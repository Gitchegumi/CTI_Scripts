"""A trailing stop loss strategy that uses the Trading API to fetch and update open positions."""

import logging as log
from decimal import Decimal
import threading
import time
from api.login import LoginManager  # pylint: disable=import-error
import api.utils as utils  # pylint: disable=import-error
from api.atr_data import calculate_atr_from_market_data  # pylint: disable=import-error
from api.price_data import PriceData  # pylint: disable=import-error


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
    system_uuid,
    auth_trading_api,
    cookie,
    positions,
    atr_values,
    swing_values,
    atr_lock,
    swing_lock,
    initial_r_values,
):
    """Update the stop loss for each position based on RR."""
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
            if side == "BUY":
                if new_sl > stop_loss:
                    log.info(
                        "Updating stop loss for %s: %s -> %s", symbol, stop_loss, new_sl
                    )
                    # Update stop loss using the Trading API
                    utils.edit_sl_position(
                        system_uuid,
                        auth_trading_api,
                        cookie,
                        position_id,
                        symbol,
                        side,
                        volume,
                        new_sl,
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
                    # Update stop loss using the Trading API
                    utils.edit_sl_position(
                        system_uuid,
                        auth_trading_api,
                        cookie,
                        position_id,
                        symbol,
                        side,
                        volume,
                        new_sl,
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


def update_positions(
    login_manager,
    system_uuid,
    auth_trading_api,
    cookie,
    positions,
    symbols,
    initial_r_values,
    interval=10,
):
    """Update positions every specified interval."""
    while True:
        positions.clear()
        try:
            new_positions = utils.fetch_open_positions_once(login_manager)
            # log.info("Positions fetched: %s", new_positions)
            if isinstance(new_positions, dict) and "positions" in new_positions:
                new_positions = new_positions["positions"]
            if isinstance(new_positions, list):
                positions.extend(new_positions)
                new_symbols = [pos["symbol"] for pos in new_positions]

                # Update symbols list in place to avoid issues in threads
                symbols.clear()
                symbols.extend(new_symbols)

                # Calculate and store initial R value for new positions
                for position in new_positions:
                    if position["id"] not in initial_r_values:
                        atr_value = calculate_atr_from_market_data(
                            system_uuid, auth_trading_api, cookie, position["symbol"]
                        )
                        sample = position["openPrice"]
                        decimal_places = abs(Decimal(str(sample)).as_tuple().exponent)
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
                            position["symbol"], position["netProfit"], initial_r_value
                        )
            else:
                log.info(
                    "Expected a list of positions, but got: %s", type(new_positions)
                )
        except (ConnectionError, KeyError) as e:
            log.error("A connection or key error occurred: %s", e)
        time.sleep(interval)


def update_atr_values(
    system_uuid, auth_trading_api, cookie, symbols, atr_values, atr_lock, interval=30
):
    """Update ATR values every specified interval."""
    while True:
        for symbol in symbols:
            if symbol not in symbols:
                log.info("Removing symbol %s from ATR values.", symbol)
                atr_values[symbol] = {}
            atr_value = calculate_atr_from_market_data(
                system_uuid, auth_trading_api, cookie, symbol
            )
            with atr_lock:
                if atr_value is not None:
                    atr_values[symbol] = atr_value
            log.info("ATR values updated for %s: %s", symbol, atr_values[symbol])
        time.sleep(interval)


def update_swing_values(price_data, symbols, swing_values, swing_lock, interval=15):
    """Update high/low values every specified interval."""
    while True:
        # log.info("Swing value symbols: %s", symbols)
        for symbol in symbols:
            log.info("Updating swing values for symbol: %s", symbol)
            if symbol not in symbols:
                log.info("Removing symbol %s from swing values.", symbol)
                swing_values[symbol] = {}
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


def run_strategy():
    """Main entry point for the trailing stop loss strategy."""
    utils.setup_logging()
    log.info("************ Running Trailing SL by ATR Strategy ************")

    while True:
        # Initialize the Login Manager
        login_manager = LoginManager()

        try:
            log.info("Attempting to log in...")
            login_manager.login()
            system_uuid = login_manager.system_uuid
            auth_trading_api = login_manager.auth_trading_api
            cookie = login_manager.cookie
            rt_token = login_manager.rt_token

            # Start the token refresh process in a separate thread

            refresh_thread = threading.Thread(
                target=login_manager.refresh_token, args=(rt_token,)
            )
            refresh_thread.start()

            # Fetch and update market data for open positions
            positions = []
            symbols = []
            price_data = PriceData(system_uuid, auth_trading_api, cookie)
            atr_values = {}
            swing_values = {}
            initial_r_values = {}

            # Create locks for ATR and swing values
            atr_lock = threading.Lock()
            swing_lock = threading.Lock()

            # Start threads for updating positions, ATR values, and swing values
            threading.Thread(
                target=update_positions,
                args=(
                    login_manager,
                    system_uuid,
                    auth_trading_api,
                    cookie,
                    positions,
                    symbols,
                    initial_r_values,
                ),
            ).start()

            while not positions:
                log.info("Waiting for positions to be fetched...")
                time.sleep(1)

            if positions:
                atr_thread = threading.Thread(
                    target=update_atr_values,
                    args=(
                        system_uuid,
                        auth_trading_api,
                        cookie,
                        symbols,
                        atr_values,
                        atr_lock,
                    ),
                )
                atr_thread.start()
                swing_thread = threading.Thread(
                    target=update_swing_values,
                    args=(price_data, symbols, swing_values, swing_lock),
                )
                swing_thread.start()
            else:
                if atr_thread.is_alive():
                    atr_thread.stop()
                    log.info("ATR thread stopped.")
                if swing_thread.is_alive():
                    swing_thread.stop()
                    log.info("Swing thread stopped.")

            # Main loop to update stop loss
            while True:
                # log.info("positions from run_strategy: %s", positions)
                # log.info("symbols from run_strategy: %s", symbols)
                if atr_values and swing_values:
                    if login_manager.cookie != cookie or login_manager.rt_token != rt_token:
                        cookie, rt_token = login_manager.cookie, login_manager.rt_token
                        log.info("Updated cookie and rt token in main loop.")

                    update_stop_loss(
                        system_uuid,
                        auth_trading_api,
                        cookie,
                        positions,
                        atr_values,
                        swing_values,
                        atr_lock,
                        swing_lock,
                        initial_r_values,
                    )
                    time.sleep(10)  # Adjust this interval as needed

        except (ConnectionError, KeyError) as e:
            log.error("A connection or key error occurred: %s", e)
        except ValueError as e:
            log.error("A value error occurred: %s", e)
        except RuntimeError as e:
            log.error("A runtime error occurred: %s", e)
