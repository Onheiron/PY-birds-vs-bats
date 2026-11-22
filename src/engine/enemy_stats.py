"""Enemy stats: the numbers that make a bat or an obstacle tough, scary or rewarding.

Stats are resolved once, when the enemy spawns, and stored in the enemy's
``stats`` dict (so they are saved with it). Layers, from the ``enemy_stats``
section of config.yml:

    defaults → tiers.<n> → kinds.<kind> → worlds.<w> (its own stats, then its
    tiers.<n> and kinds.<kind>) → elite stats → elite_kinds.<kind> → affixes

so every number of every bat and obstacle can change world by world, and an
elite of a kind can get more of what makes that kind special.

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
    'move_step': (2, 'columns per horizontal move'),
    'linger': (60, 'seconds on screen before it flies away'),
    'fear_push': (1, 'extra fall speed (speed points) of a bird it scares'),
    # Abilities (each kind uses the ones it has). The stats of the newer kinds
    # (healer, bomber, plague, necromancer, peaks) start from 0, so the value
    # set in their kind is the value they have
    'ability_chance': (0.0, 'chance per second to use its ability when ready'),
    'ability_interval': (0.0, 'seconds before its ability is ready again'),
    'dive_rows': (10, 'diver: rows of a dive'),
    'dive_interval': (2, 'diver: ticks per row while diving'),
    'dive_stun': (1.5, 'diver: seconds it stays stunned after a dive'),
    'return_interval': (6, 'diver: ticks per row while climbing back'),
    'dive_push': (1, 'diver: extra fall speed of a bird that hits it mid-dive'),
    'dive_push_time': (0.5, 'diver: seconds that push lasts'),
    'spells': (1, 'spellcaster: spells known (silence, repugnant wind, exile)'),
    'cast_time': (0.5, 'spellcaster: seconds of casting before the spell lands'),
    'silence_time': (3.0, 'spellcaster: seconds of silence'),
    'wind_time': (3.0, 'spellcaster: seconds of repugnant wind'),
    'wind_push': (1, 'spellcaster: fall speed added and rise speed removed by its wind'),
    'heal_pct': (0.0, 'healer: share of max HP healed on the bats around it'),
    'heal_range': (0, 'healer: columns its healing reaches'),
    'stone_hp': (0, 'bomber: HP of a dropped stone'),
    'stone_interval': (0, 'bomber: ticks per row of a falling stone'),
    'stone_stun': (0.0, 'bomber: seconds a stone stuns the bird it hits'),
    'plague_time': (0.0, 'plague: seconds before the infection kills the bird'),
    'plague_presses': (0, 'plague: UP presses that cure it'),
    'plague_spread': (0.0, 'plague: chance per second to infect the bird in a lane next to it'),
    'zombies': (0, 'necromancer: zombie birds it keeps at most'),
    'zombie_fear': (0.0, 'necromancer: seconds its zombies scare a bird'),
    # Obstacles (and dropped stones)
    'stun': (1.0, 'seconds it stuns a bird that hits it'),
    'knock': (0, 'extra fall speed of a bird that hits it'),
    'knock_time': (0.0, 'seconds that extra fall speed lasts'),
    'fall_interval': (5, 'ticks per row while falling'),
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


def _flat(layer):
    """The stats of a layer, without its nested ``tiers`` / ``kinds`` tables."""
    return {k: v for k, v in _as_dict(layer).items() if k not in ('tiers', 'kinds')}


def resolve(family, tier, kinds=(), affixes=(), elite=False, extra=None, world=None):
    """Stats of a new enemy of ``family`` ('bats' or 'obstacles'), as a dict of the non-default values.

    ``extra`` is one more flat/multiplier layer applied first (e.g. the armor of an armored bat).
    ``world`` defaults to the current one (``state.game.level_group``).
    """
    cfg = _config(family)
    values = {}
    _apply(values, extra)
    _apply(values, _node(cfg, 'defaults'))
    _apply(values, _node(_node(cfg, 'tiers'), tier))
    for kind in kinds:
        _apply(values, _node(_node(cfg, 'kinds'), kind))
    world_layer = _node(_node(cfg, 'worlds'), max(1, state.game.level_group) if world is None else world)
    if world_layer is not None:
        _apply(values, _flat(world_layer))
        _apply(values, _node(_node(world_layer, 'tiers'), tier))
        for kind in kinds:
            _apply(values, _node(_node(world_layer, 'kinds'), kind))
    if family == 'bats':
        for layer in state.stats.enemy_layers:
            _apply(values, layer)
    elites = getattr(constants, 'elites', None)
    if elite:
        _apply(values, _node(elites, 'stats'))
        for kind in kinds:
            _apply(values, _node(_node(cfg, 'elite_kinds'), kind))
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
    from src.engine import stats

    return min(1.0, float(table[min(group, len(table)) - 1]) + stats.flock('elite_chance'))


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


# Bat kinds, in the order their stat layers apply (a bat has at most one)
BAT_KINDS = ('armored', 'diver', 'spellcaster', 'healer', 'bomber', 'plague', 'necromancer')


def bat_kinds(bat):
    """Kinds of a bat (its ``kind``; older saves flag armored / diver / spellcaster)."""
    if bat.get('kind'):
        return [bat['kind']]
    return [k for k in BAT_KINDS if bat.get(k)]


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
    """Armor of an armored bat of ``tier`` (``bat_enemy.armored.armor_by_tier``)."""
    armored_cfg = getattr(constants.bat_enemy, 'armored', None)
    table = _node(armored_cfg, 'armor_by_tier')
    return _node(table, tier) or 0


def world_table(world=None):
    """The ``bat_enemy.worlds`` entry of a world (default: the current one), as a dict."""
    worlds = list(getattr(constants.bat_enemy, 'worlds', None) or [])
    if not worlds:
        return {}
    w = max(1, state.game.level_group if world is None else world)
    return _as_dict(worlds[min(w, len(worlds)) - 1])


def roll_tier(world):
    weights = list(world.get('tiers') or [1, 0, 0, 0])
    if not any(weights):
        weights = [1, 0, 0, 0]
    return random.choices([1, 2, 3, 4], weights=weights)[0]


def roll_kind(tier, world):
    """The kind of a new bat of ``tier`` in ``world`` (None: a plain bat). One random draw."""
    chances = _as_dict(world.get('kinds'))
    min_tiers = _as_dict(getattr(constants.bat_enemy, 'kind_min_tier', None))
    r = random.random()
    total = 0.0
    for kind in BAT_KINDS:
        chance = float(chances.get(kind, 0) or 0)
        if chance <= 0 or tier < int(min_tiers.get(kind, 1)):
            continue
        total += chance
        if r < total:
            return kind
    return None


SPELLS = ('silence', 'repugnant_wind', 'exile')


def make_bat(tier, kind, x_pos, y_pos, target_y, hp, affixes=(), **extra):
    """A new bat of ``tier`` and ``kind`` (None: plain), equipped with its stats."""
    bat = {
        'x_pos': x_pos,
        'y_pos': y_pos,
        'direction': random.choice([-1, 1]),
        'tier': tier,
        'hp': hp,
        'max_hp': hp,
        'target_y': target_y,
        'spawn_ts': clock.now(),
        'kind': kind,
        # Flags older code (and old saves) look at
        'armored': kind == 'armored',
        'diver': kind == 'diver',
        'spellcaster': kind == 'spellcaster',
    }
    bat.update(extra)
    state.enemies.bat_uid += 1
    bat['uid'] = state.enemies.bat_uid
    equip_bat(bat, affixes)
    if kind == 'diver':
        bat.update(diver_state='flying', diver_home_y=target_y, dive_start_y=None, stun_end_time=None)
    elif kind == 'spellcaster':
        bat.update(spell_state='idle', spell_cooldown=0, casting_end_time=None)
        known = max(1, min(len(SPELLS), int(get(bat, 'spells'))))
        bat['known_spells'] = list(SPELLS[:known])
    return bat


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
    kinds = [obstacle['kind']] if obstacle.get('kind') else []
    obstacle['stats'] = resolve('obstacles', obstacle.get('tier', 1), kinds)
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
