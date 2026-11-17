"""Loot collection, eggs and power-up pickups."""

import random

from src.core import constants, state
from src.engine import bird_kinds, choices, clock, events, stats
from src.engine.enemy_stats import upgrade_rarity
from src.engine.progression import award_xp
from src.entities.bird_types import get_bird_type_from_egg, get_color_for_bird_type, get_default_speed
from src.entities.sprites import (
    CLOCKWORK,
    COOKIE,
    GLITCH,
    RAINBOW,
)


def check_loot_collection():
    """Check if birds collect loot items."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_lane_x = constants.layout.lane_positions[bird_lane]
        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_kinds.is_intangible(i):
            continue

        for loot in state.items.loot_items[:]:
            if abs(bird_lane_x - loot['x_pos']) > stats.bird(i, 'pickup_radius'):
                continue
            if abs(bird_y - loot['y_pos']) > 2:
                continue

            loot_type = loot['type']

            # A dormant Orange's own egg is not loot: only UP on its lane wakes it.
            # (With a pickup radius over 3, birds in the next lane used to take it,
            # leaving the Orange asleep forever in a lane that looked occupied.)
            if loot_type == 'orange_egg':
                continue

            # COOKIE birds can't collect cookie crumbs
            if loot_type == 'cookie_crumb' and bird_color == COOKIE:
                continue

            # Glitch ignores some loot; luck upgrades the rarity of what is collected
            ignore = getattr(constants.loot, 'glitch_ignore_chance', 0.05) if bird_color == GLITCH else 0
            luck = stats.bird(i, 'luck')
            if ignore or luck:
                r = random.random()
                if r < ignore:
                    continue
                if r < ignore + luck:
                    _promote_loot_rarity(loot)

            state.items.loot_items.remove(loot)
            _apply_loot_effect(loot, i)
            events.emit('loot_collected', loot=loot, bird=i)
            break


def _promote_loot_rarity(loot):
    """Promote loot to the next rarity (lucky birds)."""
    loot['rarity'] = upgrade_rarity(loot.get('rarity', 'common'), 1)


def _apply_loot_effect(loot, collector_idx):
    """Apply the effect of collected loot."""
    loot_type = loot['type']

    if loot_type == 'egg':
        # Rarity eggs stop the game and offer cards
        choices.offer_egg(loot.get('rarity', 'common'))
    elif loot_type.endswith('_egg'):
        # Bird eggs (an Orange's own egg) hatch a new bird
        _spawn_bird_from_egg(loot_type, loot)
    elif loot_type == 'cookie_crumb':
        xp_val = loot.get('xp', 0)
        if xp_val > 0 and state.birds.colors[collector_idx] != COOKIE:
            award_xp(collector_idx, xp_val)
    else:
        apply_powerup(loot_type)


def apply_powerup(loot_type):
    """Start a power-up such as 'tailwind+', 'wide_cursor_max' or 'timelapse++'."""
    if loot_type.startswith('timelapse'):
        _apply_timelapse_power(loot_type)
        return
    for name in _POWERUPS:
        if loot_type.startswith(name):
            _apply_timed_power(name, loot_type)
            return


def hatch_bird(bird_type, loot=None):
    """Hatch a bird of ``bird_type`` into the first free slot (a bird card)."""
    _spawn_bird_from_egg(f'{bird_type.lower()}_egg', loot)


def _spawn_bird_from_egg(egg_type, loot=None):
    """Hatch an egg (the collected ``loot``) into the first free bird slot."""
    bird_type = get_bird_type_from_egg(egg_type)
    if bird_type is None:
        return
    bird_color = get_color_for_bird_type(bird_type)
    bird_speed = get_default_speed(bird_type)

    for idx in range(constants.layout.num_balls):
        if state.birds.lost[idx]:
            state.birds.lost[idx] = False
            stats.clear_bird(idx)
            state.birds.colors[idx] = bird_color
            state.birds.speeds[idx] = bird_speed
            state.birds.y[idx] = constants.layout.starting_line
            state.birds.vy[idx] = -1
            state.birds.transformed[idx] = False
            state.birds.per_bird_xp[idx] = 0
            # Only recover life if enabled in config (disabled in SURVIVAL/LEGENDARY)
            if getattr(constants.game, 'life_recovery_on_spawn', True):
                state.game.lives += 1

            if bird_color == CLOCKWORK:
                state.special.clockwork_charge[idx] = constants.clockwork.initial_charge
            if bird_color == RAINBOW:
                max_charge = getattr(constants.rainbow, 'max_charge', 100)
                state.special.rainbow_charge[idx] = max_charge
                state.special.rainbow_last_decay[idx] = clock.now()
            events.emit('bird_hatched', bird=idx, egg=egg_type, loot=loot)
            break


_TIERS = ('base', 'plus', 'plusplus', 'max')


def _loot_tier(loot_type, name):
    """Index into _TIERS for a pickup such as 'tailwind', 'tailwind+', 'tailwind++' or 'tailwind_max'."""
    suffix = loot_type[len(name) :]
    return {'': 0, '+': 1, '++': 2}.get(suffix, 3)


def _tiered(section, table_name, tier, keys, defaults, fallbacks=None):
    """Read the value of a power-up tier from ``constants.<section>.<table_name>``.

    ``keys`` and ``defaults`` give, per tier, the config key to read and the
    value to use when that key is missing; ``fallbacks`` is used when the
    whole table is missing.
    """
    table = getattr(section, table_name, None)
    if not table:
        return (fallbacks or defaults)[tier]
    return getattr(table, keys[tier], defaults[tier])


# Timed power-ups: how long each tier lasts and which extra values it sets on
# state.powerups. Every entry is (config table, keys, defaults, fallbacks) per tier.
_SECONDS_FALLBACK = (10.0, 15.0, 20.0, 30.0)
_POWERUPS = {
    'wide_cursor': {
        'seconds': ('seconds', _TIERS, (10.0, 20.0, 25.0, 50.0), _SECONDS_FALLBACK),
        'values': {
            'wide_cursor_lanes': ('lanes', ('base', 'base', 'max', 'max'), (3, 3, 5, 5), None),
        },
    },
    'tailwind': {
        'seconds': ('seconds', _TIERS, _SECONDS_FALLBACK, None),
        'values': {
            'tailwind_up_bonus': ('up_bonus', ('base', 'plus', 'plusplus', 'plusplus'), (1, 2, 3, 3), (1, 1, 2, 2)),
            'tailwind_down_penalty': ('down_penalty', _TIERS, (1, 1, 2, 3), (1, 1, 2, 2)),
        },
    },
}


def powerup_details(loot_type):
    """What a power-up such as 'tailwind++' does: {'seconds', and its values}."""
    if loot_type.startswith('timelapse'):
        tier = _loot_tier(loot_type, 'timelapse')
        section = constants.timelapse
        return {
            'seconds': _tiered(section, 'seconds', tier, _TIERS, (2.0, 3.0, 4.0, 5.0)),
            'slowdown': _tiered(section, 'slowdown', tier, ('base', 'plus', 'max', 'max'), (1.5, 1.75, 2.0, 2.0)),
        }
    for name, spec in _POWERUPS.items():
        if loot_type.startswith(name):
            section = getattr(constants, name)
            tier = _loot_tier(loot_type, name)
            table_name, keys, defaults, fallbacks = spec['seconds']
            details = {'seconds': _tiered(section, table_name, tier, keys, defaults, fallbacks)}
            for attr, (table_name, keys, defaults, fallbacks) in spec['values'].items():
                details[attr] = _tiered(section, table_name, tier, keys, defaults, fallbacks)
            return details
    return {}


def _apply_timed_power(name, loot_type):
    """Activate a timed power-up (wide cursor, tailwind) for game-clock seconds."""
    spec = _POWERUPS[name]
    section = getattr(constants, name)
    tier = _loot_tier(loot_type, name)
    powerups = state.powerups

    setattr(powerups, f'{name}_active', True)
    table_name, keys, defaults, fallbacks = spec['seconds']
    seconds = _tiered(section, table_name, tier, keys, defaults, fallbacks)
    setattr(powerups, f'{name}_until', clock.now() + seconds)
    for attr, (table_name, keys, defaults, fallbacks) in spec['values'].items():
        setattr(powerups, attr, _tiered(section, table_name, tier, keys, defaults, fallbacks))

    events.emit('power_used', power=name, lane=None)


def _apply_timelapse_power(loot_type):
    """Apply timelapse powerup - slows down the game tick for some real seconds."""
    section = constants.timelapse
    tier = _loot_tier(loot_type, 'timelapse')
    duration = _tiered(section, 'seconds', tier, _TIERS, (2.0, 3.0, 4.0, 5.0))
    slowdown = _tiered(section, 'slowdown', tier, ('base', 'plus', 'max', 'max'), (1.5, 1.75, 2.0, 2.0))

    state.powerups.timelapse_active = True
    state.powerups.timelapse_end_time = clock.now() + duration
    state.powerups.timelapse_slowdown = slowdown
    events.emit('power_used', power='timelapse', lane=None)


def restore_orange_eggs():
    """Every dormant Orange has its egg on its lane: put back one that went missing.

    Without its egg a dormant Orange can never wake or die, and its lane looks
    taken while nothing is drawn in it.
    """
    from src.engine.birds import is_orange_egg_state

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or not is_orange_egg_state(i):
            continue
        x = constants.layout.lane_positions[state.birds.random_lanes[i]]
        if any(loot['type'] == 'orange_egg' and loot['x_pos'] == x for loot in state.items.loot_items):
            continue
        state.items.loot_items.append(
            {
                'x_pos': x,
                'y_pos': constants.layout.starting_line,
                'type': 'orange_egg',
                'rarity': 'epic',
                'spawn_ts': clock.now(),
            }
        )
