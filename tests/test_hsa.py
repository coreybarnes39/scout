from unittest.mock import Mock, patch
from scout.hsa import apply_evidence, load_evidence
from scout.scoring import rejection_reason
from scout.storage import write_top_results


def test_collection_matches_product_not_other_seller_or_other_bike():
    source = {'base_url': 'https://shop.test', 'name': 'Shop',
              'hsa_evidence': {'kind': 'collection', 'collection': 'eligible',
                               'url': 'https://shop.test/collections/eligible'}}
    with patch('scout.hsa.collect', return_value=iter([
            {'url': 'https://shop.test/products/bike?variant=1'}])):
        evidence = load_evidence(source)
    for url, expected in [('https://shop.test/products/bike?variant=2', True),
                          ('https://other.test/products/bike', False),
                          ('https://shop.test/products/other', False)]:
        item = {'url': url}
        apply_evidence(item, source, evidence)
        assert item['hsa_verified'] is expected
        assert bool(item.get('hsa_checked_at')) is expected


def test_failed_or_absent_evidence_cannot_keep_old_approval():
    item = {'url': 'https://shop.test/products/bike', 'hsa_verified': True,
            'hsa_evidence_url': 'old'}
    apply_evidence(item, {'base_url': 'https://shop.test'}, {})
    assert not item['hsa_verified']
    assert 'hsa_evidence_url' not in item


def test_policy_requires_explicit_bicycle_type():
    evidence = {'kind': 'all_bicycles', 'products': set(), 'url': 'policy',
                'checked_at': 'today'}
    for kind, expected in [('Bicycles', True), ('Accessories', False), ('', False)]:
        item = {'url': 'https://shop.test/products/x', 'product_type': kind}
        apply_evidence(item, {'base_url': 'https://shop.test'}, evidence)
        assert item['hsa_verified'] is expected


def test_strict_filter_rejects_unverified_and_accepts_verified():
    profile = {'category': 'cycling', 'filters': {'hsa': {'required': True}}}
    item = {'title': 'Gravel bike', 'price': 2000}
    assert rejection_reason(item, profile) == 'hsa_unverified'
    assert rejection_reason({**item, 'hsa_verified': True}, profile) is None


def test_top_ten_excludes_unverified_and_clears_stale_rows():
    sheet = Mock()
    tab = sheet.spreadsheet.worksheet.return_value
    tab.col_count = 14
    base = {'score': 80, 'price': 2000, 'title': 'Bike', 'source': 'Shop',
            'url': 'https://shop.test/products/bike'}
    assert write_top_results(sheet, 'cycling', [base]) == []
    tab.clear.assert_called_once()
    rows = tab.update.call_args.kwargs['values']
    assert len(rows) == 1 and len(rows[0]) == 16


def test_policy_text_must_still_be_present():
    response = Mock(url='https://shop.test/policy', text='<p>Pay with Truemed</p>')
    with patch('scout.hsa.requests.get', return_value=response):
        assert load_evidence({'hsa_evidence': {'kind': 'all_bicycles',
            'url': 'https://shop.test/policy',
            'required_text': 'All bicycles are eligible'}}) == {}
