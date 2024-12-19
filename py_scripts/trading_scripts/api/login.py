"""A module for handling authentication and token retrieval.

Raises:
    ValueError: If login fails.

Returns:
    None
"""
import os
import logging as log
import time
import requests
from dotenv import load_dotenv
import api.utils as utils # pylint: disable=import-error

# Load environment variables
load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
BROKER_ID = os.getenv("BROKER_ID")
REFRESH_INTERVAL = 900  # 15 minutes

class LoginManager:
    """Handles authentication and token retrieval."""

    def __init__(self):
        self.session = requests.Session()
        self.auth_trading_api = None
        self.cookie = None
        self.system_uuid = None

    def login(self):
        """Login to the platform and retrieve tokens."""
        url = f"{utils.PLATFORM_URL}/mtr-core-edge/login"
        payload = {"email": EMAIL, "password": PASSWORD, "brokerId": BROKER_ID}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
        }
        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "tradingAccounts" in data and data["tradingAccounts"]:
                self.auth_trading_api = data["tradingAccounts"][0]["tradingApiToken"]
                self.cookie = data["token"]
                self.system_uuid = data["tradingAccounts"][0]["offer"].get("system", {}).get("uuid")
                log.info("Login successful. Tokens retrieved.")
            else:
                log.error("No trading accounts found in login response.")
                raise ValueError("Login failed: No trading accounts found.")
        except requests.exceptions.RequestException as e:
            log.error("Login failed: %s", e)
            raise

    def start_periodic_login(self):
        """Start a periodic login process."""
        while True:
            try:
                log.info("Sleeping for %s minutes until the next login.", REFRESH_INTERVAL / 60)
                time.sleep(REFRESH_INTERVAL)
                log.info("Logging in...")
                self.login()
            except (requests.exceptions.RequestException, ValueError) as e:
                log.error("An error occurred during login: %s", e)
                break
