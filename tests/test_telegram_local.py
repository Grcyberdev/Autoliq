import json
import requests
import urllib.parse
import os

# Load config
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config/config.json")

def load_config():
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def send_test_message():
    config = load_config()
    token = config.get("TELEGRAM_BOT_TOKEN")
    chat_id = config.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("❌ ERROR: Tokens missing in config.json")
        return

    print(f"🔹 Testing Telegram Bot...")
    print(f"   Token: {token[:5]}...{token[-5:]}")
    print(f"   Chat ID: {chat_id}")
    
    message = "🔔 TEST MESSAGE: Local Verification SUCCESS!"
    encoded_message = urllib.parse.quote(message)
    url = f"https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={encoded_message}&parse_mode=Markdown"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("✅ SUCCESS: Test message sent! Check your Telegram.")
        else:
            print(f"❌ FAILED: API Error {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ FAILED: Connection Error: {e}")

if __name__ == "__main__":
    send_test_message()
