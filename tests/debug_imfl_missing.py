
import os
import sys
import json
import time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add scripts dir to path to import main_stock and automation_utils
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import main_stock
import automation_utils

def debug_imfl():
    print("🐞 Starting Debug Run for IMFL_BOR - 15-Dec-2025")
    
    # 1. Get Creds
    creds = [c for c in main_stock.CREDENTIALS if c["user"] == "IMFL_BOR"][0]
    username = creds["user"]
    password = creds["pass"]
    
    # 2. Setup Driver
    class Args:
        headless = True
    
    driver = automation_utils.setup_driver(headless=True)
    wait = WebDriverWait(driver, 20)
    
    try:
        # Login
        print(f"🔐 Logging in as {username}...")
        driver.get(main_stock.PORTAL_URL)
        
        # ... (simplified login from main_stock)
        wait.until(EC.presence_of_element_located((By.ID, "LoginForm_username"))).send_keys(username)
        pwd = driver.find_element(By.ID, "LoginForm_password")
        driver.execute_script("arguments[0].removeAttribute('readonly')", pwd)
        pwd.send_keys(password)
        
        # OCR
        code = automation_utils.solve_captcha_ocr(driver)
        if code:
            driver.find_element(By.ID, "LoginForm_verifyCode").send_keys(code)
        
        driver.find_element(By.XPATH, "//button[contains(text(),'Login')]").click()
        time.sleep(5)
        
        # Navigate
        print("➡️ Navigating to Stock Dispatch...")
        driver.get("https://excise.assam.gov.in/wholesaledealer/Wholesale/stockDispatch?active=stock") 
        # Using direct URL or click? Let's try click to be safe matching main script
        # But wait, main script uses click.
        
        # Check if login success
        if "Login" in driver.title:
            print("❌ Login failed (still on login page).")
            driver.save_screenshot("debug_login_fail.png")
            return

        # Navigate UI
        try:
            stock_dispatch_tile = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[normalize-space()='Stock Dispatch']")))
            stock_dispatch_tile.click()
        except:
            print("⚠️ Could not click tile, trying direct URL...")
            driver.get("https://excise.assam.gov.in/wholesaledealer/Wholesale/stockDispatch?active=stock")

        time.sleep(3)
        driver.save_screenshot("debug_dispatch_page.png")
        
        # Select Date: 15-Dec-2025
        print("📅 Selecting Date: 15-Dec-2025")
        
        # Trigger Datepicker
        wait.until(EC.element_to_be_clickable((By.ID, "datepicker"))).click()
        time.sleep(1)
        
        # Select Dec 2025
        # Need to navigate calendar...
        # For simplicity, let's just use JS to set value? 
        # No, main script uses UI. I should replicate UI logic or use JS if UI is flaky.
        # Main script logic:
        # select_date_ui(current_date)
        
        # Let's try simpler JS set for debug
        driver.execute_script("$('#datepicker').datepicker('setDate', '15-12-2025');")
        driver.execute_script("$('#datepicker1').datepicker('setDate', '15-12-2025');")
        time.sleep(1)
        
        # Select Status
        print("Selecting 'Pass Issued'...")
        try:
            trigger_xpath = "//*[@id='select2-status-container']/parent::span"
            wait.until(EC.element_to_be_clickable((By.XPATH, trigger_xpath))).click()
            time.sleep(1)
            option_xpath = f"//li[contains(@class, 'select2-results__option') and contains(text(), 'Pass Issued')]"
            wait.until(EC.element_to_be_clickable((By.XPATH, option_xpath))).click()
        except Exception as e:
            print(f"⚠️ Status error: {e}")
        
        # Search
        print("🔍 Clicking Search...")
        driver.find_element(By.XPATH, "//a[contains(text(), 'Search')]").click()
        time.sleep(5)
        
        driver.save_screenshot("debug_results.png")
        
        # Check Results
        rows = driver.find_elements(By.CSS_SELECTOR, "#my-table-sorter tbody tr")
        print(f"📊 Rows found: {len(rows)}")
        if len(rows) > 0:
            print(f"Row 1 Text: {rows[0].text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        driver.save_screenshot("debug_error.png")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_imfl()
