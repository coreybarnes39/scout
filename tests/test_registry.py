import yaml
from scout.scoring import rejection_reason, score

def test_registry():
    with open('sources/retailers.yaml') as f: sources = yaml.safe_load(f)
    with open('profiles/cycling.yaml') as f: profile = yaml.safe_load(f)
    assert all(source in sources for source in profile['sources'])

def test_grevil_variant():
    with open('profiles/cycling.yaml') as f: profile = yaml.safe_load(f)
    item = dict(title='Pinarello Grevil F3 Patagonia Frost / 53', variant_title='Patagonia Frost / 53', description='TorayCa T700 carbon frame', price=3950, available=True)
    assert rejection_reason(item, profile) is None
    points, signals = score(item, profile)
    assert signals['size'] and signals['carbon']
