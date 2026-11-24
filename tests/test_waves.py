"""Bat waves: a countdown, then the wave's bats a few at a time, until all are dead."""

from src.engine import bat_ai, clock, enemy_stats
from src.engine.logic import bat_behaviour, waves
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


def test_no_waves_in_the_first_world():
    with Simulation(seed=2, key_rate=0) as sim:
        sim.state.game.level_group = 1
        tick(sim.state, 500)
        assert sim.state.enemies.bat_wave is None and waves.card() is None


def run_plan(state, bat, seconds, step=1 / 30):
    """Run a wave bat's plan (and its descent) for ``seconds`` of game time."""
    phases = []
    for _ in range(int(seconds / step)):
        clock.resume_at(clock.now() + step)
        state.game.frame_count += 1
        bat_behaviour.update(bat)
        if not bat_behaviour.busy(bat) and bat['y_pos'] < bat['target_y']:
            bat['y_pos'] += 1
        if not phases or phases[-1] != bat['plan']['phase']:
            phases.append(bat['plan']['phase'])
    return phases


def plain_bat(sim, tier=2):
    state = sim.state
    wave = start_wave(sim)
    wave['tier'] = tier
    tick(state, 200)
    bat = waves.wave_bats()[0]
    for other in waves.wave_bats()[1:]:
        state.enemies.bats.remove(other)
    bat['kind'] = None
    return bat


def test_a_wave_bat_holds_spots_then_flies_out_and_comes_back_with_its_hp():
    with Simulation(seed=4, key_rate=0) as sim:
        state = sim.state
        bat = plain_bat(sim)
        bat['hp'] = 7
        phases = run_plan(state, bat, 40)
        assert {'enter', 'hold', 'move', 'leave', 'out'} <= set(phases)
        assert phases.index('hold') < phases.index('leave') < phases.index('out')
        assert phases.count('enter') >= 2  # came back in
        assert bat['hp'] == 7 and bat in state.enemies.bats


def test_higher_tiers_cruise_lower():
    with Simulation(seed=4, key_rate=0) as sim:
        bat = plain_bat(sim, tier=1)
        rows1 = [bat_behaviour._cruise_row(bat) for _ in range(50)]
        bat['tier'] = 4
        rows4 = [bat_behaviour._cruise_row(bat) for _ in range(50)]
        assert max(rows1) < min(rows4)


def test_a_boxed_in_wave_bat_leaves_from_the_top():
    with Simulation(seed=4, key_rate=0) as sim:
        state = sim.state
        bat = plain_bat(sim)
        bat['plan'] = {'phase': 'move', 'target_x': (bat['x_pos'] + 10) % 30, 'stops': 3, 'until': 0}
        real = bat_ai._check_bat_can_move
        bat_ai._check_bat_can_move = lambda b, x: False
        try:
            phases = run_plan(state, bat, 3)
        finally:
            bat_ai._check_bat_can_move = real
        assert 'leave' in phases


def test_the_spellcaster_picks_its_spot_by_its_spell():
    from src.entities.sprites import GOLD, RED

    with Simulation(seed=4, key_rate=0) as sim:
        birds = sim.state.birds
        for i in range(len(birds.colors)):
            birds.lost[i] = i >= 2
        birds.colors[0], birds.random_lanes[0] = RED, 1  # has a power: worth silencing
        birds.colors[1], birds.random_lanes[1] = GOLD, 7  # no power
        bat = {'kind': 'spellcaster', 'known_spells': ['silence'], 'tier': 3, 'x_pos': 0, 'y_pos': 5}
        weights = bat_behaviour.lane_weights(bat)
        assert bat['next_spell'] == 'silence'
        assert weights.get(1, 0) > 0 and 7 not in weights


def test_overlapping_bats_can_move_apart():
    with Simulation(seed=2, key_rate=0) as sim:
        state = sim.state
        start_wave(sim)
        tick(state, 200)
        a, b = waves.wave_bats()[:2]
        a['x_pos'], b['x_pos'] = 20, 23
        assert bat_ai._check_bat_can_move(a, 19)  # away from b
        assert not bat_ai._check_bat_can_move(a, 21)  # into b


def test_a_bat_never_moves_under_a_bird():
    with Simulation(seed=4, key_rate=0) as sim:
        state = sim.state
        bat = plain_bat(sim)
        birds = state.birds
        for i in range(len(birds.colors)):
            birds.lost[i] = i != 0
        from src.core import constants

        x = constants.layout.lane_positions[4]
        birds.random_lanes[0], birds.y[0] = 4, 6  # a bird high up in lane 4
        bat['y_pos'] = 10
        bat['x_pos'] = x + 6  # just right of lane 4
        assert not bat_ai._check_bat_can_move(bat, x - 3)  # sideways into lane 4: under the bird
        bat['x_pos'], bat['y_pos'] = x - 4, 2  # above the bird, in its lane
        assert not bat_ai.can_descend(bat) or bat['y_pos'] + 2 < 6
        bat['y_pos'] = 4  # its bottom row is 5: one more row and the bird would be level with it
        assert not bat_ai.can_descend(bat)
        birds.y[0] = 20  # the bird is far below: free to come down and across
        assert bat_ai.can_descend(bat)
