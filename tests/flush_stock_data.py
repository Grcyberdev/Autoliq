
import os
import sys
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# Configuration matching main_stock.py
SPREADSHEET_NAME = "Liqour Stock Data"
WORKSHEET_NAME = "Stock_Management"
DATA_FILE = "stock_data_checkpoint.json"

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

def main():
    if not os.path.exists(DATA_FILE):
        print(f"❌ Checkpoint file '{DATA_FILE}' not found.")
        return

    print(f"📂 Loading checkpoint from {DATA_FILE}...")
    try:
        with open(DATA_FILE, "r") as f:
            master_db = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load JSON: {e}")
        return

    # Merge Data
    print("🔄 Merging Data...")
    MASTER_FLAT = {} # { date: { item: qty } }
    
    for user, dates in master_db.items():
        print(f"   - Processing user: {user} ({len(dates)} dates)")
        for d, items in dates.items():
            if d not in MASTER_FLAT: MASTER_FLAT[d] = {}
            for item, qty in items.items():
                MASTER_FLAT[d][item] = MASTER_FLAT[d].get(item, 0) + qty

    # Sort
    all_dates = sorted(list(MASTER_FLAT.keys()), key=lambda d: datetime.strptime(d, "%d-%b-%Y"))
    all_items = set()
    for d in MASTER_FLAT:
        all_items.update(MASTER_FLAT[d].keys())
    
    sorted_items = sorted(list(all_items))
    
    print(f"📊 Found {len(sorted_items)} unique items across {len(all_dates)} dates.")
    
    if not sorted_items:
        print("⚠️ No data to write.")
        return

    # Connect to Sheet
    try:
        spreadsheet = gc.open(SPREADSHEET_NAME)
        try:
            sheet = spreadsheet.worksheet(WORKSHEET_NAME)
            print(f"✅ Connected to '{SPREADSHEET_NAME}' → '{WORKSHEET_NAME}'")
        except gspread.exceptions.WorksheetNotFound:
            print(f"⚠️ Worksheet '{WORKSHEET_NAME}' not found.")
            return
    except Exception as e:
        print(f"❌ Error connecting to sheet: {e}")
        return

    # Write
    print("💾 Writing to Google Sheet...")
    sheet.clear()
    
    headers = ["Liquor Name"] + all_dates
    rows = [headers]
    
    for item in sorted_items:
        row = [item]
        for date in all_dates:
            qty = MASTER_FLAT[date].get(item, "")
            row.append(qty)
        rows.append(row)
        
    try:
        sheet.update(range_name=f"A1", values=rows)
        sheet.format("A1:Z1", {"textFormat": {"bold": True}})
        print("✅ Sheet updated successfully!")
    except Exception as e:
        print(f"❌ Sheet update failed: {e}")

if __name__ == "__main__":
    main()
