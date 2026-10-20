"""Reusable public-feed collectors; only fetch publicly exposed HTTPS resources."""
import hashlib
import logging
from urllib.parse import urlparse, urlencode
import requests
import feedparser

log = logging.getLogger(__name__)
HEADERS = {'User-Agent': 'ScoutPersonalMonitor/0.3 (personal product research)'}

def _id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:20]

def collect(source):
    kind = source['type']
    if kind == 'shopify':
        base = source['base_url'].rstrip('/')
        if urlparse(base).scheme != 'https':
            raise ValueError('Only HTTPS sources supported')
        collection = source.get('collection', 'all')
        max_pages = max(1, min(int(source.get('max_pages', 4)), 20))
        for page in range(1, max_pages + 1):
            url = f'{base}/collections/{collection}/products.json?' + urlencode({'limit': 250, 'page': page})
            response = requests.get(url, headers=HEADERS, timeout=30)
            log.info('Source=%s URL=%s HTTP=%s', source['name'], url, response.status_code)
            response.raise_for_status()
            products = response.json().get('products', [])
            log.info('Source=%s page=%s products=%s', source['name'], page, len(products))
            for product in products:
                for variant in product.get('variants') or []:
                    link = f"{base}/products/{product.get('handle', '')}?variant={variant.get('id', '')}"
                    try:
                        price = float(variant.get('price'))
                    except (ValueError, TypeError):
                        continue
                    yield {'id': _id(link), 'source': source['name'],
                           'title': ' '.join([product.get('title', ''), variant.get('title', '')]).strip(),
                           'variant_title': variant.get('title', ''),
                           'description': product.get('body_html', '') or '',
                           'url': link, 'price': price, 'currency': 'USD',
                           'available': variant.get('available', True)}
            if len(products) < 250:
                break
    elif kind == 'sitemap_products':
        yield from _structured_products(source)
    elif kind == 'rss':
        url = source['url']
        if urlparse(url).scheme != 'https':
            raise ValueError('Only HTTPS sources supported')
        response = requests.get(url, headers=HEADERS, timeout=30)
        log.info('Source=%s URL=%s HTTP=%s', source['name'], url, response.status_code)
        response.raise_for_status()
        entries = feedparser.parse(response.content).entries
        log.info('Source=%s entries=%s', source['name'], len(entries))
        for entry in entries:
            link = entry.get('link', '')
            if not link.startswith('https://'):
                continue
            yield {'id': _id(link), 'source': source['name'], 'title': entry.get('title', ''),
                   'description': entry.get('summary', ''), 'url': link,
                   'price': None, 'currency': 'USD', 'available': True}
    else:
        raise ValueError(f'Unsupported connector: {kind}')

def _structured_products(source):
    """Bounded sitemap discovery + JSON-LD Product parsing (no login/bypass)."""
    import json
    import re
    import time
    import xml.etree.ElementTree as ET
    from html.parser import HTMLParser
    from urllib.parse import urljoin
    from urllib.robotparser import RobotFileParser

    class Scripts(HTMLParser):
        def __init__(self):
            super().__init__()
            self.inside = False
            self.parts = []
            self.scripts = []
        def handle_starttag(self, tag, attrs):
            if tag == 'script' and 'ld+json' in dict(attrs).get('type', '').lower():
                self.inside = True
                self.parts = []
        def handle_data(self, data):
            if self.inside:
                self.parts.append(data)
        def handle_endtag(self, tag):
            if tag == 'script' and self.inside:
                self.scripts.append(''.join(self.parts))
                self.inside = False

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.hrefs = []
        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                href = dict(attrs).get('href')
                if href:
                    self.hrefs.append(href)

    base = source['base_url'].rstrip('/')
    if urlparse(base).scheme != 'https':
        raise ValueError('Only HTTPS sources supported')
    robot = RobotFileParser()
    robot.set_url(base + '/robots.txt')
    try:
        robot.read()
    except Exception as exc:
        log.warning('Source=%s robots unavailable: %s', source['name'], exc)
        return
    agent = HEADERS['User-Agent']
    def allowed(url):
        parsed = urlparse(url)
        return parsed.scheme == 'https' and parsed.netloc == urlparse(base).netloc and robot.can_fetch(agent, url)
    def fetch(url):
        if not allowed(url):
            return None
        response = requests.get(url, headers=HEADERS, timeout=12)
        log.info('Source=%s URL=%s HTTP=%s', source['name'], url, response.status_code)
        response.raise_for_status()
        return response

    pending = [urljoin(base + '/', source.get('sitemap', '/sitemap.xml'))]
    urls = []
    checked = set()
    max_sitemaps = min(6, max(1, int(source.get('max_sitemaps', 3))))
    while pending and len(checked) < max_sitemaps:
        sitemap = pending.pop(0)
        if sitemap in checked:
            continue
        checked.add(sitemap)
        try:
            response = fetch(sitemap)
            if response is None:
                continue
            root = ET.fromstring(response.content)
            locations = [e.text.strip() for e in root.iter()
                         if e.tag.endswith('loc') and e.text]
            if root.tag.endswith('sitemapindex'):
                product_maps = [u for u in locations if re.search(
                    r'product|bike|catalog', u, re.I)]
                pending.extend(product_maps or locations[:max_sitemaps])
            else:
                urls.extend(u for u in locations if re.search(
                    source.get('product_url_pattern', r'product|bike'), u, re.I))
        except (requests.RequestException, ET.ParseError) as exc:
            log.warning('Source=%s sitemap failed: %s', source['name'], exc)

    # Category landing pages can expose product links even when XML sitemaps
    # are unavailable or use opaque identifiers. Follow one extra category
    # level, subject to robots rules and a strict request budget.
    pattern = re.compile(source.get('product_url_pattern', r'product|bike'), re.I)
    categories = source.get('category_urls', [])[:5]
    category_pages = []
    for category in categories:
        category_url = urljoin(base + '/', category)
        if not allowed(category_url):
            log.info('Source=%s category blocked by robots: %s', source['name'], category_url)
            continue
        category_pages.append(category_url)
    discovered = []
    for category_url in category_pages:
        try:
            response = fetch(category_url)
            if response is None:
                continue
            parser = Links()
            parser.feed(response.text)
            for href in parser.hrefs:
                target = urljoin(category_url, href)
                if pattern.search(urlparse(target).path) and allowed(target):
                    discovered.append(target.split('#')[0].split('?')[0])
        except (requests.RequestException, ValueError) as exc:
            log.warning('Source=%s category failed: %s', source['name'], exc)
    log.info('Source=%s category_candidates=%s pages=%s',
             source['name'], len(set(discovered)), len(category_pages))
    max_products = min(30, max(1, int(source.get('max_products', 12))))
    candidates = list(dict.fromkeys(discovered + urls))[:max_products]
    log.info('Source=%s sitemap_candidates=%s checked=%s', source['name'],
             len(candidates), len(checked))
    for url in candidates:
        try:
            response = fetch(url)
            if response is None:
                continue
            parser = Scripts()
            parser.feed(response.text)
            for script in parser.scripts:
                try:
                    payload = json.loads(script)
                except (ValueError, TypeError):
                    continue
                queue = payload if isinstance(payload, list) else [payload]
                while queue:
                    node = queue.pop()
                    if isinstance(node, list):
                        queue.extend(node)
                        continue
                    if not isinstance(node, dict):
                        continue
                    queue.extend(node.get('@graph', []) if isinstance(node.get('@graph'), list) else [])
                    kind = node.get('@type', [])
                    kinds = kind if isinstance(kind, list) else [kind]
                    if 'Product' not in kinds:
                        continue
                    offers = node.get('offers', [])
                    if isinstance(offers, dict):
                        offers = [offers]
                    for offer in offers:
                        if not isinstance(offer, dict):
                            continue
                        try:
                            price = float(offer.get('price'))
                        except (ValueError, TypeError):
                            continue
                        title = str(node.get('name') or '')
                        description = str(node.get('description') or '')
                        offer_url = offer.get('url') or url
                        if not isinstance(offer_url, str) or not offer_url.startswith('https://'):
                            offer_url = url
                        yield {'id': _id(offer_url), 'source': source['name'],
                               'title': title, 'variant_title': '',
                               'description': description, 'url': offer_url,
                               'price': price, 'currency': offer.get('priceCurrency', 'USD'),
                               'available': 'OutOfStock' not in str(offer.get('availability', ''))}
            time.sleep(0.25)
        except (requests.RequestException, ValueError) as exc:
            log.warning('Source=%s product failed: %s', source['name'], exc)
