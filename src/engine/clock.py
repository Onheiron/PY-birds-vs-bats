"""The game clock: seconds of play, standing still while the game is paused.

Every timed effect (poison, stuns, spells, timelapse, despawn...) reads this
clock instead of the wall clock, so pausing freezes it and a saved game resumes
with the same time left on every effect.

The clock is the wall clock minus the time spent paused. Keeping that offset,
rather than counting from zero, leaves timestamps comparable to time.time().
"""

import time

from src.core import state


def now():
    """Current game time, in seconds."""
    return time.time() - state.game.clock_offset


def hold(seconds):
    """Stop the clock for ``seconds`` of wall time (the game was paused)."""
    state.game.clock_offset += seconds


def resume_at(game_time):
    """Set the clock so that it reads ``game_time`` now (used when loading)."""
    state.game.clock_offset = time.time() - game_time
