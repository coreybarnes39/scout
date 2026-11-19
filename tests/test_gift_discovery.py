import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import yaml
from scout.gift_discovery import discover_experiences, event_detail
from scout.gifts import collect_gifts, write_gifts


def event(day='2027-01-10', **extra):
    return '<script type="application/ld+json">' + json.dumps({
        '@type': 'Event', 'name': 'Pasta Dinner', 'startDate': day, **extra}) + '</script>'


def source(max_details=6):
    return {'name': 'Studio', 'products': [], 'discovery_pages': [{
        'url': 'https://studio.test/classes/?date={today}',
        'url_pattern': '/class/', 'include_any': ['dinner'],
        'exclude_any': ['private', 'kids'], 'max_details': max_details}]}


def responses(calendar):
    def get(url, **kwargs):
        text = ('User-agent: *\nAllow: /' if url.endswith('robots.txt') else
                calendar if '/classes/' in url else
                event('2026-11-18') if '/old' in url else event())
        return Mock(url=url, text=text)
    return get


def test_finds_future_events_but_not_old_external_private_or_duplicate_links():
    calendar = '''<a href="/class/old">Old Dinner</a>
        <a href="/class/new">Pasta Dinner</a><a href="/class/new#tickets">Dinner</a>
        <a href="https://other.test/class/x">Dinner</a>
        <a href="/class/private">Private Dinner</a>'''
    with patch('scout.gift_discovery.requests.get', side_effect=responses(calendar)) as get, \
            patch('scout.gift_discovery.datetime') as clock:
        clock.now.return_value = datetime(2026, 11, 19, tzinfo=timezone.utc)
        items = list(discover_experiences(source()))
    assert len(items) == 1
    assert items[0]['event_date'] == '2027-01-10'
    assert items[0]['party_size'] == 2
    assert items[0]['price'] is None and items[0]['review_reason']
    assert not any('other.test' in call.args[0] for call in get.call_args_list)
    assert any('date=2026-11-19' in call.args[0] for call in get.call_args_list)


def test_calendar_detail_requests_are_bounded():
    calendar = ''.join(f'<a href="/class/{i}">Dinner {i}</a>' for i in range(10))
    with patch('scout.gift_discovery.requests.get', side_effect=responses(calendar)) as get, \
            patch('scout.gift_discovery.datetime') as clock:
        clock.now.return_value = datetime(2026, 11, 19, tzinfo=timezone.utc)
        assert len(list(discover_experiences(source(2)))) == 2
    assert get.call_count == 4  # robots, index, two details


def test_christmas_gift_calendar_skips_pre_christmas_dates():
    config = source()
    config['discovery_pages'][0].update(not_before='2026-12-26',
        url='https://studio.test/classes/?date={start}')
    calendar = '<a href="/class/new">Pasta Dinner</a>'
    def get(url, **kwargs):
        if '/class/new' in url:
            return Mock(url=url, text=event('2026-12-04'))
        return responses(calendar)(url, **kwargs)
    with patch('scout.gift_discovery.requests.get', side_effect=get) as request, \
            patch('scout.gift_discovery.datetime') as clock:
        clock.now.return_value = datetime(2026, 11, 19, tzinfo=timezone.utc)
        assert list(discover_experiences(config)) == []
    assert any('date=2026-12-26' in call.args[0] for call in request.call_args_list)


def test_seeded_links_not_repeated_as_new_discoveries():
    calendar = '<a href="/class/new">Pasta Dinner</a>'
    with patch('scout.gift_discovery.requests.get', side_effect=responses(calendar)) as get:
        assert list(discover_experiences(source(), ['https://studio.test/class/new'])) == []
    assert get.call_count == 2


def test_robots_denial_prevents_calendar_access():
    response = Mock(url='https://studio.test/robots.txt', text='User-agent: *\nDisallow: /')
    with patch('scout.gift_discovery.requests.get', return_value=response) as get:
        assert list(discover_experiences(source())) == []
    assert get.call_count == 1


@pytest.mark.parametrize('html', [event(eventStatus='https://schema.org/EventCancelled'),
                                 event('invalid'), '<html>No structured date</html>'])
def test_undated_or_cancelled_events_are_not_invented(html):
    assert event_detail(html, 'https://studio.test/class/new') is None


def test_dining_and_garden_sources_route_to_joint_with_categories():
    registry = yaml.safe_load(Path('sources/experiences.yaml').read_text())
    for name in ['parents_dining', 'parents_gardens']:
        p = yaml.safe_load(Path(f'profiles/{name}.yaml').read_text())
        assert p['recipient'] == 'Shared' and p['filters']['max_price'] == 300
        candidates = registry[p['sources'][0]]['products']
        sheet, tab = Mock(), Mock()
        sheet.spreadsheet.worksheet.return_value = tab
        sheet.spreadsheet.worksheets.return_value = []
        write_gifts(sheet, [(p, [], [dict(i, source='Official sources') for i in candidates])])
        assert sheet.spreadsheet.worksheet.call_args.args[0] == 'Joint Christmas gifts'
        data = tab.update.call_args.kwargs['values']
        assert len(data) == len(candidates) + 1
        assert all(row[0] == p['category_label'] and row[2] == 'Both parents' for row in data[1:])


def test_collector_includes_discovered_candidates():
    with patch('scout.gift_discovery.discover_experiences', return_value=iter([{'title': 'New dinner'}])):
        assert list(collect_gifts(source())) == [{'title': 'New dinner'}]
