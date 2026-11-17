"""Headless runs: the real game loop driven by a bot, on a virtual clock.

A run plays one whole game the way game.py would (same input handling, same
Session.step, same systems), but:

- time comes from a virtual clock advancing 1/60 s per frame, so a run takes
  as long as the computer needs, not as long as the game lasts;
- nothing is drawn, played or sent: no terminal, no sound, no leaderboard;
- the bot presses the keys.

Runs are deterministic for a given RunConfig.
"""

import random
import time
from dataclasses import dataclass, field

from src.core import constants, state
from src.engine import clock, input_handler, loop, progression
from src.services import optional, sound
from src.sim.bot import PROFILES, Bot, Skill
from src.sim.stats import RunStats

FRAME_DT = 1.0 / 60.0


@dataclass
class RunConfig:
    seed: int = 1
    difficulty: int = 1  # 0=PEACEFUL 1=ADVENTURE 2=SURVIVAL 3=LEGENDARY
    skill: Skill = field(default_factory=lambda: PROFILES['expert'])
    overrides: dict = field(default_factory=dict)  # merged over the configuration
    base_config: dict = None  # replaces config.yml (e.g. hardmode.yml loaded)
    formation: list = None  # starting flock, e.g. ['RED'] * 9
    start_level: int = 1
    max_minutes: float = 240.0  # game time limit
    stop_at_level: int = None  # end the run once this level is reached
    sample_seconds: float = 5.0  # how often the time series are sampled


class _VirtualTime:
    def __init__(self, start=1_700_000_000.0):
        self.now = start

    def __call__(self):
        return self.now


def _quiet_services():
    """No sound, no telemetry during simulations."""
    sound._backend = None
    optional.firebase_client = None


def run(config):
    """Play one game with the bot and return its RunStats."""
    _quiet_services()
    virtual = _VirtualTime()
    real_time = time.time
    time.time = virtual
    try:
        return _play(config, virtual)
    finally:
        time.time = real_time


def start_game(config, now):
    """Set up a fresh game for ``config`` at time ``now``; returns (bot, session)."""
    overrides = dict(config.overrides)
    if config.formation:
        overrides = constants_merge(overrides, {'birds': {'default_formation': list(config.formation)}})
    constants.configure(config.difficulty, base=config.base_config, overrides=overrides)

    state.init(config.seed)
    state.settings.difficulty = config.difficulty
    state.ui.show_title = False
    state.ui.menu_stack = []
    state.game.start_time = now
    state.game.last_mile_update = now

    if config.start_level > 1:
        milestones = progression.get_level_milestones()
        state.game.miles = float(milestones[config.start_level - 2]) + 0.01
        progression.update_miles(1e-9)

    return Bot(config.skill, seed=config.seed ^ 0x5EED), loop.Session()


def end_reason(config):
    """Why the game is over, or None while it goes on."""
    if state.game.game_over:
        return 'game over'
    if state.game.miles >= progression.get_level_milestones()[-1]:
        return 'completed'
    if config.stop_at_level and state.game.level >= config.stop_at_level:
        return f'reached level {config.stop_at_level}'
    return None


def _play(config, virtual):
    bot, session = start_game(config, virtual.now)
    stats = RunStats(config, progression.get_level_milestones())

    frames_limit = int(config.max_minutes * 60 / FRAME_DT)
    sample_every = max(1, int(config.sample_seconds / FRAME_DT))
    end = 'time limit'

    with stats.recording():
        for frame in range(frames_limit):
            for key in bot.press():
                input_handler.process_input(key)
            session.step()
            stats.seconds = frame * FRAME_DT

            if frame % sample_every == 0:
                stats.sample(frame * FRAME_DT)
            reason = end_reason(config)
            if reason:
                end = reason
                break
            virtual.now += FRAME_DT

    stats.finish(end, (frame + 1) * FRAME_DT, bot)
    return stats


def constants_merge(base, extra):
    from src.core.config import deep_merge

    return deep_merge(base, extra)


def run_many(configs, jobs=1):
    """Run several games, in parallel processes when jobs > 1."""
    if jobs <= 1:
        return [run(config).summary() for config in configs]
    import multiprocessing

    with multiprocessing.get_context('spawn').Pool(jobs, initializer=_worker_init) as pool:
        return pool.map(_run_summary, configs, chunksize=1)


def _worker_init():
    import os
    import sys
    import tempfile

    # Discoveries and settings are written under HOME: keep them away from the player's
    home = tempfile.mkdtemp(prefix='bvb-sim-')
    os.environ['HOME'] = os.environ['USERPROFILE'] = home
    sys.argv = sys.argv[:1]
    random.seed(0)


def _run_summary(config):
    return run(config).summary()


__all__ = ['RunConfig', 'run', 'run_many', 'clock']
