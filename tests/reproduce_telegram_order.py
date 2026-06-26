
import sys
import os
from unittest.mock import MagicMock

# Mock dependencies BEFORE import
sys.modules["selenium"] = MagicMock()
sys.modules["selenium.webdriver"] = MagicMock()
sys.modules["selenium.webdriver.chrome.service"] = MagicMock()
sys.modules["selenium.webdriver.common.by"] = MagicMock()
sys.modules["webdriver_manager"] = MagicMock()
sys.modules["webdriver_manager.chrome"] = MagicMock()
sys.modules["requests"] = MagicMock()

# Mock PIL with submodules
mock_pil = MagicMock()
mock_pil.Image = MagicMock()
mock_pil.ImageOps = MagicMock()
mock_pil.ImageFilter = MagicMock()
sys.modules["PIL"] = mock_pil

sys.modules["pytesseract"] = MagicMock()

# Mock automation_utils
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import automation_utils

def test_report_ordering():
    print("🧪 Testing Telegram Report Ordering Logic")
    
    # Mock Data: 
    # Assume scraped data comes in as Newest -> Oldest (Index 0 is Newest)
    # [Date, Supplier, TruckNumber, LiquorTypes, Quantity, Status, DateArrived, DateCompleted]
    
    # Truck C (Newest) - Endorsed at 12:00
    # Truck B (Middle) - Endorsed at 11:00
    # Truck A (Oldest) - Endorsed at 10:00
    
    # If scraped/processed data is Newest First: [C, B, A]
    mock_data_newest_first = [
        ["2023-10-27", "Supplier C", "TRUCK-C-NEWEST", "Beer", 100, "Not Arrived", "", ""],
        ["2023-10-27", "Supplier B", "TRUCK-B-MIDDLE", "Whisky", 50, "Not Arrived", "", ""],
        ["2023-10-27", "Supplier A", "TRUCK-A-OLDEST", "Rum", 20, "Not Arrived", "", ""]
    ]
    
    mock_checkpoint = {} # No detailed data for simplicity
    header = "TEST REPORT"
    
    # Current Behavior: Processed in order of list
    print("\n--- Current Behavior (List as is: Newest -> Oldest) ---")
    report_current = automation_utils.generate_whatsapp_reports(mock_data_newest_first, mock_checkpoint, header)
    print(report_current)
    
    # Desired Behavior: We WANT the list to "expand naturally".
    print("\n--- Proposed Fix (Reversed List: Oldest -> Newest) ---")
    mock_data_reversed = list(reversed(mock_data_newest_first))
    report_fixed = automation_utils.generate_whatsapp_reports(mock_data_reversed, mock_checkpoint, header)
    print(report_fixed)
    
    # Verify
    lines = "\n".join(report_fixed).strip().split('\n')
    # Use loose matching because of blank lines
    # The last truck block should contain "Supplier C"
    
    expected_order = ["Supplier A", "Supplier B", "Supplier C"]
    found_order = []
    for line in lines:
        for supplier in expected_order:
            if supplier in line and supplier not in found_order:
                found_order.append(supplier)
    
    print("\nFound Order:", found_order)
    
    if found_order == expected_order:
         print("\n✅ SUCCESS: Order is Oldest -> Newest (A -> B -> C). Latest truck is at the bottom.")
    else:
         print(f"\n❌ FAILURE: Order mismatch. Found: {found_order}")

if __name__ == "__main__":
    test_report_ordering()
