import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials

print("Waking up Shayaar Bot...")

# 1. Load keys (and strip out any accidental invisible spaces!)
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
ADMIN_ID = int(os.environ['TELEGRAM_ADMIN_ID'].strip())
SHEET_ID = os.environ['SHEET_ID'].strip()
CREDS_DICT = json.loads(os.environ['GOOGLE_JSON'])

# 2. Connect to Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(CREDS_DICT, scope)
client = gspread.authorize(creds)

sheet_queue = client.open_by_key(SHEET_ID).worksheet("Queue")
sheet_config = client.open_by_key(SHEET_ID).worksheet("Config")

# 3. Read the Config sheet
try:
    cell = sheet_config.find("last_telegram_offset")
    last_offset = sheet_config.cell(cell.row, cell.col + 1).value
    last_offset = int(last_offset) if last_offset else 0
except:
    last_offset = 0

print(f"Checking for messages after offset: {last_offset}")

# 4. Check Telegram for new messages
url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_offset + 1}&timeout=10"
response = requests.get(url).json()

# -> NEW: Print exactly what Telegram says back so we can see it in the logs!
print("Telegram answered with:", json.dumps(response, indent=2))

updates = response.get("result", [])

if not updates:
    print("No new messages from Telegram.")
else:
    highest_offset = last_offset

    # 5. Process each message
    for update in updates:
        highest_offset = max(highest_offset, update['update_id'])
        
        if 'message' in update and 'text' in update['message']:
            user_id = update['message']['from']['id']
            text = update['message']['text']
            
            # 6. Security Check
            if user_id == ADMIN_ID:
                print(f"Authorized! Adding to sheet: {text}")
                sheet_queue.append_row([text, "PENDING", ""])
            else:
                print(f"Intruder alert! Ignored message from ID: {user_id}")

    # 7. Update offset
    if highest_offset > last_offset:
        try:
            sheet_config.update_cell(cell.row, cell.col + 1, highest_offset)
        except:
            # If the cell doesn't exist yet, just add it
            sheet_config.append_row(["last_telegram_offset", highest_offset])
        print("Updated the Config sheet with new offset.")

print("Finished successfully. Going back to sleep.")
