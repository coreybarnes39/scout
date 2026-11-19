import json
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import yaml
from scout.gifts import product_offer, collect_gifts, write_gifts


def html(name='Tiny Plants', **offer):
    return '<script type="application/ld+json">' + json.dumps({
        '@type': 'Product', 'name': name, 'offers': {
            '@type': 'Offer', 'price': '49.99', 'priceCurrency': 'USD',
            'availability': 'https://schema.org/InStock', **offer}}) + '</script>'


def test_current_exact_product_offer():
    assert product_offer(html(), 'Tiny Plants') == 49.99
    assert product_offer(html('Recommended unrelated set'), 'Tiny Plants') is None


@pytest.mark.parametrize('offer', [
    {'@type': 'AggregateOffer', 'lowPrice': '10'},
    {'priceCurrency': 'EUR'}, {'availability': 'https://schema.org/OutOfStock'},
    {'availability': ''}, {'price': 'NaN'}, {'price': '-10'}, {'price': 'bad'},
])
def test_unknown_or_ambiguous_prices_never_enter_shortlist(offer):
    assert product_offer(html(**offer), 'Tiny Plants') is None


def test_subscription_never_uses_monthly_headline_as_full_cost():
    source = {'name': 'Food', 'products': [{
        'title': 'Food plan', 'url': 'https://example.test/gift', 'subscription': True}]}
    with patch('scout.gifts.requests.get') as get:
        item, = collect_gifts(source)
    get.assert_not_called()
    assert item['price'] is None and not item['available']


def test_experience_never_uses_single_seat_or_deposit_price():
    source = {'name': 'Venue', 'products': [{
        'title': 'Show for two', 'url': 'https://example.test/tickets',
        'experience': True, 'party_size': 2}]}
    with patch('scout.gifts.requests.get') as get:
        item, = collect_gifts(source)
    get.assert_not_called()
    assert item['price'] is None and not item['available']


def test_updated_recipient_preferences():
    sources = yaml.safe_load(Path('sources/gifts.yaml').read_text())
    lego = sources['gift_lego']['products']
    assert all('Star Wars' in item['title'] for item in lego)
    assert all('botanical' not in item['title'].lower() for item in lego)
    events = sources['gift_experiences']['products']
    assert all(item['party_size'] == 2 and item['review_reason'] for item in events)
    assert any(item.get('event_year') == 2027 and item['location'] == 'Orlando, FL' for item in events)
    p = yaml.safe_load(Path('profiles/parents_experiences.yaml').read_text())
    assert p['filters']['max_price'] == 300


def test_denied_robots_is_reviewed_not_silently_dropped():
    response = Mock(text='User-agent: *\nDisallow: /')
    source = {'name': 'Shop', 'products': [{'title': 'Tiny Plants',
              'url': 'https://example.test/product'}]}
    with patch('scout.gifts.requests.get', return_value=response) as get:
        item, = collect_gifts(source)
    assert get.call_count == 1
    assert 'robots' in item['review_reason'] and item['price'] is None


def test_gift_profiles_and_budget_are_connected():
    sources = yaml.safe_load(Path('sources/gifts.yaml').read_text())
    for name in ['dad_lego', 'mom_aerogarden', 'parents_plants', 'parents_food']:
        p = yaml.safe_load(Path(f'profiles/{name}.yaml').read_text())
        assert p['enabled'] and p['category'] == 'gifts'
        assert p['filters']['max_price'] == 150
        assert all(s in sources for s in p['sources'])
    assert not yaml.safe_load(Path('profiles/cycling.yaml').read_text())['enabled']



def test_gift_run_separates_budget_unknown_and_qualified_without_email():
    from datetime import date
    from scout.main import run
    base = {'title': 'Gift', 'url': 'https://example.test/product',
            'source': 'Shop', 'available': True, 'review_reason': ''}
    candidates = [{**base, 'price': 100}, {**base, 'price': 151},
                  {**base, 'price': None, 'review_reason': 'Choose prepaid plan'}]
    with patch('scout.main.collect_gifts', return_value=iter(candidates)), \
            patch('scout.main.datetime') as clock, \
            patch('scout.main.open_sheet'), patch('scout.main.write_gifts') as write, \
            patch('scout.main.send_email') as email:
        clock.now.return_value.date.return_value = date(2026, 11, 19)
        run('dad_lego')
    args = write.call_args.args
    profile, qualified, pending = args[1][0]
    assert [item['price'] for item in qualified] == [100]
    assert len(pending) == 2
    assert write.call_args.kwargs['replace_all'] is False
    email.assert_not_called()


def test_dry_run_does_not_open_or_write_sheet():
    from datetime import date
    from scout.main import run
    with patch('scout.main.collect_gifts', return_value=iter([])), \
            patch('scout.main.datetime') as clock, \
            patch('scout.main.open_sheet') as sheet, \
            patch('scout.main.write_gifts') as write:
        clock.now.return_value.date.return_value = date(2026, 11, 19)
        run('dad_lego', dry_run=True)
    sheet.assert_not_called()
    write.assert_not_called()


def test_all_profiles_publish_once_after_collecting_every_category():
    from datetime import date
    from scout.main import run
    with patch('scout.main.collect_gifts', side_effect=lambda _: iter([])), \
            patch('scout.main.datetime') as clock, \
            patch('scout.main.open_sheet'), patch('scout.main.write_gifts') as write:
        clock.now.return_value.date.return_value = date(2026, 11, 19)
        run()
    write.assert_called_once()
    assert len(write.call_args.args[1]) == 6
    assert write.call_args.kwargs['replace_all'] is True
