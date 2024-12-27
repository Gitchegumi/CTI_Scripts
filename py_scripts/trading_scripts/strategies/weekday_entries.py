import os
import sys
import logging as log
from decimal import Decimal
import threading
import time
from trading_scripts.api import utils  # pylint: disable=import-error
from trading_scripts.api.login import (  # pylint: disable=import-error
    LoginManager,
)

from trading_scripts.api.atr_data import (  # pylint: disable=import-error
    calculate_atr_from_market_data,
)
from trading_scripts.api.price_data import (  # pylint: disable=import-error
    PriceData,
)

trading_hours = {
    "EURUSD": {
        "market_hours": {
            "start": "Monday 00:00:00",
            "end": "Friday 23:59:59",
        },
        "daily_swap" : {
            "start": "16:55:00",
            "end": "17:05:00",
        }
    },
    "US500": {
        "market_hours": {
            "start": "08:30:00",
            "end": "16:30:00",
        }
    },
    "US30": {
        "market_hours": {
            "start": "08:30:00",
            "end": "16:30:00",
        }
    },
    "BTCUSDC": {
        "daily_swap": {
            "start": "17:55:00",
            "end": "18:05:00",
        }
    },
}

trading_sybomls = ["EURUSD", "US500", "US30", "BTCUSDC"]

def determine_trading_hours(symbols):
    for symbol in symbols:
        pass

def calc_linear_regression(symbol):
        pass

def get_trend(symbols):
    for symbol in symbols:
        if calc_linear_regression(symbol) > 0:
            return "buy"
        else:
            return "sell"

def calc_atr(symbols):
    length = 14
    for symbol in symbols:
        pass

def calc_rsi(symbols):
    length = 14
    k = 3
    d = 3
    stoch = 14
    for symbol in symbols:
        pass

def calc_macd(symbols):
    fast_length = 12
    slow_length = 26
    signal_length = 9
    for symbol in symbols:
        pass

def calc_keltner_channel(symbols):
    lenght = 20
    multiplier = 1.5
    for symbol in symbols:
        pass

def calc_stop_loss(symbols):
    for symbol in symbols:
        pass

def calc_take_profit(symbols):
    for symbol in symbols:
        pass

def enter_trade(symbol, direction, stop_loss, take_profit):
    pass

def run_strategy():
    symbols = trading_sybomls
    direction = get_trend(symbols)
    stop_loss = calc_stop_loss(symbols)
    take_profit = calc_take_profit(symbols)
    determine_trading_hours(symbols)
    calc_atr(symbols)
    calc_rsi(symbols)
    calc_macd(symbols)
    calc_keltner_channel(symbols)
    for symbol in symbols:
        enter_trade(symbol, direction, stop_loss, take_profit)
    pass

if __name__ == "__main__":
    run_strategy()
