"""A trailing stop loss strategy that uses the Trading API to fetch and update open positions."""

import logging as log
from decimal import Decimal
import threading
import time
from api.login import LoginManager  # pylint: disable=import-error
import api.utils as utils  # pylint: disable=import-error
from api.utils import fetch_open_positions_once # pylint: disable=import-error
from api.atr_data import calculate_atr_from_market_data  # pylint: disable=import-error
from api.price_data import PriceData  # pylint: disable=import-error
from api.utils import edit_sl_position # pylint: disable=import-error

def calculate_new_sl(position, atr_value, swing_values):
    """Calculate the new stop loss based on 3xATR."""
    symbol = position["symbol"]
    side = position["side"]

    # Determine decimal precision
    example_value = position["openPrice"]  # Take example value
    decimal_places = abs(Decimal(str(example_value)).as_tuple().exponent)

    if side == "BUY":
        new_sl_calc = swing_values[symbol]["high"] - (atr_value * 3)
        new_sl = round(new_sl_calc, decimal_places)
    elif side == "SELL":
        new_sl_calc = swing_values[symbol]["low"] + (atr_value * 3)
        new_sl = round(new_sl_calc, decimal_places)
    else:
        log.error("Unknown position side: %s", side)
        return None
    return new_sl

def update_stop_loss(login_manager, positions, atr_values, swing_values, atr_lock, swing_lock):
    """Update the stop loss for each position based on 3xATR."""
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
            new_sl = calculate_new_sl(position, atr_value, swing_values)
        if new_sl is not None:
            if side == "BUY":
                if new_sl > stop_loss:
                    log.info(
                        "Updating stop loss for %s: %s -> %s", symbol, stop_loss, new_sl
                    )
                    # Update stop loss using the Trading API
                    edit_sl_position(
                        login_manager,
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
                        symbol
                    )
            elif side == "SELL":
                if new_sl < stop_loss:
                    log.info(
                        "Updating stop loss for %s: %s -> %s", symbol, stop_loss, new_sl
                    )
                    # Update stop loss using the Trading API
                    edit_sl_position(
                        login_manager,
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
                        symbol
                    )
            else:
                log.error("Unknown position side: %s", side)

def update_positions(login_manager, positions, symbols, interval=10):
    """Update positions every specified interval."""
    while True:
        positions.clear()
        new_positions = fetch_open_positions_once(login_manager)
        positions.extend(new_positions)
        new_symbols = [pos["symbol"] for pos in new_positions]

        # Update symbols list in place to avoid issues in threads
        symbols.clear()
        symbols.extend(new_symbols)

        log.info("Positions updated: %s", [position["symbol"] for position in positions])
        time.sleep(interval)

def update_atr_values(login_manager, symbols, atr_values, atr_lock, interval=30):
    """Update ATR values every specified interval."""
    while True:
        for symbol in symbols:
            atr_value = calculate_atr_from_market_data(login_manager, symbol)
            with atr_lock:
                if atr_value is not None:
                    atr_values[symbol] = atr_value
        log.info("ATR values updated: %s", atr_values)
        time.sleep(interval)

def update_swing_values(price_data, symbols, swing_values, swing_lock, interval=15):
    """Update high/low values every specified interval."""
    while True:
        for symbol in symbols:
            price_data.update_swing_values(symbol)
            with swing_lock:
                swing_values[symbol] = price_data.get_stored_values().get(symbol, {})
        log.info("Swing values updated: %s", swing_values)
        time.sleep(interval)

def run_strategy():
    """Main entry point for the trailing stop loss strategy."""
    utils.setup_logging()
    log.info("************ Running Trailing SL by ATR Strategy ************")

    # Initialize the Login Manager
    login_manager = LoginManager()
    try:
        log.info("Attempting to log in...")
        login_manager.login()

        # Start the token refresh process in a separate thread
        refresh_thread = threading.Thread(
            target=utils.start_new_login, args=(login_manager,)
        )
        refresh_thread.start()

        # Fetch and update market data for open positions
        positions = []
        symbols = []
        price_data = PriceData(login_manager)
        atr_values = {}
        swing_values = {}

        # Create locks for ATR and swing values
        atr_lock = threading.Lock()
        swing_lock = threading.Lock()

        # Start threads for updating positions, ATR values, and swing values
        threading.Thread(
            target=update_positions, args=(login_manager, positions, symbols)
        ).start()
        threading.Thread(
            target=update_atr_values, args=(login_manager, symbols, atr_values, atr_lock)
        ).start()
        threading.Thread(
            target=update_swing_values, args=(price_data, symbols, swing_values, swing_lock)
        ).start()

        # Main loop to update stop loss
        while True:
            update_stop_loss(
                login_manager,
                positions,
                atr_values,
                swing_values,
                atr_lock,
                swing_lock
            )
            time.sleep(10)  # Adjust this interval as needed

    except (ConnectionError, KeyError) as e:
        log.error("A connection or key error occurred: %s", e)
    except ValueError as e:
        log.error("A value error occurred: %s", e)
    except RuntimeError as e:
        log.error("A runtime error occurred: %s", e)
