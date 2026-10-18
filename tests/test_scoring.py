from scout.scoring import score

def test_cycling_positive():
    import yaml
    with open('profiles/cycling.yaml') as f: p = yaml.safe_load(f)
    item = {'title': 'Carbon Gravel Bike 54cm SRAM Rival AXS', 'description': 'bikepacking fork mounts, 700c endurance', 'price': 2999, 'available': True}
    result = score(item, p)
    assert result is not None and result[0] >= 65

def test_budget_reject():
    import yaml
    with open('profiles/cycling.yaml') as f: p = yaml.safe_load(f)
    assert score({'title': 'Gravel bike', 'description': '', 'price': 9000, 'available': True}, p) is None


def test_upper_budget_included_with_penalty():
    import yaml
    with open('profiles/cycling.yaml') as f: p = yaml.safe_load(f)
    base = {'title': 'Carbon Gravel Bike 54cm SRAM Rival AXS', 'description': 'bikepacking fork mounts, 700c endurance', 'available': True}
    cheap = score({**base, 'price': 3999}, p)
    pricey = score({**base, 'price': 4800}, p)
    assert cheap is not None and pricey is not None
    assert pricey[0] < cheap[0]
    assert score({**base, 'price': 5001}, p) is None
