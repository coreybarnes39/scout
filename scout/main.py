import argparse
import glob
import os
import smtplib
import time
from email.message import EmailMessage
import yaml
from .connectors import collect
from .scoring import score
from .storage import open_sheet, save

def send_email(alerts):
    if not alerts or not all(os.getenv(k) for k in ['SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'ALERT_TO']): return
    msg = EmailMessage()
    msg['Subject'] = f'Scout: {len(alerts)} new matches or price drops'
    msg['From'] = os.environ['SMTP_USER']
    msg['To'] = os.environ['ALERT_TO']
    msg.set_content('\n\n'.join(f"{a['status']} | {a['title']} | ${a['price']:.2f} | {a['score']}/100\n{a['url']}" for a in alerts))
    with smtplib.SMTP_SSL(os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT', '465')), timeout=30) as server:
        server.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
        server.send_message(msg)

def run(profile_filter=None, dry_run=False):
    sheet = None if dry_run else open_sheet()
    for path in sorted(glob.glob('profiles/*.yaml')):
        with open(path) as f: profile = yaml.safe_load(f)
        if not profile.get('enabled') or (profile_filter and profile['name'] != profile_filter): continue
        found = {}
        for source in profile.get('sources', []):
            try:
                for item in collect(source):
                    result = score(item, profile)
                    if result is None: continue
                    item['score'], item['signals'] = result
                    if item['score'] >= profile.get('alerts', {}).get('min_score', 0): found[item['id']] = item
            except Exception as exc:
                print(f"Source {source['name']} failed: {exc}")
            time.sleep(1)
        items = list(found.values())
        print(f"{profile['name']}: {len(items)} qualifying listings")
        if dry_run:
            for item in items[:20]: print(f"{item['score']:3} ${item['price']:8.2f} {item['title'][:80]} {item['url']}")
        else:
            alerts = save(sheet, profile['name'], items, profile.get('alerts', {}).get('price_drop_pct', 10))
            send_email(alerts)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    run(args.profile, args.dry_run)
