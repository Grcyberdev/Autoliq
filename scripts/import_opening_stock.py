
import os
import sys
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import argparse

# ----------------------------
# Configuration
# ----------------------------
SPREADSHEET_NAME = "Liqour Stock Data"
WORKSHEET_NAME = "Stock_Management"

# Path Setup
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Try to find keys
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

# ----------------------------
# Google Sheets Connection
# ----------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

def parse_arguments():
    parser = argparse.ArgumentParser(description="Import Opening Stock from Excel")
    parser.add_argument("file", help="Path to the Excel file containing opening stock")
    return parser.parse_args()

def main():
    args = parse_arguments()
    excel_path = args.file

    if not os.path.exists(excel_path):
        print(f"❌ File not found: {excel_path}")
        sys.exit(1)

    print(f"📂 Reading Excel file: {excel_path}...")
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"❌ Error reading Excel: {e}")
        sys.exit(1)

    # Basic cleaning
    # User didn't specify column names, so we'll try to guess or dump 1st and 2nd cols
    # Assuming Col 0 = Name, Col 1 = Quantity
    print(f"   - Found columns: {list(df.columns)}")
    
    # Standardize column selection
    liquor_names = df.iloc[:, 0].astype(str).str.strip().tolist()
    quantities = df.iloc[:, 1].fillna(0).astype(int).tolist()

    # Prepare rows for Google Sheet
    # Format: [Liquor Name, Current Stock (Formula), Opening Stock]
    
    print("🚀 Connecting to Google Sheet...")
    try:
        spreadsheet = gc.open(SPREADSHEET_NAME)
        try:
            sheet = spreadsheet.worksheet(WORKSHEET_NAME)
            print(f"   - Found existing sheet '{WORKSHEET_NAME}'. Clearing it...")
            sheet.clear()
        except gspread.exceptions.WorksheetNotFound:
            print(f"   - Creating new sheet '{WORKSHEET_NAME}'...")
            sheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=20)
    except Exception as e:
        print(f"❌ Error connecting to sheet: {e}")
        sys.exit(1)
        
    print("📝 writing data...")
    
    # Headers
    # A: Name, B: Current Stock, C: Opening Stock (22 Dec)
    headers = ["Liquor Name", "Current Stock", "Opening Stock (22-Dec-2025)"]
    
    # Prepare data rows - We CANNOT write formulas in batch_update with value_input_option='USER_ENTERED' easily 
    # if we mix them with raw values in a simple list of lists usually.
    # But gspread handles it if starting with '='.
    
    rows_to_write = [headers]
    
    for i in range(len(liquor_names)):
        row_num = i + 2 # Header is row 1
        name = liquor_names[i]
        opening_qty = quantities[i]
        
        # Formula: Opening (Col C) - Sum(Daily Dispatches (Col D onwards))
        # =C{row} - SUM(D{row}:ZZ{row})
        formula = f'=C{row_num}-SUM(D{row_num}:ZZ{row_num})'
        
        rows_to_write.append([name, formula, opening_qty])

    # Write in one go
    sheet.update(rows_to_write, value_input_option="USER_ENTERED")
    
    # Formatting
    sheet.format("A1:C1", {"textFormat": {"bold": True}})
    sheet.freeze(rows=1, cols=1)
    
    print(f"✅ Successfully imported {len(liquor_names)} items.")
    print("   - Structure: Col A (Name), Col B (Current Stock), Col C (Opening)")
    print("   - Current Stock will update automatically as you add daily columns starting from Col D.")

if __name__ == "__main__":
    main()
