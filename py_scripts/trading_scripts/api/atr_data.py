"""A module for calculating the Average True Range (ATR) using market data fetched from the PriceData class.

Returns:
    float: The calculated ATR value.
"""

import logging as log
from decimal import Decimal
from api.price_data import PriceData  # pylint: disable=import-error


def calculate_atr_from_market_data(
    login_manager, symbol, resolution="5", period=14
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
    try:
        data = atr_data.fetch_atr_data(symbol, resolution, period)
        if data is None or data.empty:
            log.error("Failed to fetch data for ATR calculation.")
            return None

        # Calculate True Range (TR)
        data["previous_close"] = data["close"].shift(1)
        data["high_low"] = data["high"] - data["low"]
        data["high_prev_close"] = abs(data["high"] - data["previous_close"])
        data["low_prev_close"] = abs(data["low"] - data["previous_close"])
        data["TR"] = data[["high_low", "high_prev_close", "low_prev_close"]].max(axis=1)

        # Calculate ATR using the rolling mean
        atr_series = data["TR"].rolling(window=period).mean()
        if atr_series.isnull().all():
            log.error("Not enough data to calculate ATR for symbol: %s", symbol)
            return None
        atr = atr_series.iloc[-1]

        # Determine decimal precision
        example_close = data["close"].iloc[0]  # Take the first 'close' value
        decimal_places = abs(Decimal(str(example_close)).as_tuple().exponent)

        # Round ATR to match precision
        rounded_atr = round(atr, decimal_places)
        log.info("Calculated ATR for %s: %s", symbol, rounded_atr)
        return rounded_atr

    except (ValueError, KeyError, AttributeError) as e:
        log.error("Error calculating ATR for symbol %s: %s", symbol, e)
        return None
