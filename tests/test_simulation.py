"""End-to-end behaviour of the real game loop, run headless and deterministically."""

import time

import pytest

from tests.harness import Screen, Simulation

BOSS_BY_LEVEL = {3: 'normal', 6: 'wind', 9: 'jelly', 12: 'tree', 15: 'owl', 18: 'normal'}


def run_digests(seed, **kwargs):
    with Simulation(seed=seed, **kwargs) as sim:
        return sim.run(600, digest_every=60)


def test_same_seed_replays_identically():
    first = run_digests(42, level=4, all_birds=True)
    second = run_digests(42, level=4, all_birds=True)
    assert first == second


def test_different_seeds_diverge():
    assert run_digests(1, level=4) != run_digests(2, level=4)


@pytest.mark.parametrize('level', [1, 4, 7, 10, 13, 16])
def test_every_biome_runs_and_keeps_state_consistent(level):
    with Simulation(seed=100 + level, level=level, all_birds=True) as sim:
        state = sim.state
        constants = sim.constants
        num_birds = constants.layout.num_balls
        for _ in range(40):
            sim.run(50)
            assert state.game.level_group == (level - 1) // 3 + 1
            # Per-bird arrays never go out of step
            for name in ('colors', 'cols', 'y', 'vy', 'speeds', 'lost', 'power_used', 'random_lanes', 'per_bird_xp'):
                assert len(getattr(state.birds, name)) == num_birds, name
            for lane in state.birds.random_lanes:
                assert 0 <= lane < constants.layout.num_lanes
            assert 1 <= state.game.speed <= constants.speed.max_speed
            assert state.game.score >= 0
        assert state.game.frame_count > 0
        assert sim.screen.text().strip()


@pytest.mark.parametrize('level, boss_type', sorted(BOSS_BY_LEVEL.items()))
def test_boss_spawns_at_the_end_of_each_biome(level, boss_type):
    with Simulation(seed=level, level=level, all_birds=True, near_boss=True) as sim:
        state = sim.state
        sim.run(30)
        boss = state.enemies.boss
        assert boss is not None, 'boss should spawn within the last mile of a boss level'
        assert boss['boss_type'] == boss_type
        miles = state.game.miles
        # The fight runs without errors and the level cannot end while the boss lives
        for _ in range(30):
            sim.run(50)
            if state.enemies.boss is None:
                break
            assert state.game.miles == miles
            assert state.enemies.boss['hp'] <= state.enemies.boss['max_hp']


def test_no_boss_away_from_the_end_of_a_level():
    with Simulation(seed=5, level=6) as sim:
        sim.run(300)
        assert sim.state.enemies.boss is None


def test_losing_every_bird_ends_the_game():
    with Simulation(seed=3, key_rate=0.0) as sim:
        state = sim.state
        for _ in range(20_000):
            sim.step(key=None, render=False)
            if state.game.game_over:
                break
        assert state.game.game_over
        assert state.game.lives <= 0 or all(state.birds.lost)


def _world_snapshot(state):
    return repr((state.birds.y, state.birds.vy, state.enemies.obstacles, state.enemies.bats, state.game.frame_count))


def test_pause_freezes_the_simulation():
    with Simulation(seed=9) as sim:
        state = sim.state
        sim.run(120)
        sim.step(key='p')
        assert state.game.paused
        frozen = _world_snapshot(state)
        miles = state.game.miles
        for _ in range(60):
            sim.step(key=None)
        assert _world_snapshot(state) == frozen
        assert state.game.miles == miles
        sim.step(key='p')
        assert not state.game.paused
        sim.run(60)
        assert state.game.miles > miles
        assert _world_snapshot(state) != frozen


def test_frame_output_reproduces_a_full_redraw():
    """After thousands of differential updates the terminal shows exactly what a
    clean repaint of the same frame would show."""
    # Default flock only: PATCHWORK and RAINBOW birds pick random colours per frame
    with Simulation(seed=11, level=13) as sim:
        state = sim.state
        state.settings.parallax_enabled = True
        sim.run(900)
        state.game.paused = True  # freeze the world; the pause overlay is drawn too
        for _ in range(3):
            sim.screen.feed(sim.render_frame())  # differential update

        sim.fb.first_frame = True
        repaint = Screen(sim.fb.width, sim.fb.height)
        repaint.feed(sim.render_frame())  # full repaint
        assert sim.screen.text() == repaint.text()
        assert sim.screen.cells == repaint.cells


def test_rendering_fits_comfortably_in_the_frame_budget():
    """A frame must cost a small fraction of the 16.6 ms available at 60 FPS."""
    with Simulation(seed=8, level=15, all_birds=True, near_boss=True) as sim:
        sim.screen.feed = lambda data: None  # measure the game, not the test terminal
        sim.run(120)  # warm caches
        frames = 600
        start = time.perf_counter()
        sim.run(frames)
        per_frame = (time.perf_counter() - start) / frames
    assert per_frame < 0.008, f'{per_frame * 1000:.2f} ms per frame'


def test_output_stays_small_between_frames():
    """Differential rendering: a typical frame sends well under a kilobyte."""
    with Simulation(seed=4, level=4, all_birds=True) as sim:
        sim.run(60)
        before = sim.output_bytes
        sim.run(600)
        assert (sim.output_bytes - before) / 600 < 1500
