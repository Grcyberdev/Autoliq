from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import sys

print("🔍 Starting Selenium Debug Test...")
print(f"   Python Version: {sys.version}")

options = webdriver.ChromeOptions()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--remote-debugging-port=9222")

print("   Attempting to launch Chrome...")
try:
    # Service() without args tries to find chromedriver on PATH
    # We will try the manager first as it's what the main script does mostly
    path = ChromeDriverManager().install()
    print(f"   ✅ Driver Path: {path}")
    
    service = Service(path)
    driver = webdriver.Chrome(service=service, options=options)
    
    print("   ✅ Browser Launched Successfully!")
    print(f"   Title: {driver.title}")
    driver.quit()
    print("   ✅ Driver Quit. Test PASSED.")

except Exception as e:
    print(f"   ❌ Test FAILED: {e}")
    import traceback
    traceback.print_exc()
