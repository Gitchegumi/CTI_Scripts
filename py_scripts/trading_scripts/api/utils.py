"""A utility module for common functions used across the trading scripts.

Returns:
    None
"""
import logging as log
from logging.handlers import RotatingFileHandler
import time
import requests
from api.open_positions import OpenPositionsAPI # pylint: disable=import-error


PLATFORM_URL = "https://platform.citytradersimperium.com"

def edit_sl_position(
        system_uuid,
        auth_trading_api,
        cookie,
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
    url = f"{PLATFORM_URL}/mtr-api/{system_uuid}/position/edit"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Auth-trading-api": auth_trading_api,
        "Cookie": f"co-auth={cookie}",
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
        "./logs/debug.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )  # 5MB per file, 3 backups
    log_handler.setFormatter(log.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    log.basicConfig(
        level=log.INFO,
        handlers=[log_handler, log.StreamHandler()],
    )

def fetch_open_positions_loop(system_uuid, auth_trading_api, cookie, check_interval=1):
    """Fetch open positions periodically."""
    log.info("Fetching Open Positions.")
    open_positions_api = OpenPositionsAPI(system_uuid, auth_trading_api, cookie)

    while True:
        try:
            # log.info("Fetching open positions...")
            positions = open_positions_api.get_open_positions()

            if positions:
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

def fetch_open_positions_once(system_uuid, auth_trading_api, cookie):
    """Fetch open positions periodically."""
    # log.info("Fetching Open Positions.")
    open_positions_api = OpenPositionsAPI(system_uuid, auth_trading_api, cookie)
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
