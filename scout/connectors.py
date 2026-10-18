"""Public-feed collectors. Respect site terms and rate limits; no login bypass."""
import hashlib
import time
from urllib.parse import urlparse
import requests
import feedparser

HEADERS = {'User-Agent': 'ScoutPersonalMonitor/0.1 (personal product research)'}

def _id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:20]

def collect(source):
    kind = source['type']
    url = source['url']
    if not url.startswith('https://'):
        raise ValueError('Only HTTPS sources supported')
    if kind == 'shopify':
        # Must point to a publicly exposed Shopify products.json endpoint.
        result = requests.get(url, headers=HEADERS, timeout=20)
        result.raise_for_status()
        for product in result.json().get('products', []):
            variants = product.get('variants') or [{}]
            for variant in variants:
                path = product.get('handle', '')
                base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                link = f'{base}/products/{path}'
                if variant.get('id'):
                    link += f"?variant={variant['id']}"
                price = variant.get('price')
                try: price = float(price)
                except (ValueError, TypeError): continue
                title = ' '.join([product.get('title', ''), variant.get('title', '')]).strip()
                yield {'id': _id(link), 'source': source['name'], 'title': title,
                       'description': product.get('body_html', '') or '',
                       'url': link, 'price': price, 'currency': 'USD',
                       'available': variant.get('available', True)}
    elif kind == 'rss':
        result = requests.get(url, headers=HEADERS, timeout=20)
        result.raise_for_status()
        feed = feedparser.parse(result.content)
        for entry in feed.entries:
            link = entry.get('link', '')
            if not link.startswith('https://'): continue
            yield {'id': _id(link), 'source': source['name'],
                   'title': entry.get('title', ''),
                   'description': entry.get('summary', ''), 'url': link,
                   'price': None, 'currency': 'USD', 'available': True}
    else:
        raise ValueError(f'Unsupported connector: {kind}')
