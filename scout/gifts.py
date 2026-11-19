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
        if item.get('subscription') or candidate.get('review_reason'):
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


def write_gifts(sheet, profile, listings, review):
    """Gift columns instead of cycling drivetrain/HSA fields; no emails."""
    headers = ['gift', 'recipient', 'price_USD', 'why', 'checks_before_buying',
               'retailer', 'link', 'checked_at', 'review_reason']
    for prefix, items in [('Gift shortlist ', listings), ('Gift review ', review)]:
        title = (prefix + profile['name'])[:100]
        doc = sheet.spreadsheet
        import gspread
        try:
            tab = doc.worksheet(title)
        except gspread.WorksheetNotFound:
            tab = doc.add_worksheet(title=title, rows=100, cols=len(headers))
        rows = [headers] + [[i['title'], profile['recipient'],
                i.get('price') if i.get('price') is not None else 'Unverified',
                i.get('why', ''), i.get('checks', ''), i['source'], i['url'],
                i.get('checked_at', ''), i.get('review_reason', '')] for i in items]
        tab.clear()
        tab.update(range_name=f'A1:I{len(rows)}', values=rows, value_input_option='RAW')
