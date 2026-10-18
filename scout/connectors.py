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
