"""Short visual cues the game logic asks for (a bite, a blast, a cure...).

The logic adds a cue at a play-area cell with a colour name; the UI draws the
live ones (src/ui/layers/hazards.py) and they expire by themselves.
"""

from src.core import state
from src.engine import clock


def add(col, row, char, color='WHITE', seconds=0.4):
    """Show ``char`` at column ``col``, row ``row`` for ``seconds`` (``color``: a theme colour name)."""
    state.special.fx.append(
        {'col': int(col), 'row': int(row), 'char': char, 'color': color, 'until': clock.now() + seconds}
    )


def at_bird(i, char, color='WHITE', seconds=0.4):
    """A cue just above bird ``i``."""
    add(state.birds.cols[i], state.birds.y[i] - 1, char, color, seconds)


def live():
    """The cues still showing (expired ones are dropped)."""
    now = clock.now()
    state.special.fx = [f for f in state.special.fx if f['until'] > now]
    return state.special.fx
