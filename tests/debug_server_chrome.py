import sys
import os
import time
import shutil
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

def log_memory():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    print(f"   [MEM] Used: {mem.used/1024/1024:.1f}MB | Free: {mem.available/1024/1024:.1f}MB | Swap Used: {swap.used/1024/1024:.1f}MB")

def setup_driver():
    print("1. Configuring Chrome Options...")
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--dns-prefetch-disable")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.page_load_strategy = 'none' 
    chrome_options.add_argument("--remote-debugging-pipe")
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=0") # Debug verbosity
    
    # FORCE Shim
    binary_path = "/home/ubuntu/shim_chrome"
    if os.path.exists(binary_path):
        chrome_options.binary_location = binary_path
        print(f"2. Using Shim: {binary_path}")
    else:
        print("2. ⚠️ Shim NOT found!")
    
    # print("2. Trusting PATH for chrome binary...")
    # print(shutil.which("google-chrome"))
        
    print("3. Initializing WebDriver...")
    log_memory()
    try:
        # Check for system chromedriver first
        system_driver = shutil.which("chromedriver")
        if system_driver:
            print(f"3a. Using System Driver: {system_driver}")
            service = Service(executable_path=system_driver, log_output="chromedriver.log", service_args=["--verbose"])
        else:
            print("3a. System driver not found, using generic Service()")
            service = Service(log_output="chromedriver.log", service_args=["--verbose"])
            
        driver = webdriver.Chrome(service=service, options=chrome_options)
        print("4. WebDriver Started Successfully!")
        log_memory()
        return driver
    except Exception as e:
        print(f"❌ WebDriver Init Failed: {e}")
        log_memory()
        raise e

if __name__ == "__main__":
    print("--- STARTING ISOLATED SERVER DEBUG ---")
    driver = None
    try:
        driver = setup_driver()
        
        target_url = "https://www.google.com"
        print(f"5. Navigating to {target_url}...")
        driver.get(target_url)
        
        print("6. Waiting 5s for render (Strategy 'none')...")
        time.sleep(5)
        
        title = driver.title
        print(f"7. Page Title: '{title}'")
        
        screenshot_path = "debug_server_screenshot.png"
        driver.save_screenshot(screenshot_path)
        print(f"8. Screenshot saved to {screenshot_path}")
        
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
    finally:
        if driver:
            driver.quit()
        print("--- END DEBUG ---")
