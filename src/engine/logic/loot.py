"""Loot collection, eggs and power-up pickups."""

from src.core import constants
from src.core import state
from src.functions import award_xp
from src.services import achievements
import random
import time
from src.entities.sprites import BERSERK, BLUE, CLOCKWORK, COOKIE, DINOSAUR, FROSTY, GLITCH, GOLD, ORANGE, PATCHWORK, POISON, PURPLE, RAINBOW, RED, ROCK, STEALTH, TWISTER, WHITE, YELLOW
from src.engine.logic.sfx import play_sfx


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
                elif r < glitch_ignore + glitch_promote:
                    _promote_loot_rarity(loot)

            state.items.loot_items.remove(loot)
            _apply_loot_effect(loot, i)
            achievements.check_achievements_event('collect', state.game.frame_count, state.ui.notifications, loot=loot_type)
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

    # Egg types - spawn new bird
    if loot_type.endswith('_egg') and loot_type != 'orange_egg':
        _spawn_bird_from_egg(loot_type)
    elif loot_type == 'orange_egg':
        _spawn_bird_from_egg(loot_type)
    elif loot_type == 'cookie_crumb':
        xp_val = loot.get('xp', 0)
        if xp_val > 0 and state.birds.colors[collector_idx] != COOKIE:
            award_xp(collector_idx, xp_val)
    elif loot_type.startswith('wide_cursor'):
        _apply_wide_cursor_power(loot_type)
    elif loot_type.startswith('bounce_boost'):
        _apply_bounce_boost_power(loot_type)
    elif loot_type.startswith('suction'):
        _apply_suction_power(loot_type)
    elif loot_type.startswith('tailwind'):
        _apply_tailwind_power(loot_type)
    elif loot_type.startswith('timelapse'):
        _apply_timelapse_power(loot_type)


def _spawn_bird_from_egg(egg_type):
    """Spawn a new bird from an egg."""
    color_map = {
        'yellow_egg': YELLOW, 'red_egg': RED, 'blue_egg': BLUE,
        'white_egg': WHITE, 'purple_egg': PURPLE, 'orange_egg': ORANGE,
        'gold_egg': GOLD, 'patchwork_egg': PATCHWORK, 'cookie_egg': COOKIE,
        'clockwork_egg': CLOCKWORK, 'stealth_egg': STEALTH,
        'dinosaur_egg': DINOSAUR, 'glitch_egg': GLITCH,
        'rainbow_egg': RAINBOW, 'twister_egg': TWISTER, 'frosty_egg': FROSTY,
        'poison_egg': POISON, 'berserk_egg': BERSERK, 'rock_egg': ROCK
    }
    # Get speeds from config
    spd_config = getattr(constants.birds, 'speed', {})
    egg_to_bird = {
        'yellow_egg': 'yellow', 'red_egg': 'red', 'blue_egg': 'blue',
        'white_egg': 'white', 'purple_egg': 'purple', 'orange_egg': 'orange',
        'gold_egg': 'gold', 'patchwork_egg': 'patchwork', 'cookie_egg': 'cookie',
        'clockwork_egg': 'clockwork', 'stealth_egg': 'stealth',
        'dinosaur_egg': 'dinosaur', 'glitch_egg': 'glitch',
        'rainbow_egg': 'rainbow', 'twister_egg': 'twister', 'frosty_egg': 'frosty',
        'poison_egg': 'poison', 'berserk_egg': 'berserk', 'rock_egg': 'rock'
    }
    default_speeds = {
        'yellow': 2, 'red': 3, 'blue': 4, 'white': 4, 'purple': 3,
        'orange': 5, 'gold': 5, 'patchwork': 3, 'cookie': 3, 'clockwork': 2,
        'stealth': 3, 'dinosaur': 4, 'glitch': 3,
        'rainbow': 6, 'twister': 4, 'frosty': 3, 'poison': 3, 'berserk': 3, 'rock': 2
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
                state.special.rainbow_last_decay[idx] = time.time()
            break


def _apply_wide_cursor_power(loot_type):
    """Apply wide cursor powerup."""
    state.powerups.wide_cursor_active = True

    wc = constants.wide_cursor
    wc_sec = getattr(wc, 'seconds', None)
    wc_lanes = getattr(wc, 'lanes', None)

    if loot_type == 'wide_cursor':
        seconds = getattr(wc_sec, 'base', 10.0) if wc_sec else 10.0
        lanes = getattr(wc_lanes, 'base', 3) if wc_lanes else 3
    elif loot_type == 'wide_cursor+':
        seconds = getattr(wc_sec, 'plus', 20.0) if wc_sec else 15.0
        lanes = getattr(wc_lanes, 'base', 3) if wc_lanes else 3
    elif loot_type == 'wide_cursor++':
        seconds = getattr(wc_sec, 'plusplus', 25.0) if wc_sec else 20.0
        lanes = getattr(wc_lanes, 'max', 5) if wc_lanes else 5
    else:  # max
        seconds = getattr(wc_sec, 'max', 50.0) if wc_sec else 30.0
        lanes = getattr(wc_lanes, 'max', 5) if wc_lanes else 5

    state.powerups.wide_cursor_frames = int(seconds / constants.timing.base_sleep)
    state.powerups.wide_cursor_lanes = lanes
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='wide_cursor')


def _apply_bounce_boost_power(loot_type):
    """Apply bounce boost powerup."""
    state.powerups.bounce_boost_active = True

    bb = constants.bounce_boost
    bb_sec = getattr(bb, 'seconds', None)
    bb_dur = getattr(bb, 'duration', None)

    if loot_type == 'bounce_boost':
        seconds = getattr(bb_sec, 'base', 10.0) if bb_sec else 10.0
        duration = getattr(bb_dur, 'base', 4) if bb_dur else 1.0
    elif loot_type == 'bounce_boost+':
        seconds = getattr(bb_sec, 'plus', 20.0) if bb_sec else 15.0
        duration = getattr(bb_dur, 'plus', 4) if bb_dur else 1.5
    elif loot_type == 'bounce_boost++':
        seconds = getattr(bb_sec, 'plusplus', 25.0) if bb_sec else 20.0
        duration = getattr(bb_dur, 'plusplus', 8) if bb_dur else 2.0
    else:  # max
        seconds = getattr(bb_sec, 'max', 50.0) if bb_sec else 30.0
        duration = getattr(bb_dur, 'max', 12) if bb_dur else 3.0

    state.powerups.bounce_boost_frames = int(seconds / constants.timing.base_sleep)
    state.powerups.bounce_boost_duration = duration
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='bounce_boost')


def _apply_suction_power(loot_type):
    """Apply suction powerup."""
    state.powerups.suction_active = True

    sc = constants.suction
    sc_sec = getattr(sc, 'seconds', None)
    sc_boost = getattr(sc, 'boost_duration', None)

    if loot_type == 'suction':
        seconds = getattr(sc_sec, 'base', 10.0) if sc_sec else 10.0
        boost = getattr(sc_boost, 'base', 0) if sc_boost else 1.0
    elif loot_type == 'suction+':
        seconds = getattr(sc_sec, 'plus', 20.0) if sc_sec else 15.0
        boost = getattr(sc_boost, 'plus', 0) if sc_boost else 1.5
    elif loot_type == 'suction++':
        seconds = getattr(sc_sec, 'plusplus', 25.0) if sc_sec else 20.0
        boost = getattr(sc_boost, 'plusplus', 4) if sc_boost else 2.0
    else:  # max
        seconds = getattr(sc_sec, 'max', 50.0) if sc_sec else 30.0
        boost = getattr(sc_boost, 'max', 8) if sc_boost else 3.0

    state.powerups.suction_frames = int(seconds / constants.timing.base_sleep)
    state.powerups.suction_boost_duration = boost
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='suction')


def _apply_tailwind_power(loot_type):
    """Apply tailwind powerup."""
    state.powerups.tailwind_active = True

    tw = constants.tailwind
    tw_sec = getattr(tw, 'seconds', None)
    tw_up = getattr(tw, 'up_bonus', None)
    tw_down = getattr(tw, 'down_penalty', None)

    if loot_type == 'tailwind':
        seconds = getattr(tw_sec, 'base', 10.0) if tw_sec else 10.0
        up_bonus = getattr(tw_up, 'base', 1) if tw_up else 1
        down_pen = getattr(tw_down, 'base', 1) if tw_down else 1
    elif loot_type == 'tailwind+':
        seconds = getattr(tw_sec, 'plus', 15.0) if tw_sec else 15.0
        up_bonus = getattr(tw_up, 'plus', 2) if tw_up else 1
        down_pen = getattr(tw_down, 'plus', 1) if tw_down else 1
    elif loot_type == 'tailwind++':
        seconds = getattr(tw_sec, 'plusplus', 20.0) if tw_sec else 20.0
        up_bonus = getattr(tw_up, 'plusplus', 3) if tw_up else 2
        down_pen = getattr(tw_down, 'plusplus', 2) if tw_down else 2
    else:  # max
        seconds = getattr(tw_sec, 'max', 30.0) if tw_sec else 30.0
        up_bonus = getattr(tw_up, 'plusplus', 3) if tw_up else 2
        down_pen = getattr(tw_down, 'max', 3) if tw_down else 2

    state.powerups.tailwind_frames = int(seconds / constants.timing.base_sleep)
    state.powerups.tailwind_up_bonus = up_bonus
    state.powerups.tailwind_down_penalty = down_pen
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='tailwind')


def _apply_timelapse_power(loot_type):
    """Apply timelapse powerup - slows down game tick."""
    # Get config values (with fallbacks)
    seconds_cfg = getattr(constants.timelapse, 'seconds', None)
    slowdown_cfg = getattr(constants.timelapse, 'slowdown', None)

    # Duration in real seconds
    if loot_type == 'timelapse':
        duration = getattr(seconds_cfg, 'base', 2.0) if seconds_cfg else 2.0
        slowdown = getattr(slowdown_cfg, 'base', 1.5) if slowdown_cfg else 1.5
    elif loot_type == 'timelapse+':
        duration = getattr(seconds_cfg, 'plus', 3.0) if seconds_cfg else 3.0
        slowdown = getattr(slowdown_cfg, 'plus', 1.75) if slowdown_cfg else 1.75
    elif loot_type == 'timelapse++':
        duration = getattr(seconds_cfg, 'plusplus', 4.0) if seconds_cfg else 4.0
        slowdown = getattr(slowdown_cfg, 'max', 2.0) if slowdown_cfg else 2.0
    else:  # max
        duration = getattr(seconds_cfg, 'max', 5.0) if seconds_cfg else 5.0
        slowdown = getattr(slowdown_cfg, 'max', 2.0) if slowdown_cfg else 2.0

    state.powerups.timelapse_active = True
    state.powerups.timelapse_end_time = time.time() + duration
    state.powerups.timelapse_slowdown = slowdown
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='timelapse')
