"""Loot collection, eggs and power-up pickups."""

import random

from src.core import constants, state
from src.engine import clock
from src.engine.progression import award_xp
from src.entities.sprites import (
    BERSERK,
    BLUE,
    CLOCKWORK,
    COOKIE,
    DINOSAUR,
    FROSTY,
    GLITCH,
    GOLD,
    ORANGE,
    PATCHWORK,
    POISON,
    PURPLE,
    RAINBOW,
    RED,
    ROCK,
    STEALTH,
    TWISTER,
    WHITE,
    YELLOW,
)
from src.services import achievements
from src.services.sound import play_sfx


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
        if bird_color == STEALTH and i not in state.special.stealth_timers:
            continue

        for loot in state.items.loot_items[:]:
            if abs(bird_lane_x - loot['x_pos']) > 2:
                continue
            if abs(bird_y - loot['y_pos']) > 2:
                continue

            loot_type = loot['type']

            # COOKIE birds can't collect cookie crumbs
            if loot_type == 'cookie_crumb' and bird_color == COOKIE:
                continue

            # GLITCH special loot interaction
            if bird_color == GLITCH:
                r = random.random()
                glitch_ignore = getattr(constants.loot, 'glitch_ignore_chance', 0.05)
                glitch_promote = getattr(constants.loot, 'glitch_promote_chance', 0.10)
                if r < glitch_ignore:
                    continue
                if r < glitch_ignore + glitch_promote:
                    _promote_loot_rarity(loot)

            state.items.loot_items.remove(loot)
            _apply_loot_effect(loot, i)
            achievements.check_achievements_event(
                'collect', state.game.frame_count, state.ui.notifications, loot=loot_type
            )
            # Play sound based on loot type
            if '_egg' in loot_type:
                play_sfx('egg')
            else:
                play_sfx('powerup')
            break


def _promote_loot_rarity(loot):
    """Promote loot to next rarity tier."""
    rar = loot.get('rarity', 'common')
    if rar == 'common':
        loot['rarity'] = 'uncommon'
    elif rar == 'uncommon':
        loot['rarity'] = 'rare'
    elif rar == 'rare':
        loot['rarity'] = 'epic'


def _apply_loot_effect(loot, collector_idx):
    """Apply the effect of collected loot."""
    loot_type = loot['type']

    if loot_type.endswith('_egg'):
        # Eggs hatch a new bird
        _spawn_bird_from_egg(loot_type)
    elif loot_type == 'cookie_crumb':
        xp_val = loot.get('xp', 0)
        if xp_val > 0 and state.birds.colors[collector_idx] != COOKIE:
            award_xp(collector_idx, xp_val)
    elif loot_type.startswith('timelapse'):
        _apply_timelapse_power(loot_type)
    else:
        for name in _POWERUPS:
            if loot_type.startswith(name):
                _apply_timed_power(name, loot_type)
                break


def _spawn_bird_from_egg(egg_type):
    """Spawn a new bird from an egg."""
    color_map = {
        'yellow_egg': YELLOW,
        'red_egg': RED,
        'blue_egg': BLUE,
        'white_egg': WHITE,
        'purple_egg': PURPLE,
        'orange_egg': ORANGE,
        'gold_egg': GOLD,
        'patchwork_egg': PATCHWORK,
        'cookie_egg': COOKIE,
        'clockwork_egg': CLOCKWORK,
        'stealth_egg': STEALTH,
        'dinosaur_egg': DINOSAUR,
        'glitch_egg': GLITCH,
        'rainbow_egg': RAINBOW,
        'twister_egg': TWISTER,
        'frosty_egg': FROSTY,
        'poison_egg': POISON,
        'berserk_egg': BERSERK,
        'rock_egg': ROCK,
    }
    # Get speeds from config
    spd_config = getattr(constants.birds, 'speed', {})
    egg_to_bird = {
        'yellow_egg': 'yellow',
        'red_egg': 'red',
        'blue_egg': 'blue',
        'white_egg': 'white',
        'purple_egg': 'purple',
        'orange_egg': 'orange',
        'gold_egg': 'gold',
        'patchwork_egg': 'patchwork',
        'cookie_egg': 'cookie',
        'clockwork_egg': 'clockwork',
        'stealth_egg': 'stealth',
        'dinosaur_egg': 'dinosaur',
        'glitch_egg': 'glitch',
        'rainbow_egg': 'rainbow',
        'twister_egg': 'twister',
        'frosty_egg': 'frosty',
        'poison_egg': 'poison',
        'berserk_egg': 'berserk',
        'rock_egg': 'rock',
    }
    default_speeds = {
        'yellow': 2,
        'red': 3,
        'blue': 4,
        'white': 4,
        'purple': 3,
        'orange': 5,
        'gold': 5,
        'patchwork': 3,
        'cookie': 3,
        'clockwork': 2,
        'stealth': 3,
        'dinosaur': 4,
        'glitch': 3,
        'rainbow': 6,
        'twister': 4,
        'frosty': 3,
        'poison': 3,
        'berserk': 3,
        'rock': 2,
    }

    bird_color = color_map.get(egg_type)
    if bird_color is None:
        return

    # Find first lost bird to revive
    for idx in range(constants.layout.num_balls):
        if state.birds.lost[idx]:
            state.birds.lost[idx] = False
            state.birds.colors[idx] = bird_color
            # Get speed from config, fallback to default
            bird_type = egg_to_bird.get(egg_type, 'yellow')
            if hasattr(spd_config, '__getitem__'):
                bird_speed = spd_config.get(bird_type, default_speeds.get(bird_type, 3))
            else:
                bird_speed = getattr(spd_config, bird_type, default_speeds.get(bird_type, 3))
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
    'bounce_boost': {
        'seconds': ('seconds', _TIERS, (10.0, 20.0, 25.0, 50.0), _SECONDS_FALLBACK),
        'values': {
            'bounce_boost_duration': ('duration', _TIERS, (4, 4, 8, 12), (1.0, 1.5, 2.0, 3.0)),
        },
    },
    'suction': {
        'seconds': ('seconds', _TIERS, (10.0, 20.0, 25.0, 50.0), _SECONDS_FALLBACK),
        'values': {
            'suction_boost_duration': ('boost_duration', _TIERS, (0, 0, 4, 8), (1.0, 1.5, 2.0, 3.0)),
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


def _apply_timed_power(name, loot_type):
    """Activate a frame-timed power-up (wide cursor, bounce boost, suction, tailwind)."""
    spec = _POWERUPS[name]
    section = getattr(constants, name)
    tier = _loot_tier(loot_type, name)
    powerups = state.powerups

    setattr(powerups, f'{name}_active', True)
    table_name, keys, defaults, fallbacks = spec['seconds']
    seconds = _tiered(section, table_name, tier, keys, defaults, fallbacks)
    setattr(powerups, f'{name}_frames', int(seconds / constants.timing.base_sleep))
    for attr, (table_name, keys, defaults, fallbacks) in spec['values'].items():
        setattr(powerups, attr, _tiered(section, table_name, tier, keys, defaults, fallbacks))

    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power=name)


def _apply_timelapse_power(loot_type):
    """Apply timelapse powerup - slows down the game tick for some real seconds."""
    section = constants.timelapse
    tier = _loot_tier(loot_type, 'timelapse')
    duration = _tiered(section, 'seconds', tier, _TIERS, (2.0, 3.0, 4.0, 5.0))
    slowdown = _tiered(section, 'slowdown', tier, ('base', 'plus', 'max', 'max'), (1.5, 1.75, 2.0, 2.0))

    state.powerups.timelapse_active = True
    state.powerups.timelapse_end_time = clock.now() + duration
    state.powerups.timelapse_slowdown = slowdown
    achievements.check_achievements_event(
        'power_used', state.game.frame_count, state.ui.notifications, power='timelapse'
    )
