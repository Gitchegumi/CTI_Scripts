"""A utility module for common functions used across the trading scripts.

Returns:
    None
"""
import logging as log
from logging.handlers import RotatingFileHandler
import time
import json
import requests
from trading_scripts.api.open_positions import OpenPositionsAPI # pylint: disable=import-error


PLATFORM_URL = "https://platform.citytradersimperium.com"

def edit_sl_position(
        login_manager,
        position_id,
        instrument,
        order_side,
        volume,
        sl_price,
        tp_price=0,
        trailing_distance=0
    ):
    """Edit the stop loss position via the Match Trader API.

    Args:
        login_manager (LoginManager): The login manager instance.
        position_id (str): The ID of the position to edit.
        instrument (str): The trading instrument (e.g., "EURUSD").
        order_side (str): The side of the order ("BUY" or "SELL").
        volume (float): The volume of the position.
        sl_price (float): The new stop loss price.
        tp_price (float, optional): The take profit price. Defaults to 0.
        trailing_distance (float, optional): The trailing distance. Defaults to 0.

    Returns:
        bool: True if the request was successful, False otherwise.
    """
    url = f"{PLATFORM_URL}/mtr-api/{login_manager.system_uuid}/position/edit"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Auth-trading-api": login_manager.auth_trading_api,
        "Cookie": f"co-auth={login_manager.cookie}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    payload = {
        "id": position_id,
        "instrument": instrument,
        "orderSide": order_side,
        "volume": volume,
        "isMobile": False,
        "slPrice": sl_price,
        "tpPrice": tp_price,
        "trailingDistance": trailing_distance,
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        log.info("Successfully updated SL for position %s: %s", position_id, sl_price)
        return True
    except requests.RequestException as e:
        log.error("Failed to update SL for position %s: %s", position_id, e)
        return False
    
def close_position(login_manager, position_id, symbol, side, volume):
    """Close a position via the Match Trader API.

    Args:
        login_manager (LoginManager): The login manager instance.
        position_id (str): The ID of the position to close.
        symbol (str): The trading symbol (e.g., "EURUSD").
        side (str): The side of the order ("BUY" or "SELL").
        volume (float): The volume of the position.

    Returns:
        bool: True if the request was successful, False otherwise.
    """
    url = f"{PLATFORM_URL}/mtr-api/{login_manager.system_uuid}/position/close"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Auth-trading-api": login_manager.auth_trading_api,
        "Cookie": f"co-auth={login_manager.cookie}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    payload = json.dumps({
        "positionId": position_id,
        "instrument": symbol,
        "orderSide": side,
        "volume": volume,
    })
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        log.info("Successfully closed position %s", position_id)
        return True
    except requests.RequestException as e:
        log.error("Failed to close position %s: %s", position_id, e)
        return False

def clean_positions(positions):
    """Remove unnecessary nested 'positions' field."""
    for position in positions:
        if "positions" in position:
            del position["positions"]
    return positions

def setup_logging():
    """Configure logging for the application.
    """
    log_handler = RotatingFileHandler(
        "./logs/debug.log", maxBytes=1 * 1024 * 1024, backupCount=3
    )  # 1MB per file, 3 backups
    log_handler.setFormatter(log.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    log.basicConfig(
        level=log.INFO,
        handlers=[log_handler, log.StreamHandler()],
    )

def fetch_open_positions_loop(login_manager, check_interval=1):
    """Fetch open positions periodically."""
    log.info("Fetching Open Positions.")
    open_positions_api = OpenPositionsAPI(login_manager)

    while True:
        try:
            # log.info("Fetching open positions...")
            positions = open_positions_api.get_open_positions()
            if not positions:
                positions = []
            elif positions:
                positions = clean_positions(positions.get("positions", []))
                # filtered_positions = [
                #     {
                #         "symbol": pos["symbol"],
                #         "side": pos["side"],
                #         "stop loss": pos["stopLoss"],
                #     }
                #     for pos in positions
                # ]
                # log.info("%s", filtered_positions)
            else:
                log.warning("No open positions found.")

            # log.info("Sleeping for %s seconds before fetching again...", check_interval)
            time.sleep(check_interval)
        except (ConnectionError, TimeoutError) as e:
            log.error("A network error occurred while fetching open positions: %s", e)
            break
        except ValueError as e:
            log.error("A value error occurred while processing positions: %s", e)
            break
        except (KeyError, TypeError) as e:
            log.error("An error occurred while processing positions: %s", e)
            break

def fetch_open_positions_once(login_manager):
    """Fetch open positions periodically."""
    # log.info("Fetching Open Positions.")
    open_positions_api = OpenPositionsAPI(login_manager)
    try:
        # log.info("Fetching open positions...")
        positions = open_positions_api.get_open_positions()

        if positions:
        #     positions = clean_positions(positions.get("positions", []))
            # filtered_positions = [
            #     {
            #         "symbol": pos["symbol"],
            #         "side": pos["side"],
            #         "stop loss": pos["stopLoss"],
            #     }
            #     for pos in positions
            # ]
            # log.info("Symbols for Market Watch: %s", filtered_positions)
            return positions
        log.warning("No open positions found.")
    except (ConnectionError, TimeoutError) as e:
        log.error("A network error occurred while fetching open positions: %s", e)
        return []
    except ValueError as e:
        log.error("A value error occurred while processing positions: %s", e)
        return []
    except (KeyError, TypeError) as e:
        log.error("An error occurred while processing positions: %s", e)
        return []

def print_boxed_message(message, log_func=log.info, fixed_width=75):
    """Print a message in a box.

    Args:
        message (str): The message to print.
    """
    try:
        # Try to parse the message as JSON
        parsed_message = json.loads(message)
        message = json.dumps(parsed_message, indent=2)
        is_json = True
    except json.JSONDecodeError:
        # If it's not JSON, leave the message as is
        is_json = False

    lines = message.split('\n')
    max_length = max(len(line) for line in lines)
    border_length = max(max_length, fixed_width) + 4
    border = '*' * border_length
    log_func(border)
    for line in lines:
        if is_json:
            log_func(f"* {line.ljust(border_length - 4)} *")
        else:
            log_func(f"* {line.center(border_length - 4)} *")
    log_func(border)

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
    url = f"{PLATFORM_URL}/mtr-api/{login_manager.system_uuid}/position/open"
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

    log.info(json.dumps(payload, indent=2))

    session = requests.Session()
    session.headers.update(headers)
    try:
        response = session.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        print_boxed_message(f"{direction} trade successfully opened for {symbol}!!!")
        print_boxed_message(json.dumps(response.json(), indent=2))
    except requests.RequestException as e:
        log.error("Failed to open position for %s: %s", symbol, e)
