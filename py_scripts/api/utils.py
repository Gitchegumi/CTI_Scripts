import logging as log
from logging.handlers import RotatingFileHandler
import time
from api.open_positions import OpenPositionsAPI


PLATFORM_URL = "https://platform.citytradersimperium.com"

def clean_positions(positions):
    """Remove unnecessary nested 'positions' field."""
    for position in positions:
        if "positions" in position:
            del position["positions"]
    return positions

def setup_logging():
    log_handler = RotatingFileHandler(
        "./logs/debug.log", maxBytes=5 * 1024 * 1024, backupCount=3
    )  # 5MB per file, 3 backups
    log_handler.setFormatter(log.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    log.basicConfig(
        level=log.INFO,
        handlers=[log_handler, log.StreamHandler()],
    )

def fetch_open_positions(login_manager, check_interval=1):
    """Fetch open positions periodically."""
    log.info("Starting open positions fetch loop.")
    open_positions_api = OpenPositionsAPI(login_manager)

    while True:
        try:
            # log.info("Fetching open positions...")
            positions = open_positions_api.get_open_positions()

            if positions:
                positions = clean_positions(positions.get("positions", []))
                filtered_positions = [
                    {
                        "symbol": pos["symbol"],
                        "volume": pos["volume"],
                        "side": pos["side"],
                        "stopLoss": pos["stopLoss"],
                        "currentPrice": pos["currentPrice"],
                        "profit": pos["profit"],
                        "netProfit": pos["netProfit"],
                    }
                    for pos in positions
                ]
                log.info("%s", filtered_positions)
            else:
                log.warning("No open positions found.")

            # log.info("Sleeping for %s seconds before fetching again...", check_interval)
            time.sleep(check_interval)
        except Exception as e:
            log.error("An error occurred while fetching open positions: %s", e)
            break

def start_new_login(login_manager):
    """Wrapper for starting periodic login in a thread."""
    login_manager.start_periodic_login()
