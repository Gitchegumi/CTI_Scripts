import os
import time
import requests
import logging as log
from dotenv import load_dotenv
import api.utils as utils

# Load environment variables
load_dotenv()

log.basicConfig(
    level=log.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[log.FileHandler("./logs/debug.log"), log.StreamHandler()],
)

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
BROKER_ID = os.getenv("BROKER_ID")
INITIAL_REFRESH_INTERVAL = 15
FINAL_REFRESH_INTERVAL = 285

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

    def get_auth_details(self):
        """Returns authentication details."""
        return {
            "auth_trading_api": self.auth_trading_api,
            "cookie": self.cookie,
            "system_uuid": self.system_uuid,
        }
    
    def refresh_token(self):
        """Refresh the authentication token periodically."""        
        if not self.cookie:
            log.error("No token available to refresh. Login is required.")
            return

        url = f"{utils.PLATFORM_URL}/manager/refresh-token?rt={self.cookie}"
        payload = {}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(url, headers=headers, data=payload, timeout=10)
            if response.status_code == 200:
                log.info("Token refreshed successfully.")
            else:
                log.error("Failed to refresh token. Status code: %s", response.status_code)
        except requests.exceptions.RequestException as e:
            log.error("Token refresh failed: %s", e)

    def start_token_refresh(self):
        """Start a periodic token refresh process."""
        while True:
            try:
                log.info("Refresh token in %s seconds.", INITIAL_REFRESH_INTERVAL)
                time.sleep(INITIAL_REFRESH_INTERVAL)
                log.info("Refreshing token...")
                self.refresh_token()
                log.info("Sleeping for %s minutes until the next refresh.", (FINAL_REFRESH_INTERVAL + INITIAL_REFRESH_INTERVAL)/60)
                time.sleep(FINAL_REFRESH_INTERVAL)
            except Exception as e:
                log.error("An error occurred during token refresh: %s", e)
                break
