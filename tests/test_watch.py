"""Watch mode: the bot playing on screen."""

import time

from src.core import state
from src.engine import timing
from src.sim import watch
from src.sim.runner import RunConfig, run
from src.ui import keyboard, terminal


def test_watching_shows_the_same_game_the_simulator_measures(monkeypatch):
    monkeypatch.setattr(keyboard, 'read_keys', lambda text=False: [])
    monkeypatch.setattr(terminal, 'write_frame', lambda output: None)
    monkeypatch.setattr(timing.FrameClock, 'wait', lambda self: None)

    args = watch.build_parser().parse_args(['--bot', 'perfect', '--seed', '4', '--speed', '16'])
    config = RunConfig(seed=4, skill=watch.skill_from(args), stop_at_level=3, max_minutes=30)

    real_time = time.time
    virtual = watch.VirtualTime()
    time.time = virtual
    try:
        viewer = watch.Watch(args, config)
        viewer.show_result = lambda clock: None
        end, minutes = viewer.play(virtual, more_games=False)
    finally:
        time.time = real_time
    watched = (end, state.game.level, int(state.game.score), round(state.game.miles, 2))

    simulated = run(config).summary()
    assert end == 'reached level 3'
    assert watched == (simulated['end'], simulated['level'], simulated['score'], simulated['miles'])
    assert round(minutes, 2) == simulated['minutes']
