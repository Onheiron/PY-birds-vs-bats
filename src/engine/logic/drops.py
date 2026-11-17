"""Putting loot into the world."""

from src.core import state
from src.engine import events


def drop_loot(loot, source):
    """Add a loot item to the playfield and announce where it came from.

    source: 'bat', 'mini_bat', 'boss', 'orange' (an Orange bird's egg) or 'cookie'.
    """
    state.items.loot_items.append(loot)
    events.emit('loot_dropped', loot=loot, source=source)
