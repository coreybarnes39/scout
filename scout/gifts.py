"""Small, explicit gift watchlists with live public structured-price checks."""
import hashlib
import json
import math
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser
import requests

AGENT = 'ScoutPersonalMonitor/0.4 (personal gift research)'


class Scripts(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.active, self.parts, self.scripts = False, [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type') == 'application/ld+json':
            self.active, self.parts = True, []

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.scripts.append(''.join(self.parts))
            self.active = False


def product_offer(html, expected_name):
    """Require an exact product name and a single USD Offer, not a from-price."""
    expected = ' '.join(expected_name.casefold().split())
    for script in Scripts(html).scripts:
        try:
            queue = [json.loads(script)]
        except ValueError:
            continue
        while queue:
            node = queue.pop()
            if isinstance(node, list):
                queue.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            graph = node.get('@graph', [])
            if isinstance(graph, (list, dict)):
                queue.append(graph)
            kinds = node.get('@type', [])
            if isinstance(kinds, str):
                kinds = [kinds]
            if 'Product' not in kinds or ' '.join(str(node.get('name', '')).casefold().split()) != expected:
                continue
            offers = node.get('offers', [])
            offers = [offers] if isinstance(offers, dict) else offers
            if (not isinstance(offers, list) or len(offers) != 1
                    or not isinstance(offers[0], dict) or offers[0].get('@type') != 'Offer'):
                continue
            offer = offers[0]
            try:
                price = float(offer['price'])
            except (KeyError, TypeError, ValueError):
                continue
            if not math.isfinite(price) or price <= 0 or offer.get('priceCurrency') != 'USD':
                continue
            availability = str(offer.get('availability', '')).rstrip('/').rsplit('/', 1)[-1]
            if availability != 'InStock':
                continue
            return price
    return None


def collect_gifts(source):
    robots = {}
    for candidate in source.get('products', []):
        item = dict(candidate)
        url = item['url']
        item.update(id=hashlib.sha256(url.encode()).hexdigest()[:20],
                    source=source['name'], price=None, currency='USD',
                    available=False, description=item.get('why', ''),
                    checked_at=datetime.now(timezone.utc).isoformat(timespec='seconds'))
        item['review_reason'] = item.get('review_reason', 'Price/stock needs verification')
        # Gift subscriptions require full term, renewal and delivery checks;
        # never treat a monthly headline or a configurable plan as a total.
        if item.get('subscription') or item.get('experience') or candidate.get('review_reason'):
            yield item
            continue
        try:
            parts = urlsplit(url)
            if parts.scheme != 'https':
                raise ValueError('HTTPS required')
            origin = f'{parts.scheme}://{parts.netloc}'
            if origin not in robots:
                response = requests.get(origin + '/robots.txt', headers={'User-Agent': AGENT}, timeout=15)
                response.raise_for_status()
                robot = RobotFileParser()
                robot.parse(response.text.splitlines())
                robots[origin] = robot
            if not robots[origin].can_fetch(AGENT, url):
                raise ValueError('Public fetch disallowed by robots.txt')
            response = requests.get(url, headers={'User-Agent': AGENT}, timeout=20)
            response.raise_for_status()
            if urlsplit(response.url).netloc != parts.netloc:
                raise ValueError('Redirected to another retailer')
            price = product_offer(response.text, item['title'])
            if price is not None:
                item.update(price=price, available=True)
                item['review_reason'] = ''
        except (requests.RequestException, ValueError) as exc:
            item['review_reason'] = str(exc)
        yield item


GIFT_CATEGORIES = {
    'dad_lego': 'Star Wars LEGO',
    'dad_classic_rock': 'Classic rock',
    'mom_aerogarden': 'AeroGarden & indoor gardening',
    'parents_plants': 'Plant accessories',
    'parents_food': 'Food subscriptions',
    'parents_experiences': 'Experiences & tickets',
}
GIFT_HEADERS = ['Category', 'Gift', 'For', 'Status', 'Price (USD)',
                'Why it fits', 'Checks before buying', 'Retailer', 'Link',
                'Last checked', 'Review reason']


def write_gifts(sheet, batches, replace_all=True):
    """Publish one consolidated tab per parent after collecting every category.

    Shared ideas appear in both tabs. Partial runs replace only their categories.
    Empty output never creates a sheet; existing output is cleared to remove stale rows.
    """
    import gspread
    doc = sheet.spreadsheet
    incoming = {'Mom': [], 'Dad': []}
    categories = {'Mom': set(), 'Dad': set()}
    for profile, listings, review in batches:
        recipient = profile['recipient']
        targets = ['Mom', 'Dad'] if recipient == 'Shared' else [recipient]
        category = GIFT_CATEGORIES.get(profile['name'], profile['name'].replace('_', ' ').title())
        for target in targets:
            categories[target].add(category)
            for status, items in [('Price/stock checked', listings), ('Needs review', review)]:
                incoming[target].extend([[category, item['title'],
                    'Both parents' if recipient == 'Shared' else recipient, status,
                    item.get('price') if item.get('price') is not None else 'Unverified',
                    item.get('why', ''), item.get('checks', ''), item['source'],
                    item['url'], item.get('checked_at', ''), item.get('review_reason', '')]
                    for item in items])
    wrote_output = False
    for parent in ['Mom', 'Dad']:
        if not categories[parent]:
            continue
        title = f'{parent} Christmas gifts'
        try:
            tab = doc.worksheet(title)
        except gspread.WorksheetNotFound:
            if not incoming[parent]:
                continue
            tab = doc.add_worksheet(title=title, rows=max(100, len(incoming[parent]) + 1),
                                    cols=len(GIFT_HEADERS))
        else:
            if not replace_all:
                old = tab.get_all_records()
                # Keep other categories during a single-profile run.
                incoming[parent] = [[row.get(h, '') for h in GIFT_HEADERS]
                    for row in old if row.get('Category') not in categories[parent]] + incoming[parent]
        rows = sorted(incoming[parent], key=lambda row: (row[0], row[3] != 'Price/stock checked', row[1]))
        tab.resize(rows=max(100, len(rows) + 1), cols=len(GIFT_HEADERS))
        tab.clear()
        tab.update(range_name=f'A1:K{len(rows) + 1}', values=[GIFT_HEADERS] + rows,
                   value_input_option='RAW')
        wrote_output = True
    # Retain earlier generated data but hide obsolete category/review tabs.
    # Only do this after a consolidated tab has been successfully written.
    if wrote_output:
        legacy = {prefix + profile['name'] for prefix in ['Gift shortlist ', 'Gift review ']
                  for profile, _, _ in batches}
        for tab in doc.worksheets():
            if tab.title in legacy:
                tab.hide()
