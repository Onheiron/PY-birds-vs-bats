"""Game events: what happened in the world, for whoever wants to react.

The simulation announces facts ("a bat was killed", "a bird was lost") with
``emit``; side effects that are not part of the simulation itself subscribe
with ``on``: achievements, sounds, run statistics (tools/simulate.py).

Dispatch is synchronous and in subscription order, so a seeded game stays
reproducible. Handlers must not change the world: they react to it.

Events and their fields:

  score_changed     score
  swap              swaps
  power_used        power, lane (lane is None for power-up pickups)
  bat_killed        bat, tier, killer
  mini_bat_killed   bat, killer
  loot_dropped      loot, source
  loot_collected    loot, bird
  bird_lost         bird, color, cause
  bird_hatched      bird, egg, loot (the collected egg)
  level_up          level
  boss_spawned      boss_type
  boss_defeated     boss_type
"""

from collections import defaultdict

_handlers = defaultdict(list)


def on(event, handler):
    """Call ``handler(**fields)`` every time ``event`` is emitted."""
    if handler not in _handlers[event]:
        _handlers[event].append(handler)


def off(event, handler):
    """Stop calling ``handler`` for ``event``."""
    if handler in _handlers[event]:
        _handlers[event].remove(handler)


def emit(event, **fields):
    """Announce ``event`` to its subscribers."""
    for handler in tuple(_handlers.get(event, ())):
        handler(**fields)
