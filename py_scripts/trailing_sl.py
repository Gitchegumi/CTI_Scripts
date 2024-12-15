"""A script to implement a trailing stop-loss strategy using the ATR indicator.

Raises:
    Exception: If the co-auth cookie is not found

Returns:
    str: The co-auth cookie value
"""

import time
import os
import logging as log
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()

# Logging configuration
log.basicConfig(
    level=log.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[log.FileHandler("./logs/trailing_SL.log"), log.StreamHandler()],
)

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL")  # Match-Trader API URL
ATR_MULTIPLIER = 3
CHECK_INTERVAL = 60  # Time in seconds between API calls

# Initialize Selenium WebDriver
CHROME_DRIVER_PATH = os.getenv("CHROME_DRIVER_PATH")
driver_service = Service(CHROME_DRIVER_PATH)
options = Options()
binary_path = os.getenv("CHROME_BINARY_PATH")  # Path to Chrome/Chromium binary
if binary_path:
    options.binary_location = binary_path

# Add options to run Chrome in headless mode and disable GPU
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--remote-debugging-port=9222")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
)

driver = webdriver.Chrome(service=driver_service, options=options)


def login_and_get_cookie():
    """A function to log in to the platform and extract the co-auth cookie.

    Raises:
        Exception: If the co-auth cookie is not found

    Returns:
        str: The co-auth cookie value
    """
    driver.get("https://platform.citytradersimperium.com/")

    # Wait for the email input to be present
    log.info("Login page loaded")
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-testid='login-field']")
            )
        )
    except TimeoutException:
        log.error(
            "Timeout waiting for email input. Page source: %s", driver.page_source
        )
        driver.quit()
        raise

    # Log in to the platform
    email_input = driver.find_element(By.CSS_SELECTOR, "[data-testid='login-field']")
    password_input = driver.find_element(
        By.CSS_SELECTOR, "[data-testid='password-field']"
    )
    email_input.send_keys(os.getenv("EMAIL"))
    password_input.send_keys(os.getenv("PASSWORD"))

    # Click the login button
    login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    login_button.click()

    # Wait for the dashboard or main page to load
    driver.implicitly_wait(10)

    # Extract cookies
    cookies = driver.get_cookies()
    for cookie in cookies:
        if cookie["name"] == "co-auth":
            return cookie["value"]

    raise ValueError("co-auth cookie not found")


headers = {"Accept": "application/json", "Content-Type": "application/json"}

co_auth_cookie = login_and_get_cookie()
headers["Cookie"] = f"co-auth={co_auth_cookie}"


def fetch_open_positions():
    """Fetch the open positions from the platform.

    Returns:
        dict: The open positions data
    """
    url = f"{API_BASE_URL}/open-positions"
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        log.info("Open positions fetched successfully.")
        return response.json()
    log.info(
        "Failed to fetch open positions: %s %s", response.status_code, response.text
    )
    return None


def fetch_indicator_data():
    """Fetch the ATR indicator data.

    Returns:
        float: The ATR value
    """
    url = f"{API_BASE_URL}/indicator-data"  # Replace with the correct endpoint for indicators
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code == 200:
        data = response.json()
        # Extract ATR value; adjust key access based on actual response structure
        atr_value = data.get("ATR", {}).get("value", 0)
        return float(atr_value)
    log.info(
        "Failed to fetch indicator data: %s %s", response.status_code, response.text
    )
    return 0


def calculate_new_stop_loss(recent_high_price, atr_value):
    """Calculate the new stop-loss based on the recent high and ATR.

    Args:
        recent_high (float): The recent high price
        atr (float): The ATR value

    Returns:
        float: The new stop-loss value
    """
    return recent_high_price - (ATR_MULTIPLIER * atr_value)


def update_stop_loss(position_id_value, instrument_code, stop_loss, order_direction):
    """Update the stop-loss for a position.

    Args:
        position_id_value (str): The position ID
        instrument_code (str): The instrument code
        stop_loss (float): The new stop-loss value
        order_direction (str): The order direction (BUY or SELL)
    """
    url = f"{API_BASE_URL}/position/edit"
    payload = {
        "positionId": position_id_value,
        "instrument": instrument_code,
        "orderSide": order_direction,
        "slPrice": stop_loss,
    }
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    if response.status_code == 200:
        log.info(
            "Stop-loss for position %s updated to %s", position_id_value, stop_loss
        )
    else:
        log.info(
            "Failed to update stop-loss for position %s: %s %s",
            position_id_value,
            response.status_code,
            response.text,
        )


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
                if new_stop_loss < position.get(
                    "slPrice", 0
                ):  # Check if the stop-loss should be moved
                    update_stop_loss(position_id, instrument, new_stop_loss, order_side)
                else:
                    log.info(
                        "Stop-loss for position %s not moved as new SL is higher than current SL.",
                        position_id,
                    )
    else:
        log.info("No open positions found.")
    time.sleep(CHECK_INTERVAL)

# Close the Selenium WebDriver after script ends
driver.quit()
