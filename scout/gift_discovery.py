"""Bounded discovery of future experiences from explicitly configured calendars."""
import hashlib
import json
import logging
import re
from datetime import date, datetime, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
from zoneinfo import ZoneInfo
import requests

log = logging.getLogger(__name__)
AGENT = 'ScoutPersonalMonitor/0.4 (personal gift research)'


def canonical(url):
    return urlsplit(url)._replace(fragment='').geturl().rstrip('/')


class Calendar(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.scripts, self.words = [], [], []
        self.href, self.script = None, False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.href, self.words = attrs.get('href'), []
        if tag == 'script' and attrs.get('type') == 'application/ld+json':
            self.script, self.parts = True, []

    def handle_data(self, value):
        if self.script:
            self.parts.append(value)
        elif self.href:
            self.words.append(value)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href:
            self.links.append((self.href, ' '.join(' '.join(self.words).split())))
            self.href = None
        if tag == 'script' and self.script:
            self.scripts.append(''.join(self.parts))
            self.script = False


def event_detail(html, url):
    events = []
    for script in Calendar(html).scripts:
        try:
            queue = [json.loads(script)]
        except ValueError:
            continue
        while queue:
            node = queue.pop()
            if isinstance(node, list):
                queue.extend(node)
            elif isinstance(node, dict):
                graph = node.get('@graph')
                if isinstance(graph, (list, dict)):
                    queue.append(graph)
                kinds = node.get('@type', [])
                kinds = [kinds] if isinstance(kinds, str) else kinds
                if not isinstance(kinds, list):
                    continue
                if any(str(kind).endswith('Event') for kind in kinds):
                    events.append(node)
    matching = [event for event in events if isinstance(event.get('url'), str)
                and canonical(event['url']) == canonical(url)]
    candidates = matching or (events if len(events) == 1 else [])
    if len(candidates) != 1:
        return None
    event = candidates[0]
    if not event.get('name') or str(event.get('eventStatus', '')).rstrip('/').endswith(('EventCancelled', 'EventPostponed')):
        return None
    try:
        day = date.fromisoformat(str(event['startDate'])[:10])
    except (KeyError, ValueError):
        return None
    return unescape(str(event['name'])), day


def discover_experiences(source, seen=None):
    seen = {canonical(url) for url in (seen or [])}
    robots = {}
    today = datetime.now(ZoneInfo('America/New_York')).date()
    count = 0
    for config in source.get('discovery_pages', [])[:3]:
        earliest = max(today, date.fromisoformat(config.get('not_before', today.isoformat())))
        page = config['url'].replace('{today}', today.isoformat()).replace('{start}', earliest.isoformat())
        origin = urlsplit(page)
        if origin.scheme != 'https':
            continue

        def fetch(url):
            parts = urlsplit(url)
            if parts.scheme != 'https' or parts.netloc != origin.netloc:
                raise ValueError('Calendar discovery stays on its configured HTTPS origin')
            if origin.netloc not in robots:
                response = requests.get(f'https://{origin.netloc}/robots.txt',
                                        headers={'User-Agent': AGENT}, timeout=15)
                response.raise_for_status()
                if urlsplit(response.url).netloc != origin.netloc:
                    raise ValueError('Robots redirected to another origin')
                robot = RobotFileParser()
                robot.parse(response.text.splitlines())
                robots[origin.netloc] = robot
            if not robots[origin.netloc].can_fetch(AGENT, url):
                raise ValueError('Calendar disallowed by robots.txt')
            response = requests.get(url, headers={'User-Agent': AGENT}, timeout=20)
            response.raise_for_status()
            if urlsplit(response.url).netloc != origin.netloc:
                raise ValueError('Calendar redirected to another origin')
            return response.text

        try:
            calendar = Calendar(fetch(page))
        except (requests.RequestException, ValueError) as exc:
            log.warning('Experience discovery failed for %s: %s', page, exc)
            continue
        checked = 0
        for href, label in calendar.links:
            target = canonical(urljoin(page, href))
            lower = label.lower()
            if (target in seen or urlsplit(target).netloc != origin.netloc
                    or not re.search(config.get('url_pattern', r'/events?/'), urlsplit(target).path)
                    or any(word.lower() in lower for word in config.get('exclude_any', []))
                    or (config.get('include_any') and not any(word.lower() in lower for word in config['include_any']))):
                continue
            if checked >= min(6, max(0, int(config.get('max_details', 6)))) or count >= 12:
                break
            seen.add(target)
            checked += 1
            try:
                detail = event_detail(fetch(target), target)
            except (requests.RequestException, ValueError) as exc:
                log.warning('Experience detail failed for %s: %s', target, exc)
                continue
            if not detail:
                continue
            name, day = detail
            if not earliest <= day <= date(2027, 12, 31):
                continue
            # Recheck the actual event name, not just the calendar link label.
            if any(word.lower() in name.lower() for word in config.get('exclude_any', [])):
                continue
            count += 1
            yield {'id': hashlib.sha256(target.encode()).hexdigest()[:20],
                   'title': f'{name} â€” {day.isoformat()}', 'url': target,
                   'source': config.get('name', source['name']),
                   'price': None, 'currency': 'USD', 'available': False,
                   'experience': True, 'party_size': 2, 'event_date': day.isoformat(),
                   'why': 'New experience discovered on an official calendar.',
                   'checks': f'Calendar: {page}. Confirm two places, full cost with fees/tax/tip, location and gift terms.',
                   'review_reason': 'Future event date found; current availability and complete price for two need review.',
                   'checked_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
