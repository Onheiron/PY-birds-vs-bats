"""tools/analyze.py: statistics and the decision report, on made-up data."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('analyze', Path(__file__).parent.parent / 'tools' / 'analyze.py')
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


def test_eta_squared_measures_how_much_a_factor_explains():
    assert analyze.eta_squared({'a': [1, 1, 1], 'b': [5, 5, 5]}) == 1.0
    assert analyze.eta_squared({'a': [1, 5], 'b': [1, 5]}) == 0.0


def decision(card, offered, levels, lives=5):
    context = {'level': 3, 'lives': lives, 'birds': 9, 'gear': 5, 'prestige': 2, 'scared': 0, 'boss': False, 'bats': 1}
    return {
        'offer': 'egg',
        'card': card,
        'offered': offered,
        'levels_after': levels,
        'birds_after': 0,
        'died_after': False,
        'context': context,
    }


def test_decision_report_finds_the_better_card_per_situation():
    items = []
    for k in range(20):
        noise = 0.1 * (k % 3)
        items.append(decision('good', ['good', 'bad'], 2 + noise))
        items.append(decision('bad', ['good', 'bad'], noise))
        items.append(decision('shield', ['shield', 'good'], 3 + noise, lives=2))
        items.append(decision('good', ['shield', 'good'], noise, lives=2))
    report = analyze.decision_report(items, ['lives'], min_samples=10)
    assert '| good' in report and '+2.00' in report
    assert 'When **lives <= 3**: take **shield**' in report
    assert 'When **lives > 3**: take **good**' in report
    assert 'avoid **bad**' in report
