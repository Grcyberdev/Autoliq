import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import automation_utils
import liquor_data

def test_is_plate_typo():
    print("🧪 Testing is_plate_typo...")
    assert automation_utils.is_plate_typo("AS03CC8606", "AS03CC3606") == True, "Should match 8 vs 3 typo"
    assert automation_utils.is_plate_typo("AS01FC3369", "AS01FC3369") == True, "Should match identical"
    assert automation_utils.is_plate_typo("AS01FC3369", "AS01PC3369") == True, "Should match 1 char diff"
    assert automation_utils.is_plate_typo("AS01DD3587", "AS18C7825") == False, "Should not match different trucks"
    assert automation_utils.is_plate_typo("AS18C7825", "AS18CC7825") == True, "Should match 1 char insertion/deletion"
    print("✅ is_plate_typo tests passed!")

def test_find_fuzzy_truck_match():
    print("🧪 Testing find_fuzzy_truck_match...")
    existing_data = {
        "2026-09-30|AS03CC3606": {
            'row': 14,
            'quantity': 167,
            'liquor': 'Bacardi Mango Chilli, Breezer Blackberry',
            'truck': 'AS03CC3606',
            'supplier': 'Bacardi',
            'date': '2026-09-30'
        },
        "2026-09-30|AS01FC3369": {
            'row': 2,
            'quantity': 1400,
            'liquor': 'Kingfisher Original Strong Bottle',
            'truck': 'AS01FC3369',
            'supplier': 'Sunit',
            'date': '2026-09-30'
        }
    }

    # Case 1: Matching AS03CC8606 to AS03CC3606 because AS03CC3606 is not in scraped set
    scraped_on_date = {"AS03CC8606", "AS01FC3369"}
    matched_key, matched_entry = automation_utils.find_fuzzy_truck_match(
        date_val="2026-09-30",
        supplier_name="Bacardi India Pvt. Ltd.",
        clean_truck="AS03CC8606",
        existing_data=existing_data,
        scraped_trucks_on_date=scraped_on_date
    )
    assert matched_key == "2026-09-30|AS03CC3606", f"Expected match with AS03CC3606, got {matched_key}"
    assert matched_entry['row'] == 14
    assert matched_entry['quantity'] == 167
    print("✅ Case 1: Successfully matched AS03CC8606 to existing AS03CC3606 row!")

    # Case 2: Should NOT match if the candidate truck is also currently scraped
    scraped_with_both = {"AS03CC8606", "AS03CC3606", "AS01FC3369"}
    matched_key2, matched_entry2 = automation_utils.find_fuzzy_truck_match(
        date_val="2026-09-30",
        supplier_name="Bacardi India Pvt. Ltd.",
        clean_truck="AS03CC8606",
        existing_data=existing_data,
        scraped_trucks_on_date=scraped_with_both
    )
    assert matched_key2 is None, "Should not match when candidate is a distinct active truck on portal"
    print("✅ Case 2: Correctly avoided matching when candidate is active on portal!")

    # Case 3: Should NOT match if supplier is different
    matched_key3, matched_entry3 = automation_utils.find_fuzzy_truck_match(
        date_val="2026-09-30",
        supplier_name="Pernod Ricard",
        clean_truck="AS03CC8606",
        existing_data=existing_data,
        scraped_trucks_on_date=scraped_on_date
    )
    assert matched_key3 is None, "Should not match when supplier differs"
    print("✅ Case 3: Correctly rejected match when supplier differs!")

def test_telegram_combined_message():
    print("🧪 Testing Telegram combined endorsement report generation...")
    # Simulate Bacardi 8-case addition combined with 167 cases truck
    diff_record = [
        "30-Sep-2026",
        "Bacardi",
        "AS03CC8606",
        "Camino Tequila, Dewar's White Label",
        "8",
        "Not Arrived",
        "",
        "",
        "Camino Tequila (Full: 3); Dewar's White Label (Full: 5)",
        "Bacardi India Pvt. Ltd."
    ]

    diff_checkpoint = {
        "30-Sep-2026": {
            "AS03CC8606": {
                "Camino Tequila": {"750ml": 3},
                "Dewar's White Label": {"750ml": 5},
                "_TelegramSupplier": "Bacardi India Pvt. Ltd."
            }
        }
    }

    combined_meta = {
        "is_combined": True,
        "previous_qty": 167,
        "total_qty": 175,
        "diff_qty": 8
    }

    combined_info_map = {
        "AS03CC8606": combined_meta
    }

    reports = automation_utils.generate_whatsapp_reports(
        [diff_record],
        diff_checkpoint,
        "New Liqour Endorsement",
        combined_info_map=combined_info_map
    )

    assert len(reports) == 1, "Should generate exactly 1 report"
    msg = reports[0]
    print("\n📬 Generated Combined Telegram Message:")
    print(msg)
    print("\n------------------------------------")

    # Assertions
    assert "(8 Cases - Combined)" in msg, "Header should mention (8 Cases - Combined)"
    assert "Camino Tequila" in msg and "Dewar's White Label" in msg, "Diff brands should be in header/body"
    assert "🚛 *Truck:* `AS03CC8606`" in msg, "Truck number mismatch"
    assert "📦 *Added Cases:* 8" in msg, "Should show Added Cases: 8"
    assert "🔗 *Combined Truck:* Added to previous 167 cases truck (Total: 175 cases)" in msg, "Combined truck notice missing"
    assert "Details (8 Cases):" in msg, "Details header should specify 8 Cases"
    assert "• *Camino Tequila*\n  ↳ Full (QQ): 3" in msg, "Tequila size and quantity breakdown mismatch"
    assert "• *Dewar's White Label*\n  ↳ Full (QQ): 5" in msg, "Dewar's size and quantity breakdown mismatch"
    assert "Breezer" not in msg, "Old 167-case Breezers must not appear in the 8-case report"

    print("✅ Telegram combined endorsement report passed with flying colors!")

if __name__ == "__main__":
    test_is_plate_typo()
    test_find_fuzzy_truck_match()
    test_telegram_combined_message()
    print("\n🎉 ALL TESTS PASSED!")
