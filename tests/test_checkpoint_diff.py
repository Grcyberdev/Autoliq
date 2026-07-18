import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import automation_utils

def test_checkpoint_lookups():
    print("🧪 Running Checkpoint Lookups Test...")
    
    # 1. Mock checkpoint with raw date keys (like the actual code saves them)
    checkpoint = {
        "18-Jul-2026": {
            "AS01MC3440": {
                "Bacardi Limon Rum": {
                    "NN": 15,
                    "PP": 5
                },
                "_TelegramSupplier": "Bacardi India"
            }
        }
    }

    # Test 1A: Direct raw match
    details = automation_utils.get_checkpoint_details(checkpoint, "18-Jul-2026", "AS01MC3440")
    assert "Bacardi Limon Rum" in details, "Failed raw direct match"
    assert details["Bacardi Limon Rum"]["NN"] == 15
    print("✅ Test 1A (Direct raw match) passed!")

    # Test 1B: Normalized date lookup (the bug case)
    details_normalized = automation_utils.get_checkpoint_details(checkpoint, "2026-07-18", "AS01MC3440")
    assert "Bacardi Limon Rum" in details_normalized, "Failed normalized date lookup match"
    assert details_normalized["Bacardi Limon Rum"]["NN"] == 15
    print("✅ Test 1B (Normalized date lookup) passed!")

    # 2. Mock checkpoint with normalized ISO keys (testing the reverse)
    checkpoint_iso = {
        "2026-07-18": {
            "AS01MC3440": {
                "Bacardi Limon Rum": {
                    "NN": 15
                }
            }
        }
    }

    # Test 2: Raw date lookup in ISO checkpoint
    details_iso = automation_utils.get_checkpoint_details(checkpoint_iso, "18-Jul-2026", "AS01MC3440")
    assert "Bacardi Limon Rum" in details_iso, "Failed raw date lookup in ISO checkpoint"
    assert details_iso["Bacardi Limon Rum"]["NN"] == 15
    print("✅ Test 2 (Raw date lookup in ISO checkpoint) passed!")

    # 3. Test subtraction logic with the new lookup
    old_checkpoint = {
        "18-Jul-2026": {
            "AS01MC3440": {
                "Bacardi Limon Rum": {
                    "NN": 15,
                    "PP": 5
                }
            }
        }
    }
    
    new_checkpoint = {
        "18-Jul-2026": {
            "AS01MC3440": {
                "Bacardi Limon Rum": {
                    "NN": 15,
                    "PP": 7 # 2 new cases of Half (PP)
                }
            }
        }
    }

    # Simulating main logic lookup
    new_details = automation_utils.get_checkpoint_details(new_checkpoint, "2026-07-18", "AS01MC3440")
    old_details = automation_utils.get_checkpoint_details(old_checkpoint, "2026-07-18", "AS01MC3440")

    diff = automation_utils.subtract_checkpoint_details(new_details, old_details)
    assert "Bacardi Limon Rum" in diff, "Failed diff brand check"
    assert diff["Bacardi Limon Rum"].get("PP") == 2, "Failed diff quantity check"
    assert "NN" not in diff["Bacardi Limon Rum"], "Old unchanged quantities should not be in diff"
    print("✅ Test 3 (Subtraction diffing integration) passed!")

    print("🎉 All checkpoint lookup tests passed successfully!")

if __name__ == "__main__":
    test_checkpoint_lookups()
