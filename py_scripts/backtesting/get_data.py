import os
import requests

# Define constants
base_url = "https://www.histdata.com/get.php"

# Input: Symbol and Year Range
symbol = input("Enter the symbol (e.g. EURUSD): ").upper()
output_folder = os.path.join("/mnt/g", "My Drive", "0 - Business Files", "Trading", "Historical Data", symbol)
os.makedirs(output_folder, exist_ok=True)

yearly_data_year_range = input("Enter range of years (e.g. 2020-2023): ").split("-")
if len(yearly_data_year_range) != 2 or not all(year.isdigit() for year in yearly_data_year_range):
    raise ValueError("Invalid range of years. Please enter in the format 'YYYY-YYYY'.")
yearly_data_years = range(int(yearly_data_year_range[0]), int(yearly_data_year_range[1]) + 1)

monthly_data_year = None
monthly_data_months = []
if yearly_data_year_range[1] == "2024":
    monthly_data_year = 2024
    monthly_data_end_month = input("Enter end month (e.g. 3): ")
    if not monthly_data_end_month.isdigit():
        raise ValueError("Invalid end month. Please enter a numeric value.")
    monthly_data_months = range(1, int(monthly_data_end_month) + 1)

def get_dynamic_token():
    # Make an initial request to the website to get the token
    response = requests.get("https://www.histdata.com/")
    # Debugging statements to inspect the response
    print(f"Response status code: {response.status_code}")
    print(f"Response cookies: {response.cookies}")
    print(f"Response content: {response.text[:500]}")
    # Parse the response to extract the token (this will depend on how the token is provided)
    # For example, if the token is in a cookie:
    token = response.cookies.get("tk")
    return token

# Use the dynamic token in your payload
token = get_dynamic_token()
payload_template = {
    "tk": token,
    "platform": "MT",
    "timeframe": "M1",
    "fxpair": symbol,
}

# Function to download files
def download_file(payload, folder, filename):
    try:
        response = requests.post(base_url, data=payload, stream=True)
        response.raise_for_status()
        print(f"Response status code: {response.status_code}")  # Debugging statement
        print(f"Response content length: {response.headers.get('Content-Length')}")
        file_path = os.path.join(folder, filename)
        print(f"Writing to: {file_path}")
        with open(file_path, "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"Downloaded: {filename}")
    except requests.RequestException as e:
        print(f"Failed to download {filename}. Error: {e}")

print(f"Downloading files to: {output_folder}")
# Download yearly data
for year in yearly_data_years:
    payload = payload_template.copy()
    payload["date"] = str(year)
    payload["datemonth"] = str(year)
    filename = f"HISTDATA_COM_MT_{symbol}_M1_{year}.zip"
    print("payload:", payload)
    download_file(payload, output_folder, filename)

# Download monthly data for 2024
if monthly_data_year and monthly_data_months:
    for month in monthly_data_months:
        payload = payload_template.copy()
        payload["date"] = "2024"
        payload["datemonth"] = f"2024{month:02d}"  # Format month as two digits
        filename = f"HISTDATA_COM_MT_{symbol}_M1_2024{month:02d}.zip"
        print("payload:", payload)
        download_file(payload, output_folder, filename)