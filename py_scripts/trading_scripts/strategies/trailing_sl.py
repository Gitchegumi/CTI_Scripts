"""A trailing stop loss strategy that uses the Trading API to fetch and update open positions."""

import logging as log
import threading
from api.login import LoginManager  # pylint: disable=import-error
import api.utils as utils  # pylint: disable=import-error
from api.fetch_price_data import fetch_price_data  # pylint: disable=import-error
from api.atr_data import calculate_atr_from_market_data  # pylint: disable=import-error


def run_strategy():
    """Main entry point for the trailing stop loss strategy."""
    utils.setup_logging()
    log.info("************ Running Trailing SL by ATR Strategy ************")

    # Initialize the Login Manager
    login_manager = LoginManager()
    try:
        log.info("Attempting to log in...")
        login_manager.login()
        cookie = login_manager.cookie
        auth_trading_api = login_manager.auth_trading_api
        system_uuid = login_manager.system_uuid

        # Start the token refresh process in a separate thread
        # refresh_thread = threading.Thread(
        #     target=login_manager.refresh_token, args=(auth_trading_api,)
        # )
        # refresh_thread.start()

        # Fetch and update market data for open positions
        data_symbols = utils.fetch_open_positions_once(
            system_uuid, auth_trading_api, cookie
        )
        fetch_thred = threading.Thread(
            target=fetch_price_data,
            args=(system_uuid, auth_trading_api, cookie, data_symbols),
        )
        fetch_thred.start()

        # Fetch and update ATR data for open positions
        atr_thread = threading.Thread(
            target=calculate_atr_from_market_data,
            args=(system_uuid, auth_trading_api, cookie, data_symbols),
        )
        atr_thread.start()

        # while True:
        #     fetch_open_positions_loop(login_manager, check_interval=10)

    except (ConnectionError, KeyError) as e:
        log.error("A connection or key error occurred: %s", e)
    except ValueError as e:
        log.error("A value error occurred: %s", e)
    except RuntimeError as e:
        log.error("A runtime error occurred: %s", e)
