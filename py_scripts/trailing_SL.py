import requests
import time
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL")  # Match-Trader API URL
CO_AUTH_COOKIE = os.getenv("CO_AUTH_COOKIE")  # Co-auth cookie from .env
ATR_MULTIPLIER = 3
CHECK_INTERVAL = 60  # Time in seconds between API calls

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Cookie": f"co-auth={CO_AUTH_COOKIE}"
}

def fetch_open_positions():
    """Fetch details of open positions."""
    url = f"{API_BASE_URL}/open-positions"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch open positions: {response.status_code} {response.text}")
        return None

def fetch_indicator_data():
    """Fetch indicator data for ATR."""
    url = f"{API_BASE_URL}/indicator-data"  # Replace with the correct endpoint for indicators
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        # Extract ATR value; adjust key access based on actual response structure
        atr = data.get("ATR", {}).get("value", 0)
        return float(atr)
    else:
        print(f"Failed to fetch indicator data: {response.status_code} {response.text}")
        return 0

def calculate_new_stop_loss(recent_high, atr):
    """Calculate the new stop-loss level."""
    return recent_high - (ATR_MULTIPLIER * atr)

def update_stop_loss(position_id, instrument, stop_loss, order_side):
    """Update the stop-loss for a specific position."""
    url = f"{API_BASE_URL}/position/edit"
    payload = {
        "positionId": position_id,
        "instrument": instrument,
        "orderSide": order_side,  # BUY or SELL
        "slPrice": stop_loss
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        print(f"Stop-loss for position {position_id} updated to {stop_loss}")
    else:
        print(f"Failed to update stop-loss for position {position_id}: {response.status_code} {response.text}")

# Main Loop
while True:
    positions = fetch_open_positions()
    if positions:
        for position in positions.get("positions", []):
            position_id = position.get("id")
            instrument = position.get("instrument")
            order_side = position.get("side")  # Adjust based on platform structure
            recent_high = float(position.get("high", 0))
            atr = fetch_indicator_data()  # Dynamically fetch ATR value
            if recent_high and atr:
                new_stop_loss = calculate_new_stop_loss(recent_high, atr)
                if new_stop_loss < position.get("slPrice", 0):  # Check if the stop-loss should be moved
                    update_stop_loss(position_id, instrument, new_stop_loss, order_side)
                else:
                    print(f"Stop-loss for position {position_id} not moved as ATR threshold has not progressed.")
    time.sleep(CHECK_INTERVAL)
