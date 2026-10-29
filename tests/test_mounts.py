import json
from unittest.mock import Mock
import pytest
from scout.mounts import mounting_evidence
from scout.scoring import score
from scout.storage import save, write_top_results


@pytest.mark.parametrize('title', [
    'Checkpoint SL 5 Gen 3', 'Trek Checkpoint SL5 AXS Gen 3 M',
    'Checkpoint SL 6 AXS Gen 3 White / 54',
])
def test_reviewed_checkpoint_mounts_receive_full_credit(title):
    item = {'title': title, 'description': '', 'price': 3000}
    result = score(item, {'category': 'cycling'})
    assert result[1]['mounts'] is True
    assert item['evidence']['mounts'] == 100
    assert item['evidence']['mounts_source']['source'].startswith('https://www.trekbikes.com/')
    assert item['evidence']['mounts_source']['reviewed_on'] == '2026-10-29'
    # 15 mounts + 15 value + 20 drivetrain (AXS) or 10 unknown + 25 unknown others.
    assert item['confidence'] == (50 if 'axs' in title.lower() else 30)


@pytest.mark.parametrize('title', [
    'Checkpoint SL 6 AXS Gen 2', 'Checkpoint SL 6 AXS',
    'Checkpoint SLR 6 AXS Gen 3', 'Checkpoint+ SL 6 AXS Gen 3',
    'Checkpoint SL 6 AXS Gen 30', 'Checkpoint SL 6 Gen 3',
    'Checkpoint SL 6 AXS Gen 3 custom', 'Checkpoint SL 5 Gen 3 frameset',
])
def test_different_or_unknown_generation_does_not_inherit_specs(title):
    assert mounting_evidence({'title': title}) == (None, None)


def test_unknown_stays_unverified_through_sheet_output():
    item = {'title': 'Other gravel bike AXS', 'description': '', 'price': 3000,
            'url': 'https://shop.test/bike', 'id': 'bike', 'source': 'Shop',
            'currency': 'USD', 'hsa_verified': True}
    item['score'], item['signals'] = score(item, {'category': 'cycling'})
    assert item['signals']['mounts'] is None
    assert item['evidence']['mounts'] == 'Unverified'
    sheet = Mock()
    sheet.get_all_records.return_value = []
    save(sheet, 'cycling', [item], 10)
    row = sheet.append_rows.call_args.args[0][0]
    assert json.loads(row[8])['mounts'] == 'Unverified'
    tab = sheet.spreadsheet.worksheet.return_value
    tab.col_count = 16
    write_top_results(sheet, 'cycling', [item])
    row = tab.update.call_args.kwargs['values'][1]
    assert 'mounts' not in row[8]


def test_listing_specs_still_work_without_manufacturer_record():
    assert mounting_evidence({'title': 'Other bike',
                             'description': 'Rack mounts and fender mounts'})[0] == 1.0
    assert mounting_evidence({'title': 'Other bike',
                             'description': 'No rack mounts'})[0] is None
