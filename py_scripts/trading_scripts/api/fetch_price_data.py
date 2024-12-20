"""A module for fetching and updating market data for open positions.
   This module does not work in utils.py as it imports PriceData from api.price_data
   and PriceData imports fetch_open_positions from utils.py.
"""
import time
import logging as log
from api.price_data import PriceData # pylint: disable=import-error
from api.utils import fetch_open_positions_once # pylint: disable=import-error

def fetch_price_data(system_uuid, auth_trading_api, cookie, symbols, check_interval=15):
    """Fetch market data for the given symbols."""
    log.info("Starting price data fetch loop.")
    price_data = PriceData(system_uuid, auth_trading_api, cookie)
    positions = fetch_open_positions_once(system_uuid, auth_trading_api, cookie)
    symbols = [pos["symbol"] for pos in positions]
    # log.info("Symbols for Market Watch: %s", symbols)
    while True:
        try:
            for symbol in symbols:
                price_data.update_swing_values(symbol)
            stored_values = price_data.get_stored_values()
            log.info("Stored swing values: %s", stored_values)
            time.sleep(check_interval)
        except (ConnectionError, TimeoutError) as e:
            log.error("A network error occurred while fetching market data: %s", e)
            break
        except ValueError as e:
            log.error("A value error occurred while processing market data: %s", e)
            break
        except (KeyError, TypeError) as e:
            log.error("An error occurred while processing market data: %s", e)
            break
