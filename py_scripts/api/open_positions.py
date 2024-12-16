from api.login import LoginManager
import api.utils as utils
import requests
import logging as log

log.basicConfig(
    level=log.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[log.FileHandler("./logs/debug.log"), log.StreamHandler()],
)

class OpenPositionsAPI:
    """Class to interact with open positions API."""

    def __init__(self, login_manager):
        self.session = login_manager.session
        self.auth_trading_api = login_manager.auth_trading_api
        self.cookie = login_manager.cookie
        self.system_uuid = login_manager.system_uuid

    def get_open_positions(self):
        """Fetch open positions from the trading API.
        """
        url = f"{utils.PLATFORM_URL}/mtr-api/{self.system_uuid}/open-positions"
        payload = {}
        headers = {
            "Auth-trading-api": self.auth_trading_api,
            "Cookie": f"co-auth={self.cookie}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.6",
            "Origin": utils.PLATFORM_URL,
            "Referer": utils.PLATFORM_URL,
        }
        # log.debug("Open positions request headers: %s", headers)
        try:
            response = requests.request("GET", url, headers=headers, data=payload, timeout=10)
            response.raise_for_status()
            open_positions = response.json()
            # log.info("Retrieved open positions: %s", open_positions)
            return open_positions
        except requests.exceptions.RequestException as e:
            log.error("Failed to fetch open positions: %s", e)
            return []