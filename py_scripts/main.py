import logging as log
import threading
from api.login import LoginManager
import api.utils as utils
from api.price_data import PriceData

def main():
    utils.setup_logging()
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
            refresh_thread = threading.Thread(target=utils.start_new_login, args=(login_manager,))
            refresh_thread.start()

            # Initialize PriceData
            price_data = PriceData(login_manager)

            # Test the PriceData functionality
            log.info("Fetching and updating swing values...")
            price_data.update_swing_values()

            # Log stored values to verify functionality
            stored_values = price_data.get_stored_values()
            log.info("Stored swing values: %s", stored_values)

            # Start fetching open positions in the main thread
            utils.fetch_open_positions(login_manager)
        else:
            log.error("Login failed. Missing auth details.")
    except Exception as e:
        log.error("An error occurred: %s", e)

if __name__ == "__main__":
    main()
