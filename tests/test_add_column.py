import os
import sys
import gspread
from google.oauth2.service_account import Credentials
import time

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
# Assume credentials exist for this test

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)

spreadsheet = gc.open(SPREADSHEET_NAME)
sheet = spreadsheet.worksheet(WORKSHEET_NAME)

print(f"Original Cols: {sheet.col_count}")
print(f"Original Headers: {sheet.row_values(1)}")

# Simulate adding a new column
headers = sheet.row_values(1)
new_col_index = len(headers) + 1

if new_col_index > sheet.col_count:
    print(f"Adding column because {new_col_index} > {sheet.col_count}")
    sheet.add_cols(1)
    print("Column added.")
else:
    print("No need to add column in this test run (maybe already added).")

# Verify
sheet = spreadsheet.worksheet(WORKSHEET_NAME) # Reload
print(f"New Cols: {sheet.col_count}")

# Optional: Add dummy header if we just created a column space
if new_col_index <= sheet.col_count:
     # Write a dummy header to verify write access
     test_header = "TEST_COL"
     sheet.update_cell(1, new_col_index, test_header)
     print(f"Written '{test_header}' to column {new_col_index}")
     
     time.sleep(2)
     
     # Clean up
     sheet.update_cell(1, new_col_index, "")
     print(f"Cleaned up column {new_col_index}")

