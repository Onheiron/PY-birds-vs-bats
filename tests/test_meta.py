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


def test_every_run_pays_a_reward_by_level_bosses_bats_and_difficulty():
    with Simulation(seed=1, key_rate=0):
        state.settings.difficulty = 1  # ADVENTURE: x1
        fresh()
        events.emit('level_up', level=3)
        for _ in range(50):
            events.emit('bat_killed', bat={}, tier=1, killer=0)
        state.meta.run['bosses'] = 1
        assert meta.run_gold() == 3 * 1 + 1 * 4 + 50 // 25
        gold = meta.end_run(save=False)
        assert gold == 9 and meta.profile()['gold'] >= 9
        # Next run: it pays again, x1.5 on SURVIVAL
        state.settings.difficulty = 2
        state.game.meta_applied = False
        meta.start_run()
        events.emit('level_up', level=2)
        assert meta.run_gold() == 3  # 2 x 1.5
        state.settings.difficulty = 1


def test_goals_within_one_run():
    with Simulation(seed=1, key_rate=0):
        fresh()
        events.emit('bird_lost', bird=0, color='', cause='floor')
        events.emit('level_up', level=6)
        assert 'careful_flock' in meta.profile()['achievements'], 'reached 2-3 losing one bird'
        fresh()
        for _ in range(4):
            events.emit('bird_lost', bird=0, color='', cause='floor')
        state.meta.profile['achievements'] = []
        events.emit('level_up', level=6)
        assert 'careful_flock' not in meta.profile()['achievements'], '4 birds lost in this run'


def test_world_goals_are_counted_when_its_boss_falls():
    with Simulation(seed=1, key_rate=0):
        fresh()
        events.emit('boss_spawned', boss_type='normal')
        events.emit('boss_defeated', boss_type='normal')
        run = state.meta.run
        assert run['bosses'] == 1 and run['clean_worlds'] == 1 and run['clean_bosses'] == 1
        assert {'boss_down', 'clean_world', 'clean_boss'} <= set(meta.profile()['achievements'])
        assert meta.profile()['boss_kinds'] == ['normal']
        events.emit('bird_lost', bird=0, color='', cause='floor')
        events.emit('boss_defeated', boss_type='wind')
        assert run['clean_worlds'] == 1  # a bird was lost in the second world


def test_evolutions_count():
    with Simulation(seed=1, key_rate=0):
        fresh()
        events.emit('bird_evolved', bird=0, into='GOLD')
        assert state.meta.run['evolved_gold'] == 1
        assert 'golden_touch' in meta.profile()['achievements']


def test_global_achievements_pay_once():
    with Simulation(seed=1, key_rate=0):
        fresh()
        meta.end_run(save=False)
        assert 'hatchling' in meta.profile()['achievements']
        gold = meta.profile()['gold']
        state.game.meta_applied = False
        meta.start_run()
        reward = meta.end_run(save=False)
        assert meta.profile()['achievements'].count('hatchling') == 1
        assert meta.profile()['gold'] == gold + reward  # only the run's reward


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
        state.settings.difficulty = 1
        events.emit('level_up', level=10)
        assert meta.run_gold() == round(10 * 1.1)


def test_momentum_grows_and_falls_at_their_own_pace():
    from src.core import constants
    from src.engine import progression

    with Simulation(seed=1, key_rate=0):
        constants.speed.momentum_gain_multiplier = 90.0
        constants.speed.momentum_loss_multiplier = 115.0
        state.game.momentum = 1000.0
        progression.update_momentum(2.0)
        assert state.game.momentum == 1180.0
        progression.update_momentum(-1.0)
        assert state.game.momentum == 1065.0


def test_momentum_stops_at_the_worlds_gear_cap():
    from src.core import constants
    from src.engine import progression

    with Simulation(seed=1, key_rate=0):
        state.game.level_group = 1  # world 1: gear 5 at most
        state.game.momentum = progression.calculate_gear_threshold(5)
        for _ in range(2000):
            progression.update_momentum(2.0)
        assert state.game.momentum < progression.calculate_gear_threshold(6)
        state.game.level_group = 2  # the next world: the gear climbs from 5, it does not jump
        progression.update_momentum(0.0)
        assert progression.compute_gear_from_momentum(state.game.momentum) == 5
        assert constants.speed.max_gear_by_world[1] > 5
