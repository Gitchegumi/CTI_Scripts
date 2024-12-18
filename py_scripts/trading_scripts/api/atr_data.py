"""A module for calculating the Average True Range (ATR) using market data fetched from the PriceData class.

Returns:
    float: The calculated ATR value.
"""

import time
import logging as log
from decimal import Decimal
from api.price_data import PriceData  # pylint: disable=import-error
from api.utils import fetch_open_positions_once  # pylint: disable=import-error


def calculate_atr_from_market_data(
    login_manager, symbol, resolution="5", period=14, check_interval=30
):
    """
    Calculate ATR using market data fetched from the PriceData class.

    Parameters:
    - price_data_instance: An instance of the PriceData class.
    - symbol: The trading instrument (e.g., "EURUSD").
    - resolution: The timeframe for candles (e.g., "5").
    - period: The ATR period (default: 14).

    Returns:
    - ATR value for the given symbol.
    """
    atr_data = PriceData(login_manager)
    positions = fetch_open_positions_once(login_manager)
    symbols = [pos["symbol"] for pos in positions]

    while True:
        try:
            for symbol in symbols:
                data = atr_data.fetch_atr_data(symbol, resolution, period)
                if data is None or data.empty:
                    log.error("Failed to fetch data for ATR calculation.")
                    return None

                # Calculate ATR
                data["TR"] = data.apply(
                    lambda row: max(
                        row["high"] - row["low"],
                        abs(row["high"] - row["close"]),
                        abs(row["low"] - row["close"]),
                    ),
                    axis=1,
                )

                # Calculate ATR using the rolling mean
                atr = data["TR"].rolling(window=period).mean().iloc[-1]

                # Determine decimal precision
                example_close = data["close"].iloc[0]  # Take the first 'close' value
                decimal_places = abs(Decimal(str(example_close)).as_tuple().exponent)

                # Round ATR to match precision
                rounded_atr = round(atr, decimal_places)
                log.info(
                    "Calculated ATR for %s: %s",
                    symbol,
                    rounded_atr,
                )

            time.sleep(check_interval)
        except (ConnectionError, TimeoutError) as e:
            log.error("A network error occurred while calculating ATR: %s", e)
            break
