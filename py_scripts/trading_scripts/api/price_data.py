"""A module for fetching market data from the Match Trader API.

Returns:
    dict: A dictionary containing market data.
"""

import logging as log
from datetime import datetime
from trading_scripts.api import utils  # pylint: disable=import-error
import requests
import pandas as pd # pylint: disable=import-error


class PriceData:
    """A class for fetching and updating market data."""

    def __init__(self, login_manager):
        self.system_uuid = login_manager.system_uuid
        self.auth_trading_api = login_manager.auth_trading_api
        self.cookie = login_manager.cookie
        self.stored_values = {}  # To store the most recent swing values per position

    def fetch_market_data(self, symbol, resolution="5", countback=500):
        """Fetch market data for the given symbols."""
        url = f"{utils.PLATFORM_URL}/market-data-api/{self.system_uuid}/api/trading-view/history"

        headers = {
            "Auth-trading-api": self.auth_trading_api,
            "Cookie": f"co-auth={self.cookie}",
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
        }

        # Calculate timestamps dynamically
        to_time = int(datetime.now().timestamp())
        from_time = to_time - (int(resolution) * 60 * countback)

        params = {
            "symbol": symbol,
            "resolution": resolution,
            "from": from_time,
            "to": to_time,
            "shouldRetrieveOnlyFromCache": "true",
            "countback": countback,
        }

        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            # log.info("Market data fetched successfully.")
            data = response.json()
            if data.get("s") == "ok":
                # log.info("Market data fetched for %s: %s", symbol, data)
                return data
            else:
                log.error("Failed to fetch market data for %s: %s", symbol, data)
                return {}
        except requests.exceptions.RequestException as e:
            log.error("Failed to fetch market data: %s", e)
            return {}

    def update_swing_values(self, symbol, resolution="5", countback=1):
        """Update the most recent swing values for each open position."""
        market_data = self.fetch_market_data(symbol, resolution, countback)
        # log.info("Market data: %s", market_data)

        if not market_data:
            log.warning("No market data found for symbol: %s", symbol)
            return

        timestamps = market_data.get("t", [])
        highs = market_data.get("h", [])
        lows = market_data.get("l", [])

        if not timestamps or not highs or not lows:
            log.warning("Incomplete market data for symbol: %s", symbol)
            return

        # Extract latest high and low
        latest_high = float(highs[-1])
        latest_low = float(lows[-1])

        # Initialize or update swing values
        if symbol not in self.stored_values:
            self.stored_values[symbol] = {"high": latest_high, "low": latest_low}
            log.info(
                "Initialized values for %s: High=%s, Low=%s",
                symbol,
                latest_high,
                latest_low,
            )
        else:
            stored_high = self.stored_values[symbol]["high"]
            stored_low = self.stored_values[symbol]["low"]

            if latest_high > stored_high:
                self.stored_values[symbol]["high"] = latest_high
                log.info("Updated high for %s: %s", symbol, latest_high)

            if latest_low < stored_low:
                self.stored_values[symbol]["low"] = latest_low
                log.info("Updated low for %s: %s", symbol, latest_low)

    def get_stored_values(self):
        """Retrieve the current stored swing values."""
        return self.stored_values

    def fetch_atr_data(self, symbol, resolution="5", period=14):
        """
        Fetch market data to calculate ATR.

        Parameters:
        - symbol: The trading instrument (e.g., "EURUSD").
        - resolution: The timeframe for candles (e.g., "5" for 5-minute candles).
        - period: The ATR period (default: 14).

        Returns:
        - DataFrame with 'high', 'low', and 'close' columns for ATR calculation.
        """
        market_data = self.fetch_market_data(symbol, resolution, countback=period)
        # log.info(
        #     "Market data fetched for ATR calculation for %s: %s", symbol, market_data
        # )

        if not market_data:
            log.warning(
                "No market data fetched for ATR calculation for symbol: %s", symbol
            )
            return None

        timestamps = market_data.get("t", [])
        highs = market_data.get("h", [])
        lows = market_data.get("l", [])
        closes = market_data.get("c", [])

        if not (timestamps and highs and lows and closes):
            log.warning(
                "Incomplete market data for ATR calculation for symbol: %s", symbol
            )
            return None

        # Convert data into a DataFrame for easier processing
        data = pd.DataFrame(
            {
                "timestamp": timestamps,
                "high": highs,
                "low": lows,
                "close": closes,
            }
        )

        # Convert timestamp to datetime for readability
        data["timestamp"] = pd.to_datetime(data["timestamp"], unit="ms")
        return data
    
    def fetch_account_balance(self):
        """Fetch account balance data."""
        url = f"{utils.PLATFORM_URL}/mtr-api/{self.system_uuid}/balance"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Origin": "https://platform.citytradersimperium.com",
            "Referer": "https://platform.citytradersimperium.com/dashboard",
            "Auth-trading-api": self.auth_trading_api,
            "Cookie": f"co-auth={self.cookie}",
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
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            account_balance = response.json()
            log.info("Account balance fetched successfully.")
            return account_balance
        except requests.exceptions.RequestException as e:
            log.error("Failed to fetch account balance: %s", e)
            return {}
        
    def fetch_symbol_data(self, symbol):
        """Get the latest news for a symbol."""
        url = f"{utils.PLATFORM_URL}/market-data-api/{self.system_uuid}/api/trading-view/symbols?symbol={symbol}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
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

        session = requests.Session()
        session.headers.update(headers)
        session.cookies.set("co-auth", self.cookie, domain="citytradersimperium.com", path="/mtr-backend/refresh-token")
        try:
            response = session.get(url)
            response.raise_for_status()
            symbol_data = response.json()
            return symbol_data
        except requests.exceptions.RequestException as e:
            print(f"Failed to get symbol data: {e}")
            return None
