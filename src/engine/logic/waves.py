"""Bat waves.

Bats come in waves (``bat_enemy.waves``). Before a wave a card in the right
panel counts down the seconds to its start and says how many bats it has and
their tier. Then the bats come in from the top a few at a time: never more
than the world's ``max_bats`` at once, a new one every ``spawn_interval``
ticks while there is room, until the whole wave has come. How a wave bat
moves (picking spots, holding them, flying out and back in with the HP it
has left) is in logic/bat_behaviour.py; wave bats do not fly away (linger). The wave is over when
all its bats are dead; after a pause the next one starts.

Mini bats and jumpscares are not part of waves: they still come out of the
obstacles at random. No waves during a boss fight, nor in a world without
bats (``max_bats`` 0).
"""

import random

from src.core import constants, state
from src.engine import clock, enemy_stats


def _cfg(name, default):
    return getattr(getattr(constants.bat_enemy, 'waves', None), name, default)


def _between(pair, default):
    low, high = list(pair or default)
    return random.uniform(float(low), float(high))


def wave_size(tier, world=None):
    """Bats in a wave of ``tier``: the world's size, + per level in the world, − per tier above 1."""
    w = max(1, state.game.level_group if world is None else world)
    sizes = list(_cfg('size_by_world', None) or [6])
    size = int(sizes[min(w, len(sizes)) - 1])
    size += int(_cfg('size_per_level', 1)) * (max(1, state.game.level_sub) - 1)
    size -= int(_cfg('size_cut_per_tier', 1)) * (tier - 1)
    return max(int(_cfg('min_size', 3)), size)


def _plan(pause):
    """The next wave: rolled now, it starts after ``pause`` seconds."""
    world = enemy_stats.world_table()
    tier = enemy_stats.roll_tier(world)
    state.enemies.wave_count += 1
    state.enemies.bat_wave = {
        'number': state.enemies.wave_count,
        'world': state.game.level_group,
        'tier': tier,
        'size': wave_size(tier),
        'spawned': 0,
        'starts_at': clock.now() + pause,
    }


def wave_bats(wave=None):
    wave = wave or state.enemies.bat_wave
    if not wave:
        return []
    return [b for b in state.enemies.bats if b.get('wave') == wave['number']]


def update():
    """Every tick (not during bosses): plan, start, feed and end the waves."""
    from src.engine.logic.spawning import new_bat

    world = enemy_stats.world_table()
    max_bats = int(world.get('max_bats', 0) or 0)
    wave = state.enemies.bat_wave
    if max_bats <= 0:
        state.enemies.bat_wave = None
        return
    if wave is None or wave.get('world') != state.game.level_group:
        # First wave of a world (or after a boss): a short countdown
        _plan(float(_cfg('first_pause', 5.0)))
        return
    now = clock.now()
    if now < wave['starts_at']:
        return
    alive = wave_bats(wave)
    if wave['spawned'] >= wave['size']:
        if not alive:
            _plan(_between(_cfg('pause', None), (6, 10)))  # wave cleared
        return
    state.enemies.bat_spawn_timer -= 1
    if state.enemies.bat_spawn_timer > 0 or len(alive) >= max_bats:
        return
    state.enemies.bat_spawn_timer = max(1, int(world.get('spawn_interval', 60) or 60))
    bat = new_bat(wave['tier'], world)
    bat['wave'] = wave['number']
    from src.engine.logic import bat_behaviour

    bat_behaviour.start(bat)  # in above the spot it wants
    wave['spawned'] += 1
    state.enemies.spawn_queue.append({'type': 'bat', 'data': bat})


def free_column(bat):
    """A random column where the bat overlaps no other bat (any column if there is none)."""
    width = enemy_stats.bat_width(bat)
    last = constants.layout.width - width
    others = [(b['x_pos'], b['x_pos'] + enemy_stats.bat_width(b)) for b in state.enemies.bats if b is not bat]
    free = [x for x in range(last + 1) if all(x + width < left or x > right for left, right in others)]
    return random.choice(free) if free else random.randint(0, last)


def card():
    """The right panel card of the coming or running wave (None: no wave)."""
    wave = state.enemies.bat_wave
    if not wave or state.enemies.boss is not None:
        return None
    left = wave['starts_at'] - clock.now()
    if left > 0:
        return {
            'title': f'Wave {wave["number"]} in {int(left) + 1}s',
            'text': f'{wave["size"]} bats, tier {wave["tier"]}',
        }
    remaining = wave['size'] - wave['spawned'] + len(wave_bats(wave))
    return {'title': f'Wave {wave["number"]}', 'text': f'{remaining}/{wave["size"]} bats left, tier {wave["tier"]}'}
