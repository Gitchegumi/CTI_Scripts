import logging as log
from api.open_positions import OpenPositionsAPI
from api.utils import PLATFORM_URL
import requests

class PriceData:
    def __init__(self, login_manager):
        self.login_manager = login_manager
        self.stored_values = {}  # To store the most recent swing values per position

    def fetch_market_data(self, symbols):
        """Fetch market data for the given symbols."""
        url = f"{PLATFORM_URL}/mtr-api/{self.login_manager.system_uuid}/quotations"
        headers = {
            "Auth-trading-api": self.login_manager.auth_trading_api,
            "Cookie": f"co-auth={self.login_manager.cookie}",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
        params = {"symbols": ",".join(symbols)}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            log.info("Market data fetched successfully. %s", response.json())
            data = response.json()
            return data.get("body", [])
        except requests.exceptions.RequestException as e:
            log.error("Failed to fetch market data: %s", e)
            return []

    def update_swing_values(self):
        """Update the most recent swing values for each open position."""
        open_positions_api = OpenPositionsAPI(self.login_manager)
        open_positions = open_positions_api.get_open_positions()

        if not open_positions:
            log.info("No open positions found.")
            return

        symbols = [position["symbol"] for position in open_positions]
        market_data = self.fetch_market_data(symbols)

        market_data_dict = {item["symbol"]: item for item in market_data}

        for position in open_positions:
            symbol = position["symbol"]
            side = position["side"].upper()

            if symbol not in market_data_dict:
                log.warning("Market data for %s not found.", symbol)
                continue

            current_high = float(market_data_dict[symbol]["high"])
            current_low = float(market_data_dict[symbol]["low"])

            if symbol not in self.stored_values:
                self.stored_values[symbol] = {
                    "high": current_high,
                    "low": current_low,
                }
                log.info("Initialized stored values for %s: High=%s, Low=%s", symbol, current_high, current_low)

            if side == "BUY":
                if current_high > self.stored_values[symbol]["high"]:
                    self.stored_values[symbol]["high"] = current_high
                    log.info("Updated high for %s: %s", symbol, current_high)

            elif side == "SELL":
                if current_low < self.stored_values[symbol]["low"]:
                    self.stored_values[symbol]["low"] = current_low
                    log.info("Updated low for %s: %s", symbol, current_low)

    def get_stored_values(self):
        """Retrieve the current stored swing values."""
        return self.stored_values
