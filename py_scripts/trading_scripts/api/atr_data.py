"""A module for calculating the Average True Range (ATR) 
using market data fetched from the PriceData class.

Returns:
    float: The calculated ATR value.
"""

import logging as log
from decimal import Decimal
import pandas as pd # pylint: disable=import-error
import talib
from api.price_data import PriceData  # pylint: disable=import-error


def calculate_atr_from_market_data(
    system_uuid, auth_trading_api, cookie, symbol, resolution="5", period=14
):
    """
    Calculate ATR using market data fetched from the PriceData class.

    Parameters:
    - price_data_instance: An instance of the PriceData class.
    - symbol: The trading instrument (e.g., "EURUSD").
    - resolution: The timeframe for candles (e.g., "5").
    - period: The ATR period (default: 50).

    Returns:
    - ATR value for the given symbol.
    """
    atr_data = PriceData(system_uuid, auth_trading_api, cookie)
    try:
        data = atr_data.fetch_atr_data(symbol, resolution, 50)
        # log.info("ATR data: %s", data)
        if data is None or data.empty:
            log.error("Failed to fetch data for ATR calculation.")
            return None

        # Extract high, low, and close prices as numpy arrays
        high = data["high"].to_numpy()
        low = data["low"].to_numpy()
        close = data["close"].to_numpy()

        # Calculate ATR using TA-Lib
        atr_values = talib.ATR(high, low, close, period)
        if atr_values is None or pd.isna(atr_values[-1]):
            log.error("Not enough data to calculate ATR for symbol: %s", symbol)
            return None

        # Determine decimal precision
        example_close = data["close"].iloc[0]  # Take the first 'close' value
        decimal_places = abs(Decimal(str(example_close)).as_tuple().exponent)

        # Round ATR to match precision
        rounded_atr = round(atr_values[-1], decimal_places)
        # log.info("Calculated ATR for %s: %s", symbol, rounded_atr)
        return rounded_atr

    except (ValueError, KeyError, AttributeError) as e:
        log.error("Error calculating ATR for symbol %s: %s", symbol, e)
        return None
