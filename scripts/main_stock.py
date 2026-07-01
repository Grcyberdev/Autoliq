import os
import sys
import time
import json
from datetime import datetime, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

import gspread
from google.oauth2.service_account import Credentials

# Import shared automation utilities
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import automation_utils
from liquor_data import get_short_name

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

CONFIG_POSSIBLE = ["../config/config.json", "./config/config.json", "config/config.json"]
CONFIG_FILE = next((p for p in CONFIG_POSSIBLE if os.path.exists(p)), None)
if not CONFIG_FILE:
    print("❌ config.json not found.")
    sys.exit(1)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

PORTAL_URL = config.get("portal_url")

# Credentials List
CREDENTIALS = [
    {"user": config.get("IMFL_USERNAME"), "pass": config.get("IMFL_PASSWORD"), "type": "IMFL"},
    {"user": config.get("CS_USERNAME"), "pass": config.get("CS_PASSWORD"), "type": "CS"}
]

if not PORTAL_URL or not CREDENTIALS[0]["user"] or not CREDENTIALS[1]["user"]:
    print("❌ config.json missing keys.")
    sys.exit(1)

# ----------------------------
# Google Sheets Connection
# ----------------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

def get_or_create_worksheet():
    try:
        spreadsheet = gc.open(SPREADSHEET_NAME)
        try:
            sheet = spreadsheet.worksheet(WORKSHEET_NAME)
            print(f"✅ Connected to '{SPREADSHEET_NAME}' → '{WORKSHEET_NAME}'")
            return sheet
        except gspread.exceptions.WorksheetNotFound:
            print(f"⚠️ Worksheet '{WORKSHEET_NAME}' not found. Creating it...")
            sheet = spreadsheet.add_worksheet(title=WORKSHEET_NAME, rows=1000, cols=20)
            sheet.update('A1', [['Liquor Name']])
            print(f"✅ Created '{WORKSHEET_NAME}'.")
            return sheet
    except Exception as e:
        print(f"❌ Error connecting to sheet: {e}")
        sys.exit(1)

# ----------------------------
# Checkpoints
# ----------------------------
OUTBOUND_FILE = "stock_data_checkpoint.json"
INCOMING_FILE = "incoming_stock_checkpoint.json"

def load_json(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def save_json(filepath, data):
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"⚠️ Failed to save checkpoint {filepath}: {e}")

# Load DBs
outbound_db = load_json(OUTBOUND_FILE)
incoming_db = load_json(INCOMING_FILE)

# ----------------------------
# Size Reconciliation Helper
# ----------------------------
def get_incoming_qty(outbound_key, start_date=None, end_date=None):
    """
    Calculates total Incoming stock for a given Outbound Key (e.g. 'RS (180/48)')
    by matching it against the structured Incoming DB.
    """
    # 1. Parse Outbound Key
    # Format is typically "Short Name (Size/...)" or just "Short Name"
    base_name = outbound_key
    size_hint = None
    
    if "(" in outbound_key and ")" in outbound_key:
        try:
            p_start = outbound_key.rfind("(")
            p_end = outbound_key.rfind(")")
            base_name = outbound_key[:p_start].strip()
            # Extract content inside parens, e.g. "180/48" or "750ml"
            size_content = outbound_key[p_start+1:p_end]
            # Try to find a size indicator (750, 375, 180, 650, 500)
            if "750" in size_content: size_hint = "750ml"
            elif "375" in size_content: size_hint = "375ml"
            elif "180" in size_content: size_hint = "180ml"
            elif "650" in size_content: size_hint = "650ml"
            elif "500" in size_content: size_hint = "500ml"
            elif "330" in size_content: size_hint = "330ml"
            elif "275" in size_content: size_hint = "275ml"
            elif "200" in size_content: size_hint = "200ml"
            elif "1000" in size_content: size_hint = "1000ml"
            elif "90" in size_content: size_hint = "90ml"
            elif "60" in size_content: size_hint = "60ml"
            # Fallback mappings for Beer/Pack sizes if specific codes exist
        except:
             pass

    total_in = 0
    
    # 2. Iterate Incoming DB
    # Structure: Date -> Truck -> LiquorName -> Size -> Qty
    for date_str, trucks in incoming_db.items():
        # Date Filter (Optional)
        # if start_date and ... 
        # (For now, we assume ALL incoming since Dec 23 is relevant, but let's just sum all)
        
        for truck, items in trucks.items():
            # Check if this truck has our liquor
            if base_name in items:
                size_map = items[base_name]
                # If we have a size hint, look for it
                if size_hint and size_hint in size_map:
                    total_in += size_map[size_hint]
                elif not size_hint:
                    # If outbound has no size (rare), sum all sizes? 
                    # Or maybe it's a size-agnostic entry.
                    total_in += sum(size_map.values())
                
                # Handling Edge Case: What if size mismatch?
                # e.g. Outbound "RS (180/48)" implies 180ml. Incoming has "RS" -> "180ml". Match!
                
    return total_in


# ----------------------------
# Scraping Function
# ----------------------------
def scrape_data_for_user(driver_args, username, password, start_date, end_date, master_db):
    """
    Scrapes stock dispatch data for a single user over a date range.
    Updates master_db and saves checkpoint.
    Robustly handles session crashes by restarting driver.
    """
    # Ensure user key exists
    if username not in master_db:
        master_db[username] = {}

    driver = None
    wait = None
    
    current_date = start_date
    retry_count = 0
    MAX_RETRIES = 3 # Max retries per specific date before skipping

    def start_session():
        """Helper to start driver, login, and navigate to Stock Dispatch."""
        nonlocal driver, wait
        
        # 1. Init Driver
        if driver:
            try: driver.quit()
            except: pass
        
        driver = automation_utils.setup_driver(headless=driver_args.headless)
        wait = WebDriverWait(driver, 10)

        # 2. Login
        print(f"\n🚀 Starting session for {username}...")
        driver.get(PORTAL_URL)
        
        max_login_retries = 5
        login_success = False

        for attempt in range(max_login_retries):
            try:
                # Wait for interactive state / JS to settle
                time.sleep(2)
                
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

                print(f"🔐 Logging in as {username} (Attempt {attempt+1}/{max_login_retries})...")
                wait.until(EC.presence_of_element_located((By.ID, "LoginForm_username"))).clear()
                driver.find_element(By.ID, "LoginForm_username").send_keys(username)
                
                pwd_box = driver.find_element(By.ID, "LoginForm_password")
                try: driver.execute_script("arguments[0].removeAttribute('readonly')", pwd_box)
                except: pass
                pwd_box.clear()
                pwd_box.send_keys(password)
                
                captcha_box = driver.find_element(By.ID, "LoginForm_verifyCode")
                captcha_box.clear()

                # OCR Logic with Manual Fallback
                if attempt >= 2: # On 3rd attempt (0, 1, 2)
                    print("⚠️ OCR struggling. Switch to Manual Input.")
                    try:
                        c_img = driver.find_element(By.ID, "loginCaptcha") 
                    except:
                        c_img = driver.find_element(By.XPATH, "//img[contains(@src, 'captcha')]")
                    
                    c_img.screenshot("manual_captcha.png")
                    print(f"   🖼️  Captcha saved to: {os.path.abspath('manual_captcha.png')}")
                    
                    if driver_args.headless:
                         print("   (Headless Mode: Please open the image manually)")

                    manual_code = input(f"🧩 Enter Captcha Code: ")
                    captcha_box.send_keys(manual_code)
                else:
                    captcha_text = automation_utils.solve_captcha_ocr(driver)
                    
                    if captcha_text:
                        print(f"   - OCR Attempt: '{captcha_text}'")
                        captcha_box.send_keys(captcha_text)
                    else:
                        print("   - OCR failed to read. Retrying...")
                        driver.refresh()
                        time.sleep(2)
                        continue

                driver.find_element(By.XPATH, "//button[contains(text(),'Login')]").click()
                
                # Check Login
                try:
                    wait.until(EC.presence_of_element_located((By.XPATH, 
                        "//a[contains(@href, 'Wholesale/reports')] | "
                        "//div[contains(text(), 'Stock Dispatch')] | "
                        "//a[contains(text(), 'Stock')] | " 
                        "//form[contains(@action, 'logout')]"
                    )))
                    print("✅ Login successful.")
                    login_success = True
                    break
                except TimeoutException:
                     print("   - Login verify timed out.")
                     if attempt < max_login_retries - 1:
                        driver.refresh()
                        time.sleep(2)
                     continue

            except Exception as e:
                print(f"⚠️ Login error: {e}")
                try:
                    driver.refresh()
                    time.sleep(2)
                except:
                    # If refresh fails (e.g. browser died), re-raise to restart driver
                    raise e

        if not login_success:
            raise Exception(f"Failed to login as {username} after multiple attempts.")

        # 3. Navigate
        print("PAGE: Dashboard -> Stock Dispatch...")
        
        # Try clicking tile first
        try:
            stock_dispatch_tile = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[normalize-space()='Stock Dispatch'] | //span[normalize-space()='Stock Dispatch'] | //a[contains(., 'Stock Dispatch')]")))
            driver.execute_script("arguments[0].scrollIntoView(true);", stock_dispatch_tile)
            time.sleep(0.5)
            stock_dispatch_tile.click()
        except:
            print("   - Tile click failed, trying direct URL...")
            fallback_url = PORTAL_URL.replace("/site/login", "/Retailer/Retailer/Indentlist?param=stockdispatch")
            driver.get(fallback_url)
        
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, 
            "//input[@id='datepicker'] | //button[contains(., 'Search')]"
        )))
        
        print("✅ Stock Dispatch loaded.")
        time.sleep(2)


    # --- Main Date Loop ---
    
    try:
        start_session()
        
        while current_date <= end_date:
            target_date_str = current_date.strftime("%d-%b-%Y")
            print(f"   📅 [{username}] Checking {target_date_str}...")
            
            try:
                # IMPORTANT: Check if driver is alive before starting
                if not driver:
                     print("   🔄 Driver not active. Restarting session...")
                     start_session()

                daily_counts = {}

                # Helper to select date via UI
                def select_date_ui(target_date):
                    day_to_select = str(int(target_date.strftime('%d')))
                    try:
                        current_calendar_month_year = driver.find_element(By.CSS_SELECTOR, "div.datepicker-days .datepicker-switch").text
                    except: return

                    target_month_year = target_date.strftime('%B %Y')
                    while target_month_year != current_calendar_month_year:
                        curr_dt_obj = datetime.strptime(current_calendar_month_year, '%B %Y')
                        if target_date.year < curr_dt_obj.year or (target_date.year == curr_dt_obj.year and target_date.month < curr_dt_obj.month):
                             driver.find_element(By.CSS_SELECTOR, "div.datepicker-days .prev").click()
                        else:
                             driver.find_element(By.CSS_SELECTOR, "div.datepicker-days .next").click()
                        time.sleep(0.5)
                        current_calendar_month_year = driver.find_element(By.CSS_SELECTOR, "div.datepicker-days .datepicker-switch").text

                    day_element_xpath = f"//div[contains(@class,'datepicker-days')]//td[not(contains(@class, 'old')) and not(contains(@class, 'new')) and text()='{day_to_select}']"
                    wait.until(EC.element_to_be_clickable((By.XPATH, day_element_xpath))).click()

                # Start Date
                wait.until(EC.element_to_be_clickable((By.ID, "datepicker"))).click()
                time.sleep(0.5)
                select_date_ui(current_date)
                
                # End Date
                wait.until(EC.element_to_be_clickable((By.ID, "datepicker1"))).click()
                time.sleep(0.5)
                select_date_ui(current_date)
                
                # Select Status
                try:
                    trigger_xpath = "//*[@id='select2-status-container']/parent::span"
                    wait.until(EC.element_to_be_clickable((By.XPATH, trigger_xpath))).click()
                    time.sleep(1)
                    option_xpath = f"//li[contains(@class, 'select2-results__option') and contains(text(), 'Pass Issued')]"
                    wait.until(EC.element_to_be_clickable((By.XPATH, option_xpath))).click()
                    
                    search_btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Search') or contains(@class, 'btn-search')]")
                    driver.execute_script("arguments[0].click();", search_btn)
                    time.sleep(3)
                except Exception as e:
                    print(f"     ⚠️ Status selection error: {e}")
                    # If this fails, it might be a transient UI issue, just retry current date?
                    # Or skip? If we raise, we restart driver.
                    raise e 

                # Scrape Indents
                while True: # Pagination Loop
                    try:
                        table_body = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#my-table-sorter tbody")))
                        rows = table_body.find_elements(By.TAG_NAME, "tr")
                    except: break
                    
                    if len(rows) > 0 and "No results" in rows[0].text:
                        break
                    
                    i = 0
                    while True: # Row Loop
                        try:
                            # Re-fetch rows
                            table_body = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#my-table-sorter tbody")))
                            rows = table_body.find_elements(By.TAG_NAME, "tr")
                            if i >= len(rows): break
                            
                            current_row = rows[i]
                            
                            # Click Form 34
                            try:
                                btn = current_row.find_element(By.CSS_SELECTOR, "button.upload-btn")
                            except:
                                try: btn = current_row.find_element(By.XPATH, ".//button[contains(@onclick, 'form34print')]")
                                except: 
                                    i += 1
                                    continue
                                    
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                            time.sleep(0.5)
                            try: driver.execute_script("arguments[0].click();", btn)
                            except:
                                driver.execute_script("$('.lb_overlay_clear').remove();")
                                driver.execute_script("arguments[0].click();", btn)
                            time.sleep(2)
                            
                            # To New Tab
                            main_window = driver.current_window_handle
                            new_window = [w for w in driver.window_handles if w != main_window][0]
                            driver.switch_to.window(new_window)
                            
                            # Scrape Table
                            try:
                                tables = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "table")))
                                f34_table = max(tables, key=lambda t: len(t.find_elements(By.TAG_NAME, "tr")))
                                f34_rows = f34_table.find_elements(By.TAG_NAME, "tr")
                                
                                for f_row in f34_rows:
                                    f_cols = f_row.find_elements(By.TAG_NAME, "td")
                                    if len(f_cols) < 6 or not f_cols[0].text.strip().isdigit(): continue
                                    
                                    # [Index, Code, Name, Cat, Size, Qty, ...]
                                    raw_name = f_cols[2].text.strip()
                                    size_val = f_cols[4].text.strip()
                                    qty_str = f_cols[5].text.strip()
                                    
                                    if not raw_name: continue
                                    try: qty = int(float(qty_str.replace(',', '')))
                                    except: qty = 0
                                    
                                    if qty > 0:
                                        short_name = get_short_name(raw_name)
                                        key = f"{short_name} ({size_val})" if size_val else short_name
                                        
                                        daily_counts[key] = daily_counts.get(key, 0) + qty

                            except Exception as e:
                                print(f"       ⚠️ Form 34 error: {e}")
                                
                            driver.close()
                            driver.switch_to.window(main_window)
                            time.sleep(0.5)
                            i += 1

                        except Exception as e:
                            # Handle Window Errors specifically
                            if "invalid session id" in str(e).lower() or "no such window" in str(e).lower():
                                raise e # Escalate to main loop for restart
                            
                            if len(driver.window_handles) > 1:
                                 for w in driver.window_handles:
                                     if w != main_window:
                                         driver.switch_to.window(w)
                                         driver.close() # Close stray tab
                                 driver.switch_to.window(main_window)
                            i += 1
                            continue
                            
                    # Pagination Next
                    try:
                        driver.execute_script("$('.lb_overlay_clear').remove();")
                        next_btn = driver.find_element(By.ID, "my-table-sorter_next")
                        if "paginate_disabled_next" in next_btn.get_attribute("class"): break
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                        time.sleep(0.5); next_btn.click(); time.sleep(3)
                    except: break

                # Save Data and Advance
                master_db[username][target_date_str] = daily_counts
                save_json(OUTBOUND_FILE, master_db)
                print(f"     -> Found {len(daily_counts)} items. Saved checkpoint.")
                
                current_date += timedelta(days=1)
                retry_count = 0 # Reset retry on success
                time.sleep(1)

            except Exception as e:
                print(f"     ❌ Error processing {target_date_str}: {e}")
                
                retry_count += 1
                if retry_count > MAX_RETRIES:
                    print(f"     ⏭️  Max retries exceeded for {target_date_str}. Skipping to next day.")
                    current_date += timedelta(days=1)
                    retry_count = 0
                
                # Force restart
                print("     🔄 Triggering session restart...")
                try: driver.quit()
                except: pass
                driver = None # Will cause start_session() to run next loop

    finally:
        if driver:
            try: driver.quit()
            except: pass
        print(f"👋 {username} session ended.")

# ----------------------------
# Main Execution
# ----------------------------
# ----------------------------
# Scraping Function
# ----------------------------
def scrape_data_for_user(driver_args, username, password, start_date, end_date, master_db):
    """
    Scrapes stock dispatch data for a single user over a date range.
    Updates master_db and saves checkpoint.
    Robustly handles session crashes by restarting driver.
    """
    # Ensure user key exists
    if username not in master_db:
        master_db[username] = {}

    driver = None
    wait = None
    
    current_date = start_date
    retry_count = 0
    MAX_RETRIES = 3 # Max retries per specific date before skipping

    def start_session():
        # ... (Same as before, abbreviated for brevity in replacement if unchanged, but I need to include it or keep it)
        # To avoid replacing the huge function body, I will target the *lines around the save_data call* if possible?
        # But 'scrape_data_for_user' calls 'save_data'. I need to import/use 'save_json' with OUTBOUND_FILE.
        pass
    
    # ... (I need to replace the SAVE call inside).
    # Since I can't partial replace nicely without context, I will replace the whole function structure.
    # checking line 470 in previous view: `save_data(master_db)`
    
# Actually, I will just do a Multi Replace for the specific call sites if possible?
# But `save_data` takes 1 arg (data), `save_json` takes 2 (file, data).
# So I must change the call site.

# Let's replace the whole `scrape_data_for_user` to be safe and clean.
# Wait, `start_session` is nested.
# I'll use multi-replace.

# ----------------------------
# Main Execution
# ----------------------------
def main():
    args = automation_utils.parse_arguments()
    
    # Define Date Range
    if args.start_date:
        try:
            start_date = datetime.strptime(args.start_date, "%d-%m-%Y")
        except ValueError:
            print("❌ Invalid start_date format. Use DD-MM-YYYY.")
            sys.exit(1)
    else:
        start_date = datetime(2025, 12, 1) # Default: 01-Dec-2025

    if args.end_date:
        try:
            end_date = datetime.strptime(args.end_date, "%d-%m-%Y")
        except ValueError:
            print("❌ Invalid end_date format. Use DD-MM-YYYY.")
            sys.exit(1)
    else:
        end_date = datetime.now()
    
    print(f"📅 Scraping Range: {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')}")
    
    # Load Checkpoint
    master_db = load_json(OUTBOUND_FILE) # UPDATED

    # 1. Scrape for each user
    for cred in CREDENTIALS:
        if not cred["user"]: continue
        scrape_data_for_user(args, cred["user"], cred["pass"], start_date, end_date, master_db)
        
    # 2. Merge Data for Sheet
    print("\n🔄 Merging Data from Checkpoint...")
    MASTER_FLAT = {} # { date: { item: qty } }
    
    for user, dates in master_db.items():
        for d, items in dates.items():
            if d not in MASTER_FLAT: MASTER_FLAT[d] = {}
            for item, qty in items.items():
                MASTER_FLAT[d][item] = MASTER_FLAT[d].get(item, 0) + qty

    # 3. Sort and Process Data
    # Sort dates chronologically
    all_dates = sorted(list(MASTER_FLAT.keys()), key=lambda d: datetime.strptime(d, "%d-%b-%Y"))
    
    # Get all items
    all_items = set()
    for d in MASTER_FLAT:
        all_items.update(MASTER_FLAT[d].keys())
    
    sorted_items = sorted(list(all_items))
    
    # 4. Write to Sheet
    print("💾 Writing to Google Sheet with Reconciliation...")
    sheet = get_or_create_worksheet()
    
    # --- Data Preservation Logic ---
    existing_opening_stock = {}
    try:
        all_values = sheet.get_all_values()
        if all_values:
            headers_current = all_values[0]
            if "Liquor Name" in headers_current and "Opening Stock" in headers_current:
                name_idx = headers_current.index("Liquor Name")
                stock_idx = headers_current.index("Opening Stock")
                
                print("   ℹ️  Preserving existing 'Opening Stock' values...")
                for row_p in all_values[1:]:
                    if len(row_p) > max(name_idx, stock_idx):
                        l_name = row_p[name_idx]
                        o_stock = row_p[stock_idx]
                        if l_name and o_stock:
                            existing_opening_stock[l_name] = o_stock
    except Exception as e:
        print(f"   ⚠️ Could not read existing data for prevention: {e}")

    sheet.clear()
    
    # Updated Headers
    # Format: [Name, Opening, Total Incoming, Closing, Date1, Date2...]
    headers = ["Liquor Name", "Opening Stock", "Total Incoming", "Closing Stock"] + all_dates
    rows = [headers]
    
    for item in sorted_items:
        # 1. Opening Stock (Manual)
        op_stock_val = existing_opening_stock.get(item, "")
        try:
            opening_qty = int(str(op_stock_val).replace(',', '')) if op_stock_val else 0
        except: opening_qty = 0
        
        # 2. Incoming Stock (Total from Checkpoint)
        # Matches 'item' (e.g. 'RS (180/48)') to incoming buckets
        incoming_qty = get_incoming_qty(item)
        
        # 3. Outgoing Stock (Total for this item across ALL dates in DB)
        # Note: We sum from MASTER_FLAT which contains all dates in DB
        outgoing_qty = 0
        for d in MASTER_FLAT:
             outgoing_qty += MASTER_FLAT[d].get(item, 0)
             
        # 4. Closing Stock Calculation
        # Closing = Opening + Incoming - Outgoing
        closing_qty = opening_qty + incoming_qty - outgoing_qty
        
        # Build Row
        row = [item, op_stock_val, incoming_qty, closing_qty]
        
        # Add Daily Dispatch Columns
        for date in all_dates:
            qty = MASTER_FLAT[date].get(item, "")
            row.append(qty)
        rows.append(row)
        
    try:
        sheet.update(range_name=f"A1", values=rows)
        sheet.format("A1:Z1", {"textFormat": {"bold": True}})
        # Highlight Closing Stock Column (Column D, Index 3)?
        # Not implementing generic highlighting yet to avoid complexity.
        print("✅ Sheet updated successfully with Reconciliation!")
    except Exception as e:
        print(f"❌ Sheet update failed: {e}")

if __name__ == "__main__":
    main()

