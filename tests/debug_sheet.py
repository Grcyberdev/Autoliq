import os
import sys
import gspread
from google.oauth2.service_account import Credentials

# ----------------------------
# Configuration
# ----------------------------
SPREADSHEET_NAME = "Liqour Stock Data"
WORKSHEET_NAME = "Stock_Management"

POSSIBLE_KEY_PATHS = [
    "liquorbond-service.json",
    "../liquorbond-service.json",
    "../keys/liquorbond-service.json",
    "./keys/liquorbond-service.json",
    "../config/liquorbond-service.json"
]

SERVICE_ACCOUNT_FILE = next((os.path.abspath(p) for p in POSSIBLE_KEY_PATHS if os.path.exists(p)), None)
if not SERVICE_ACCOUNT_FILE:
    print("❌ Service account JSON file not found.")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

try:
    spreadsheet = gc.open(SPREADSHEET_NAME)
    sheet = spreadsheet.worksheet(WORKSHEET_NAME)
    print(f"✅ Connected to '{SPREADSHEET_NAME}' → '{WORKSHEET_NAME}'")
    
    print(f"Current Cols: {sheet.col_count}")
    print(f"Current Rows: {sheet.row_count}")
    print(f"Headers (Row 1): {sheet.row_values(1)}")
    
except Exception as e:
    print(f"❌ Error: {e}")
