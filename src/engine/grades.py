"""Bird grades derived from XP."""

from src.core import constants
import functools
from src.entities.sprites import DARK_GRAY, GOLD, GREEN, ORANGE, RED, WHITE

_GRADE_LABELS = ('C1', 'C2', 'B1', 'B2', 'A1', 'A2', 'S')

_GRADE_COLORS = {'D': GREEN, 'C': ORANGE, 'B': WHITE, 'A': GOLD, 'S': RED}


@functools.lru_cache(maxsize=8)
def _grade_thresholds(base, factor):
    """XP needed for each grade, highest grade first: ((label, threshold), ...)."""
    pairs = [(label, int(round(base ** (factor ** n)))) for n, label in enumerate(_GRADE_LABELS)]
    return tuple(reversed(pairs))


def compute_grade_from_xp(xp):
    """Return (grade_label, color) tuple for given XP value."""
    xp = int(float(xp))

    base = float(constants.progression.xp_base)
    factor = float(constants.progression.grade_exp_factor)

    if xp < int(base):
        return ('D', GREEN)

    for label, threshold in _grade_thresholds(base, factor):
        if xp >= threshold:
            return (label, _GRADE_COLORS.get(label[0], DARK_GRAY))

    return ('C1', ORANGE)
