"""Putting loot into the world."""

import random

from src.core import constants, state
from src.engine import events, stats
from src.engine.enemy_stats import upgrade_rarity


def _drop_chance(source):
    table = getattr(getattr(constants, 'cards', None), 'drop_chance', None)
    if table is None:
        return 1.0
    table = table if isinstance(table, dict) else vars(table)
    return float(table.get(source, 1.0))


def drop_loot(loot, source):
    """Add a loot item to the playfield and announce where it came from.

    source: 'bat', 'mini_bat', 'boss', 'orange' (an Orange bird's egg) or 'cookie'.
    Rarity eggs from enemies drop with ``cards.drop_chance[source]`` and can be
    upgraded by the flock's egg luck.
    """
    if loot['type'] == 'egg':
        chance = _drop_chance(source)
        if chance < 1 and random.random() >= chance:
            return
        luck = stats.flock('egg_luck')
        if luck > 0 and random.random() < luck:
            loot['rarity'] = upgrade_rarity(loot.get('rarity', 'common'), 1)
    state.items.loot_items.append(loot)
    events.emit('loot_dropped', loot=loot, source=source)
