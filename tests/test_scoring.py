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

def test_unknown_specs_are_neutral_not_failures():
    import yaml
    with open('profiles/cycling.yaml') as f: p = yaml.safe_load(f)
    sparse = {'title': 'Checkpoint SL 6 AXS Gen 3', 'description': '',
              'price': 3699, 'available': True}
    result = score(sparse, p)
    assert result is not None
    assert sparse['confidence'] == 35  # drivetrain and price; no guessed frame/fit/mounts
    assert sparse['evidence']['fit'] == 'Unverified'
    assert sparse['evidence']['mounts'] == 'Unverified'
    assert result[0] > 55  # no zero-score punishment for missing description


def test_verified_specs_increase_confidence_and_score():
    import yaml
    with open('profiles/cycling.yaml') as f: p = yaml.safe_load(f)
    sparse = {'title': 'Gravel bike SRAM Rival AXS', 'description': '', 'price': 3500, 'available': True}
    rich = {**sparse, 'variant_title': '54cm',
            'description': 'fork mount, tire clearance 45mm, endurance geometry'}
    low = score(sparse, p)
    high = score(rich, p)
    assert low is not None and high is not None
    assert rich['confidence'] > sparse['confidence']
    assert high[0] > low[0]
