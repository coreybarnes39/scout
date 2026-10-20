import argparse
import logging
from collections import Counter
import glob
import os
import smtplib
import time
from email.message import EmailMessage
import yaml
from .connectors import collect
from .scoring import score, rejection_reason
from .storage import open_sheet, save, write_top_results, write_diagnostics

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

def run(profile_filter=None, dry_run=False, debug=False):
    logging.basicConfig(level=logging.INFO if debug else logging.WARNING, format='[SCOUT] %(message)s')
    with open('sources/retailers.yaml') as f:
        registry = yaml.safe_load(f) or {}
    sheet = None if dry_run else open_sheet()
    for path in sorted(glob.glob('profiles/*.yaml')):
        with open(path) as f: profile = yaml.safe_load(f)
        if not profile.get('enabled') or (profile_filter and profile['name'] != profile_filter): continue
        found, reasons = {}, Counter()
        review, health = [], []
        review_by_source = {}
        for source_id in profile.get('sources', []):
            source = registry.get(source_id) if isinstance(source_id, str) else source_id
            if not source:
                print(f'[SCOUT] Unknown source: {source_id}')
                continue
            source = dict(source)
            source.setdefault('name', source_id if isinstance(source_id, str) else 'Unnamed source')
            source_reasons = Counter()
            source_error = ''
            try:
                for item in collect(source):
                    source_reasons['variants_seen'] += 1
                    if source.get('hsa_pathway'):
                        item['hsa_pathway'] = source['hsa_pathway']
                    reason = rejection_reason(item, profile)
                    if reason:
                        source_reasons[reason] += 1
                        if (profile.get('category') == 'cycling' and
                                reason == 'electronic_unverified' and
                                item.get('available', True) and
                                len(review_by_source.get(source['name'], [])) < 25):
                            item['review_reason'] = 'Electronic shifting not confirmed'
                            item['drivetrain'] = 'Unverified'
                            item['frame_size'] = 'Unverified'
                            review_by_source.setdefault(source['name'], []).append(item)
                        continue
                    result = score(item, profile)
                    if result is None:
                        source_reasons['other'] += 1
                        continue
                    item['score'], item['signals'] = result
                    if source.get('hsa_pathway'):
                        item['hsa_status'] = f"{source['hsa_pathway']} pathway; qualification required"
                    found[item['id']] = item
                    source_reasons['relevant'] += 1
            except Exception as exc:
                source_error = str(exc)
                print(f"[SCOUT] Source {source['name']} failed: {exc}")
            reasons.update(source_reasons)
            examined = source_reasons['variants_seen']
            qualified = source_reasons['relevant']
            review_count = len(review_by_source.get(source['name'], []))
            status = ('Connector Failed' if source_error else
                      'No Products Found' if not examined else
                      'Working' if qualified else
                      'Needs Verification' if review_count else 'No Matches')
            health.append({'source': source['name'], 'status': status,
                           'examined': examined, 'qualified': qualified,
                           'needs_review': review_count,
                           'rejections': str(dict(source_reasons)),
                           'error': source_error})
            print(f"[SCOUT] Retailer status: {source['name']} = {status} "
                  f"({examined} examined, {qualified} qualified, {review_count} review)")
            if debug:
                print(f"[SCOUT] {source['name']}: {dict(source_reasons)}")
            time.sleep(1)
        review = [item for batch in review_by_source.values() for item in batch]
        items = list(found.values())
        threshold = profile.get('alerts', {}).get('min_score', 0)
        print(f"{profile['name']}: {len(items)} relevant listings, {sum(i['score'] >= threshold for i in items)} above alert threshold")
        if debug:
            print(f'[SCOUT] Filter counts: {dict(reasons)}')
            for item in sorted(items, key=lambda x: -x['score'])[:15]:
                print(f"[SCOUT] {item['score']:3} ${item['price']:8.2f} {item['title'][:70]} {item['url']}")
        if dry_run:
            continue
        alerts = save(sheet, profile['name'], items, profile.get('alerts', {}).get('price_drop_pct', 10))
        if profile.get('category') == 'cycling':
            write_diagnostics(sheet, review, health)
        results_config = profile.get('results', {})
        if results_config.get('top_n'):
            selected = write_top_results(sheet, profile['name'], items,
                                         top_n=int(results_config['top_n']),
                                         deduplicate=results_config.get('deduplicate_models', True))
            print(f"[SCOUT] Updated Top 10 tab: {len(selected)} distinct bikes")
        send_email([a for a in alerts if a['score'] >= threshold])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()
    run(args.profile, args.dry_run, args.debug)
