import os
import sys
import time
import json
import pandas as pd
import pandas as pd
try:
    import pyperclip
except ImportError:
    pyperclip = None
from datetime import datetime, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import gspread
from google.oauth2.service_account import Credentials

# Import shared automation utilities
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import automation_utils

# ----------------------------
# Shared Data & Utils
# ----------------------------
import liquor_data # Import entire module to access shared sets
from liquor_data import (
    LIQUOR_NAME_MAPPING, 
    SIZE_SUFFIX_MAPPING, 
    SUPPLIER_NAME_MAPPING, 
    get_short_name, 
    get_short_supplier_name, 
    get_telegram_supplier_name,
    normalize_date_string,
    unmapped_liquor_names,
    unmapped_suppliers,
    BEER_BRANDS
)


# ----------------------------
# Configuration / paths (remains the same)
# ----------------------------
POSSIBLE_KEY_PATHS = [
    "liquorbond-service.json",
    "../liquorbond-service.json",
    "../keys/liquorbond-service.json",
    "./keys/liquorbond-service.json",
    "../config/liquorbond-service.json"
]

SERVICE_ACCOUNT_FILE = next((os.path.abspath(p) for p in POSSIBLE_KEY_PATHS if os.path.exists(p)), None)
if not SERVICE_ACCOUNT_FILE:
    print("❌ Service account JSON file not found. Checked paths:", POSSIBLE_KEY_PATHS)
    sys.exit(1)

print("✅ Using service account JSON:", SERVICE_ACCOUNT_FILE)

# --- UPDATED TO LOAD CONFIG SECURELY ---
config = automation_utils.load_config()

PORTAL_URL = config.get("portal_url")
USERNAME = config.get("IMFL_USERNAME")
PASSWORD = config.get("IMFL_PASSWORD")
TELEGRAM_BOT_TOKEN = config.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = config.get("TELEGRAM_CHAT_ID")

# ADDITION: Add extra receivers if not present (Comma separated)
# Target IDs: 6548934624, 7816111753, 1293273562, 8586503756

if TELEGRAM_CHAT_ID:
    current_ids = str(TELEGRAM_CHAT_ID).split(',')
    required_ids = ["6548934624", "7816111753", "1293273562", "8586503756"]
    
    for rid in required_ids:
        if rid not in current_ids:
            current_ids.append(rid)
    
    TELEGRAM_CHAT_ID = ",".join(current_ids)

if not PORTAL_URL or not USERNAME or not PASSWORD:
    print("❌ Configuration missing. Ensure either config/config.json exists OR Environment Variables are set.")
    sys.exit(1)
# --- END UPDATE ---

SPREADSHEET_NAME = "Liqour Stock Data"
WORKSHEET_NAME = "Truck Endorsements" # <-- This is for IMFL

# --- UPDATED: Define expected headers (No PassNumber, include Bifurcation) ---
EXPECTED_HEADERS = ["DateofEndorsement", "Supplier", "TruckNumber", "LiqourTypes", "TotalQuantity", "Status", "DateArrived", "DateCompleted", "Bifurcation"]


# ----------------------------
# Google Sheets auth (remains the same)
# ----------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

max_retries = 3
retry_delay = 5

for attempt in range(max_retries):
    try:
        print(f"📄 Connecting to Google Sheets (Attempt {attempt + 1}/{max_retries})...")
        spreadsheet = gc.open(SPREADSHEET_NAME)
        # --- Try to open the specific sheet ---
        try:
            sheet = spreadsheet.worksheet(WORKSHEET_NAME)
            print(f"✅ Connected to spreadsheet '{SPREADSHEET_NAME}' → worksheet '{WORKSHEET_NAME}'")
        except gspread.exceptions.WorksheetNotFound:
            # This sheet *should* exist, but we'll handle the error just in case
            print(f"❌ Worksheet '{WORKSHEET_NAME}' not found inside spreadsheet '{SPREADSHEET_NAME}'.")
            print(f"   - Please create a sheet named '{WORKSHEET_NAME}' or check for typos.")
            sys.exit(1)
        # --- END ---
        break # Success
    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ Spreadsheet '{SPREADSHEET_NAME}' not found (or service account not shared).")
        sys.exit(1)
    except gspread.exceptions.APIError as e:
        print(f"⚠️ Google Sheets API Error (Attempt {attempt + 1}): {e}")
        if attempt < max_retries - 1:
            print(f"   - Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2
        else:
             print("❌ Failed to connect to Google Sheets after multiple retries.")
             sys.exit(1)
    except Exception as e:
        print(f"❌ Error connecting to sheet: {e}")
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
        else:
            sys.exit(1)

# ----------------------------
# Helper for Conditional Formatting with self-cleaning logic
# ----------------------------
def setup_conditional_formatting(worksheet):
    """Clears old rules and sets up new ones to color entire rows based on Status and DateCompleted."""
    print("🎨 Setting up conditional formatting rules...")
    try:
        print("   - Clearing old conditional formatting rules...")
        sheet_metadata = worksheet.spreadsheet.fetch_sheet_metadata()
        sheet_info = next((s for s in sheet_metadata['sheets'] if s['properties']['sheetId'] == worksheet.id), None)
        
        clear_requests = []
        if sheet_info and 'conditionalFormats' in sheet_info:
            for i in range(len(sheet_info['conditionalFormats']) - 1, -1, -1):
                clear_requests.append({"deleteConditionalFormatRule": {"sheetId": worksheet.id, "index": i}})
        
        if clear_requests:
            body = {"requests": clear_requests}
            worksheet.spreadsheet.batch_update(body)
            print("   - ✅ Old rules cleared.")
        else:
            print("   - No old rules to clear.")

        print("   - Applying new conditional formatting rules...")
        grey_color = {"red": 0.85, "green": 0.85, "blue": 0.85}
        red_color = {"red": 1.0, "green": 0.8, "blue": 0.8}
        yellow_color = {"red": 1.0, "green": 0.95, "blue": 0.8}
        green_color = {"red": 0.8, "green": 1.0, "blue": 0.8}

        rules = {
            "Not Arrived": grey_color,
            "Not opened": red_color,
            "Unloading": yellow_color
        }

        headers = EXPECTED_HEADERS # <-- Use the correct headers
        status_column_letter = gspread.utils.rowcol_to_a1(1, headers.index("Status") + 1).rstrip('1')
        date_completed_column_letter = gspread.utils.rowcol_to_a1(1, headers.index("DateCompleted") + 1).rstrip('1')

        add_requests = []
        
        completed_today_formula = f'=AND(NOT(ISBLANK(${date_completed_column_letter}2)), TEXT(${date_completed_column_letter}2, "yyyy-mm-dd")=TEXT(TODAY(), "yyyy-mm-dd"))'
        completed_rule = { "addConditionalFormatRule": { "rule": { "ranges": [{"sheetId": worksheet.id, "startRowIndex": 1}], "booleanRule": { "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": completed_today_formula}]}, "format": {"backgroundColor": green_color}}}, "index": 0}}
        add_requests.append(completed_rule)
        
        for status_text, color in rules.items():
            formula = f'=${status_column_letter}2="{status_text}"'
            rule = { "addConditionalFormatRule": { "rule": { "ranges": [{"sheetId": worksheet.id, "startRowIndex": 1}], "booleanRule": { "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formula}]}, "format": {"backgroundColor": color}}}, "index": 0}}
            add_requests.append(rule)

        if add_requests:
            body = {"requests": add_requests}
            worksheet.spreadsheet.batch_update(body)
            print("✅ Conditional formatting rules applied successfully.")

    except Exception as e:
        print(f"⚠️ Could not set up conditional formatting. Error: {e}")

setup_conditional_formatting(sheet)

# ----------------------------
# Setup & Configuration
# ----------------------------
args = automation_utils.parse_arguments()
driver = automation_utils.setup_driver(headless=args.headless)
wait = WebDriverWait(driver, 30)

# ----------------------------
# UPDATED: Robust Helper to load existing keys from sheet
# ----------------------------
def load_existing_data():
    """Return dict of unique keys (Date|TruckNumber) -> {row, quantity, liquor_types} from existing sheet."""
    print("... Loading existing data from Google Sheet to check for updates...")
    
    max_load_retries = 3
    load_retry_delay = 5
    headers = []
    
    for attempt in range(max_load_retries):
        try:
            headers = sheet.row_values(1)
            break
        except Exception as e:
            print(f"⚠️ Error reading sheet headers (Attempt {attempt+1}): {e}")
            if attempt < max_load_retries - 1:
                time.sleep(load_retry_delay)
                load_retry_delay *= 2
            else:
                print("❌ Failed to read headers after retries. Aborting to prevent data duplication.")
                sys.exit(1)

    # --- UPDATED KEY: Now Date|TruckNumber ---
    if not headers or 'TruckNumber' not in headers:
        print("... 'TruckNumber' column not found or sheet is empty. No existing data.")
        return {}

    print("... Using 'Date|TruckNumber' for duplicate/update checking.")

    records = []
    load_retry_delay = 5
    for attempt in range(max_load_retries):
        try:
            # get_all_records returns a list of dictionaries
            records = sheet.get_all_records()
            break
        except Exception as e:
            print(f"⚠️ Error reading existing sheet records (Attempt {attempt+1}): {e}")
            if attempt < max_load_retries - 1:
                time.sleep(load_retry_delay)
                load_retry_delay *= 2
            else:
                print("❌ Failed to read existing records after retries. Aborting to prevent data duplication.")
                sys.exit(1)

    if not records:
        print("... No existing records found.")
        return {}

    existing_data = {}
    # Iterate with index to track Row Number (1-based)
    # Header is Row 1. First record is Row 2.
    for i, record in enumerate(records):
        try:
            date_val = normalize_date_string(str(record.get('DateofEndorsement', '')))
            truck_val = str(record.get('TruckNumber', '')).strip()
            
            if date_val and truck_val:
                clean_truck = "".join(truck_val.split()).upper()
                k = f"{date_val}|{clean_truck}"
                existing_data[k] = {
                    'row': i + 2, # 1-based index (Header is 1, so indices start at 2)
                    'quantity': record.get('TotalQuantity', 0),
                    'liquor': record.get('LiqourTypes', '')
                }
        except Exception as e:
            print(f"⚠️ Warning: Could not process a row. Row: {record}, Error: {e}")
            
    print(f"... Found {len(existing_data)} existing entries.")
    return existing_data

# ----------------------------
# Incoming Stock Checkpoint Logic
# ----------------------------
INCOMING_CHECKPOINT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../incoming_stock_checkpoint.json")

def load_incoming_checkpoint():
    if os.path.exists(INCOMING_CHECKPOINT_FILE):
        try:
            with open(INCOMING_CHECKPOINT_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_incoming_checkpoint(data):
    try:
        with open(INCOMING_CHECKPOINT_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print("💾 Incoming stock checkpoint saved.")
    except Exception as e:
        print(f"⚠️ Failed to save incoming checkpoint: {e}")

incoming_checkpoint = load_incoming_checkpoint()
import copy
old_incoming_checkpoint = copy.deepcopy(incoming_checkpoint)


# ----------------------------
# Main scraping logic
# ----------------------------
try:
    # ----------------------------
    # AUTOMATIC: Run Cleanup
    # ----------------------------
    def perform_sheet_cleanup(sheet_obj):
        print("🧼 Auto-Cleaning Sheet Data...")
        try:
            all_data = sheet_obj.get_all_records()
            if not all_data:
                print("   - Sheet is empty, nothing to clean.")
                return

            headers = sheet_obj.row_values(1)
            if not headers or "TruckNumber" not in headers:
                print(f"   - 'TruckNumber' column not found. Skipping cleanup.")
                return
            
            suffixes_to_strip = list(SIZE_SUFFIX_MAPPING.values())
            updates_to_push = []
            
            # Find indices for Supplier and LiqourTypes (1-based for gspread)
            try:
                supplier_col_idx = headers.index("Supplier") + 1
                liquor_col_idx = headers.index("LiqourTypes") + 1
            except ValueError:
                print("   - Required columns missing for cleanup. Skipping.")
                return

            bifurcation_col_idx = None
            if "Bifurcation" in headers:
                bifurcation_col_idx = headers.index("Bifurcation") + 1

            def clean_bifurcation_string(bifurcation_str):
                if not bifurcation_str or not isinstance(bifurcation_str, str):
                    return ""
                parts = bifurcation_str.split(';')
                cleaned_parts = []
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    if '(' in part and part.endswith(')'):
                        idx = part.rfind('(')
                        brand_name = part[:idx].strip()
                        sizes = part[idx:].strip()
                        mapped_brand = get_short_name(brand_name)
                        cleaned_parts.append(f"{mapped_brand} {sizes}")
                    else:
                        cleaned_parts.append(get_short_name(part))
                return "; ".join(cleaned_parts)

            for i, record in enumerate(all_data):
                row_num = i + 2 # Header is row 1
                original_supplier = record.get('Supplier', '')
                original_liquor_str = record.get('LiqourTypes', '')
                
                # Clean Supplier
                cleaned_supplier = get_short_supplier_name(original_supplier)
                if cleaned_supplier != original_supplier:
                    updates_to_push.append(gspread.Cell(row_num, supplier_col_idx, cleaned_supplier))

                # Clean Liquor Types
                if original_liquor_str:
                    cleaned_liquors = []
                    liquor_list = [item.strip() for item in str(original_liquor_str).replace('`S', "'S").split(',')]
                    
                    for liquor_name in liquor_list:
                        # Strip suffixes
                        name_stripped = liquor_name
                        detected_suffix = None
                        
                        for suffix in suffixes_to_strip:
                            if name_stripped.endswith(f" {suffix}"):
                                 name_stripped = name_stripped[:-len(f" {suffix}")]
                                 detected_suffix = suffix
                            elif name_stripped.endswith(suffix):
                                 name_stripped = name_stripped[:-len(suffix)]
                                 detected_suffix = suffix
                        
                        base_name = get_short_name(name_stripped.strip())
                        
                        # Logic: Restore Bottle/Can ONLY if it is a Beer Brand
                        if detected_suffix in ["Bottle", "Can"] and (base_name in BEER_BRANDS or any(base_name.startswith(b) for b in BEER_BRANDS)):
                            # Avoid double suffix if base_name already has it
                            if not base_name.endswith(detected_suffix):
                                cleaned_liquors.append(f"{base_name} {detected_suffix}")
                            else:
                                cleaned_liquors.append(base_name)
                        # If base_name ITSELF implies Bottle/Can, use it
                        elif base_name in BEER_BRANDS or any(base_name.startswith(b) for b in BEER_BRANDS): 
                             cleaned_liquors.append(base_name)
                        else:
                             cleaned_liquors.append(base_name)
                        
                    cleaned_liquor_str = ", ".join(sorted(list(set(cleaned_liquors))))
                    
                    if cleaned_liquor_str != original_liquor_str:
                        updates_to_push.append(gspread.Cell(row_num, liquor_col_idx, cleaned_liquor_str))

                # Clean Bifurcation Column
                if bifurcation_col_idx:
                    original_bif = record.get('Bifurcation', '')
                    if original_bif:
                        cleaned_bif = clean_bifurcation_string(original_bif)
                        if cleaned_bif != original_bif:
                            updates_to_push.append(gspread.Cell(row_num, bifurcation_col_idx, cleaned_bif))

            if updates_to_push:
                print(f"   - Pushing {len(updates_to_push)} cleaned cells back to the sheet...")
                sheet_obj.update_cells(updates_to_push)
                print("✅ Sheet cleaned.")
            else:
                print("✅ Sheet already clean, no updates needed.")

        except Exception as e:
            print(f"⚠️ Cleanup failed (continuing execution): {e}")

    # Run it!
    perform_sheet_cleanup(sheet)

    # ----------------------------
    # Normal Scraping Logic
    # ----------------------------
    print("🚀 Opening portal:", PORTAL_URL)
    automation_utils.navigate_to_url_with_retry(driver, PORTAL_URL)
    if not args.headless:
        driver.maximize_window()
    if not args.headless:
        driver.maximize_window()
    # time.sleep(15) # Removed: Normal strategy waits for load


    print(f"🔐 Filling login fields for user: {USERNAME}...")
    
    max_retries = 15
    login_success = False

    for attempt in range(max_retries):
        try:
            # Wait for interactive state (clickable) not just presence
            time.sleep(2) # Allow JS to settle
            
            # Toggle login modal if fields are hidden (Redesigned UI support)
            try:
                temp_user_box = driver.find_element(By.ID, "LoginForm_username")
                if not temp_user_box.is_displayed():
                    print("   - Login form is hidden. Clicking header Login button...")
                    login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'header-login-btn') or contains(text(), 'Login')]")))
                    driver.execute_script("arguments[0].click();", login_btn)
                    time.sleep(2) # Wait for animation/modal
            except Exception as e_toggle:
                print(f"   - (Info) Header login button toggle check/click skipped or failed: {e_toggle}")

            username_box = wait.until(EC.element_to_be_clickable((By.ID, "LoginForm_username")))
            username_box.clear()
            username_box.send_keys(USERNAME)
            
            password_box = wait.until(EC.presence_of_element_located((By.ID, "LoginForm_password")))
            driver.execute_script("arguments[0].removeAttribute('readonly')", password_box)
            password_box.clear()
            password_box.send_keys(PASSWORD)
            
            captcha_box = wait.until(EC.presence_of_element_located((By.ID, "LoginForm_verifyCode")))
            captcha_box.clear()
            
            # 1. Attempt OCR
            captcha_text = automation_utils.solve_captcha_ocr(driver)
            
            if captcha_text:
                print(f"   - Attempt {attempt+1}/{max_retries}: Trying OCR code: '{captcha_text}'")
                captcha_box.send_keys(captcha_text)
            else:
                print(f"   - Attempt {attempt+1}/{max_retries}: OCR failed to read code. Retrying...")
                driver.refresh()
                time.sleep(2)
                continue

            login_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'Login')]")))
            driver.execute_script("arguments[0].click();", login_button)
            
            # Check success
            try:
                # 1. Check if 'reports' tab is available
                # 2. OR Check if URL contains 'dashboard' (Strong indicator of success)
                try:
                    wait.until(lambda d: "dashboard" in d.current_url.lower() or d.find_elements(By.XPATH, "//a[contains(@href, 'Wholesale/reports')]"))
                    print("✅ Login successful (Dashboard or Reports found).")
                    login_success = True
                    break
                except:
                   # Reraise to fail handling
                   raise TimeoutException("Neither Dashboard URL nor Reports element found.")
            except TimeoutException:
                # Check for error message
                try:
                    error_msg = driver.find_element(By.CSS_SELECTOR, ".alert-danger").text
                    print(f"⚠️ Login Warning: {error_msg}")
                    
                    # Refresh captcha if needed or simple retry
                    if "code" in error_msg.lower() or "captcha" in error_msg.lower():
                        print("   - Refreshing page to get new captcha...")
                        driver.refresh()
                        time.sleep(2)
                        continue
                except:
                    pass
                
                print("   - Login verify timed out. Retrying...")
                driver.refresh()
                time.sleep(2)

        except Exception as e:
            print(f"⚠️ Error during login attempt {attempt+1}: {e}")
            print(f"   🔍 Debug: Exception Type: {type(e).__name__}")
            try:
                print(f"   🔍 Debug: Current URL: {driver.current_url}")
                print(f"   🔍 Debug: Page Title: {driver.title}")
                print(f"   🔍 Debug: Page Source Snippet (First 1000 chars):\n{driver.page_source[:1000]}")
            except:
                print("   ⚠️ Could not retrieve detailed driver info (driver might be dead).")
            
            try:
                # Capture Screenshot of failure
                fail_ss = f"login_failed_attempt_{attempt+1}.png"
                driver.save_screenshot(fail_ss)
                print(f"   📸 Saved screenshot: {fail_ss}")
                 # Print Page Source Snippet (Redundant but keep existing logic flow)
                with open(f"login_failed_source_{attempt+1}.html", "w") as f:
                    f.write(driver.page_source)
            except: pass
            
            driver.refresh()
            time.sleep(2)

    if not login_success:
        print("❌ Login Failed after retries.")
        driver.quit()
        sys.exit(1)

     # Navigation continues...
    print("📄 Navigating to Permits & Pass Reports...")
    try:
        reports_index_url = PORTAL_URL.replace("/site/login", "/report/index")
        driver.get(reports_index_url)
        time.sleep(2)
        child_link = wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href,'Wholesale/reports/tpdet_stockrec')]")))
        driver.execute_script("arguments[0].click();", child_link)
        time.sleep(3)
    except Exception as e_nav:
        print(f"❌ Could not find reports tab or navigate after login: {e_nav}") 
        sys.exit(1)

    today = datetime.now()
    
    # 1. Determine the end date (defaults to today)
    if args.end_date:
        try:
            today = datetime.strptime(args.end_date, "%d-%m-%Y")
        except ValueError:
            print("❌ Invalid end_date format. Use DD-MM-YYYY. Defaulting to today.")
            
    # 2. Determine the start date (defaults to start of month, looking back if early in month)
    if args.start_date:
        try:
            start_of_month = datetime.strptime(args.start_date, "%d-%m-%Y")
        except ValueError:
            print("❌ Invalid start_date format. Use DD-MM-YYYY. Defaulting to start of month.")
            start_of_month = today.replace(day=1)
            if today.day <= 3:
                last_day_prev = today.replace(day=1) - timedelta(days=1)
                start_of_month = last_day_prev.replace(day=1)
    else:
        start_of_month = today.replace(day=1)
        if today.day <= 3:
            last_day_prev = today.replace(day=1) - timedelta(days=1)
            start_of_month = last_day_prev.replace(day=1)
    
    
    def select_date(target_date):
        day_to_select = str(int(target_date.strftime('%d')))
        current_calendar_month_year = driver.find_element(By.CSS_SELECTOR, "div.datepicker-days .datepicker-switch").text
        target_month_year = target_date.strftime('%B %Y')
        
        while target_month_year != current_calendar_month_year:
            print(f"    Target month ({target_month_year}) is different from current view ({current_calendar_month_year}). Clicking previous.")
            prev_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "div.datepicker-days .prev")))
            prev_button.click()
            time.sleep(0.5)
            current_calendar_month_year = driver.find_element(By.CSS_SELECTOR, "div.datepicker-days .datepicker-switch").text

        day_element_xpath = f"//div[contains(@class,'datepicker-days')]//td[not(contains(@class, 'old')) and not(contains(@class, 'new')) and text()='{day_to_select}']"
        day_element = wait.until(EC.element_to_be_clickable((By.XPATH, day_element_xpath)))
        day_element.click()

    print(f"🤖 Automating date selection for range: {start_of_month.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}")
    wait.until(EC.element_to_be_clickable((By.ID, "datepicker"))).click(); time.sleep(0.8); select_date(start_of_month)
    wait.until(EC.element_to_be_clickable((By.ID, "datepicker1"))).click(); time.sleep(0.8); select_date(today)
    
    # Initialize tracking lists - REMOVED (Using shared sets in liquor_data)
    # unmapped_suppliers = set()
    # unmapped_liquor_names = set()

    search_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@onclick='searchtext()']")))
    driver.execute_script("arguments[0].click();", search_button)
    print("🔎 Search clicked — waiting for results...")
    time.sleep(4)
    print_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@onclick='PrintFormNo1();']")))
    driver.execute_script("arguments[0].click();", print_button)
    time.sleep(3)
    driver.switch_to.window(driver.window_handles[-1])
    time.sleep(2)

    print("📊 Scraping supplier, liquor types, and subtotal for each truck...")
    scraped_data = []
    headers = EXPECTED_HEADERS # <-- Use the correct headers
    
    try:
        all_rows = driver.find_elements(By.XPATH, "//tbody/tr[./td]")
        print(f"Found {len(all_rows)} data rows to process.")
        current_supplier_info = {} 
        liquor_types_for_current_truck = []
        
        # Track which trucks we have already reset in this session to avoid clearing them if they appear again (e.g. merge rows)
        scraped_trucks_session = set()

        for row in all_rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            row_data = [col.text.strip() for col in cols]

            # --- UPDATED: No PassNumber ---
            # Check for start of a new truck entry (Row starts with a digit)
            if row_data and row_data[0].isdigit() and row_data[1]:
                original_supplier_name = row_data[1]
                short_supplier_name = get_short_supplier_name(original_supplier_name)
                
                if short_supplier_name == original_supplier_name and original_supplier_name:
                    unmapped_suppliers.add(original_supplier_name)
                
                # --- NEW: Reset Checkpoint Logic for this Truck ---
                t_date_chk = row_data[7]
                t_num_chk = "".join(row_data[6].split()).upper()
                
                if t_date_chk not in incoming_checkpoint: 
                    incoming_checkpoint[t_date_chk] = {}
                
                # Use a unique key for the session reset
                session_key = f"{t_date_chk}|{t_num_chk}"
                
                if session_key not in scraped_trucks_session:
                    # First time seeing this truck in this run. 
                    # If it exists in the checkpoint (from a PREVIOUS run), we MUST clear it to avoid double counting.
                    if t_num_chk in incoming_checkpoint[t_date_chk]:
                         # Keep TelegramSupplier if we already caught it, else empty
                         incoming_checkpoint[t_date_chk][t_num_chk] = {}
                         # print(f"   ... [DEBUG] Cleared stale data for {t_num_chk} before re-scraping.")
                    
                    scraped_trucks_session.add(session_key)
                # --------------------------------------------------

                # --- NEW: Keep Original Name for Telegram ---
                telegram_supplier_name = get_telegram_supplier_name(original_supplier_name)

                current_supplier_info = { 
                    "Supplier": short_supplier_name, 
                    "TelegramSupplier": telegram_supplier_name,
                    "TruckNumber": t_num_chk, 
                    "DateofEndorsement": row_data[7] 
                }
                liquor_types_for_current_truck = []
            # --- END UPDATE ---

            # --- UPDATED: Logic to capture liquor from ALL rows (Start row + Continuation rows) ---
            if current_supplier_info:
                liquor_type_name = None
                size_code = None
                quantity_detailed = 0

                # Case 1: Standard Full Row (Start of truck or full row with empty first cols)
                # We check if index 10 exists.
                if len(row_data) > 11:
                    liquor_type_name = row_data[10]
                    size_code = row_data[11]
                    try:
                        quantity_detailed = int(row_data[12].replace(',', ''))
                    except:
                         quantity_detailed = 0
                
                # Case 2: Continuation Row (Short row due to rowspan)
                # If the row is short (e.g., < 10 cols) but has content, and we are inside a truck block.
                # Based on user logs/screenshot: Continuation rows have [ProductCode, ProductName, ProductSize, Quantity]
                # So Liquor Name is at Index 1, Size is at Index 2, Quantity at Index 3.
                elif len(row_data) > 3 and not row_data[0].isdigit() and "Sub Total" not in row_data[0]:
                     # Ensure it's not a "Sub Total" row and not a new truck row (already handled above)
                     liquor_type_name = row_data[1]
                     size_code = row_data[2]
                     try:
                        quantity_detailed = int(row_data[3].replace(',', ''))
                     except:
                        quantity_detailed = 0

                if liquor_type_name:
                    short_liquor_name = get_short_name(liquor_type_name)
                    suffix = SIZE_SUFFIX_MAPPING.get(size_code, size_code) # Use code itself if not mapped, or specific mapping
                    
                    if short_liquor_name in BEER_BRANDS or any(short_liquor_name.startswith(b) for b in BEER_BRANDS):
                         # Strip any pre-existing "Bottle" or "Can" from the mapped name to start fresh
                         clean_base_name = short_liquor_name
                         for s in ["Bottle", "Can"]:
                             if clean_base_name.endswith(f" {s}"):
                                 clean_base_name = clean_base_name[:-len(f" {s}")]
                         
                         # Apply suffix strictly based on size code (AP=Can, BS=Bottle)
                         if suffix == "Can":
                             final_name = f"{clean_base_name} Can"
                         elif suffix == "Bottle":
                             final_name = f"{clean_base_name} Bottle"
                         else:
                             final_name = short_liquor_name
                    else:
                        clean_base_name = short_liquor_name
                        final_name = short_liquor_name

                    # --- NEW: Capture Detailed Data for Checkpoint ---
                    t_date = current_supplier_info["DateofEndorsement"]
                    t_num = current_supplier_info["TruckNumber"]
                    
                    # Ensure structure exists
                    if t_date not in incoming_checkpoint: incoming_checkpoint[t_date] = {}
                    if t_num not in incoming_checkpoint[t_date]: 
                        incoming_checkpoint[t_date][t_num] = {
                            "_TelegramSupplier": current_supplier_info.get("TelegramSupplier", "")
                        }
                    
                    # Use clean_base_name for WhatsApp Report grouping to prevent "Kingfisher Bottle \n ↳ Can"
                    if clean_base_name not in incoming_checkpoint[t_date][t_num]: 
                        incoming_checkpoint[t_date][t_num][clean_base_name] = {}
                    
                    # Add quantity (handle potential duplicates if any, though unlikely for same size/truck)
                    current_qty = incoming_checkpoint[t_date][t_num][clean_base_name].get(suffix, 0)
                    incoming_checkpoint[t_date][t_num][clean_base_name][suffix] = current_qty + quantity_detailed
                    # ------------------------------------------------
                    
                    # Avoid adding empty or garbage entries
                    if short_liquor_name.strip():
                        liquor_types_for_current_truck.append(final_name)
            # --- END UPDATE ---

            if row_data and "Sub Total" in row_data[0] and current_supplier_info:
                cells_with_content = [cell for cell in row_data if cell]
                if cells_with_content:
                    # --- UPDATED: Handle comma in quantity ---
                    subtotal_quantity = cells_with_content[-1].replace(',', '')
                    all_liquor_types = ", ".join(sorted(list(set(liquor_types_for_current_truck))))

                    # --- UPDATED: Passing TelegramSupplier as 6th element ---
                    record = [
                        current_supplier_info["DateofEndorsement"],
                        current_supplier_info["Supplier"],
                        current_supplier_info["TruckNumber"],
                        all_liquor_types,
                        subtotal_quantity,
                        current_supplier_info["TelegramSupplier"]
                    ]
                    scraped_data.append(record)
                
                current_supplier_info = {}
                liquor_types_for_current_truck = []
        
        print(f"✅ Scraped {len(scraped_data)} initial truck entries.")
        # Save Checkpoint after scraping
        save_incoming_checkpoint(incoming_checkpoint)


    except Exception as e:
        print(f"❌ Error during the scraping process: {e}")
        import traceback
        traceback.print_exc()
        driver.quit()
        sys.exit(1)

    # -----------------------------------------------------------------
    # --- RE-ADDED MERGING LOGIC ---
    # -----------------------------------------------------------------
    print("🔄 Merging entries for duplicate trucks on the same day...")
    merged_records = {}

    for record in scraped_data:
        # record is [date, supplier, truck_number, liquor_types_str, quantity_str, telegram_supplier]
        date, supplier, truck_number, liquor_types_str, quantity_str, telegram_supplier = record
        # Normalize truck number to handle spacing/casing inconsistencies
        clean_truck = "".join(truck_number.split()).upper()
        key = (normalize_date_string(date), clean_truck) # Use normalized date and truck for merging key

        try:
            # Quantity string is already cleaned of commas
            quantity = int(quantity_str)
        except ValueError:
            print(f"⚠️ Warning: Could not convert quantity '{quantity_str}' to a number. Skipping record: {record}")
            continue

        if key not in merged_records:
            merged_records[key] = {
                'DateofEndorsement': date,
                'Supplier': supplier,
                'TelegramSupplier': telegram_supplier,
                'TruckNumber': clean_truck, # Use clean truck number for consistency
                'LiqourTypes': set(t.strip() for t in liquor_types_str.split(',') if t.strip()),
                'TotalQuantity': 0
            }
        
        merged_records[key]['TotalQuantity'] += quantity
        new_liquor_types = set(t.strip() for t in liquor_types_str.split(',') if t.strip())
        merged_records[key]['LiqourTypes'].update(new_liquor_types)
    
    processed_data = []
    for data in merged_records.values():
        liquor_types_str = ", ".join(sorted(list(data['LiqourTypes'])))
        bifurcation_str = automation_utils.get_bifurcation_string(data['DateofEndorsement'], data['TruckNumber'], incoming_checkpoint)
        processed_data.append([
            data['DateofEndorsement'],
            data['Supplier'],
            data['TruckNumber'],
            liquor_types_str,
            str(data['TotalQuantity']),
            "Not Arrived",
            "", 
            "",
            bifurcation_str,
            data['TelegramSupplier']
        ])
    print(f"✅ Data processed into {len(processed_data)} final merged entries.")
    # --- END RE-ADDED MERGING LOGIC ---
        
    existing_data = load_existing_data()
    
    new_rows = []
    updates_to_push = [] # List of gspread.Cell objects
    updated_permit_messages_to_send = [] # Track diffs for Telegram updates

    # Map headers to column indices (1-based)
    # EXPECTED_HEADERS = ["DateofEndorsement", "Supplier", "TruckNumber", "LiqourTypes", "TotalQuantity", ...]
    # Date (1), Supplier (2), Truck (3), Liquor (4), Qty (5), Bifurcation (9)
    LIQUOR_COL_IDX = 4
    QTY_COL_IDX = 5
    BIFURCATION_COL_IDX = 9

    print("🔄 Comparing scraped data with existing sheet data...")
    
    sheet_rows_to_insert = []

    for r in processed_data:
        date_val = normalize_date_string(r[0])
        truck_val = str(r[2]).strip()
        clean_truck = "".join(truck_val.split()).upper()
        key = f"{date_val}|{clean_truck}"
        
        scraped_qty = int(r[4])
        scraped_liquor = r[3]
        
        # Slicing the row to remove TelegramSupplier before pushing it to Google sheets.
        sheet_row_to_insert = r[:9]

        if key in existing_data:
            # Check for updates
            existing_entry = existing_data[key]
            existing_qty = 0
            try:
                existing_qty = int(str(existing_entry['quantity']).replace(',', ''))
            except: pass
            
            # Update if Scraped Quantity is DIFFERENT (usually higher)
            if scraped_qty != existing_qty:
                print(f"   📝 Updating Row {existing_entry['row']} for {truck_val}: Qty {existing_qty} -> {scraped_qty}")
                
                # Add Cell objects for batch update
                updates_to_push.append(gspread.Cell(existing_entry['row'], LIQUOR_COL_IDX, scraped_liquor))
                updates_to_push.append(gspread.Cell(existing_entry['row'], QTY_COL_IDX, scraped_qty))
                updates_to_push.append(gspread.Cell(existing_entry['row'], BIFURCATION_COL_IDX, r[8]))

                # Calculate the diff for Telegram: only send the new permit's quantity and brand breakdown
                diff_qty = scraped_qty - existing_qty
                if diff_qty > 0:
                    diff_record = list(r)
                    diff_record[4] = str(diff_qty)
                    
                    # Compute subtraction checkpoint for this specific truck update
                    diff_checkpoint = {}
                    diff_details = automation_utils.subtract_checkpoint_details(
                        incoming_checkpoint.get(date_val, {}).get(truck_val, {}),
                        old_incoming_checkpoint.get(date_val, {}).get(truck_val, {})
                    )
                    if date_val not in diff_checkpoint:
                        diff_checkpoint[date_val] = {}
                    diff_checkpoint[date_val][truck_val] = diff_details
                    
                    updated_permit_messages_to_send.append((diff_record, diff_checkpoint))
        else:
            new_rows.append(r)
            sheet_rows_to_insert.append(sheet_row_to_insert)
            
    # 1. Perform Updates
    if updates_to_push:
        try:
            print(f"🚀 Pushing {len(updates_to_push)} cell updates to Google Sheet...")
            sheet.update_cells(updates_to_push)
            print("✅ Updates successful.")
        except Exception as e:
            print(f"❌ Failed to push updates: {e}")

    # 2. Perform Inserts
    if not new_rows:
        print("✅ No new rows to append.")
    else:
        try:
            current_headers = sheet.row_values(1)
        except gspread.exceptions.APIError:
            current_headers = []

        if current_headers != headers:
            print("Headers are missing or incorrect, updating headers on row 1.")
            try:
                # Update ONLY the first row (headers) to avoid wiping data
                target_range = f"A1:{gspread.utils.rowcol_to_a1(1, len(headers))}"
                sheet.update([headers], target_range)
            except Exception as e:
                 print(f"Failed to update headers: {e}")
        elif not sheet.get_all_values():
            print("Sheet is completely empty, writing new headers.")
            sheet.append_row(headers, value_input_option="USER_ENTERED")
        
        sheet.append_rows(sheet_rows_to_insert, value_input_option="USER_ENTERED")
        print(f"✅ Appended {len(sheet_rows_to_insert)} new rows to Google Sheet.")

    # ---------------------------------------------------------
    # --- WHATSAPP SUMMARY GENERATION (Smart Fallback) ---
    # ---------------------------------------------------------
    print("\n--- WhatsApp Report Generation ---")
    
    user_day_input = ""
    run_auto_mode = args.auto

    # FORCED AUTOMATION: No input() allowed on server
    if args.day:
        user_day_input = args.day
    else:
        # Default to auto mode always
        run_auto_mode = True
        print("🤖 Automation Mode: Defaulting to Today/New Rows (No User Input)")

    data_to_summary = []
    report_date_title = ""

    today_date = datetime.now()

    if args.yesterday:
        target_date = today_date - timedelta(days=1)
        report_date_title = target_date.strftime('%d-%b-%Y') + " (Yesterday's Report)"
        target_date_str = target_date.strftime('%Y-%m-%d')
        print(f"   - Yesterday Flag Active: Generating report for {report_date_title}")
        # Filter for strictly yesterday
        data_to_summary = [r for r in processed_data if normalize_date_string(r[0]) == target_date_str]

    elif user_day_input:
        # Handle explicit date request
        day_num = "".join(filter(str.isdigit, user_day_input))
        
        if day_num:
            current_date = datetime.now()
            try:
                target_date = current_date.replace(day=int(day_num))
                target_date_str = target_date.strftime('%Y-%m-%d')
                
                print(f"   - Generating report for: {target_date.strftime('%d-%b-%Y')}")
                report_date_title = target_date.strftime('%d-%b-%Y')
                
                # Filter processed_data (contains all scraped data for this month)
                # row index 0 is DateofEndorsement
                data_to_summary = [r for r in processed_data if normalize_date_string(r[0]) == target_date_str]
                
                if not data_to_summary:
                    print(f"   ⚠️ No data found for {report_date_title} in the scraped records.")
            except ValueError:
                print(f"   ❌ Invalid day entered: {day_num}")
    else:
        # Auto-mode
        # If --daily is used, we FORCE generating report for TODAY (or specific day if given) using ALL data
        if args.daily:
            print("   - Daily Flag Active: Genering report for TODAY's full data (ignoring 'new rows' constraint).")
            today_str = datetime.now().strftime('%Y-%m-%d')
            data_to_summary = [r for r in processed_data if normalize_date_string(r[0]) == today_str]
            report_date_title = datetime.now().strftime('%d-%b-%Y') + " (Daily Summary)"
        elif new_rows or updated_permit_messages_to_send:
            print("   - Auto-Mode: Generating report for NEWLY added or updated rows.")
            data_to_summary = new_rows
            report_date_title = datetime.now().strftime('%d-%b-%Y') + " (New Data)"
        else:
            print("   - Auto-Mode: No new rows. Generating report for TODAY's data.")
            today_str = datetime.now().strftime('%Y-%m-%d')
            data_to_summary = [r for r in processed_data if normalize_date_string(r[0]) == today_str]
            report_date_title = datetime.now().strftime('%d-%b-%Y')
    
    if data_to_summary or (run_auto_mode and not args.daily) or updated_permit_messages_to_send:
        # In Auto-Mode, we might want to report even if 'data_to_summary' (new rows) is empty, 
        # specifically for the 23:00 Buffer Flush of the day's total data.
        
        # --- NEW: Smart Buffer & Cumulative Logic ---
        current_hour = datetime.now().hour
        current_minute = datetime.now().minute
        should_send = False
        final_data_to_send = []
        final_header = ""

        # 1. Determine what data to send (Cumulative for today vs Just New)
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_full_data = [r for r in processed_data if normalize_date_string(r[0]) == today_str]

        if run_auto_mode and not (args.day or args.yesterday or args.daily):
             # Auto-Mode Logic
             has_new_data = (len(new_rows) > 0)
             has_updates = (len(updated_permit_messages_to_send) > 0)
             
             if has_new_data or has_updates:
                 print(f"🔔 Auto-Mode: New/updated data found at {current_hour}:{current_minute}. Sending Individual Updates.")
                 should_send = True
             else:
                 print(f"⏳ Auto-Mode: No new/updated data. Silent.")
                 should_send = False
                 
             # If sending, send ONLY the new rows individually and standard messages for updated permits
             final_data_to_send = new_rows
             final_header = f"New Liqour Endorsement"

        else:
             # Manual / Forced Mode -> Always Send whatever was matched
             should_send = True if data_to_summary else False
             final_data_to_send = data_to_summary
             final_header = f"Liqour Endorsements - {report_date_title}"

        if should_send:
            summary_texts = []
            
            # 1. Process standard new rows in Auto-Mode or manual data
            if final_data_to_send:
                # Sort deterministically
                new_trucks_set = set(r[2] for r in new_rows) if new_rows else set()
                enum_data = list(enumerate(final_data_to_send))
                def sort_key(item):
                    orig_idx, r = item
                    is_new = 1 if r[2] in new_trucks_set else 0
                    date_val = normalize_date_string(r[0])
                    key = f"{date_val}|{r[2]}"
                    row_idx = existing_data.get(key, {}).get('row', float('inf'))
                    return (is_new, row_idx, orig_idx)
                enum_data.sort(key=sort_key)
                sorted_new_data = [item[1] for item in enum_data]
                
                print("\n📋 Generating WhatsApp Summary for standard new/filtered rows...")
                new_reports = automation_utils.generate_whatsapp_reports(sorted_new_data, incoming_checkpoint, final_header)
                summary_texts.extend(new_reports)

            # 2. Process updated permits separately as normal new notifications containing only diff data
            if run_auto_mode and not (args.day or args.yesterday or args.daily) and updated_permit_messages_to_send:
                print("\n📋 Generating WhatsApp Summary for updated permits (diff reports)...")
                # Sort updated permits for consistent order
                enum_updated = list(enumerate(updated_permit_messages_to_send))
                def sort_key_updated(item):
                    orig_idx, (r, _) = item
                    date_val = normalize_date_string(r[0])
                    key = f"{date_val}|{r[2]}"
                    row_idx = existing_data.get(key, {}).get('row', float('inf'))
                    return (row_idx, orig_idx)
                enum_updated.sort(key=sort_key_updated)
                sorted_updated_list = [item[1] for item in enum_updated]
                
                for diff_record, diff_checkpoint in sorted_updated_list:
                    # Generate report as standard 'New Liqour Endorsement' with the diff info
                    update_reports = automation_utils.generate_whatsapp_reports([diff_record], diff_checkpoint, "New Liqour Endorsement")
                    summary_texts.extend(update_reports)
            
            if summary_texts:
                if not args.headless and pyperclip:
                    try:
                        pyperclip.copy("\n\n".join(summary_texts))
                        print("✅ WhatsApp summary copied to clipboard!")
                    except: pass
                
                for summary_text in summary_texts:
                    print("-" * 20)
                    print(summary_text)
                    print("-" * 20)
                
                # --- SEND VIA TELEGRAM API ---
                if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID and not args.no_telegram:
                    time.sleep(2)
                    for summary_text in summary_texts:
                        automation_utils.send_telegram_message(summary_text, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
                        time.sleep(1) # Small delay to avoid rate limiting
                else:
                    print("ℹ️ Telegram auto-send skipped (keys missing or disabled).")
            else:
                print("ℹ️ Report triggered but no summary messages generated.")
        elif should_send and not final_data_to_send:
             print("ℹ️ Report triggered but no data found to report.")

    else:
        # Fallback
        print("ℹ️ No data to report for the selected criteria.")


    if liquor_data.unmapped_suppliers:
        print("\n--- ACTION REQUIRED ---\nUnmapped suppliers found:")
        for name in sorted(list(liquor_data.unmapped_suppliers)): print(f'"{name}": "Your Short Name Here",')
        print("\n-----------------------\n")

    if liquor_data.unmapped_liquor_names:
        print("\n--- ACTION REQUIRED ---\nNew liquor names were found. Add these to LIQUOR_NAME_MAPPING:")
        for name in sorted(list(liquor_data.unmapped_liquor_names)): print(f'"{name}": "Your Short Name Here",')
        print("\n-----------------------\n")


finally:
    driver.quit()