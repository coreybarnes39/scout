from unittest.mock import Mock
import gspread
from scout.gifts import write_gifts, GIFT_HEADERS


def setup_sheet(exists=True):
    sheet = Mock()
    doc = sheet.spreadsheet
    tabs = {parent: Mock() for parent in ['Mom Christmas gifts', 'Dad Christmas gifts']}
    if exists:
        doc.worksheet.side_effect = tabs.__getitem__
    else:
        doc.worksheet.side_effect = gspread.WorksheetNotFound('missing')
        doc.add_worksheet.side_effect = lambda **kwargs: tabs[kwargs['title']]
    doc.worksheets.return_value = []
    return sheet, tabs


def item(title='Gift', price=20):
    return {'title': title, 'price': price, 'source': 'Shop',
            'url': 'https://example.test/gift'}


def profile(name='dad_lego', recipient='Dad'):
    return {'name': name, 'recipient': recipient}


def rows(tab):
    return tab.update.call_args.kwargs['values']


def test_categories_combine_instead_of_overwriting_each_other():
    sheet, tabs = setup_sheet()
    write_gifts(sheet, [(profile(), [item('Helmet')], []),
                       (profile('dad_classic_rock'), [], [item('Rock book', None)])])
    data = rows(tabs['Dad Christmas gifts'])
    assert len(data) == 3
    assert {r[0] for r in data[1:]} == {'Star Wars LEGO', 'Classic rock'}
    assert {r[3] for r in data[1:]} == {'Price/stock checked', 'Needs review'}
    tabs['Dad Christmas gifts'].clear.assert_called_once()
    tabs['Mom Christmas gifts'].update.assert_not_called()


def test_shared_ideas_appear_in_both_parent_tabs():
    sheet, tabs = setup_sheet()
    write_gifts(sheet, [(profile('parents_experiences', 'Shared'), [], [item('Concert', None)])])
    for tab in tabs.values():
        assert rows(tab)[1][0] == 'Experiences & tickets'
        assert rows(tab)[1][2] == 'Both parents'
        assert rows(tab)[1][4] == 'Unverified'


def test_empty_results_do_not_create_tabs():
    sheet, _ = setup_sheet(exists=False)
    write_gifts(sheet, [(profile(), [], [])])
    sheet.spreadsheet.add_worksheet.assert_not_called()
    sheet.spreadsheet.worksheets.assert_not_called()


def test_empty_existing_tab_clears_stale_results():
    sheet, tabs = setup_sheet()
    write_gifts(sheet, [(profile(), [], [])])
    assert rows(tabs['Dad Christmas gifts']) == [GIFT_HEADERS]
    tabs['Dad Christmas gifts'].clear.assert_called_once()


def test_first_results_create_only_the_target_parent_tab():
    sheet, tabs = setup_sheet(exists=False)
    write_gifts(sheet, [(profile(), [item()], [])])
    assert sheet.spreadsheet.add_worksheet.call_count == 1
    assert sheet.spreadsheet.add_worksheet.call_args.kwargs['title'] == 'Dad Christmas gifts'
    assert len(rows(tabs['Dad Christmas gifts'])) == 2


def test_single_profile_run_keeps_other_categories():
    sheet, tabs = setup_sheet()
    dad = tabs['Dad Christmas gifts']
    dad.get_all_records.return_value = [
        {'Category': 'Classic rock', 'Gift': 'Existing music'},
        {'Category': 'Star Wars LEGO', 'Gift': 'Old helmet'},
    ]
    write_gifts(sheet, [(profile(), [item('New helmet')], [])], replace_all=False)
    assert {r[1] for r in rows(dad)[1:]} == {'Existing music', 'New helmet'}


def test_legacy_managed_tabs_hidden_only_for_processed_profiles():
    sheet, _ = setup_sheet()
    legacy = Mock(title='Gift review dad_lego')
    other = Mock(title='Gift review mom_aerogarden')
    custom = Mock(title='My Christmas notes')
    sheet.spreadsheet.worksheets.return_value = [legacy, other, custom]
    write_gifts(sheet, [(profile(), [item()], [])])
    legacy.hide.assert_called_once()
    other.hide.assert_not_called()
    custom.hide.assert_not_called()
