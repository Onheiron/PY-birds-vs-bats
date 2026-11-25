"""Bird grades derived from XP."""

import functools

from src.core import constants
from src.entities.sprites import DARK_GRAY, GOLD, GREEN, ORANGE, RED, WHITE

_GRADE_LABELS = ('C1', 'C2', 'B1', 'B2', 'A1', 'A2', 'S')

_GRADE_COLORS = {'D': GREEN, 'C': ORANGE, 'B': WHITE, 'A': GOLD, 'S': RED}


@functools.lru_cache(maxsize=8)
def _grade_thresholds(base, factor):
    """XP needed for each grade, highest grade first: ((label, threshold), ...)."""
    pairs = [(label, int(round(base ** (factor**n)))) for n, label in enumerate(_GRADE_LABELS)]
    return tuple(reversed(pairs))


def grade_progress(xp):
    """Share (0..1) of the way from the current grade to the next one (1 at S)."""
    xp = float(xp)
    base = float(constants.progression.xp_base)
    factor = float(constants.progression.grade_exp_factor)
    steps = [0] + [t for _label, t in reversed(_grade_thresholds(base, factor))]
    for low, high in zip(steps, steps[1:]):
        if xp < high:
            return max(0.0, (xp - low) / max(1, high - low))
    return 1.0


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


def grade_steps():
    """XP at which each grade starts, lowest first: [0, C1, C2, ..., S] (the start grades of the
    meta progression index it)."""
    base = float(constants.progression.xp_base)
    factor = float(constants.progression.grade_exp_factor)
    return [0] + [threshold for _label, threshold in reversed(_grade_thresholds(base, factor))]
