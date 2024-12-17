"""A trailing stop loss strategy that uses the Trading API to fetch and update open positions."""

import logging as log
import threading
from api.login import LoginManager  # pylint: disable=import-error
import api.utils as utils  # pylint: disable=import-error
from api.fetch_price_data import fetch_price_data  # pylint: disable=import-error

def run_strategy():
    """Main entry point for the trailing stop loss strategy."""
    utils.setup_logging()
    log.info("************ Running Trailing SL Strategy ************")

    # Initialize the Login Manager
    login_manager = LoginManager()
    try:
        log.info("Attempting to log in...")
        login_manager.login()

        auth_details = login_manager.get_auth_details()
        if auth_details["auth_trading_api"] and auth_details["cookie"]:
            log.info("Login successful!")

            # Start the token refresh process in a separate thread
            refresh_thread = threading.Thread(
                target=utils.start_new_login, args=(login_manager,)
            )
            refresh_thread.start()

            # Start fetching price data in the main thread
            symbols = ["EURUSD", "US500", "US30"]
            price_thread = threading.Thread(
                target=fetch_price_data, args=(login_manager, symbols)
            )
            price_thread.start()

            # Start fetching open positions in the main thread
            utils.fetch_open_positions(login_manager)

        else:
            log.error("Login failed. Missing auth details.")
    except (ConnectionError, KeyError) as e:
        log.error("A connection or key error occurred: %s", e)
    except ValueError as e:
        log.error("A value error occurred: %s", e)
    except RuntimeError as e:
        log.error("A runtime error occurred: %s", e)
