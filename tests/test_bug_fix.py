import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import automation_utils
import json
from datetime import datetime

# Fake checkpoint data for our test case (simulating the NEW behavior where clean_base_name is the key)
incoming_checkpoint = {
    "2026-03-13": {
        "HR55AC5070": {
            "Kingfisher": {
                "Can": 1400
            },
            "_TelegramSupplier": "Aether"
        }
    }
}

# Fake row that would be passed to generating logic
final_data_to_send = [
    [
        "13-Mar-2026", # DateofEndorsement
        "Aether",      # Supplier
        "HR55AC5070",  # TruckNumber
        "Kingfisher Can", # LiqourTypes
        "1400",        # TotalQuantity
        "Aether"       # TelegramSupplier
    ]
]

final_header = f"Liqour Endorsements - {datetime.now().strftime('%d-%b-%Y')} (Cumulative)"

summary_text = automation_utils.generate_whatsapp_reports(final_data_to_send, incoming_checkpoint, final_header)
print(summary_text)
