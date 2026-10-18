"""Conservative rules: unknown product features never receive credit."""
import re
from html import unescape

def normalize(s):
    return re.sub(r'<[^>]+>', ' ', unescape(str(s or ''))).lower()

def rejection_reason(item, profile):
    text = normalize(item['title'] + ' ' + item.get('description', ''))
    filters = profile.get('filters', {})
    price = item.get('price')
    if not item.get('available', True): return 'unavailable'
    if price is None: return 'missing_price'
    if price > filters.get('max_price', float('inf')): return 'over_budget'
    if price < filters.get('min_price', 0): return 'under_minimum'
    if any(word.lower() in normalize(item['title']) for word in filters.get('excluded_any', [])): return 'excluded_keyword'
    if filters.get('required_any') and not any(word.lower() in text for word in filters['required_any']): return 'not_relevant'
    return None

def score(item, profile):
    text = normalize(item['title'] + ' ' + item.get('description', ''))
    filters = profile.get('filters', {})
    price = item.get('price')
    if rejection_reason(item, profile): return None
    if profile.get('category') == 'cycling':
        # Size is NOT a hard filter: ambiguous size descriptions need manual verification.
        signals = {
            'carbon': any(x in text for x in ['carbon', 'cf ', 'cfr ', 'sl 5', 'sl 6']),
            'size': bool(re.search(r'\b(52|53|54)\s*(cm)?\b|\bsize\s*m\b|\bmedium\b', normalize(item.get('variant_title') or item['title']))),
            'electronic': any(x in text for x in ['axs', 'di2', 'electronic shifting', 'etap']),
            'removable_battery': any(x in text for x in ['rival axs', 'force axs', 'red axs', 'sram axs']),
            'bikepacking': any(x in text for x in ['rack mount', 'fork mount', 'cargo mount', 'bikepacking', 'mounting points']),
            'endurance': any(x in text for x in ['endurance', 'relaxed geometry', 'upright']),
            'road_compatible': any(x in text for x in ['700c', 'road tire', 'road wheel']),
        }
    else:
        keywords = profile.get('keywords', [])
        signals = {'matching_keywords': any(k.lower() in text for k in keywords),
                   'discounted': any(k in text for k in ['sale', 'discount', 'clearance'])}
    weights = profile.get('weights', {})
    total = sum(max(0, v) for v in weights.values()) or 1
    points = sum(max(0, w) for k, w in weights.items() if signals.get(k))
    base_score = round(100 * points / total)
    penalty_config = profile.get("price_penalty", {})
    threshold = penalty_config.get("starts_above")
    if threshold is not None and price > threshold:
        import math
        step = max(1, penalty_config.get("points_per_500", 0))
        penalty = min(penalty_config.get("max_points", 10),
                      math.ceil((price - threshold) / 500) * step)
        base_score = max(0, base_score - penalty)
    return base_score, signals
