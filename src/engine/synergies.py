"""Synergies between birds in neighbouring lanes.

A synergy is "X next to Y does Z". Neighbours are the living birds in the
lanes right next to a bird (one to the left, one to the right). Patchwork has
a passive synergy with everyone: it counts as the partner of every synergy.

- Yellow next to Yellow: the Yellow power bounces it (see powers.py).
- Red or Purple next to Red: stronger Red shot (see powers.py).
- Yellow next to Blue: a scared Blue falling past a rising Yellow (at most
  ``yellow_cures_blue_rows`` rows apart) is no longer scared.
- Red next to Phoenix: each Red adds ``phoenix_per_red`` to the chance that UP
  wakes the dormant Phoenix egg.
- Yellow next to Clockwork: the Yellow power also adds
  ``yellow_clockwork_charge`` to the Clockwork's charge (see powers.py).
- Twister next to Blue: each Twister adds ``twister_sprint`` to the Blue's
  sprint after a bounce.
- Frosty or Poison next to Red or Purple: their shots freeze or poison what
  they hit (not the contact hits).
- Cookie next to Cookie: each Cookie neighbour adds ``cookie_xp`` to the XP a
  Cookie earns, so its crumbs carry more.

Values live in config.yml ``synergies``.
"""

from src.core import constants, state
from src.entities.bird_types import BirdType, get_bird_type_by_color


def value(key, default):
    return getattr(getattr(constants, 'synergies', None), key, default)


def kind(i):
    return get_bird_type_by_color(state.birds.colors[i])


def counts_as(i, *kinds):
    """Does bird ``i`` count as one of ``kinds`` for a synergy? (Patchwork counts as all.)"""
    k = kind(i)
    return k in kinds or k == BirdType.PATCHWORK


def neighbours(i):
    """Living birds in the lanes right next to bird ``i``."""
    lane = state.birds.random_lanes[i]
    return [
        j
        for j in range(len(state.birds.colors))
        if j != i and not state.birds.lost[j] and abs(state.birds.random_lanes[j] - lane) == 1
    ]


def count(i, *kinds):
    """How many neighbours of bird ``i`` count as one of ``kinds``."""
    return sum(1 for j in neighbours(i) if counts_as(j, *kinds))


def phoenix_wake_chance(i):
    base = getattr(constants.orange, 'recover_chance', 0.1)
    return min(1.0, base + value('phoenix_per_red', 0.05) * count(i, BirdType.RED))


def blue_sprint(i):
    """Extra sprint (×10 speed scale) a Blue gets from its Twister neighbours."""
    if kind(i) != BirdType.BLUE:
        return 0
    return value('twister_sprint', 4) * count(i, BirdType.TWISTER)


def xp_bonus(i):
    """Extra XP share a Cookie earns from its Cookie neighbours."""
    if kind(i) != BirdType.COOKIE:
        return 0.0
    return value('cookie_xp', 0.25) * count(i, BirdType.COOKIE)


def shot_afflictions(i):
    """Birds next to shooter ``i`` whose affliction its shots carry (Frosty, Poison)."""
    return [j for j in neighbours(i) if kind(j) in (BirdType.FROSTY, BirdType.POISON)]


def cure_blues():
    """Yellow next to Blue: a scared falling Blue passing a rising Yellow stops being scared."""
    scared = state.special.scared_birds
    if not scared:
        return
    rows = value('yellow_cures_blue_rows', 1)
    for i in list(scared):
        if state.birds.lost[i] or kind(i) != BirdType.BLUE or state.birds.vy[i] != 1:
            continue
        if i in state.special.stunned_birds:
            continue  # stunned by an impact, not scared
        for j in neighbours(i):
            if state.birds.vy[j] == -1 and counts_as(j, BirdType.YELLOW):
                if abs(state.birds.y[j] - state.birds.y[i]) <= rows:
                    del scared[i]
                    from src.engine import events, fx

                    fx.at_bird(i, '✓', 'GREEN', 0.6)
                    events.emit('power_effect', bird=j, kind='YELLOW', effect='blues cured', count=1)
                    break
