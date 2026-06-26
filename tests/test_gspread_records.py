import sys, os
import gspread
from google.oauth2.service_account import Credentials
SERVICE_ACCOUNT_FILE = "./keys/liquorbond-service.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
spreadsheet = gc.open("Liqour Stock Data")
sheet = spreadsheet.worksheet("Truck Endorsements")
headers = sheet.row_values(1)
print("HEADERS:", headers)
records = sheet.get_all_records()
print("RECORDS COUNT:", len(records))
if len(records) > 0:
    print("FIRST RECORD:", records[0])
    print("SECOND RECORD:", records[1])
