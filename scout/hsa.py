"""Check published retailer evidence; never infer personal medical approval."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit
import requests
from .connectors import HEADERS, collect


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.words = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.extend(v for k, v in attrs if k == 'href')

    def handle_data(self, data):
        self.words.append(data)


def product_key(url):
    parts = urlsplit(url)
    return parts.netloc.lower(), parts.path.rstrip('/')


def load_evidence(source):
    """Fetch once per retailer per run. Missing or failed checks fail closed."""
    config = source.get('hsa_evidence', {})
    url = config.get('url', '')
    if not url.startswith('https://'):
        return {}
    if config.get('kind') == 'collection':
        products = {product_key(item['url']) for item in collect({
            **source, 'type': 'shopify', 'collection': config['collection'],
            'max_pages': 20})}
        return {'kind': 'product_links', 'url': url, 'products': products,
                'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    if urlsplit(response.url).netloc != urlsplit(url).netloc:
        return {}
    html = response.text
    section = config.get('section')
    if section:
        # Restrict links to the eligible-products section, excluding navigation.
        position = html.lower().find(section.lower())
        if position < 0:
            return {}
        html = html[position:]
        html = re.split(r'<footer\b', html, maxsplit=1, flags=re.I)[0]
    page = Page(html)
    text = ' '.join(' '.join(page.words).lower().split())
    phrase = config.get('required_text', '').lower()
    if phrase and phrase not in text:
        return {}
    return {'kind': config.get('kind'), 'url': url,
            'products': {product_key(urljoin(url, link)) for link in page.links},
            'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}


def apply_evidence(item, source, evidence):
    for field in ('hsa_evidence_url', 'hsa_checked_at'):
        item.pop(field, None)
    item['hsa_verified'] = False
    item['hsa_status'] = 'Unverified'
    same_store = urlsplit(item['url']).netloc == urlsplit(source.get('base_url', '')).netloc
    linked = product_key(item['url']) in evidence.get('products', set())
    # Only an explicit bicycle product type can use an all-bicycles policy.
    bike = bool(re.fullmatch(r'(?:bikes?|bicycles?|gravel bikes?|road bikes?)',
                             item.get('product_type', '').strip(), re.I))
    verified = same_store and (linked if evidence.get('kind') == 'product_links'
                               else bike if evidence.get('kind') == 'all_bicycles' else False)
    if verified:
        item.update(hsa_verified=True, hsa_evidence_url=evidence['url'],
                    hsa_checked_at=evidence['checked_at'],
                    hsa_status='HSA pathway verifiedâ€”personal qualification required')
