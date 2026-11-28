"""Bird stats: every number that describes how a bird flies, fights and scores.

A stat's value for one bird is built in layers:

    value = (default + type value + grade growth + flat modifiers) × product of
            multiplier modifiers, clamped to the stat's range

- defaults, values per bird type and growth per grade come from the
  ``bird_stats`` section of config.yml;
- modifiers are added at runtime (cards, boosts, pacts) with an optional
  duration in game seconds, for one bird or for the whole flock.

Speeds are on a ×10 scale (20 = the old speed 2). The bird's current speed in
points lives in ``state.birds.speeds`` (``speed`` / 10 when it hatches) and
changes with some mechanics (Clockwork charge, Stealth power...); the
movement bonuses are added on top of it.
"""

from dataclasses import dataclass

from src.core import constants, state
from src.engine import clock
from src.engine.grades import compute_grade_from_xp
from src.entities.bird_types import get_bird_type_by_color

GRADES = ('D', 'C1', 'C2', 'B1', 'B2', 'A1', 'A2', 'S')


@dataclass(frozen=True)
class StatDef:
    default: float
    minimum: float = float('-inf')
    maximum: float = float('inf')
    description: str = ''


BIRD_STATS = {
    # Base
    'speed': StatDef(20, 0, 100, 'base speed (10 = 1 cell every 5 ticks, 50+ = 1 cell per tick)'),
    'damage': StatDef(10, 0, 99999, 'base contact damage'),
    # Movement
    'rise_speed_bonus': StatDef(0, -40, 40, 'speed added while rising'),
    'fall_speed_bonus': StatDef(0, -40, 40, 'speed added while falling (negative: falls slower)'),
    'bounce_sprint': StatDef(0, 0, 40, 'speed added for a moment after each bounce'),
    'bounce_sprint_seconds': StatDef(1.0, 0, 10, 'how long the bounce sprint lasts'),
    'weight': StatDef(1.0, 0, 10, 'share of the flock centre of mass (drives momentum)'),
    'presses_to_bounce': StatDef(1, 1, 99, 'UP presses needed to bounce it'),
    'hitbox_height': StatDef(2, 1, 5, 'rows the bird occupies when colliding'),
    'hitbox_width': StatDef(5, 1, 15, 'columns the bird occupies when colliding (centred on its lane)'),
    # Attack
    'damage_bonus': StatDef(0, 0, 999, 'flat damage added to the base damage'),
    'damage_mult': StatDef(1.0, 0, 100, 'multiplier on all damage dealt'),
    'speed_damage': StatDef(1.0, 1, 5, 'how strongly current speed multiplies damage (1 = damage × speed, never less)'),
    'vs_bats': StatDef(0, -1, 10, 'extra damage against bats (0.5 = +50%)'),
    'vs_obstacles': StatDef(0, -1, 10, 'extra damage against obstacles'),
    'vs_elites': StatDef(0, -1, 10, 'extra damage against elites and bosses'),
    'armor_pierce': StatDef(0, 0, 99, 'armor points ignored'),
    'crit_chance': StatDef(0, 0, 0.5, 'chance of a critical hit (at most 50%)'),
    'crit_damage': StatDef(2.0, 1, 20, 'damage multiplier of a critical hit'),
    'affliction_chance': StatDef(0, 0, 1, "chance to apply the bird's affliction (freeze, poison, bleed) on hit"),
    'knockback': StatDef(0, 0, 10, 'rows a hit pushes a bat back up'),
    'impact_stun': StatDef(1.0, 0, 5, 'multiplier on the stun suffered when hitting something that survives'),
    # Fear
    'fear_resist': StatDef(0, 0, 0.6, 'share of the fear fall-speed bonus ignored (at most 60%)'),
    'fear_duration_mult': StatDef(1.0, 0, 5, 'multiplier on fear duration'),
    'fear_duration_cut': StatDef(0, 0, 10, 'seconds removed from fear (never below 1 s)'),
    'fear_immunity': StatDef(0, 0, 0.5, 'chance to ignore a scare entirely (at most 50%)'),
    # Power
    'power_uses': StatDef(1, 0, 10, 'power activations per ascent'),
    'power_potency': StatDef(1.0, 0, 10, 'multiplier on power strength'),
    'power_duration': StatDef(1.0, 0, 10, 'multiplier on power duration'),
    # Survival
    'floor_save': StatDef(0, 0, 1, 'chance to bounce back instead of being lost at the floor'),
    # Economy
    'prestige': StatDef(0, 0, 99, 'prestige the bird adds to the flock'),
    'score_mult': StatDef(1.0, 0, 100, 'score multiplier for this kind of bird'),
    'score_grade_bonus': StatDef(0, 0, 10, 'score bonus from grade (+0.1 = ×1.1)'),
    'xp_gain': StatDef(1.0, 0, 10, 'multiplier on XP earned'),
    'pickup_radius': StatDef(2, 0, 10, 'columns within which it collects loot'),
    'luck': StatDef(0, 0, 1, 'chance to upgrade the rarity of what it collects'),
}

# Stats of the flock as a whole (not of one bird): modified with target 'flock'
FLOCK_STATS = {
    'choices': StatDef(3, 1, 6, 'options offered by an egg'),
    'egg_luck': StatDef(0, 0, 0.25, 'luck: chance that an enemy drop is one rarity higher'),
    'egg_time': StatDef(0, 0, 30, 'seconds more a dropped egg lasts (and rises) before it is gone'),
    'prestige_bonus': StatDef(0, 0, 999, 'prestige added to the flock (before prestige_mult)'),
    'prestige_mult': StatDef(1, 0.1, 100, 'multiplier on the whole prestige'),
    'elite_chance': StatDef(0, 0, 1, 'added to the chance that a bat spawns as an elite'),
    'card_max_level': StatDef(6, 1, 10, 'times a card type can be taken in a run'),
    'card_types': StatDef(4, 1, 7, 'different card types a run can follow'),
}

# Bird types cards and pacts leave alone
UNBOOSTED_TYPES = ('GOLD',)

# Modifiers: {'target': bird index or 'flock', 'stat', 'add', 'mul', 'until', 'source'}
_cache = {}
_cache_key = [None]


def _config():
    return getattr(constants, 'bird_stats', None)


def _table(section, key):
    """A {stat: value} table from the bird_stats config (missing tables are empty)."""
    node = getattr(_config(), section, None)
    if node is None:
        return {}
    node = getattr(node, key, None) if not isinstance(node, dict) else node.get(key)
    if node is None:
        return {}
    return node if isinstance(node, dict) else vars(node)


def _defaults():
    node = getattr(_config(), 'defaults', None)
    if node is None:
        return {}
    return node if isinstance(node, dict) else vars(node)


def type_of(i):
    return get_bird_type_by_color(state.birds.colors[i])


def grade_of(i):
    label, _ = compute_grade_from_xp(state.birds.per_bird_xp[i])
    return label


def _growth(bird_type, grade):
    """Grade bonuses: each stat takes the value of the highest grade reached that sets it.

    Generic growth and per-type growth (``type_growth: {RED_A1: {...}}``) add up.
    """
    generic, typed = {}, {}
    reached = GRADES[: GRADES.index(grade) + 1] if grade in GRADES else ('D',)
    for name in reached:
        generic.update(_table('growth', name))
        typed.update(_table('type_growth', f'{bird_type}_{name}'))
    for stat, value in typed.items():
        generic[stat] = generic.get(stat, 0) + value
    return generic


def base(i, name):
    """Value before modifiers: default, then type value, then grade growth."""
    definition = BIRD_STATS[name]
    bird_type = type_of(i) or 'YELLOW'
    value = _defaults().get(name, definition.default)
    value = _table('types', bird_type).get(name, value)
    value += _growth(bird_type, grade_of(i)).get(name, 0)
    return value


def _modifier_terms(i, name):
    add, mul = 0.0, 1.0
    # Cards and pacts do not touch the Gold bird (keeping it alive must stay a task)
    unboosted = type_of(i) in UNBOOSTED_TYPES
    for mod in state.stats.modifiers:
        if unboosted and str(mod.get('source', '')).startswith(('card:', 'pact:')):
            continue
        if mod['stat'] == name and mod['target'] in (i, 'flock'):
            add += mod.get('add', 0)
            mul *= mod.get('mul', 1)
    return add, mul


def bird(i, name):
    """Current value of stat ``name`` for bird ``i``."""
    key = (state.game.frame_count, state.stats.version)
    if _cache_key[0] != key:
        _cache.clear()
        _cache_key[0] = key
    cached = _cache.get((i, name, state.birds.colors[i], state.birds.per_bird_xp[i]))
    if cached is not None:
        return cached
    definition = BIRD_STATS[name]
    add, mul = _modifier_terms(i, name)
    value = (base(i, name) + add) * mul
    value = max(definition.minimum, min(definition.maximum, value))
    _cache[(i, name, state.birds.colors[i], state.birds.per_bird_xp[i])] = value
    return value


def add_modifier(target, stat, add=0.0, mul=1.0, seconds=None, source=''):
    """Change a stat for one bird (index) or for the whole flock ('flock')."""
    if stat not in BIRD_STATS and stat not in FLOCK_STATS:
        raise KeyError(f'unknown stat {stat!r}')
    if stat in FLOCK_STATS and target != 'flock':
        raise ValueError(f'{stat!r} is a flock stat: its target must be "flock"')
    until = None if seconds is None else clock.now() + seconds
    state.stats.modifiers.append(
        {'target': target, 'stat': stat, 'add': add, 'mul': mul, 'until': until, 'source': source}
    )
    state.stats.version += 1


def clear_bird(i):
    """Drop the modifiers of one bird (it was lost or replaced)."""
    before = len(state.stats.modifiers)
    state.stats.modifiers[:] = [m for m in state.stats.modifiers if m['target'] != i]
    if len(state.stats.modifiers) != before:
        state.stats.version += 1


def expire_modifiers():
    """Remove modifiers whose time is up (run once per tick)."""
    now = clock.now()
    before = len(state.stats.modifiers)
    state.stats.modifiers[:] = [m for m in state.stats.modifiers if m['until'] is None or m['until'] > now]
    if len(state.stats.modifiers) != before:
        state.stats.version += 1


def flock(name):
    """Current value of the flock stat ``name`` (choices per egg, egg luck...)."""
    definition = FLOCK_STATS[name]
    add, mul = 0.0, 1.0
    for mod in state.stats.modifiers:
        if mod['stat'] == name:
            add += mod.get('add', 0)
            mul *= mod.get('mul', 1)
    return max(definition.minimum, min(definition.maximum, (definition.default + add) * mul))


def flock_bird_stat(name):
    """A bird stat as the cards, pacts and upgrades set it for the whole flock (no bird type, no grade)."""
    definition = BIRD_STATS[name]
    add, mul = 0.0, 1.0
    for mod in state.stats.modifiers:
        if mod['stat'] == name and mod['target'] == 'flock':
            add += mod.get('add', 0)
            mul *= mod.get('mul', 1)
    return max(definition.minimum, min(definition.maximum, (definition.default + add) * mul))


def duration_mult():
    """How much longer timed cards and power-ups last: the flock's power_duration (Lasting Powers...)."""
    return flock_bird_stat('power_duration') / BIRD_STATS['power_duration'].default


def type_value(bird_type, name):
    """Value of stat ``name`` for a kind of bird at grade D, before modifiers."""
    value = _defaults().get(name, BIRD_STATS[name].default)
    return _table('types', bird_type).get(name, value)


def speed_points(bird_type):
    """Starting speed of a kind of bird in the movement code's points (speed / 10)."""
    return type_value(bird_type, 'speed') / 10


def describe(i):
    """Every stat of bird ``i`` with its value (for debugging and the Birdpedia)."""
    return {name: bird(i, name) for name in BIRD_STATS}
