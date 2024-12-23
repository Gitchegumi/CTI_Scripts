"""A module for interacting with Match Trader API to fetch open positions.

Returns:
    dict: A dictionary containing open positions data.
"""
import logging as log
import requests
from trading_scripts.api import utils # pylint: disable=import-error
from trading_scripts.api.login import LoginManager # pylint: disable=import-error

class OpenPositionsAPI:
    """Class to interact with open positions API."""

    def __init__(self, login_manager: LoginManager):
        self.login_manager = login_manager

    def get_open_positions(self):
        """Fetch open positions from the trading API.
        """
        url = f"{utils.PLATFORM_URL}/mtr-api/{self.login_manager.system_uuid}/open-positions"
        headers = {
            "Auth-trading-api": self.login_manager.auth_trading_api,
            "Cookie": f"co-auth={self.login_manager.cookie}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.6",
            "Origin": utils.PLATFORM_URL,
            "Referer": utils.PLATFORM_URL,
        }
        session = requests.Session()
        session.headers.update(headers)

        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            open_positions = response.json()
            if not open_positions:
                log.info("No open positions")
                return []
            else:
                return open_positions
        except requests.exceptions.RequestException as e:
            log.error("Failed to fetch open positions: %s", e)
            return []
