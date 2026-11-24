"""Synergies between birds in neighbouring lanes."""

from src.core import state as game_state
from src.engine import powers, synergies
from src.engine.logic import collisions
from src.engine.progression import award_xp
from src.entities.sprites import (
    BLUE,
    CLOCKWORK,
    COOKIE,
    FROSTY,
    GOLD,
    ORANGE,
    PATCHWORK,
    RED,
    TWISTER,
    YELLOW,
)
from tests.harness import Simulation


def line_up(*colors):
    """Birds 0.. in lanes 0.. with these colours."""
    birds = game_state.birds
    for i in range(len(birds.colors)):
        birds.lost[i] = i >= len(colors)
    for i, color in enumerate(colors):
        birds.colors[i] = color
        birds.random_lanes[i] = i


def test_neighbours_are_the_lanes_right_next_to_a_bird():
    with Simulation(seed=1, key_rate=0):
        line_up(RED, YELLOW, RED, YELLOW)
        assert synergies.count(1, 'RED') == 2
        assert synergies.count(0, 'RED') == 0


def test_patchwork_counts_as_every_partner():
    with Simulation(seed=1, key_rate=0):
        line_up(PATCHWORK, ORANGE, PATCHWORK)
        assert synergies.count(1, 'RED') == 2
        assert synergies.count(1, 'TWISTER') == 2


def test_a_rising_yellow_cures_a_scared_blue_falling_past_it():
    with Simulation(seed=1, key_rate=0):
        line_up(YELLOW, BLUE)
        birds = game_state.birds
        birds.vy[0], birds.y[0] = -1, 10
        birds.vy[1], birds.y[1] = 1, 11
        game_state.special.scared_birds[1] = 100
        synergies.cure_blues()
        assert 1 not in game_state.special.scared_birds


def test_a_far_yellow_does_not_cure_the_blue():
    with Simulation(seed=1, key_rate=0):
        line_up(YELLOW, BLUE)
        birds = game_state.birds
        birds.vy[0], birds.y[0] = -1, 2
        birds.vy[1], birds.y[1] = 1, 15
        game_state.special.scared_birds[1] = 100
        synergies.cure_blues()
        assert 1 in game_state.special.scared_birds


def test_reds_next_to_the_phoenix_make_it_wake_more_often():
    with Simulation(seed=1, key_rate=0):
        line_up(RED, ORANGE, RED)
        base = synergies.phoenix_wake_chance(1) - 2 * synergies.value('phoenix_per_red', 0)
        assert abs(base - 0.1) < 1e-9
        assert synergies.phoenix_wake_chance(1) > 0.1


def test_the_yellow_power_winds_up_a_falling_clockwork():
    with Simulation(seed=1, key_rate=0):
        line_up(YELLOW, CLOCKWORK)
        game_state.birds.vy[1] = 1
        game_state.special.clockwork_charge[1] = 1
        powers._power_yellow(0, 0)
        assert game_state.special.clockwork_charge[1] == 2
        game_state.special.clockwork_charge[1] = 3
        powers._power_yellow(0, 0)
        assert game_state.special.clockwork_charge[1] == 3  # never above the maximum


def test_twisters_add_to_the_blue_sprint():
    with Simulation(seed=1, key_rate=0):
        line_up(TWISTER, BLUE, TWISTER)
        assert synergies.blue_sprint(1) == 2 * synergies.value('twister_sprint', 0)
        assert synergies.blue_sprint(0) == 0


def test_cookies_next_to_cookies_learn_faster():
    with Simulation(seed=1, key_rate=0):
        line_up(COOKIE, RED, RED, COOKIE, COOKIE)
        game_state.birds.per_bird_xp[0] = game_state.birds.per_bird_xp[3] = 0
        award_xp(0, 100)
        award_xp(3, 100)
        assert game_state.birds.per_bird_xp[3] > game_state.birds.per_bird_xp[0]


def test_a_frosty_next_to_a_red_freezes_what_its_shots_hit():
    with Simulation(seed=1, key_rate=0) as sim:
        line_up(FROSTY, RED)
        game_state.birds.vy[1] = -1
        powers._power_red(1, 1)
        shot = game_state.special.red_projectiles[-1]
        assert shot['afflict'] == [0]
        target = {'tier': 1, 'hp': 99999, 'max_hp': 99999, 'x_pos': shot['x_pos'] - 4, 'y_pos': shot['y_pos']}
        from src.engine import enemy_stats

        enemy_stats.equip_bat(target)
        target['target_y'] = target['y_pos']
        sim.state.enemies.bats[:] = [target]
        game_state.special.red_projectiles[:] = [shot]
        collisions.check_projectile_collision()
        assert id(target) in game_state.special.frozen_enemies


def test_other_birds_powers_leave_the_gold_alone():
    with Simulation(seed=1, key_rate=0):
        line_up(GOLD, YELLOW, GOLD)
        birds = game_state.birds
        for i in (0, 2):
            birds.vy[i], birds.y[i] = 1, 10
        powers._power_yellow(1, 1)
        assert birds.vy[0] == 1 and birds.vy[2] == 1  # not bounced
        assert 0 not in game_state.special.speed_boosts and 2 not in game_state.special.speed_boosts
