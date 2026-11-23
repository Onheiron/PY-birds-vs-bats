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


def test_the_cave_light_fades_from_the_cursor_and_fireflies_lift_it():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 5)
        game_state.hazards.light_until = 0
        sim.state.player.lane = 4
        for i in range(len(game_state.birds.colors)):
            game_state.birds.colors[i] = game_state.birds.colors[0]  # no Clockwork lights
        level = hazards.darkness_levels()
        mid = sim.constants.layout.height // 2
        assert [level(lane, mid) for lane in (4, 5, 6, 7)] == [0, 1, 2, 3]
        assert level(4, 0) == 3 and level(4, 2) == 1  # the top rows fade into the dark
        assert not hazards.visible(7, mid) and hazards.visible(6, mid)
        hazards.collect_firefly()
        level = hazards.darkness_levels()
        assert [level(lane, mid) for lane in (4, 5, 6, 7, 8)] == [0, 0, 1, 2, 3]  # one level lighter
        in_world(sim, 4)
        assert not hazards.dark()


def test_stalactites_warn_then_fall_from_the_top():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 5)
        sim.state.enemies.obstacles[:] = []
        game_state.hazards.next_stalactite = clock.now() - 1
        hazards.update()
        assert len(game_state.hazards.stalactite_warnings) == 1
        game_state.hazards.stalactite_warnings[0]['falls_at'] = clock.now() - 1
        hazards.update()
        stalactite = [o for o in sim.state.enemies.obstacles if o.get('kind') == 'stalactite'][0]
        assert enemy_stats.get(stalactite, 'fall_interval') == 3


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


def test_a_portal_never_puts_two_birds_in_one_lane():
    from src.engine.logic import portals

    with Simulation(seed=3, key_rate=0) as sim:
        birds = game_state.birds
        for i in range(len(birds.colors)):
            birds.random_lanes[i] = i
            birds.lost[i] = False
        sim.state.enemies.portals[:] = [
            {'pair_id': 1, 'portal_idx': 0, 'lane': 2, 'y_pos': 10, 'height': 2, 'from_owl_boss': True},
            {'pair_id': 1, 'portal_idx': 1, 'lane': 6, 'y_pos': 10, 'height': 2, 'from_owl_boss': True},
        ]
        birds.y[2], birds.vy[2] = 10, -1
        portals._check_bird_portal_teleport()
        lanes = [birds.random_lanes[i] for i in range(len(birds.colors)) if not birds.lost[i]]
        assert birds.random_lanes[2] == 6 and len(set(lanes)) == len(lanes)


def test_an_obstacle_coming_down_on_a_falling_bird_pushes_it_below():
    from src.engine.logic.collisions import keep_birds_below_enemies

    with Simulation(seed=3, key_rate=0) as sim:
        birds = game_state.birds
        for i in range(len(birds.colors)):
            birds.random_lanes[i] = i
            birds.lost[i] = i != 4
        birds.y[4], birds.vy[4] = 12, 1
        rock = enemy_stats.equip_obstacle(
            {'id': 9, 'lane': 4, 'y_pos': 11, 'tier': 1, 'hp': 50, 'sprite': ['##', '##'], 'sprite_width': 2}
        )
        sim.state.enemies.obstacles[:] = [rock]
        sim.state.enemies.bats[:] = []
        keep_birds_below_enemies()
        assert birds.y[4] == 13  # below the obstacle, never above


def test_emerging_obstacles_appear_above_the_birds():
    with Simulation(seed=3, key_rate=0) as sim:
        in_world(sim, 3)
        birds = game_state.birds
        for i in range(len(birds.colors)):
            birds.random_lanes[i] = i
            birds.lost[i] = False
            birds.y[i] = 8
        obstacle = {'id': 1, 'lane': 4, 'y_pos': -2, 'tier': 1, 'hp': 50, 'sprite': ['##'], 'sprite_width': 2}
        assert hazards.place_emerging(obstacle)
        assert obstacle['y_pos'] + 1 < 8
