import sys, os
import gspread
from google.oauth2.service_account import Credentials
SERVICE_ACCOUNT_FILE = "./keys/liquorbond-service.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
spreadsheet = gc.open("Liqour Stock Data")
sheet = spreadsheet.worksheet("Truck Endorsements")
records = sheet.get_all_records()

from collections import Counter
keys = [f"{r.get('DateofEndorsement', '')}|{r.get('TruckNumber', '')}" for r in records]
counts = Counter(keys)
duplicates = {k: v for k, v in counts.items() if v > 1}
if duplicates:
    print("FOUND DUPLICATES:", duplicates)
else:
    print("NO DUPLICATES")
