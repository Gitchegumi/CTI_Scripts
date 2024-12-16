"""A script to fetch open positions from the City Traders Imperium platform.

Returns:
    dict: Open positions
"""
import os
import logging as log
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

log.basicConfig(
    level=log.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[log.FileHandler("./logs/debug.log"), log.StreamHandler()],
)

PLATFORM_URL = "https://platform.citytradersimperium.com"
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
BROKER_ID = os.getenv("BROKER_ID")
CHECK_INTERVAL = 60


class TradingAPI:
    """Class to interact
    """
    def __init__(self):
        self.session = requests.Session()
        self.auth_trading_api = None
        self.cookie = None
        self.system_uuid = None

    def login(self):
        """Login to the platform and retrieve tokens.
        """
        url = f"{PLATFORM_URL}/mtr-core-edge/login"
        payload = {"email": EMAIL, "password": PASSWORD, "brokerId": BROKER_ID}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.6",
            "Origin": "https://platform.citytradersimperium.com",
            "Referer": "https://platform.citytradersimperium.com/login",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Sec-Gpc": "1",
        }
        # masked_payload = {**payload, "password": "******"}  # Mask the password
        # log.debug("Login request payload: %s", masked_payload)
        try:
            response = self.session.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            # log.debug("Login response: %s", data)

            # Handle tradingAccounts list
            try:
                if "tradingAccounts" in data and data["tradingAccounts"]:
                    self.auth_trading_api = data["tradingAccounts"][0]["tradingApiToken"]
                    log.info("Trading API Token set for the first trading account.")
                    # log.debug("Trading API Token: %s", self.auth_trading_api)
                else:
                    log.error("No trading accounts found in login response.")
                    return
            except (KeyError, IndexError) as e:
                log.error("Error processing trading accounts: %s", e)
                raise
            self.cookie = data["token"]
            # log.debug("co-auth=%s", self.cookie)

            system = data["tradingAccounts"][0]["offer"].get("system", {})
            self.system_uuid = system.get("uuid")
            # log.debug("System UUID: %s", self.system_uuid)

            log.info("Login successful. Tokens retrieved.")
        except requests.exceptions.RequestException as e:
            log.error("Login failed: %s", e)

    def get_open_positions(self):
        """Fetch open positions from the trading API.
        """
        url = f"{PLATFORM_URL}/mtr-api/{self.system_uuid}/open-positions"
        payload = {}
        headers = {
            "Auth-trading-api": self.auth_trading_api,
            "Cookie": f"co-auth={self.cookie}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.6",
            "Origin": PLATFORM_URL,
            "Referer": PLATFORM_URL,
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

def clean_positions(positions):
    """Remove unnecessary nested 'positions' field."""
    for position in positions:
        if 'positions' in position:
            del position['positions']
    return positions


if __name__ == "__main__":
    log.info("************Starting************")
    api = TradingAPI()
    api.login()
    if api.auth_trading_api and api.cookie:
        while True:
            try:
                positions = api.get_open_positions()

                if positions:
                    positions = clean_positions(positions.get("positions", []))
                    log.info("Processing positions: %s", positions)
                else:
                    log.warning("No open positions to process.")

                log.info("Sleeping for %s seconds", CHECK_INTERVAL)
                time.sleep(CHECK_INTERVAL)
            except (requests.exceptions.RequestException, KeyError, IndexError) as e:
                log.error("An error occurred: %s", e)
                break
