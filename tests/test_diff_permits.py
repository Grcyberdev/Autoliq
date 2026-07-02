import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import automation_utils
import copy

def run_test():
    print("🧪 Running unit test for permit diff extraction...")
    
    # 1. Mock checkpoints simulating 25-Jun-2026 endorsements
    # First permit was Budweiser Magnum (500 cases)
    old_incoming_checkpoint = {
        "2026-06-25": {
            "AS01DC2251": {
                "Budweiser Magnum": {
                    "Bottle": 500
                },
                "_TelegramSupplier": "Anheuser Busch Inbev India Limited"
            }
        }
    }
    
    # Second run scraped both Permit 1 (Budweiser Magnum: 500) and Permit 2 (Budweiser: 400, Corona: 60, Hoegaarden: 40)
    incoming_checkpoint = {
        "2026-06-25": {
            "AS01DC2251": {
                "Budweiser Magnum": {
                    "Bottle": 500
                },
                "Budweiser": {
                    "Bottle": 400
                },
                "Corona": {
                    "Pint": 60
                },
                "Hoegaarden Witbier": {
                    "Pint": 40
                },
                "_TelegramSupplier": "Anheuser Busch Inbev India Limited"
            }
        }
    }
    
    # 2. Subtract checkpoints for truck AS01DC2251
    date_val = "2026-06-25"
    truck_val = "AS01DC2251"
    
    diff_details = automation_utils.subtract_checkpoint_details(
        incoming_checkpoint.get(date_val, {}).get(truck_val, {}),
        old_incoming_checkpoint.get(date_val, {}).get(truck_val, {})
    )
    
    # Asserting correct subtraction
    print("  - Extracted Diff Details:")
    import pprint
    pprint.pprint(diff_details)
    
    assert "Budweiser Magnum" not in diff_details, "Old permit brand should be subtracted entirely"
    assert diff_details["Budweiser"] == {"Bottle": 400}, "Budweiser Bottle quantity mismatch"
    assert diff_details["Corona"] == {"Pint": 60}, "Corona Pint quantity mismatch"
    assert diff_details["Hoegaarden Witbier"] == {"Pint": 40}, "Hoegaarden Pint quantity mismatch"
    assert diff_details["_TelegramSupplier"] == "Anheuser Busch Inbev India Limited"
    print("✅ Checkpoint subtraction assertion passed!")
    
    # 3. Simulate report generation for the new permit
    # Scraped cumulative row: [Date, Supplier, TruckNumber, LiquorTypes, TotalQty, Status, ...]
    # Cumulative: 1000 cases. We want to send a message showing only the diff of 500 cases.
    r = ["25-Jun-2026", "Anheuser Busch Inbev India Limited", "AS01DC2251", "Budweiser Bottle, Corona, Hoegaarden Witbier", "1000", "Not Arrived", "", "", "", "Anheuser Busch Inbev India Limited"]
    
    # Diff quantity
    scraped_qty = int(r[4])
    existing_qty = 500
    diff_qty = scraped_qty - existing_qty
    
    diff_record = list(r)
    diff_record[4] = str(diff_qty)
    
    diff_checkpoint = {
        date_val: {
            truck_val: diff_details
        }
    }
    
    # Generate the report
    reports = automation_utils.generate_whatsapp_reports([diff_record], diff_checkpoint, "New Liqour Endorsement")
    
    print("\n📬 Generated Telegram Message for the Second Permit:")
    print(reports[0])
    
    # Assert message contents
    assert "*Anheuser Busch (500 Cases) - Budweiser, Corona, ...*" in reports[0], "Telegram message dynamic header mismatch"
    assert "📅 *Date:* 25-Jun-2026" in reports[0], "Date line layout mismatch"
    assert "🏢 *Supplier:* Anheuser Busch Inbev India Limited" in reports[0], "Full supplier name layout mismatch"
    assert "🚛 *Truck:* `AS01DC2251`" in reports[0], "Truck line layout mismatch"
    assert "📦 *Total Cases:* 500" in reports[0], "Total Cases line layout mismatch"
    assert "Budweiser" in reports[0] and "Corona" in reports[0] and "Hoegaarden Witbier" in reports[0], "Second permit brands missing"
    assert "Budweiser Magnum" not in reports[0], "Old permit brand should not be in the second permit report"
    print("\n✅ Report formatting assertion passed successfully!")

if __name__ == "__main__":
    run_test()
