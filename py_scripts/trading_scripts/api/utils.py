"""A utility module for common functions used across the trading scripts.

Returns:
    None
"""

import os
import logging as log
from logging.handlers import RotatingFileHandler
import time
from datetime import datetime, timedelta, timezone
import json
import csv
from decimal import Decimal
import requests
import pandas as pd
import pandas_ta as ta  # pylint: disable=unused-import
from trading_scripts.api.open_positions import (
    OpenPositionsAPI,
)
from trading_scripts.api.indicators import Indicators
from trading_scripts.api.price_data import PriceData


PLATFORM_URL = "https://platform.citytradersimperium.com"
CSV_FILE = "./logs/trade_log.csv"


def initialize_csv():
    """Initialize the CSV file for logging trade details."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, mode="w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "trade_id",
                    "symbol",
                    "open_date_time",
                    "volume",
                    "side",
                    "open_price",
                    "initial_stop_loss",
                    "take_profit",
                    "close_date_time",
                    "swap",
                    "commission",
                    "profit",
                    "close_reason",
                    "candle_patterns",
                ]
            )


def log_trade(trade_details):
    """Log trade details to a CSV file.

    Args:
        trade_details (JSON): The trade details to log.
    """
    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                trade_details["trade_id"],
                trade_details["symbol"],
                trade_details["open_date_time"],
                trade_details["volume"],
                trade_details["side"],
                trade_details["open_price"],
                trade_details["initial_stop_loss"],
                trade_details["take_profit"],
                trade_details["close_date_time"],
                trade_details["swap"],
                trade_details["commission"],
                trade_details["profit"],
                trade_details["close_reason"],
                json.dumps(trade_details["candle_patterns"]),
            ]
        )

def update_csv(trade_id, close_date_time, swap, profit, close_reason):
    """Update the CSV file with the closed trade details.

    Args:
        trade_id (str): The ID of the trade to update.
        close_date_time (str): The close date and time of the trade.
        swap (float): The swap value of the trade.
        profit (float): The profit of the trade.
        close_reason (str): The reason for closing the trade.
    """
    updated_rows = []
    with open(CSV_FILE, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['trade_id'] == trade_id:
                row['close_date_time'] = close_date_time
                row['swap'] = swap
                row['profit'] = profit
                row['close_reason'] = close_reason
            updated_rows.append(row)

    with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=reader.fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)


def edit_sl_position(
    login_manager,
    position_id,
    instrument,
    order_side,
    volume,
    sl_price,
    tp_price=0,
    trailing_distance=0,
):
    """Edit the stop loss position via the Match Trader API.

    Args:
        login_manager (LoginManager): The login manager instance.
        position_id (str): The ID of the position to edit.
        instrument (str): The trading instrument (e.g., "EURUSD").
        order_side (str): The side of the order ("BUY" or "SELL").
        volume (float): The volume of the position.
        sl_price (float): The new stop loss price.
        tp_price (float, optional): The take profit price. Defaults to 0.
        trailing_distance (float, optional): The trailing distance. Defaults to 0.

    Returns:
        bool: True if the request was successful, False otherwise.
    """
    url = f"{PLATFORM_URL}/mtr-api/{login_manager.system_uuid}/position/edit"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Auth-trading-api": login_manager.auth_trading_api,
        "Cookie": f"co-auth={login_manager.cookie}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    payload = {
        "id": position_id,
        "instrument": instrument,
        "orderSide": order_side,
        "volume": volume,
        "isMobile": False,
        "slPrice": sl_price,
        "tpPrice": tp_price,
        "trailingDistance": trailing_distance,
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        response = session.post(url, json=payload, timeout=10)
        response.raise_for_status()
        log.info("Successfully updated SL for position %s: %s", position_id, sl_price)
        return True
    except requests.RequestException as e:
        log.error("Failed to update SL for position %s: %s", position_id, e)
        return False


def close_position(login_manager, position_id, symbol, side, volume):
    """Close a position via the Match Trader API.

    Args:
        login_manager (LoginManager): The login manager instance.
        position_id (str): The ID of the position to close.
        symbol (str): The trading symbol (e.g., "EURUSD").
        side (str): The side of the order ("BUY" or "SELL").
        volume (float): The volume of the position.

    Returns:
        bool: True if the request was successful, False otherwise.
    """
    url = f"{PLATFORM_URL}/mtr-api/{login_manager.system_uuid}/position/close"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Auth-trading-api": login_manager.auth_trading_api,
        "Cookie": f"co-auth={login_manager.cookie}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }
    payload = json.dumps(
        {
            "positionId": position_id,
            "instrument": symbol,
            "orderSide": side,
            "volume": volume,
        }
    )
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        log.info("Successfully closed position %s", position_id)
        return True
    except requests.RequestException as e:
        log.error("Failed to close position %s: %s", position_id, e)
        return False


def clean_positions(positions):
    """Remove unnecessary nested 'positions' field."""
    for position in positions:
        if "positions" in position:
            del position["positions"]
    return positions


def setup_logging():
    """Configure logging for the application."""
    log_handler = RotatingFileHandler(
        "./logs/debug.log", maxBytes=1 * 1024 * 1024, backupCount=3
    )  # 1MB per file, 3 backups
    log_handler.setFormatter(log.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

    log.basicConfig(
        level=log.INFO,
        handlers=[log_handler, log.StreamHandler()],
    )


def fetch_open_positions_loop(login_manager, check_interval=1):
    """Fetch open positions periodically."""
    log.info("Fetching Open Positions.")
    open_positions_api = OpenPositionsAPI(login_manager)

    while True:
        try:
            # log.info("Fetching open positions...")
            positions = open_positions_api.get_open_positions()
            if not positions:
                positions = []
            elif positions:
                positions = clean_positions(positions.get("positions", []))
                # filtered_positions = [
                #     {
                #         "symbol": pos["symbol"],
                #         "side": pos["side"],
                #         "stop loss": pos["stopLoss"],
                #     }
                #     for pos in positions
                # ]
                # log.info("%s", filtered_positions)
            else:
                log.warning("No open positions found.")

            # log.info("Sleeping for %s seconds before fetching again...", check_interval)
            time.sleep(check_interval)
        except (ConnectionError, TimeoutError) as e:
            log.error("A network error occurred while fetching open positions: %s", e)
            break
        except ValueError as e:
            log.error("A value error occurred while processing positions: %s", e)
            break
        except (KeyError, TypeError) as e:
            log.error("An error occurred while processing positions: %s", e)
            break


def fetch_open_positions_once(login_manager):
    """Fetch open positions periodically."""
    # log.info("Fetching Open Positions.")
    open_positions_api = OpenPositionsAPI(login_manager)
    try:
        # log.info("Fetching open positions...")
        positions = open_positions_api.get_open_positions()

        if positions:
            #     positions = clean_positions(positions.get("positions", []))
            # filtered_positions = [
            #     {
            #         "symbol": pos["symbol"],
            #         "side": pos["side"],
            #         "stop loss": pos["stopLoss"],
            #     }
            #     for pos in positions
            # ]
            # log.info("Symbols for Market Watch: %s", filtered_positions)
            return positions
        log.warning("No open positions found.")
    except (ConnectionError, TimeoutError) as e:
        log.error("A network error occurred while fetching open positions: %s", e)
        return []
    except ValueError as e:
        log.error("A value error occurred while processing positions: %s", e)
        return []
    except (KeyError, TypeError) as e:
        log.error("An error occurred while processing positions: %s", e)
        return []


def print_boxed_message(message, log_func=log.info, fixed_width=75):
    """Print a message in a box.

    Args:
        message (str): The message to print.
    """
    try:
        # Try to parse the message as JSON
        parsed_message = json.loads(message)
        message = json.dumps(parsed_message, indent=2)
        is_json = True
    except json.JSONDecodeError:
        # If it's not JSON, leave the message as is
        is_json = False

    lines = message.split("\n")
    max_length = max(len(line) for line in lines)
    border_length = max(max_length, fixed_width) + 4
    border = "*" * border_length
    log_func(border)
    for line in lines:
        if is_json:
            log_func(f"* {line.ljust(border_length - 4)} *")
        else:
            log_func(f"* {line.center(border_length - 4)} *")
    log_func(border)


def detect_candlestick_patterns(df):
    """Detect candlestick patterns from the latest market data.

    Args:
        df (pd.DataFrame): DataFrame containing OHLC data.

    Returns:
        list: List of detected candlestick patterns.
    """
    candlestick = Indicators.calculate_candlestick_patterns(df)
    recent_candles = candlestick.iloc[-5:].dropna(how="all")
    recent_candle_patterns = recent_candles[(recent_candles != 0).any(axis=1)]
    recent_candle_patterns = recent_candle_patterns.loc[
        :, (recent_candle_patterns != 0).any(axis=0)
    ]
    identified_patterns = recent_candle_patterns.columns[
        (recent_candle_patterns != 0).any(axis=0)
    ].tolist()
    return identified_patterns

def fetch_closed_positions(login_manager, countback = 30):
    """Fetch the closed positions."""
    to_time = datetime.now(timezone.utc)
    from_time = to_time - timedelta(days=countback)

    to_time_str = to_time.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    from_time_str = from_time.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    # log.info(f"Fetching closed positions from {from_time_str} to {to_time_str}")

    url = f"{PLATFORM_URL}/mtr-api/{login_manager.system_uuid}/closed-positions"
    payload = json.dumps({
        "from": from_time_str,
        "to": to_time_str,
    })
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Auth-trading-api": login_manager.auth_trading_api,
        "Cookie": f"co-auth={login_manager.cookie}",
        "Origin": f"{PLATFORM_URL}",
        "Referer": f"{PLATFORM_URL}/dashboard",
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        response = session.post(url, data=payload)
        response.raise_for_status()
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Failed to get closed positions: {e}")
        return None


def enter_trade(login_manager, symbol, direction, volume, stop_loss, take_profit):
    """Enter a trade for the given symbol with the specified parameters.

    Args:
        symbol (str): The trading symbol.
        direction (str): The trade direction ("BUY" or "SELL").
        volume (float): The volume to trade.
        stop_loss (float): The stop loss value.
        take_profit (float): The take profit value.
    """
    price_data = PriceData()
    ohlc = price_data.fetch_market_data(
        login_manager, symbol, resolution="5", countback=100
    )
    df = pd.DataFrame(ohlc).set_index("t")
    candle_patterns = detect_candlestick_patterns(df)

    # Logic to enter trade for the given symbol
    url = f"{PLATFORM_URL}/mtr-api/{login_manager.system_uuid}/position/open"
    payload = json.dumps(
        {
            "instrument": symbol,
            "orderSide": direction.upper(),
            "volume": volume,
            "slPrice": stop_loss,
            "tpPrice": take_profit,
            "isMobile": False,
        }
    )
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Auth-trading-api": login_manager.auth_trading_api,
        "Cookie": f"co-auth={login_manager.cookie}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
    }

    print_boxed_message(json.dumps(payload, indent=2))

    session = requests.Session()
    session.headers.update(headers)
    try:
        response = session.post(url, headers=headers, data=payload, timeout=10)
        response.raise_for_status()
        print_boxed_message(f"{direction} trade successfully opened for {symbol}!!!")
        print_boxed_message(json.dumps(response.json(), indent=2))
        order_id = response.json().get("orderId")
        if not order_id:
            log.error("Failed to open position for %s: No order ID returned.", symbol)

        open_positions_response = fetch_open_positions_once(login_manager)
        open_positions = (
            open_positions_response.get("positions", [])
            if open_positions_response
            else []
        )
        position_data = next(
            (pos for pos in open_positions if pos["id"] == order_id), None
        )
        if not position_data:
            log.error("Could not find position data for orderId: %s", order_id)
            return None

        decimal_places = abs(Decimal(str(position_data["openPrice"])).as_tuple().exponent)

        log_trade(
            {
                "trade_id": order_id,
                "symbol": symbol,
                "open_date_time": position_data["openTime"],
                "volume": volume,
                "side": direction,
                "open_price": position_data["openPrice"],
                "initial_stop_loss": round(stop_loss, decimal_places),
                "take_profit": round(take_profit, decimal_places),
                "close_date_time": None,
                "swap": None,
                "commission": position_data["commission"],
                "profit": None,
                "close_reason": None,
                "candle_patterns": candle_patterns,
            }
        )
    except requests.RequestException as e:
        log.error("Failed to open position for %s: %s", symbol, e)

def check_spread(login_manager, symbol):
    """Check the spread for the given symbol.

    Args:
        symbol (str): The trading symbol to check.

    Returns:
        float: The spread value for the symbol.
    """
    price_data = PriceData()
    market_watch = price_data.fetch_market_watch(login_manager, symbol)
    bid = float(market_watch[0]["bid"])
    ask = float(market_watch[0]["ask"])
    spread = abs(ask - bid)
    return spread

    
