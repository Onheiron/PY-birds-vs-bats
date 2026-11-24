"""Bat waves: a countdown, then the wave's bats a few at a time, until all are dead."""

from src.engine import bat_ai, clock, enemy_stats
from src.engine.logic import waves
from src.engine.logic.spawning import process_spawn_queue, spawn_bat
from tests.harness import Simulation


def tick(state, n=1):
    for _ in range(n):
        spawn_bat()
        process_spawn_queue()


def start_wave(sim, world=3):
    state = sim.state
    state.game.level_group, state.game.level_sub = world, 1
    state.enemies.bats.clear()
    state.enemies.bat_wave = None
    tick(state)
    wave = state.enemies.bat_wave
    wave['starts_at'] = clock.now()  # skip the countdown
    return wave


def test_a_wave_is_announced_with_its_size_and_tier():
    with Simulation(seed=2, key_rate=0) as sim:
        sim.state.game.level_group, sim.state.game.level_sub = 3, 1
        sim.state.enemies.bat_wave = None
        tick(sim.state)
        card = waves.card()
        wave = sim.state.enemies.bat_wave
        assert card['title'].startswith(f'Wave {wave["number"]} in')
        assert f'{wave["size"]} bats, tier {wave["tier"]}' == card['text']
        assert not sim.state.enemies.spawn_queue and not sim.state.enemies.bats  # nothing before the start


def test_a_wave_never_has_more_than_max_bats_at_once_and_ends_when_all_are_dead():
    with Simulation(seed=2, key_rate=0) as sim:
        state = sim.state
        wave = start_wave(sim)
        max_bats = enemy_stats.world_table()['max_bats']
        tick(state, 2000)
        assert len(waves.wave_bats()) == max_bats
        assert wave['spawned'] == max_bats < wave['size']
        while wave['spawned'] < wave['size'] or waves.wave_bats():
            state.enemies.bats.clear()  # all killed
            tick(state, 200)
        assert state.enemies.bat_wave['number'] == wave['number'] + 1  # the next one is coming
        assert state.enemies.bat_wave['starts_at'] > clock.now()


def test_a_wave_bat_at_a_side_comes_back_from_the_top_with_its_hp():
    with Simulation(seed=2, key_rate=0) as sim:
        state = sim.state
        start_wave(sim)
        tick(state, 200)
        bat = waves.wave_bats()[0]
        bat['hp'], bat['y_pos'], bat['x_pos'], bat['direction'] = 7, 10, 1, -1
        for _ in range(12):
            state.game.frame_count += 1
            bat_ai._move_horizontally(bat)
            if bat['y_pos'] < 0:
                break
        assert bat['y_pos'] < 0 and bat['hp'] == 7 and bat in state.enemies.bats


def test_no_waves_in_the_first_world():
    with Simulation(seed=2, key_rate=0) as sim:
        sim.state.game.level_group = 1
        tick(sim.state, 500)
        assert sim.state.enemies.bat_wave is None and waves.card() is None
