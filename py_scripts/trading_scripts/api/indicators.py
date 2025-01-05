"""Module for calculating technical indicators.
"""
import pandas as pd  # pylint: disable=unused-import
import pandas_ta as ta  # pylint: disable=unused-import


class Indicators:
    """A class for calculating technical indicators.

    Raises:
        ValueError: If the DataFrame is missing required columns.

    Returns:
        pd.Series: The calculated indicator values.
    """
    @staticmethod
    def validate_data(data):
        """Validate that the DataFrame has the required columns."""
        required_columns = ["o", "h", "l", "c"]  # 's' is optional
        for col in required_columns:
            if col not in data.columns:
                raise ValueError(f"Missing required column: {col}")

    @staticmethod
    def prepare_data(data):
        """Prepare data by renaming columns for compatibility with pandas-ta."""
        Indicators.validate_data(data)
        # Rename columns for pandas-ta compatibility
        return data.rename(
            columns={"o": "open", "h": "high", "l": "low", "c": "close", "s": "volume"}
        )

    @staticmethod
    def calculate_rsi(data, length=14):
        """Calculate RSI using pandas-ta."""
        data = Indicators.prepare_data(data)
        return data.ta.rsi(length=length)

    @staticmethod
    def calculate_stoch_rsi(data, length=14, k=3, d=3):
        """Calculate Stochastic RSI using pandas-ta."""
        data = Indicators.prepare_data(data)
        return data.ta.stochrsi(length=length, k=k, d=d)

    @staticmethod
    def calculate_macd(data, fast=12, slow=26, signal=9):
        """Calculate MACD using pandas-ta."""
        data = Indicators.prepare_data(data)
        macd = data.ta.macd(fast=fast, slow=slow, signal=signal)
        return macd

    @staticmethod
    def calculate_atr(data, length=14):
        """Calculate ATR using pandas-ta."""
        data = Indicators.prepare_data(data)
        return data.ta.atr(length=length)

    @staticmethod
    def calculate_keltner_channels(data, length=20, multiplier=1.5, mamode="ema"):
        """Calculate Keltner Channels using pandas-ta."""
        data = Indicators.prepare_data(data)
        kc = data.ta.kc(length=length, scalar=multiplier, mamode=mamode)
        return kc

    @staticmethod
    def calculate_ema(data, length=20):
        """Calculate EMA using pandas-ta."""
        data = Indicators.prepare_data(data)
        return data.ta.ema(length=length)

    @staticmethod
    def calculate_super_trend(data, length=10, multiplier=3.0):
        """Calculate Super Trend using pandas-ta."""
        data = Indicators.prepare_data(data)
        return data.ta.supertrend(length=length, multiplier=multiplier)

    @staticmethod
    def calculate_candlestick_patterns(data, name="all"):
        """Calculate candlestick patterns using pandas-ta."""
        data = Indicators.prepare_data(data)
        return data.ta.cdl_pattern(name=name)

    @staticmethod
    def calculate_aroon(data, length=14):
        """Calculate Aroon using pandas-ta."""
        data = Indicators.prepare_data(data)
        return data.ta.aroon(length=length)
