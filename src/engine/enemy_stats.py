"""Enemy stats: the numbers that make a bat or an obstacle tough, scary or rewarding.

Stats are resolved once, when the enemy spawns, and stored in the enemy's
``stats`` dict (so they are saved with it). Layers, from the ``enemy_stats``
section of config.yml:

    default → per tier → per kind (armored, diver, spellcaster) → elite affixes

Flat stats add up along the layers, multiplier stats (``MULTIPLIERS``)
multiply. An enemy without a ``stats`` dict (boss minions, old saves) uses
the defaults, which leave the game as it was before stats existed.

Elites are bats that spawn with extra HP, one or more affixes (``elites.affixes``)
and better rewards; birds' ``vs_elites`` bonus applies against them.
"""

import random

from src.core import constants, state
from src.engine import clock

ENEMY_STATS = {
    # Toughness
    'hp_mult': (1.0, 'multiplier on spawn HP'),
    'defense': (0, 'damage removed from every hit'),
    'contact_defense': (0, 'damage removed from bird contact hits'),
    'projectile_defense': (0, 'damage removed from projectile hits'),
    'armor': (0, 'damage removed from contact hits; lowered by freeze, bleed and armor pierce'),
    'damage_taken': (1.0, 'multiplier on damage received'),
    'regen': (0, 'HP regenerated per second (up to max HP)'),
    # Threat
    'fear_strength': (1.0, 'multiplier on how long its scare lasts'),
    'fear_radius': (0, 'lanes on each side also scared on contact'),
    'speed': (1.0, 'horizontal speed multiplier'),
    'descent_interval': (5, 'ticks per row while descending to its height'),
    # Rewards
    'xp_mult': (1.0, 'multiplier on kill XP'),
    'score_mult': (1.0, 'multiplier on kill score'),
    'loot_rarity_bonus': (0, 'rarity steps added to its drop'),
}
MULTIPLIERS = {'hp_mult', 'damage_taken', 'fear_strength', 'speed', 'xp_mult', 'score_mult'}
RARITIES = ('common', 'uncommon', 'rare', 'epic', 'legendary', 'mythical')


def _node(parent, key):
    if parent is None:
        return None
    if isinstance(parent, dict):
        return parent.get(key, parent.get(str(key)))
    return getattr(parent, str(key), None)


def _as_dict(node):
    if node is None:
        return {}
    return node if isinstance(node, dict) else vars(node)


def _config(family):
    return _node(getattr(constants, 'enemy_stats', None), family)


def _apply(values, layer):
    for name, value in _as_dict(layer).items():
        if name not in ENEMY_STATS:
            raise KeyError(f'unknown enemy stat {name!r}')
        if name in MULTIPLIERS:
            values[name] = values.get(name, ENEMY_STATS[name][0]) * value
        else:
            values[name] = values.get(name, ENEMY_STATS[name][0]) + value


def resolve(family, tier, kinds=(), affixes=(), elite=False, extra=None):
    """Stats of a new enemy of ``family`` ('bats' or 'obstacles'), as a dict of the non-default values.

    ``extra`` is one more flat/multiplier layer applied first (e.g. the armor of an armored bat).
    """
    cfg = _config(family)
    values = {}
    _apply(values, extra)
    _apply(values, _node(cfg, 'defaults'))
    _apply(values, _node(_node(cfg, 'tiers'), tier))
    for kind in kinds:
        _apply(values, _node(_node(cfg, 'kinds'), kind))
    elites = getattr(constants, 'elites', None)
    if elite:
        _apply(values, _node(elites, 'stats'))
    for affix in affixes:
        _apply(values, _node(_node(_node(elites, 'affixes'), affix), 'stats'))
    return {name: value for name, value in values.items() if value != ENEMY_STATS[name][0]}


def get(enemy, name):
    """Current value of stat ``name`` for an enemy dict."""
    stats = enemy.get('stats')
    if stats and name in stats:
        return stats[name]
    return ENEMY_STATS[name][0]


def mitigate(enemy, damage, hit='contact', bird=None, armor_cut=0):
    """Damage left after the enemy's defences (never below 1).

    ``hit`` is 'contact' or 'projectile'; armor only stops contact hits and is
    lowered by ``armor_cut`` (debuffs) and the hitting bird's armor pierce.
    """
    reduction = get(enemy, 'defense') + get(enemy, f'{hit}_defense')
    if hit == 'contact':
        armor = get(enemy, 'armor') - armor_cut
        if bird is not None:
            from src.engine import stats

            armor -= stats.bird(bird, 'armor_pierce')
        reduction += max(0, armor)
    taken = get(enemy, 'damage_taken')
    if taken != 1:
        damage = round(damage * taken)
    return max(1, damage - reduction)


def elite_chance():
    """Chance that a bat spawning now is an elite (by biome, ``elites.chance_by_biome``)."""
    table = _node(getattr(constants, 'elites', None), 'chance_by_biome')
    if not table:
        return 0.0
    group = max(1, state.game.level_group)
    return float(table[min(group, len(table)) - 1])


def roll_elite():
    """Affixes for a new bat: empty unless it rolled elite. Uses no randomness when the chance is 0."""
    chance = elite_chance()
    if chance <= 0 or random.random() >= chance:
        return []
    elites = constants.elites
    names = sorted(_as_dict(_node(elites, 'affixes')))
    if not names:
        return []
    counts = _node(elites, 'affix_count_by_biome') or [1]
    count = int(counts[min(max(1, state.game.level_group), len(counts)) - 1])
    return random.sample(names, min(count, len(names)))


def affix_names(affixes):
    """Display names of an elite's affixes ('Swift Regenerating')."""
    table = _node(getattr(constants, 'elites', None), 'affixes')
    return ' '.join(str(_node(_node(table, a), 'name') or a.title()) for a in affixes)


def bat_kinds(bat):
    """Kinds of a bat, in the order their stat layers apply."""
    return [k for k in ('armored', 'diver', 'spellcaster') if bat.get(k)]


def regenerate():
    """Heal regenerating enemies (run once per tick)."""
    now = clock.now()
    for enemy in state.enemies.bats:
        rate = get(enemy, 'regen')
        if rate <= 0:
            continue
        last = enemy.setdefault('regen_ts', now)
        pool = enemy.get('regen_pool', 0.0) + rate * (now - last)
        whole = int(pool)
        enemy['regen_pool'] = pool - whole
        enemy['regen_ts'] = now
        if whole:
            enemy['hp'] = min(enemy.get('max_hp', enemy['hp']), enemy['hp'] + whole)


def _armored_armor(tier):
    """Armor of an armored bat of ``tier`` (``bat_enemy.armored.damage_reduction_by_tier``)."""
    armored_cfg = getattr(constants.bat_enemy, 'armored', None)
    table = _node(armored_cfg, 'damage_reduction_by_tier')
    return _node(table, tier) or 0


def equip_bat(bat, affixes=()):
    """Give a freshly built bat its stats (tier, kinds, elite affixes) and scale its HP."""
    extra = {'armor': _armored_armor(bat['tier'])} if bat.get('armored') else None
    if affixes:
        bat['elite'] = True
        bat['affixes'] = list(affixes)
    bat['stats'] = resolve('bats', bat['tier'], bat_kinds(bat), affixes, elite=bool(affixes), extra=extra)
    hp_mult = get(bat, 'hp_mult')
    if hp_mult != 1:
        bat['hp'] = bat['max_hp'] = max(1, int(bat['hp'] * hp_mult))
    return bat


def equip_obstacle(obstacle):
    """Give a freshly built obstacle its stats and scale its HP."""
    obstacle['stats'] = resolve('obstacles', obstacle.get('tier', 1))
    hp_mult = get(obstacle, 'hp_mult')
    if hp_mult != 1:
        obstacle['hp'] = max(1, int(obstacle['hp'] * hp_mult))
    return obstacle


def upgrade_rarity(rarity, steps):
    """``rarity`` moved up by ``steps`` (capped at mythical)."""
    steps = int(steps)
    if steps <= 0 or rarity not in RARITIES:
        return rarity
    return RARITIES[min(len(RARITIES) - 1, RARITIES.index(rarity) + steps)]
