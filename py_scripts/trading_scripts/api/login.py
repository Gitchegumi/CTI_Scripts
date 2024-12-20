"""A module for handling authentication and token retrieval.

Raises:
    ValueError: If login fails.

Returns:
    None
"""

import os
import time
import logging as log
import requests
from dotenv import load_dotenv
import api.utils as utils  # pylint: disable=import-error

# Load environment variables
load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
BROKER_ID = os.getenv("BROKER_ID")
REFRESH_INTERVAL = 60 * 10  # 10 minutes


class LoginManager:
    """Handles authentication and token retrieval."""

    def __init__(self):
        self.session = requests.Session()
        self.auth_trading_api = None
        self.cookie = None
        self.system_uuid = None
        self.rt_token = None

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
            # log.info("response cookies: %s", response.cookies)
            # log.info("Login response: %s", data)

            if "tradingAccounts" in data and data["tradingAccounts"]:
                self.auth_trading_api = data["tradingAccounts"][0]["tradingApiToken"]
                rt_cookie = next(
                    (
                        cookie.value
                        for cookie in response.cookies
                        if cookie.name == "rt" and "mtr-backend" in cookie.path
                    ),
                    None,
                )
                self.rt_token = rt_cookie
                self.cookie = data["token"]
                self.system_uuid = (
                    data["tradingAccounts"][0]["offer"].get("system", {}).get("uuid")
                )
                log.info("Login successful. Tokens retrieved.")
                # log.info("rt token: %s", self.rt_token)
            else:
                log.error("No trading accounts found in login response.")
                raise ValueError("Login failed: No trading accounts found.")
        except requests.exceptions.RequestException as e:
            log.error("Login failed: %s", e)
            raise

    def refresh_token(self, rt_token, refresh_interval=REFRESH_INTERVAL):
        """Refresh the authentication token."""
        url = f"{utils.PLATFORM_URL}/mtr-backend/refresh-token"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Origin": "https://platform.citytradersimperium.com",
            "Referer": "https://platform.citytradersimperium.com/dashboard",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.8",
            "Sec-CH-UA": '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": "Windows",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-GPC": "1",
        }

        while True:
            log.info("Refreshing token in %s minutes.", refresh_interval / 60)
            time.sleep(refresh_interval)
            session = requests.Session()
            session.headers.update(headers)
            session.cookies.set(
                "rt",
                rt_token,
                domain="citytradersimperium.com",
                path="/mtr-backend/refresh-token",
            )
            try:
                response = session.post(url, json={})
                response.raise_for_status()
                # Extract the updated co-auth token from cookies
                new_co_auth = next(
                    (
                        cookie.value
                        for cookie in response.cookies
                        if cookie.name == "co-auth"
                    ),
                    None,
                )
                new_rt_token = next(
                    (
                        cookie.value
                        for cookie in response.cookies
                        if cookie.name == "rt" and "mtr-backend" in cookie.path
                    ),
                    None,
                )
                if new_co_auth != self.cookie:
                    print("Co-auth cookie refreshed successfully.")
                    self.cookie = new_co_auth
                if new_rt_token != self.rt_token:
                    print("RT token refreshed successfully.")
                    self.rt_token = new_rt_token
                else:
                    print("Failed to refresh token: No co-auth token in response.")
                    return None
            except requests.exceptions.RequestException as e:
                print(f"Failed to refresh token: {e}")
                return None
