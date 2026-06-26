import gspread
from google.oauth2.service_account import Credentials
import os
import sys
import json
from datetime import datetime
from collections import defaultdict
import time

# --- Shared Config & Auth ---
POSSIBLE_KEY_PATHS = [
    "keys/liquorbond-service.json",
    "../keys/liquorbond-service.json",
    "liquorbond-service.json",
    "./keys/liquorbond-service.json",
    "../config/liquorbond-service.json",
    "/Users/rajdeepgrover/Desktop/Coding/Liquor_Bond_Automation_VSCode/keys/liquorbond-service.json"
]

SERVICE_ACCOUNT_FILE = next((os.path.abspath(p) for p in POSSIBLE_KEY_PATHS if os.path.exists(p)), None)
if not SERVICE_ACCOUNT_FILE:
    print("❌ Service account JSON file not found. Checked paths:", POSSIBLE_KEY_PATHS)
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

SPREADSHEET_NAME = "Liqour Stock Data"
WORKSHEETS = ["Truck Endorsements", "Country Spirit Endorsements"]

def normalize_date_string(date_str):
    if not date_str: return ''
    possible_formats = ['%d-%b-%Y', '%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d/%m/%y']
    for fmt in possible_formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError: pass
    return str(date_str).strip()

def get_row_score(row_data, header_idx_map):
    score = 0
    # Higher score = better row to keep
    
    # Check Status
    status_idx = header_idx_map.get("Status", -1)
    if status_idx != -1 and len(row_data) > status_idx:
        status = str(row_data[status_idx]).strip().lower()
        if status not in ["", "not arrived"]:
            score += 100
            if status == "arrived":
                score += 50
    
    # Check Dates
    arrived_idx = header_idx_map.get("DateArrived", -1)
    if arrived_idx != -1 and len(row_data) > arrived_idx:
         if str(row_data[arrived_idx]).strip() != "":
             score += 50
             
    completed_idx = header_idx_map.get("DateCompleted", -1)
    if completed_idx != -1 and len(row_data) > completed_idx:
         if str(row_data[completed_idx]).strip() != "":
             score += 50
    
    # Check quantity
    qty_idx = header_idx_map.get("TotalQuantity", -1)
    if qty_idx != -1 and len(row_data) > qty_idx:
        try:
            qty = int(str(row_data[qty_idx]).replace(',', ''))
            score += qty / 100000.0  # Fraction so it breaks ties
        except: pass
        
    return score

def main():
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            spreadsheet = gc.open(SPREADSHEET_NAME)
            print(f"✅ Connected to '{SPREADSHEET_NAME}'")
            break
        except Exception as e:
            print(f"⚠️ Failed to open spreadsheet (Attempt {attempt+1}): {e}")
            if attempt == max_retries - 1:
                return
            time.sleep(retry_delay)

    for ws_name in WORKSHEETS:
        print(f"\n--- Processing '{ws_name}' ---")
        try:
            worksheet = spreadsheet.worksheet(ws_name)
            all_values = dict(enumerate(worksheet.get_all_values())) # get_all_values might just return list
            # We must map correctly
            all_values = list(worksheet.get_all_values())
        except Exception as e:
            print(f"⚠️ Could not load {ws_name}: {e}")
            continue

        if not all_values:
            print("Sheet is empty.")
            continue

        headers = all_values[0]
        rows = all_values[1:]
        
        # Backup
        backup_file = f"backup_{ws_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(backup_file, "w") as f:
                json.dump({"headers": headers, "rows": rows}, f)
            print(f"💾 Saved backup to {backup_file}")
        except:
             print("⚠️ Failed to write backup, continuing anyway.")

        date_idx = -1
        truck_idx = -1
        
        for i, h in enumerate(headers):
             if h.strip() == "DateofEndorsement": date_idx = i
             elif h.strip() == "TruckNumber": truck_idx = i
             
        if date_idx == -1 or truck_idx == -1:
             print("⚠️ Missing DateofEndorsement or TruckNumber column. Skipping.")
             continue

        header_idx_map = {h: i for i, h in enumerate(headers)}

        grouped_rows = defaultdict(list)
        
        for r in rows:
            r_padded = r + [''] * (max(len(headers) - len(r), 0)) # Ensure row is at least header length
            
            d_val = normalize_date_string(r_padded[date_idx])
            t_val = str(r_padded[truck_idx]).strip()
            if d_val and t_val:
                key = f"{d_val}|{t_val}"
                grouped_rows[key].append(r_padded)
            else:
                grouped_rows["INVALID_OR_EMPTY"].append(r_padded)

        duplicate_count = 0
        best_row_for_key = {}
        
        for key, duplicates in list(grouped_rows.items()):
            if key == "INVALID_OR_EMPTY": continue
            if len(duplicates) > 1:
                duplicate_count += len(duplicates) - 1
                
                # Pick the BEST row to KEEP based on score
                best_row = duplicates[0]
                best_score = get_row_score(best_row, header_idx_map)
                
                for dup in duplicates[1:]:
                    score = get_row_score(dup, header_idx_map)
                    if score > best_score:
                        best_score = score
                        best_row = dup
                        
                best_row_for_key[key] = best_row
            else:
                best_row_for_key[key] = duplicates[0]

        cleaned_rows = []
        seen_keys = set()
        
        for r in rows:
            r_padded = r + [''] * (max(len(headers) - len(r), 0))
            d_val = normalize_date_string(r_padded[date_idx])
            t_val = str(r_padded[truck_idx]).strip()
            
            if not d_val or not t_val:
                cleaned_rows.append(r_padded) # Keep invalids
                continue
                
            key = f"{d_val}|{t_val}"
            if key not in seen_keys:
                cleaned_rows.append(best_row_for_key[key])
                seen_keys.add(key)
            else:
                # Omit duplicate, keeping only the first chronological occurrence (but with the best data)
                pass
                
        print(f"✅ Found {len(rows)} total rows. Removed {duplicate_count} duplicated rows.")
        
        if duplicate_count > 0:
            print(f"🚀 Updating Google Sheet '{ws_name}' with {len(cleaned_rows)} unique rows...")
            try:
                worksheet.clear()
                worksheet.update([headers] + cleaned_rows, value_input_option="USER_ENTERED")
                print("🎉 Sheet cleaned successfully!")
            except Exception as e:
                print(f"❌ Failed to update sheet. Data is safe in {backup_file}. Error: {e}")
        else:
            print("👍 No duplicates found.")

if __name__ == "__main__":
    main()
