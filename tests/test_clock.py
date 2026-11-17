"""The game clock: timed effects stand still while the game is paused."""

from src.engine import clock
from src.services import save_manager
from tests.harness import FRAME_DT, Simulation


def pause_for(sim, seconds):
    sim.step(key='p')
    assert sim.state.game.paused
    for _ in range(int(seconds / FRAME_DT)):
        sim.step(key=None, render=False)
    sim.step(key='ESC')  # RESUME from the pause menu root
    assert not sim.state.game.paused


def alive_bird(state):
    return next(i for i, lost in enumerate(state.birds.lost) if not lost)


def test_clock_stops_while_paused():
    with Simulation(seed=1, key_rate=0) as sim:
        sim.run(60)
        before = clock.now()
        pause_for(sim, 30)
        # Only the frames around the pause went by, not the 30 paused seconds
        assert clock.now() - before < 0.2


def test_poison_does_not_tick_during_a_pause():
    with Simulation(seed=2, key_rate=0) as sim:
        state = sim.state
        sim.run(30)
        bird = alive_bird(state)
        state.special.poisoned_birds[bird] = {'death_time': clock.now() + 5.0, 'cure_attempts_needed': 99}

        pause_for(sim, 60)
        sim.run(10, immortal=False)
        assert not state.birds.lost[bird], 'a minute of pause must not let the poison kill'

        sim.run(int(6 / FRAME_DT), immortal=False)
        assert bird not in state.special.poisoned_birds


def test_loot_does_not_despawn_during_a_pause():
    with Simulation(seed=3, key_rate=0) as sim:
        state = sim.state
        sim.run(30)
        loot = {'x_pos': 5, 'y_pos': 0, 'type': 'tailwind', 'rarity': 'common', 'spawn_ts': clock.now()}
        state.items.loot_items.append(loot)
        pause_for(sim, 120)
        sim.step(key=None)
        assert loot in state.items.loot_items or loot['y_pos'] > 0


def test_saved_effects_keep_their_remaining_time():
    with Simulation(seed=4, key_rate=0) as sim:
        state = sim.state
        sim.run(30)
        bird = alive_bird(state)
        state.special.poisoned_birds[bird] = {'death_time': clock.now() + 5.0, 'cure_attempts_needed': 99}
        assert save_manager.save_game(1)

        sim.clock.advance(3600)  # an hour later
        assert save_manager.load_game(1)
        remaining = state.special.poisoned_birds[bird]['death_time'] - clock.now()
        assert 4.9 < remaining <= 5.0
        save_manager.delete_save(1)
