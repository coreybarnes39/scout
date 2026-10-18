import os
import json
from datetime import datetime, timezone
import gspread
from google.oauth2.service_account import Credentials

HEADERS = ['profile', 'id', 'source', 'title', 'url', 'price', 'currency', 'score', 'signals', 'first_seen', 'last_seen', 'previous_price', 'status']

def open_sheet():
    creds = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
    client = gspread.authorize(Credentials.from_service_account_info(creds, scopes=['https://www.googleapis.com/auth/spreadsheets']))
    doc = client.open_by_key(os.environ['GOOGLE_SHEET_ID'])
    try: sheet = doc.worksheet('Listings')
    except gspread.WorksheetNotFound: sheet = doc.add_worksheet(title='Listings', rows=1000, cols=len(HEADERS))
    if not sheet.row_values(1): sheet.append_row(HEADERS)
    return sheet

def save(sheet, profile, listings, price_drop_pct):
    existing = sheet.get_all_records()
    by_key = {(str(r['profile']), str(r['id'])): (idx + 2, r) for idx, r in enumerate(existing)}
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    alerts = []
    for item in listings:
        key = (profile, item['id'])
        old = by_key.get(key)
        prev = float(old[1]['price']) if old and old[1].get('price') not in ('', None) else None
        is_drop = prev is not None and prev > 0 and item['price'] <= prev * (1 - price_drop_pct / 100)
        status = 'NEW' if not old else 'PRICE DROP' if is_drop else 'SEEN'
        row = [profile, item['id'], item['source'], item['title'], item['url'], item['price'], item['currency'],
               item['score'], json.dumps(item['signals'], sort_keys=True), old[1]['first_seen'] if old else now,
               now, prev if prev is not None else '', status]
        if old: sheet.update(range_name=f'A{old[0]}:M{old[0]}', values=[row])
        else: sheet.append_row(row, value_input_option='RAW')
        if status != 'SEEN': alerts.append(item | {'status': status})
    return alerts
