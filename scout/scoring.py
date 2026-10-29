"""Conservative rules: unknown product features never receive credit."""
import re
from html import unescape
from .mounts import mounting_evidence

def normalize(s):
    return re.sub(r'<[^>]+>', ' ', unescape(str(s or ''))).lower()

def drivetrain(text):
    """Detect drivetrain on the specific listing; no inference from brand/model alone."""
    if re.search(r'\b(?:sram\s+)?(?:rival|force|red|apex)?\s*axs\b|\betap\b', text):
        return 'SRAM AXS'
    if re.search(r'\bdi2\b', text):
        return 'Shimano Di2'
    if re.search(r'\b(?:eps|super record wireless)\b', text):
        return 'Other electronic'
    return 'Unverified'

def variant_size(item):
    """Return an explicit size when the variant identifies one, otherwise None."""
    variant = normalize(item.get('variant_title', ''))
    if not variant or variant == 'default title':
        return None
    match = re.search(r'(?<!\d)(?:4[4-9]|5[0-9]|6[0-2])\s*(?:cm)?(?!\d)', variant)
    if match:
        return str(int(re.match(r'\d+', match.group()).group()))
    # Match isolated sizes, not arbitrary letters inside a color name.
    match = re.search(r'(?<![a-z])(?:xxs|xs|xxl|xl|small|medium|large|s|m|l)(?![a-z])', variant)
    if match:
        return {'small': 'S', 'medium': 'M', 'large': 'L'}.get(match.group(), match.group().upper())
    return None

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
    if profile.get('category') == 'cycling':
        electronic = filters.get('electronic_shifting', {})
        # Configurable OBED bikes may mention AXS/Di2 in the description even
        # when the selected variant has no specified drivetrain.
        drive_text = normalize(item['title']) if item.get('hsa_pathway') else text
        if electronic.get('required') and drivetrain(drive_text) == 'Unverified':
            return 'electronic_unverified'
        size_filter = filters.get('frame_sizes', {})
        if isinstance(size_filter, dict) and size_filter.get('required'):
            size = variant_size(item)
            accepted = {str(x).upper() for x in size_filter.get('accepted', [])}
            if size is not None and size.upper() not in accepted:
                return 'wrong_size'
            if size is None and not size_filter.get('include_unknown', True):
                return 'size_unverified'
        # HSA status must be verified independently. No retailer listing is
        # considered verified solely because it mentions HSA/FSA.
        hsa = filters.get('hsa', {})
        if hsa.get('required') and not item.get('hsa_verified'):
            return 'hsa_unverified'
    return None

def score(item, profile):
    text = normalize(item['title'] + ' ' + item.get('description', ''))
    filters = profile.get('filters', {})
    price = item.get('price')
    if rejection_reason(item, profile): return None
    if profile.get('category') == 'cycling':
        drive = drivetrain(normalize(item['title']) if item.get('hsa_pathway') else text)
        size = variant_size(item)
        accepted = {str(x).upper() for x in filters.get('frame_sizes', {}).get('accepted', ['52', '53', '54', 'S', 'M'])}
        # Each criterion is (weight, evidence-based quality in [0,1] or None).
        # None means unknown, NOT a negative. Use reviewed model records only when explicitly matched.
        # Fit 25, versatility 25, components 20, comfort 15, value 15.
        size_fit = (1.0 if size.upper() in accepted else 0.0) if size else None
        mounts, mounts_source = mounting_evidence(item)
        tires = 1.0 if any(x in text for x in ['tire clearance', 'tyre clearance', '700c', '650b', 'gravel tire', 'road tire']) else None
        # Electronic shifting is a hard requirement; don't award 25 points again.
        # AXS earns a modest preference for its removable batteries.
        components = 1.0 if drive == 'SRAM AXS' else 0.75 if drive == 'Shimano Di2' else 0.5 if drive != 'Unverified' else None
        comfort = 1.0 if any(x in text for x in ['endurance', 'relaxed geometry', 'upright', 'compliance', 'vibration damping', 'is ospeed', 'isospeed']) else None
        # Price is verified, but value relative to comparable components isn't.
        # Reward affordability modestly without pretending to know market value.
        value = 1.0 if price <= filters.get('preferred_max_price', 4000) else max(0.0, 1 - (price - filters.get('preferred_max_price', 4000)) / max(1, filters.get('max_price', 5000) - filters.get('preferred_max_price', 4000)))
        criteria = {'fit': (25, size_fit), 'mounts': (15, mounts),
                    'road_gravel': (10, tires), 'components': (20, components),
                    'comfort': (15, comfort), 'value': (15, value)}
        known_weight = sum(weight for weight, quality in criteria.values() if quality is not None)
        # Unknown criteria are neutral; confidence reveals evidence coverage.
        base_score = round(sum(weight * (0.5 if quality is None else quality)
                               for weight, quality in criteria.values()))
        item['confidence'] = known_weight
        item['drivetrain'] = drive
        item['frame_size'] = size or 'Unverified'
        item.setdefault('hsa_status', 'Unverified')
        signals = {key: (None if quality is None else quality >= 0.75)
                   for key, (_, quality) in criteria.items()}
        item['evidence'] = {key: ('Unverified' if quality is None else round(quality * 100))
                            for key, (_, quality) in criteria.items()}
        if mounts_source:
            item['evidence']['mounts_source'] = mounts_source
        return base_score, signals
    else:
        keywords = profile.get('keywords', [])
        signals = {'matching_keywords': any(k.lower() in text for k in keywords),
                   'discounted': any(k in text for k in ['sale', 'discount', 'clearance'])}
    weights = profile.get('weights', {})
    total = sum(max(0, v) for v in weights.values()) or 1
    points = sum(max(0, w) for k, w in weights.items() if signals.get(k))
    base_score = round(100 * points / total)
    penalty_config = profile.get('price_penalty', {})
    threshold = penalty_config.get('starts_above')
    if threshold is not None and price > threshold:
        import math
        step = max(1, penalty_config.get('points_per_500', 0))
        penalty = min(penalty_config.get('max_points', 10),
                      math.ceil((price - threshold) / 500) * step)
        base_score = max(0, base_score - penalty)
    return base_score, signals
