"""Freeze, poison and bleed on bats and bosses."""

from src.core import state as game_state
from src.engine import clock, enemy_stats, stats
from src.engine.logic import afflictions
from src.entities.sprites import BERSERK, FROSTY, POISON
from tests.harness import FRAME_DT, Simulation


def bat(**extra):
    b = {'tier': 1, 'hp': 2000, 'max_hp': 2000, 'x_pos': 10, 'y_pos': 5, 'target_y': 5, 'direction': 1}
    b.update(extra)
    return enemy_stats.equip_bat(b)


def afflict(bird, color, target, is_boss=False):
    game_state.birds.colors[bird] = color
    stats.add_modifier(bird, 'affliction_chance', add=1)
    return afflictions.try_afflict(bird, target, is_boss)


def test_frozen_bats_move_slower_and_lose_armor():
    with Simulation(seed=1, key_rate=0) as sim:
        # Above the screen, where no bird reaches them
        frozen, free = bat(y_pos=-40, target_y=-40), bat(y_pos=-40, target_y=-40, x_pos=20)
        sim.state.enemies.bats[:] = [frozen, free]
        assert afflict(0, FROSTY, frozen) == 'frozen'
        assert afflictions.armor_cut(frozen) == 20
        moved = {id(frozen): 0, id(free): 0}
        last = {id(frozen): frozen['x_pos'], id(free): free['x_pos']}
        for _ in range(int(1.5 / FRAME_DT)):
            sim.step(key=None, render=False)
            for b in (frozen, free):
                moved[id(b)] += abs(b['x_pos'] - last[id(b)])
                last[id(b)] = b['x_pos']
        assert 0 < moved[id(frozen)] < moved[id(free)] * 0.6


def test_poison_damage_and_xp_go_to_the_bird_that_applied_it():
    with Simulation(seed=1, key_rate=0) as sim:
        target = bat(y_pos=-40, target_y=-40)
        sim.state.enemies.bats[:] = [target]
        assert afflict(4, POISON, target) == 'poisoned'
        xp_before = [sim.state.birds.per_bird_xp[i] for i in (0, 4)]
        start = clock.now()
        sim.run(int(3.2 / FRAME_DT))
        ticks = int(clock.now() - start)
        assert 2000 - target['hp'] >= 20 * (ticks - 1)
        assert sim.state.birds.per_bird_xp[4] > xp_before[1]


def test_damage_over_time_follows_damage_taken():
    with Simulation(seed=1, key_rate=0) as sim:
        target = bat(y_pos=-40, target_y=-40)
        target['stats']['damage_taken'] = 0.5
        sim.state.enemies.bats[:] = [target]
        afflict(2, BERSERK, target)
        sim.run(int(1.2 / FRAME_DT))
        assert target['hp'] == 2000 - 5


def test_bosses_can_be_afflicted_and_die_of_it(monkeypatch):
    from src.core import constants

    with Simulation(seed=1, key_rate=0) as sim:
        monkeypatch.setattr(constants.combat, 'boss_affliction_factor', 1.0)
        boss = {'boss_type': 'normal', 'hp': 15, 'max_hp': 15, 'state': 'active', 'x_pos': 5, 'y_pos': 3}
        sim.state.enemies.boss = boss
        assert afflict(1, POISON, boss, is_boss=True) == 'poisoned'
        now = [clock.now()]
        monkeypatch.setattr(clock, 'now', lambda: now[0])
        now[0] += 1.1
        afflictions.update()
        assert boss['hp'] == 15 - 20 and boss['state'] == 'dying'
        assert id(boss) not in sim.state.special.poisoned_enemies
