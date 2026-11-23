"""World hazards: winds, emerging obstacles, darkness, stalactites, peaks, fog."""

from src.core import state as game_state
from src.engine import clock, enemy_stats, hazards
from src.engine.physics import update_obstacle_positions
from tests.harness import Simulation


def in_world(sim, world):
    sim.state.game.level_group = world
    sim.state.enemies.boss = None


def test_windy_woods_gusts_are_tailwind_on_adjacent_lanes():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 1)
        for _ in range(5):
            game_state.hazards.next_wind = clock.now() - 1
            hazards.update()
            lanes = sorted(game_state.hazards.lane_winds)
            assert 2 <= len(lanes) <= 4
            assert lanes == list(range(lanes[0], lanes[0] + len(lanes)))
            assert all(w['tail'] for w in game_state.hazards.lane_winds.values())
            assert hazards.lane_wind(lanes[0]) == (1.0, -1.0)
            game_state.hazards.lane_winds.clear()


def test_no_winds_where_the_world_has_none():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 2)
        game_state.hazards.next_wind = clock.now() - 1
        hazards.update()
        assert not game_state.hazards.lane_winds


def test_emerging_obstacles_wait_mid_screen_and_do_not_block():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 3)
        obstacle = {'id': 1, 'lane': 4, 'y_pos': -2, 'tier': 1, 'hp': 50, 'sprite': ['##'], 'kind': 'emerging'}
        hazards.place_emerging(obstacle)
        screen = sim.constants.layout.starting_line
        assert int(screen * 0.35) <= obstacle['y_pos'] <= int(screen * 0.70)
        assert hazards.is_emerging(obstacle)
        sim.state.enemies.obstacles[:] = [enemy_stats.equip_obstacle(obstacle)]
        y = obstacle['y_pos']
        for _ in range(20):
            sim.state.game.frame_count += 1
            update_obstacle_positions()
        assert obstacle['y_pos'] == y


def test_the_cave_is_dark_but_around_the_cursor_and_fireflies_light_it():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 5)
        sim.state.player.lane = 4
        assert hazards.dark()
        assert {3, 4, 5} <= hazards.lit_lanes()
        hazards.collect_firefly()
        assert not hazards.dark()
        in_world(sim, 4)
        game_state.hazards.light_until = 0
        assert not hazards.dark()


def test_stalactites_warn_then_fall_fast():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 5)
        sim.state.enemies.obstacles[:] = []
        game_state.hazards.next_stalactite = clock.now() - 1
        hazards.update()
        assert len(game_state.hazards.stalactite_warnings) == 1
        game_state.hazards.stalactite_warnings[0]['falls_at'] = clock.now() - 1
        hazards.update()
        stalactite = [o for o in sim.state.enemies.obstacles if o.get('kind') == 'stalactite'][0]
        assert enemy_stats.get(stalactite, 'fall_interval') == 2


def test_peaks_are_hard_and_knock_birds_down():
    with Simulation(seed=3, key_rate=0):
        peak = enemy_stats.equip_obstacle({'tier': 4, 'hp': 320, 'kind': 'peak'})
        assert peak['hp'] == 640
        assert enemy_stats.get(peak, 'knock') == 2
        assert enemy_stats.get(peak, 'armor') == 8 + 15


def test_rocks_are_harder_in_the_cave():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 5)
        rock = enemy_stats.equip_obstacle({'tier': 2, 'hp': 80})
        assert rock['hp'] == 120 and enemy_stats.get(rock, 'defense') == 6


def test_fog_only_in_the_mountains():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 6)
        sim.state.enemies.cloud_spawn_timer = 0
        hazards.update()
        assert sim.state.enemies.cloud_banks
        in_world(sim, 5)
        hazards.update()
        assert not sim.state.enemies.cloud_banks


def test_the_bot_sees_what_the_player_sees_in_the_dark():
    from dataclasses import replace

    from src.sim.bot import PROFILES, Bot

    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 5)
        game_state.hazards.light_until = 0
        birds = game_state.birds
        for i in range(len(birds.colors)):
            birds.random_lanes[i] = i
            birds.lost[i] = i != 8
        sim.state.player.lane = 0
        birds.y[8], birds.vy[8] = 20, 1  # falling, far from the light
        bot = Bot(replace(PROFILES['expert'], memory=0.0))
        bot._perceive()
        assert 8 not in bot.view  # never seen: unknown
        sim.state.player.lane = 7  # now its lane is lit
        bot._perceive()
        assert bot.view[8] == (20, 1)
        sim.state.player.lane = 0
        bot.skill = replace(bot.skill, memory=3.0)
        bot.frame += 10
        bot._perceive()
        assert 8 in bot.view and bot.view[8][0] >= 20  # remembered, and guessed lower
