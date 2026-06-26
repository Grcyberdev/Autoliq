import gspread
from google.oauth2.service_account import Credentials

# Define the required scopes
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Path to your service account file
SERVICE_ACCOUNT_FILE = "/Users/rajdeepgrover/Desktop/Coding/Liquor_Bond_Automation_VSCode/keys/liquorbond-service.json"

# Authorize client
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
client = gspread.authorize(creds)

# Open the Google Sheet
spreadsheet_name = "Liqour Stock Data"
worksheet_name = "Truck Endorsements"

sheet = client.open(spreadsheet_name).worksheet(worksheet_name)

print("✅ Successfully connected to Google Sheet!")

# --- READ TEST ---
data = sheet.get_all_values()
print(f"📄 Total rows found: {len(data)}")
if len(data) > 0:
    print("🔹 First 3 rows preview:")
    for row in data[:3]:
        print(row)
else:
    print("⚠️ Sheet is currently empty.")

# --- WRITE TEST ---
test_row = ["2025-10-13", "MH12AB1234", "500 Cases", "Delivered"]
sheet.append_row(test_row)
print("✅ Test row added successfully!")
