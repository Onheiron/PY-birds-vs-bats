"""Afflictions that birds put on bats and bosses: frozen, poisoned, bleeding.

Frosty freezes, Poison poisons, Berserk makes bleed. Each contact hit has
the bird's ``affliction_chance`` (its kind's ``boosted_chance`` while its
power is active); against bosses the chance is multiplied by
``combat.boss_affliction_factor``.

- Frozen (``frosty``): the target moves ``freeze_slow`` times as fast and
  loses ``armor_reduction`` armor, for ``freeze_duration`` seconds.
- Poisoned (``poison``): ``damage_per_second`` for ``effect_duration`` s.
- Bleeding (``berserk``): ``damage_per_second`` for ``effect_duration`` s and
  ``armor_reduction`` armor less.

Damage over time is scaled by the target's ``damage_taken`` stat; its XP,
and the kill, go to the bird that applied it.
"""

import random

from src.core import constants, state
from src.engine import clock, enemy_stats, events, stats
from src.entities.bird_types import get_bird_type_by_color

# Bird type -> (affliction, config section, state.special table, its power's boost table)
AFFLICTIONS = {
    'FROSTY': ('frozen', 'frosty', 'frozen_enemies', 'frosty_boosted'),
    'POISON': ('poisoned', 'poison', 'poisoned_enemies', 'poison_boosted'),
    'BERSERK': ('bleeding', 'berserk', 'bleeding_enemies', 'berserk_boosted'),
}
_TABLES = ('frozen_enemies', 'poisoned_enemies', 'bleeding_enemies')


def _cfg(section):
    return getattr(constants, section, None)


def _value(section, key, default):
    return getattr(_cfg(section), key, default)


def try_afflict(bird_idx, target, is_boss=False, always=False):
    """Maybe put the bird's affliction on ``target`` (a bat or the boss) after a contact hit.

    ``always``: a shot carrying the affliction (Frosty / Poison next to a shooter)
    applies it every time (against a boss, the boss factor still applies).
    """
    kind = get_bird_type_by_color(state.birds.colors[bird_idx])
    if kind not in AFFLICTIONS:
        return None
    name, section, table, boost_table = AFFLICTIONS[kind]
    now = clock.now()
    boosts = getattr(state.special, boost_table)
    if always:
        chance = 1.0
    elif bird_idx in boosts and now < boosts[bird_idx]:
        chance = _value(section, 'boosted_chance', 0.60)
    else:
        chance = stats.bird(bird_idx, 'affliction_chance')
    if is_boss:
        chance *= float(getattr(constants.combat, 'boss_affliction_factor', 0.33))
    if random.random() >= chance:
        return None
    if bird_idx in boosts and now < boosts[bird_idx]:
        events.emit('power_effect', bird=bird_idx, kind=kind, effect='boosted afflictions', count=1)

    entry = {'bat': target, 'owner': bird_idx, 'last_tick': now}
    if name == 'frozen':
        entry['end_time'] = now + _value(section, 'freeze_duration', 3.0)
        entry['armor_reduction'] = _value(section, 'armor_reduction', 20)
        entry['slow'] = _value(section, 'freeze_slow', 0.4)
    else:
        entry['end_time'] = now + _value(section, 'effect_duration', 5.0 if name == 'poisoned' else 10.0)
        entry['damage_per_second'] = _value(section, 'damage_per_second', 20 if name == 'poisoned' else 10)
        if name == 'bleeding':
            entry['armor_reduction'] = _value(section, 'armor_reduction', 10)
    getattr(state.special, table)[id(target)] = entry
    return name


def armor_cut(target):
    """Armor removed from ``target`` by freezing and bleeding."""
    cut = 0
    for table in ('frozen_enemies', 'bleeding_enemies'):
        entry = getattr(state.special, table).get(id(target))
        if entry:
            cut += entry.get('armor_reduction', 0)
    return cut


def slow_factor(target):
    """Speed multiplier of ``target`` (1 unless frozen)."""
    entry = state.special.frozen_enemies.get(id(target))
    return entry.get('slow', 0.4) if entry else 1.0


def _alive(target):
    boss = state.enemies.boss
    if target is boss:
        return boss.get('state') not in ('dying', 'dead') and boss.get('hp', 0) > 0
    return target in state.enemies.bats


def _kill(target, owner):
    if target is state.enemies.boss:
        target['state'] = 'dying'
        from src.services.sound import play_sfx

        play_sfx('boss_death')
        return
    from src.engine.logic.damage import handle_bat_death

    handle_bat_death(target, owner)


def update():
    """Expire afflictions and apply damage over time (once per second of game time)."""
    from src.engine.progression import award_damage_xp

    now = clock.now()
    for table_name in _TABLES:
        table = getattr(state.special, table_name)
        for key in list(table):
            entry = table.get(key)
            if entry is None:
                continue
            target = entry.get('bat')
            if now >= entry['end_time'] or target is None or not _alive(target):
                table.pop(key, None)
                continue
            if 'damage_per_second' not in entry or now - entry['last_tick'] < 1.0:
                continue
            entry['last_tick'] = now
            damage = max(1, round(entry['damage_per_second'] * enemy_stats.get(target, 'damage_taken')))
            target['hp'] -= damage
            owner = entry.get('owner', 0)
            if 0 <= owner < constants.layout.num_balls:
                award_damage_xp(owner, damage, 'dot')
            if target['hp'] <= 0:
                for other in _TABLES:
                    getattr(state.special, other).pop(key, None)
                _kill(target, owner)
