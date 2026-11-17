"""Meta progression: achievements, gold, upgrades, the saved profile."""

from src.core import state
from src.engine import events, meta, stats
from src.services import save_manager
from tests.harness import Simulation


def fresh(gold=0):
    state.meta.profile = meta.new_profile()
    state.meta.profile['gold'] = gold
    state.game.meta_applied = False
    meta.start_run()


def test_run_achievements_pay_gold_each_run():
    with Simulation(seed=1, key_rate=0):
        fresh()
        events.emit('level_up', level=3)
        # First Steps, Forest Edge and Untouched (no bird lost yet)
        assert set(state.meta.run_achievements) == {'first_steps', 'forest_edge', 'untouched'}
        assert meta.run_gold() == 2 + 3 + 6
        gold = meta.end_run(save=False)
        assert gold == 11 and meta.profile()['gold'] >= 11
        # Next run: the same achievements pay again
        state.game.meta_applied = False
        meta.start_run()
        events.emit('level_up', level=3)
        assert meta.run_gold() == 11


def test_limits_in_goals():
    with Simulation(seed=1, key_rate=0):
        fresh()
        events.emit('bird_lost', bird=0, color='', cause='floor')
        events.emit('level_up', level=3)
        assert 'untouched' not in state.meta.run_achievements, 'a bird was lost before level 1-3'


def test_global_achievements_pay_once():
    with Simulation(seed=1, key_rate=0):
        fresh()
        meta.end_run(save=False)
        assert 'hatchling' in meta.profile()['achievements']
        gold = meta.profile()['gold']
        state.game.meta_applied = False
        meta.start_run()
        meta.end_run(save=False)
        assert meta.profile()['achievements'].count('hatchling') == 1
        assert meta.profile()['gold'] == gold


def test_upgrades_need_gold_and_requirements_and_apply_to_new_runs():
    with Simulation(seed=1, key_rate=0):
        fresh(gold=1000)
        assert not meta.buy('piercing', save=False), 'needs Sharp Talons 2'
        assert meta.buy('sharp_talons', save=False) and meta.buy('sharp_talons', save=False)
        assert meta.buy('piercing', save=False)
        assert meta.profile()['gold'] == 1000 - 15 - 25 - 30
        meta.buy('extra_life', save=False)
        lives = state.game.lives
        base = stats.bird(0, 'damage_mult')
        state.game.meta_applied = False
        meta.start_run()
        assert state.game.lives == lives + 1
        assert abs(stats.bird(0, 'damage_mult') - base * 1.08) < 1e-9
        # Upgrades apply once per run, even if the run is resumed
        meta.start_run()
        assert state.game.lives == lives + 1


def test_profile_is_saved_and_loaded(tmp_path, monkeypatch):
    monkeypatch.setattr(save_manager, 'get_profile_path', lambda: tmp_path / 'profile.json')
    with Simulation(seed=1, key_rate=0):
        fresh(gold=50)
        meta.buy('gold_digger')
        loaded = save_manager.load_profile()
        assert loaded['gold'] == 35 and loaded['upgrades'] == {'gold_digger': 1}


def test_gold_digger_multiplies_run_gold():
    with Simulation(seed=1, key_rate=0):
        fresh(gold=100)
        meta.buy('gold_digger', save=False)
        state.game.meta_applied = False
        meta.start_run()
        events.emit('level_up', level=3)
        assert meta.run_gold() == round(11 * 1.1)
