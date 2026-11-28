"""Bat waves.

Every level has a number of waves (``bat_enemy.waves.per_level_by_world``): they come one
every ``interval_by_world`` seconds whether the ones before are dead or not, so they add up.
Before a wave a card in the right panel counts down the seconds to its start and says how
many bats it has and their tier. Then its bats come in from the top a few at a time: never
more than the world's ``max_bats`` wave bats on screen at once (the oldest wave first), a new
one every ``spawn_interval`` ticks while there is room. How a wave bat moves (picking spots,
holding them, flying out and back in with the HP it has left) is in logic/bat_behaviour.py;
wave bats never fly away. A wave is over when all its bats are dead. The waves a level could
not finish go on into the next one; a world's boss comes only once every wave of its level
is dead (the miles wait at the boss, see progression.py).

Mini bats and jumpscares are not part of waves: they still come out of the obstacles at
random. No waves during a boss fight, nor in a world without bats (``max_bats`` 0).
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


def _by_world(name, default):
    values = list(_cfg(name, None) or default)
    return values[min(max(1, state.game.level_group), len(values)) - 1]


def _plan(pause):
    """A new wave: rolled now, it starts after ``pause`` seconds."""
    world = enemy_stats.world_table()
    tier = enemy_stats.roll_tier(world)
    state.enemies.wave_count += 1
    wave = {
        'number': state.enemies.wave_count,
        'world': state.game.level_group,
        'tier': tier,
        'size': wave_size(tier),
        'spawned': 0,
        'starts_at': clock.now() + pause,
    }
    state.enemies.waves.append(wave)
    state.enemies.bat_wave = wave  # the latest one (the card counts down to it)
    return wave


def wave_bats(wave=None):
    """The bats on screen of ``wave`` (default: the latest one)."""
    wave = wave or state.enemies.bat_wave
    if not wave:
        return []
    return [b for b in state.enemies.bats if b.get('wave') == wave['number']]


def per_level():
    return int(_by_world('per_level_by_world', [0, 3, 3, 4, 4, 5]))


def remaining():
    """Waves still to fight in this level: planned ones not dead yet, plus those not yet planned."""
    plan = state.enemies.level_waves or {}
    to_plan = max(0, per_level() - plan.get('planned', 0)) if plan.get('level') == state.game.level else per_level()
    return len(state.enemies.waves) + to_plan


def update():
    """Every tick (not during bosses): plan the level's waves, feed them, end the dead ones."""
    from src.engine.logic.spawning import new_bat

    world = enemy_stats.world_table()
    max_bats = int(world.get('max_bats', 0) or 0)
    if max_bats <= 0:
        state.enemies.waves.clear()
        state.enemies.bat_wave = None
        state.enemies.level_waves = None
        return
    now = clock.now()
    plan = state.enemies.level_waves
    if plan is None or plan.get('level') != state.game.level:
        plan = state.enemies.level_waves = {'level': state.game.level, 'planned': 0, 'next_at': now}
    if plan['planned'] < per_level() and now >= plan['next_at']:
        _plan(float(_cfg('countdown', 5.0)))
        plan['planned'] += 1
        plan['next_at'] = now + float(_by_world('interval_by_world', [0, 30, 27, 24, 21, 18]))

    started = []
    for wave in list(state.enemies.waves):
        if now < wave['starts_at']:
            continue
        if wave['spawned'] >= wave['size'] and not wave_bats(wave):
            state.enemies.waves.remove(wave)  # all its bats dead
            continue
        started.append(wave)
    feeding = next((w for w in started if w['spawned'] < w['size']), None)
    if feeding is None:
        return
    state.enemies.bat_spawn_timer -= 1
    on_screen = sum(1 for b in state.enemies.bats if b.get('wave') is not None)
    if state.enemies.bat_spawn_timer > 0 or on_screen >= max_bats:
        return
    state.enemies.bat_spawn_timer = max(1, int(world.get('spawn_interval', 60) or 60))
    bat = new_bat(feeding['tier'], world)
    bat['wave'] = feeding['number']
    from src.engine.logic import bat_behaviour

    bat_behaviour.start(bat)  # in above the spot it wants
    feeding['spawned'] += 1
    state.enemies.spawn_queue.append({'type': 'bat', 'data': bat})


def free_column(bat):
    """A random column where the bat overlaps no other bat (any column if there is none)."""
    width = enemy_stats.bat_width(bat)
    last = constants.layout.width - width
    others = [(b['x_pos'], b['x_pos'] + enemy_stats.bat_width(b)) for b in state.enemies.bats if b is not bat]
    free = [x for x in range(last + 1) if all(x + width < left or x > right for left, right in others)]
    return random.choice(free) if free else random.randint(0, last)


def card():
    """The right panel card of the waves (None: no wave)."""
    if state.enemies.boss is not None:
        return None
    now = clock.now()
    coming = [w for w in state.enemies.waves if w['starts_at'] > now]
    if coming:
        wave = coming[0]
        return {
            'title': f'Wave {wave["number"]} in {int(wave["starts_at"] - now) + 1}s',
            'text': f'{wave["size"]} bats, tier {wave["tier"]}',
        }
    if not state.enemies.waves:
        return None
    left = sum(w['size'] - w['spawned'] + len(wave_bats(w)) for w in state.enemies.waves)
    numbers = [w['number'] for w in state.enemies.waves]
    title = f'Wave {numbers[0]}' if len(numbers) == 1 else f'Waves {numbers[0]}-{numbers[-1]}'
    from src.engine.logic.bosses import director

    text = f'{left} bats left' + (': then the boss' if director.waiting_for_waves() else '')
    return {'title': title, 'text': text}
