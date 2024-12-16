import logging as log
import threading
import time
from api.login import LoginManager
from api.open_positions import OpenPositionsAPI
import api.utils as utils

CHECK_INTERVAL = 1

def fetch_open_positions(login_manager):
    """Fetch open positions periodically."""
    log.info("Starting open positions fetch loop.")
    open_positions_api = OpenPositionsAPI(login_manager)

    while True:
        try:
            # log.info("Fetching open positions...")
            positions = open_positions_api.get_open_positions()

            if positions:
                positions = utils.clean_positions(positions.get("positions", []))
                log.info("%s", positions)
            else:
                log.warning("No open positions found.")

            # log.info("Sleeping for %s seconds before fetching again...", CHECK_INTERVAL)
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            log.error("An error occurred while fetching open positions: %s", e)
            break

def start_token_refresh(login_manager):
    """Start token refresh in a separate thread."""
    log.info("Starting token refresh loop.")
    login_manager.start_token_refresh()

def main():
    log.info("************ Starting Application ************")

    # Initialize the Login Manager
    login_manager = LoginManager()
    try:
        log.info("Attempting to log in...")
        login_manager.login()

        auth_details = login_manager.get_auth_details()
        if auth_details["auth_trading_api"] and auth_details["cookie"]:
            log.info("Login successful!")

            # Start the token refresh process in a separate thread
            refresh_thread = threading.Thread(target=start_token_refresh, args=(login_manager,), daemon=True)
            refresh_thread.start()

            # Start fetching open positions in the main thread
            fetch_open_positions(login_manager)
        else:
            log.error("Login failed. Missing auth details.")
    except Exception as e:
        log.error("An error occurred: %s", e)

if __name__ == "__main__":
    log.basicConfig(
        level=log.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[log.StreamHandler()],
    )
    main()
