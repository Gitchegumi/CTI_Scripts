"""A module for interacting with Match Trader API to fetch open positions.

Returns:
    dict: A dictionary containing open positions data.
"""
import logging as log
import api.utils as utils # pylint: disable=import-error
import requests

class OpenPositionsAPI:
    """Class to interact with open positions API."""

    def __init__(self, system_uuid, auth_trading_api, cookie):
        self.system_uuid = system_uuid
        self.auth_trading_api = auth_trading_api
        self.cookie = cookie

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
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=10)
            response.raise_for_status()
            open_positions = response.json()
            return open_positions
        except requests.exceptions.RequestException as e:
            log.error("Failed to fetch open positions: %s", e)
            return []
