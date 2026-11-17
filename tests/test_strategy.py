"""Bot strategies: formations, braking, letting birds go, adaptive cards."""

from src.engine import stats
from src.sim import strategy
from src.sim.bot import Bot, profile
from src.sim.runner import RunConfig, run
from tests.harness import Simulation


def test_formation_score_rewards_reds_side_by_side():
    lanes = dict(enumerate(['RED', 'YELLOW', 'RED', 'YELLOW', 'RED', 'BLUE', 'BLUE', 'YELLOW', 'YELLOW']))
    together = dict(enumerate(['RED', 'RED', 'RED', 'YELLOW', 'YELLOW', 'BLUE', 'BLUE', 'YELLOW', 'YELLOW']))
    assert strategy.formation_score(together, 'red_battery') > strategy.formation_score(lanes, 'red_battery')
    guard = dict(enumerate(['YELLOW', 'BLUE', 'YELLOW', 'RED', 'RED', 'RED', 'YELLOW', 'BLUE', 'YELLOW']))
    assert strategy.formation_score(guard, 'yellow_guard') > strategy.formation_score(together, 'yellow_guard')


def test_letting_birds_go_is_limited_by_lives():
    with Simulation(seed=1, key_rate=0) as sim:
        skill = profile('expert', keep_birds=3, min_lives_to_cull=3)
        sim.state.game.lives = 5
        assert len(strategy.abandoned(skill)) == 2
        sim.state.game.lives = 3
        assert strategy.abandoned(skill) == set()


def test_favorites_are_kept_and_hatched():
    with Simulation(seed=1, key_rate=0):
        skill = profile('expert', favorites=('RED',), cull_others=True, min_lives_to_cull=0)
        let_go = strategy.abandoned(skill)
        assert all(strategy.kind(i) != 'RED' for i in let_go)
        assert strategy.wants_bird('RED', skill) and not strategy.wants_bird('YELLOW', skill)


def test_adaptive_cards_follow_what_the_flock_needs():
    with Simulation(seed=1, key_rate=0) as sim:
        skill = profile('expert', card_policy='adaptive')
        fear = {'id': 'a', 'kind': 'stat', 'rarity': 'rare', 'effects': [{'stat': 'fear_resist', 'add': 0.15}]}
        luck = {'id': 'b', 'kind': 'flock', 'rarity': 'rare', 'effects': [{'stat': 'egg_luck', 'add': 0.02}]}
        offer = {'kind': 'egg', 'cards': [fear, luck], 'index': 0}
        for i in range(9):
            sim.state.special.scared_birds[i] = 10
        assert strategy.choose_card(offer, skill) == 0, 'a scared flock wants fear resistance'
        sim.state.special.scared_birds.clear()
        stats.add_modifier('flock', 'damage_mult', mul=1.0)
        assert strategy.card_value(luck, skill) > 0


def test_a_braking_bot_swaps_and_slows_down():
    braking = run(RunConfig(seed=3, skill=profile('expert', max_gear=3), max_minutes=3))
    plain = run(RunConfig(seed=3, max_minutes=3))
    assert braking.summary()['swaps'] > 0
    assert braking.summary()['gear_mean'] <= plain.summary()['gear_mean']


def test_strategies_are_valid_skill_changes():
    for changes in strategy.STRATEGIES.values():
        Bot(profile('expert', **changes))
