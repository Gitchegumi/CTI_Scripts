"""A module for fetching market data from the Match Trader API.

Returns:
    dict: A dictionary containing market data.
"""

import logging as log
from datetime import datetime
from api.utils import (  # pylint: disable=import-error
    PLATFORM_URL,
)
import requests
import pandas as pd # pylint: disable=import-error


class PriceData:
    """A class for fetching and updating market data."""

    def __init__(self, system_uuid, auth_trading_api, cookie):
        self.system_uuid = system_uuid
        self.auth_trading_api = auth_trading_api
        self.cookie = cookie
        self.stored_values = {}  # To store the most recent swing values per position

    def fetch_market_data(self, symbol, resolution="5", countback=500):
        """Fetch market data for the given symbols."""
        url = f"{PLATFORM_URL}/market-data-api/{self.system_uuid}/api/trading-view/history"

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
