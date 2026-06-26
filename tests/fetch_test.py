import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
import json
from datetime import datetime

# Google Sheets Connection
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../keys/liquorbond-service.json")

creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
client = gspread.authorize(creds)

try:
    print("Connecting to Google Sheets...")
    sheet_metadata = client.open("Liqour Stock Data")
    worksheet = sheet_metadata.worksheet("Truck Endorsements")
    values = worksheet.get_all_values()
    print("Found", len(values), "rows.")
    
    headers = values[0] if values else []
    print("Headers:", headers)
    # date is col 0, truck is col 2
    for r in values[-15:]:
        # Handle cases where row might be shorter than expected
        date_raw = r[0] if len(r) > 0 else ''
        truck_raw = r[2] if len(r) > 2 else ''
        
        date_norm = ''
        possible_formats = ['%d-%b-%Y', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d/%m/%y']
        for fmt in possible_formats:
            try:
                date_norm = datetime.strptime(date_raw, fmt).strftime('%Y-%m-%d')
                break
            except ValueError:
                pass
        if not date_norm:
            date_norm = date_raw.strip()
            
        key = f"{date_norm}|{truck_raw.strip()}"
        print(f"Raw: date='{date_raw}' truck='{truck_raw}' -> Key: {key}")

except Exception as e:
    import traceback
    traceback.print_exc()

