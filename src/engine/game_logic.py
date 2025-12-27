#!/usr/bin/env python3
"""
Game logic module for BVB.
Handles collisions, spawning, scoring, powerups, and game state transitions.
"""

import random
import time

from src.core import state
from src.core import constants
from src.services import achievements
from src.entities.sprites import *
from src.functions import (
    compute_level_from_score,
    compute_grade_from_xp,
    compute_prestige,
    add_score,
    award_xp,
    deduct_score,
    adjust_rarity_weights,
    choose_loot_type,
    get_scared_frames,
    perform_shuffle,
    set_ball_vy,
    reset_bird_power,
    find_bird_in_lane,
)

# Audio module (optional)
try:
    from src.services import audio
    AUDIO_AVAILABLE = audio.is_audio_available()
except ImportError:
    audio = None
    AUDIO_AVAILABLE = False


def play_sfx(name):
    """Play sound effect if audio is available."""
    if AUDIO_AVAILABLE and audio:
        audio.play_sfx(name)


# =============================================================================
# HELPER FUNCTIONS (local wrappers)
# =============================================================================

def _set_ball_vy(idx, val):
    """Wrapper for functions.set_ball_vy."""
    set_ball_vy(idx, val)


def _reset_bird_power(idx):
    """Wrapper for functions.reset_bird_power."""
    reset_bird_power(idx)


def _find_bird_in_lane(lane):
    """Wrapper for functions.find_bird_in_lane."""
    return find_bird_in_lane(lane)


# =============================================================================
# COLLISION DETECTION
# =============================================================================

def check_bird_ceiling_bounce():
    """Check if birds hit ceiling and bounce them."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        if state.birds.y[i] <= 1:
            # ORANGE special: goes to dormant state
            if state.birds.colors[i] == ORANGE:
                lane = state.birds.random_lanes[i]
                state.birds.y[i] = 999  # Out of play
                _set_ball_vy(i, 0)
                _reset_bird_power(i)
                state.birds.speeds[i] = 0
                # Spawn orange egg loot if not transformed
                if not state.birds.transformed[i]:
                    state.items.loot_items.append({
                        'x_pos': constants.layout.lane_positions[lane],
                        'y_pos': constants.layout.starting_line,
                        'type': 'orange_egg',
                        'rarity': 'epic',
                        'spawn_ts': time.time()
                    })
                continue

            # Normal bounce
            state.birds.y[i] = 1
            _set_ball_vy(i, 1)
            _reset_bird_power(i)


def check_bird_floor_collision():
    """Check if birds hit floor (game over condition)."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        if state.birds.y[i] < constants.layout.height - 1:
            continue

        bird_color = state.birds.colors[i]

        # CLOCKWORK auto-bounce if has charge
        if bird_color == CLOCKWORK:
            charge = state.special.clockwork_charge.get(i)
            if charge is None:
                charge = constants.clockwork.initial_charge
                state.special.clockwork_charge[i] = charge
            if charge > 0:
                state.birds.y[i] = constants.layout.starting_line
                _set_ball_vy(i, -1)
                _reset_bird_power(i)
                continue

        # ORANGE birds don't die at floor
        if bird_color == ORANGE:
            continue

        # GLITCH survival chance
        if bird_color == GLITCH and random.random() < constants.glitch.survive_on_floor_chance:
            state.birds.y[i] = constants.layout.starting_line
            _set_ball_vy(i, -1)
            _reset_bird_power(i)
            continue

        # Bird dies
        state.birds.lost[i] = True
        state.birds.y[i] = constants.layout.height - 1
        state.birds.per_bird_xp[i] = 0
        state.game.lives -= 1
        play_sfx('bird_lost')

        if state.game.lives <= 0:
            state.game.game_over = True


def _get_obstacle_lanes(obs):
    """Ritorna il set di lane occupate da un ostacolo."""
    obs_tier = obs.get('tier', 1)
    obs_width = OBSTACLE_LANE_WIDTH.get(obs_tier, 1)
    obs_lane = obs['lane']
    return set(range(obs_lane, min(obs_lane + obs_width, constants.layout.num_lanes)))


def check_bird_obstacle_collision():
    """Check bird-obstacle collisions."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_color = state.birds.colors[i]
        next_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_color == STEALTH and i not in state.special.stealth_timers:
            continue

        for obs in state.enemies.obstacles[:]:
            # Check if bird lane is within obstacle's lanes
            obs_lanes = _get_obstacle_lanes(obs)
            if bird_lane not in obs_lanes:
                continue

            # Check vertical proximity (consider sprite height)
            obs_tier = obs.get('tier', 1)
            sprite_height = len(OBSTACLE_SPRITES.get(obs_tier, OBSTACLE_SPRITE_T1))
            if next_y < obs['y_pos'] - 1 or next_y > obs['y_pos'] + sprite_height:
                continue

            # Hit obstacle
            damage = _calculate_bird_damage(i)

            if bird_color == ORANGE:
                obs['hp'] = 0
            else:
                obs['hp'] -= damage
                award_xp(i, damage)

            if obs['hp'] <= 0:
                tier = obs.get('tier', 1)
                award_xp(i, 5 * tier)
                add_score(tier * 50)
                state.enemies.obstacles.remove(obs)
                play_sfx('destroy')
            else:
                _set_ball_vy(i, 1)
                # Applica stun (1 secondo) - impedisce bounce
                stun_frames = int(1.0 / constants.timing.base_sleep)
                state.special.stunned_birds[i] = stun_frames
                # Aggiungi a scared_birds per speed boost in caduta (1 secondo)
                state.special.scared_birds[i] = stun_frames
                if bird_color == BLUE:
                    _reset_bird_power(i)
                play_sfx('hit')
            break


def check_bird_bat_collision():
    """Check bird-bat collisions."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_lane_x = constants.layout.lane_positions[bird_lane]
        bird_color = state.birds.colors[i]
        next_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_color == STEALTH and i not in state.special.stealth_timers:
            continue

        bird_height = 3 if bird_color == DINOSAUR else 2

        for bat in state.enemies.bats[:]:
            bat_left = bat['x_pos']
            bat_right = bat['x_pos'] + 8
            bat_top = bat['y_pos']
            bat_bottom = bat['y_pos'] + 1

            lane_left = bird_lane_x - 2
            lane_right = bird_lane_x + 2

            horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)
            vertical_overlap = not (next_y + bird_height < bat_top or next_y > bat_bottom)

            if not (horizontal_overlap and vertical_overlap):
                continue

            # Hit bat
            damage = _calculate_bird_damage(i)

            if bird_color == ORANGE:
                bat['hp'] = 0
            else:
                bat['hp'] -= damage
                award_xp(i, damage)

            # Apply scared effect (unless stealth tangible)
            is_stealth_tangible = bird_color == STEALTH and i in state.special.stealth_timers
            if not is_stealth_tangible:
                bat_tier = bat.get('tier', 1)
                state.special.scared_birds[i] = get_scared_frames(i, 2.0)
                if bat_tier >= 3:
                    state.special.speed_boosts[i] = int(2.0 / constants.timing.base_sleep)

            if bat['hp'] <= 0:
                _handle_bat_death(bat, i)
            else:
                _set_ball_vy(i, 1)
                state.birds.y[i] = bat_bottom + 1
                if bird_color == BLUE:
                    _reset_bird_power(i)
            break


def _calculate_bird_damage(bird_idx):
    """Calculate damage a bird deals."""
    bird_color = state.birds.colors[bird_idx]

    if bird_color == DINOSAUR:
        return 16
    elif bird_color == STEALTH and bird_idx in state.special.stealth_timers:
        return 24
    elif bird_color == GOLD:
        return 1
    elif bird_color == GLITCH:
        return random.randint(1, 32)

    current_speed = state.birds.speeds[bird_idx]
    if bird_color == BLUE and state.birds.power_used[bird_idx]:
        current_speed += 1
    return current_speed


def _handle_bat_death(bat, killer_bird_idx):
    """Handle bat death: score, loot drop, achievements."""
    tier = bat.get('tier', 1)
    award_xp(killer_bird_idx, 5 * tier)
    add_score(bat.get('max_hp', 0))

    # Drop loot at closest lane
    bat_center_x = bat['x_pos'] + 4
    closest_lane = min(range(constants.layout.num_lanes),
                       key=lambda l: abs(constants.layout.lane_positions[l] - bat_center_x))

    prestige = compute_prestige()
    base_weights = [60, 25, 10, 5]
    adj_weights = adjust_rarity_weights(base_weights, prestige)
    rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
    loot_type = choose_loot_type(rarity)

    state.items.loot_items.append({
        'x_pos': constants.layout.lane_positions[closest_lane],
        'y_pos': bat['y_pos'],
        'type': loot_type,
        'rarity': rarity,
        'spawn_ts': time.time()
    })

    # Notify achievements
    bird_color = state.birds.colors[killer_bird_idx]
    if bird_color == ORANGE:
        achievements.check_achievements_event('destroy_bat_with_orange', state.game.frame_count, state.ui.notifications)
    achievements.check_achievements_event('destroy_bat', state.game.frame_count, state.ui.notifications, tier=tier)

    state.enemies.bats.remove(bat)
    play_sfx('destroy')


def check_projectile_collision():
    """Check projectile-enemy collisions."""
    for proj in state.special.red_projectiles[:]:
        removed = False

        # Check bat collision
        for bat in state.enemies.bats[:]:
            bat_left = bat['x_pos']
            bat_right = bat['x_pos'] + 8
            bat_top = bat['y_pos']
            bat_bottom = bat['y_pos'] + 1

            if (bat_left <= proj['x_pos'] <= bat_right and
                bat_top <= proj['y_pos'] <= bat_bottom):

                damage = proj.get('damage', 1)
                bat['hp'] -= damage

                owner = proj.get('owner')
                if owner is not None:
                    award_xp(owner, damage)

                if bat['hp'] <= 0:
                    _handle_bat_death(bat, owner if owner is not None else 0)

                if proj in state.special.red_projectiles:
                    state.special.red_projectiles.remove(proj)
                removed = True
                break

        if removed:
            continue

        # Check obstacle collision
        for obs in state.enemies.obstacles[:]:
            # Check if projectile lane is within obstacle's lanes
            obs_lanes = _get_obstacle_lanes(obs)
            if proj['lane'] not in obs_lanes:
                continue

            # Check vertical proximity (consider sprite height)
            obs_tier = obs.get('tier', 1)
            sprite_height = len(OBSTACLE_SPRITES.get(obs_tier, OBSTACLE_SPRITE_T1))
            if proj['y_pos'] < obs['y_pos'] - 1 or proj['y_pos'] > obs['y_pos'] + sprite_height:
                continue

            damage = proj.get('damage', 1)
            obs['hp'] -= damage

            owner = proj.get('owner')
            if owner is not None:
                award_xp(owner, damage)

            if obs['hp'] <= 0:
                tier = obs.get('tier', 1)
                if owner is not None:
                    award_xp(owner, 5 * tier)
                add_score(tier * 50)
                state.enemies.obstacles.remove(obs)

            if proj in state.special.red_projectiles:
                state.special.red_projectiles.remove(proj)
            break


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
                if r < 0.05:  # Ignore
                    continue
                elif r < 0.10:  # Promote rarity
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
    elif loot_type.startswith('shuffle'):
        _apply_shuffle_power(loot_type)


def _spawn_bird_from_egg(egg_type):
    """Spawn a new bird from an egg."""
    color_map = {
        'yellow_egg': YELLOW, 'red_egg': RED, 'blue_egg': BLUE,
        'white_egg': WHITE, 'purple_egg': PURPLE, 'orange_egg': ORANGE,
        'gold_egg': GOLD, 'patchwork_egg': PATCHWORK, 'cookie_egg': COOKIE,
        'clockwork_egg': CLOCKWORK, 'stealth_egg': STEALTH,
        'dinosaur_egg': DINOSAUR, 'glitch_egg': GLITCH
    }
    speed_map = {
        'yellow_egg': 2, 'red_egg': 3, 'blue_egg': 4, 'white_egg': 5,
        'purple_egg': 3, 'orange_egg': 5, 'gold_egg': 6, 'patchwork_egg': 3,
        'cookie_egg': 3, 'clockwork_egg': 2, 'stealth_egg': 3,
        'dinosaur_egg': 4, 'glitch_egg': 3
    }

    bird_color = color_map.get(egg_type)
    if bird_color is None:
        return

    # Find first lost bird to revive
    for idx in range(constants.layout.num_balls):
        if state.birds.lost[idx]:
            state.birds.lost[idx] = False
            state.birds.colors[idx] = bird_color
            state.birds.speeds[idx] = speed_map.get(egg_type, 3)
            state.birds.y[idx] = constants.layout.starting_line
            state.birds.vy[idx] = -1
            state.birds.transformed[idx] = False
            state.birds.per_bird_xp[idx] = 0
            state.game.lives += 1

            if bird_color == CLOCKWORK:
                state.special.clockwork_charge[idx] = constants.clockwork.initial_charge
            break


def _apply_wide_cursor_power(loot_type):
    """Apply wide cursor powerup."""
    state.powerups.wide_cursor_active = True

    if loot_type == 'wide_cursor':
        seconds = 10
        lanes = 3
    elif loot_type == 'wide_cursor+':
        seconds = 15
        lanes = 3
    elif loot_type == 'wide_cursor++':
        seconds = 20
        lanes = 5
    else:  # max
        seconds = 30
        lanes = 5

    state.powerups.wide_cursor_frames = int(seconds / constants.timing.base_sleep)
    state.powerups.wide_cursor_lanes = lanes
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='wide_cursor')


def _apply_bounce_boost_power(loot_type):
    """Apply bounce boost powerup."""
    state.powerups.bounce_boost_active = True

    if loot_type == 'bounce_boost':
        seconds = 10
        duration = 1.0
    elif loot_type == 'bounce_boost+':
        seconds = 15
        duration = 1.5
    elif loot_type == 'bounce_boost++':
        seconds = 20
        duration = 2.0
    else:  # max
        seconds = 30
        duration = 3.0

    state.powerups.bounce_boost_frames = int(seconds / constants.timing.base_sleep)
    state.powerups.bounce_boost_duration = duration
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='bounce_boost')


def _apply_suction_power(loot_type):
    """Apply suction powerup."""
    state.powerups.suction_active = True

    if loot_type == 'suction':
        seconds = 10
        boost = 1.0
    elif loot_type == 'suction+':
        seconds = 15
        boost = 1.5
    elif loot_type == 'suction++':
        seconds = 20
        boost = 2.0
    else:  # max
        seconds = 30
        boost = 3.0

    state.powerups.suction_frames = int(seconds / constants.timing.base_sleep)
    state.powerups.suction_boost_duration = boost
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='suction')


def _apply_tailwind_power(loot_type):
    """Apply tailwind powerup."""
    state.powerups.tailwind_active = True

    if loot_type == 'tailwind':
        seconds = 10
        up_bonus = 1
        down_pen = 1
    elif loot_type == 'tailwind+':
        seconds = 15
        up_bonus = 1
        down_pen = 1
    elif loot_type == 'tailwind++':
        seconds = 20
        up_bonus = 2
        down_pen = 2
    else:  # max
        seconds = 30
        up_bonus = 2
        down_pen = 2

    state.powerups.tailwind_frames = int(seconds / constants.timing.base_sleep)
    state.powerups.tailwind_up_bonus = up_bonus
    state.powerups.tailwind_down_penalty = down_pen
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='tailwind')


def _apply_shuffle_power(loot_type):
    """Apply shuffle powerup."""
    level_map = {
        'shuffle': 2, 'shuffle+': 4, 'shuffle++': 6, 'shuffle_max': 9
    }
    level = level_map.get(loot_type, 2)
    perform_shuffle(level)
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power='shuffle')


def check_bat_obstacle_collision():
    """Check bat-obstacle collisions (bats destroy obstacles)."""
    for bat in state.enemies.bats:
        bat_left = bat['x_pos']
        bat_right = bat['x_pos'] + 8
        bat_top = bat['y_pos']
        bat_bottom = bat['y_pos'] + 1

        for obs in state.enemies.obstacles[:]:
            # Calcola l'area occupata dall'ostacolo (multi-lane)
            tier = obs.get('tier', 1)
            lane_width = OBSTACLE_LANE_WIDTH.get(tier, 1)
            sprite = OBSTACLE_SPRITES.get(tier, OBSTACLE_SPRITE_T1)
            sprite_width = max(len(line) for line in sprite)
            sprite_height = len(sprite)

            start_lane = obs['lane']
            end_lane = min(start_lane + lane_width - 1, constants.layout.num_lanes - 1)

            start_x = constants.layout.lane_positions[start_lane]
            end_x = constants.layout.lane_positions[end_lane]
            center_x = (start_x + end_x) // 2

            obs_left = center_x - sprite_width // 2
            obs_right = center_x + sprite_width // 2
            obs_top = obs['y_pos']
            obs_bottom = obs['y_pos'] + sprite_height

            horizontal_overlap = not (bat_right < obs_left or bat_left > obs_right)
            vertical_overlap = not (bat_bottom < obs_top or bat_top > obs_bottom)

            if horizontal_overlap and vertical_overlap:
                state.enemies.obstacles.remove(obs)


# =============================================================================
# SPAWNING
# =============================================================================

def spawn_obstacle():
    """Potentially spawn a new obstacle."""
    state.enemies.obstacle_spawn_timer -= 1
    if state.enemies.obstacle_spawn_timer > 0:
        return

    level = compute_level_from_score(state.game.score)
    # Spawn più frequente: da 50 a livello 1, fino a 10 a livelli alti
    base_spawn_rate = max(10, 50 - level * 4)
    state.enemies.obstacle_spawn_timer = base_spawn_rate

    # Tier based on level - più aggressivo
    if level <= 2:
        tier = random.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]
    elif level <= 4:
        tier = random.choices([1, 2, 3, 4], weights=[30, 35, 25, 10])[0]
    elif level <= 6:
        tier = random.choices([1, 2, 3, 4], weights=[20, 30, 35, 15])[0]
    else:
        tier = random.choices([1, 2, 3, 4], weights=[10, 25, 40, 25])[0]

    # Larghezza in lane per questo tier
    lane_width = OBSTACLE_LANE_WIDTH.get(tier, 1)

    # Trova gruppi di lane consecutive libere
    def get_lanes_occupied_by_obstacle(obs):
        """Ritorna set di lane occupate da un ostacolo."""
        obs_tier = obs.get('tier', 1)
        obs_width = OBSTACLE_LANE_WIDTH.get(obs_tier, 1)
        obs_lane = obs['lane']
        return set(range(obs_lane, min(obs_lane + obs_width, constants.layout.num_lanes)))

    # Mappa quali lane sono occupate
    occupied_lanes = set()
    for obs in state.enemies.obstacles:
        if obs['y_pos'] < 5:  # Solo ostacoli vicini al top
            occupied_lanes.update(get_lanes_occupied_by_obstacle(obs))

    # Trova posizioni valide per il nuovo ostacolo (lane iniziale)
    valid_start_lanes = []
    for start_lane in range(constants.layout.num_lanes - lane_width + 1):
        lanes_needed = set(range(start_lane, start_lane + lane_width))
        if not lanes_needed & occupied_lanes:
            valid_start_lanes.append(start_lane)

    if not valid_start_lanes:
        state.enemies.obstacle_spawn_timer = max(5, base_spawn_rate // 4)
        return

    # Permetti più ostacoli consecutivi ai livelli alti
    consecutive_limit = 2 + level // 3  # 2 a lv1, 3 a lv3, 4 a lv6, etc.
    if len(state.enemies.spawn_queue) >= consecutive_limit:
        obstacle_count = sum(1 for item in state.enemies.spawn_queue[-consecutive_limit:]
                            if item.get('type') == 'obstacle')
        if obstacle_count >= consecutive_limit:
            state.enemies.obstacle_spawn_timer = max(5, base_spawn_rate // 4)
            return

    lane = random.choice(valid_start_lanes)

    # HP bilanciati per danno uccelli (giallo 2, rosso 3, blu 4)
    hp_map = {1: 4, 2: 6, 3: 12, 4: 27}
    hp = hp_map.get(tier, 4)

    # Calcola altezza sprite per far entrare l'ostacolo gradualmente dall'alto
    sprite = OBSTACLE_SPRITES.get(tier, OBSTACLE_SPRITE_T1)
    sprite_height = len(sprite)
    # Spawn fuori schermo: y negativo così entra gradualmente
    start_y = -sprite_height + 1

    state.enemies.spawn_queue.append({
        'type': 'obstacle',
        'data': {'lane': lane, 'y_pos': start_y, 'tier': tier, 'hp': hp}
    })


def spawn_bat():
    """Potentially spawn a new bat."""
    state.enemies.bat_spawn_timer -= 1
    if state.enemies.bat_spawn_timer > 0:
        return

    level = compute_level_from_score(state.game.score)
    if level < 3:  # Bats iniziano a livello 3
        return

    # Spawn rate PROGRESSIVO e ragionevole:
    # Lv 3-5:   ogni ~200 frame (raro)
    # Lv 6-10:  ogni ~150 frame
    # Lv 11-15: ogni ~100 frame
    # Lv 16-20: ogni ~70 frame
    # Lv 21-30: ogni ~50 frame
    if level <= 5:
        base_spawn_rate = 200
    elif level <= 10:
        base_spawn_rate = 150
    elif level <= 15:
        base_spawn_rate = 100
    elif level <= 20:
        base_spawn_rate = 70
    else:
        base_spawn_rate = 50

    state.enemies.bat_spawn_timer = base_spawn_rate

    # Max bats on screen PROGRESSIVO:
    # Lv 3-5:   max 1
    # Lv 6-10:  max 2
    # Lv 11-15: max 3
    # Lv 16-20: max 4
    # Lv 21-30: max 5
    if level <= 5:
        max_bats = 1
    elif level <= 10:
        max_bats = 2
    elif level <= 15:
        max_bats = 3
    elif level <= 20:
        max_bats = 4
    else:
        max_bats = 5

    if len(state.enemies.bats) >= max_bats:
        state.enemies.bat_spawn_timer = base_spawn_rate // 2
        return

    # Tier based on level - progressivo
    if level <= 5:
        tier = random.choices([1, 2, 3, 4], weights=[70, 25, 5, 0])[0]
    elif level <= 10:
        tier = random.choices([1, 2, 3, 4], weights=[50, 35, 12, 3])[0]
    elif level <= 15:
        tier = random.choices([1, 2, 3, 4], weights=[30, 40, 22, 8])[0]
    elif level <= 20:
        tier = random.choices([1, 2, 3, 4], weights=[15, 35, 35, 15])[0]
    else:
        tier = random.choices([1, 2, 3, 4], weights=[5, 25, 45, 25])[0]

    # HP ragionevoli ma sfidanti
    hp_map = {1: 20, 2: 40, 3: 70, 4: 120}
    hp = hp_map.get(tier, 20)

    # Spawn position X
    x_pos = random.randint(0, constants.layout.width - 8)

    # Target Y PROGRESSIVO - più in alto all'inizio, più in basso ai livelli alti
    # starting_line è dove stanno gli uccelli (es. 26)
    # All'inizio: target_y tra 3 e 10 (molto in alto, lontano)
    # Ai livelli alti: target_y tra 15 e starting_line-3 (più vicino agli uccelli)
    if level <= 5:
        target_y_min = 3
        target_y_max = 8
    elif level <= 10:
        target_y_min = 5
        target_y_max = 12
    elif level <= 15:
        target_y_min = 8
        target_y_max = 16
    elif level <= 20:
        target_y_min = 10
        target_y_max = 20
    else:
        target_y_min = 12
        target_y_max = constants.layout.starting_line - 5

    target_y = random.randint(target_y_min, min(target_y_max, constants.layout.starting_line - 3))

    # Pipistrelli hanno sprite di 2 righe, spawn fuori schermo
    bat_sprite_height = 2
    start_y = -bat_sprite_height + 1

    state.enemies.spawn_queue.append({
        'type': 'bat',
        'data': {
            'x_pos': x_pos,
            'y_pos': start_y,
            'direction': random.choice([-1, 1]),
            'tier': tier,
            'hp': hp,
            'max_hp': hp,
            'target_y': target_y,
            'spawn_ts': time.time()
        }
    })


def process_spawn_queue():
    """Process the spawn queue to actually spawn entities."""
    while state.enemies.spawn_queue:
        item = state.enemies.spawn_queue.pop(0)
        if item['type'] == 'obstacle':
            state.enemies.obstacles.append(item['data'])
        elif item['type'] == 'bat':
            state.enemies.bats.append(item['data'])


# =============================================================================
# POWERUP TIMER UPDATES
# =============================================================================

def update_powerup_timers():
    """Update all powerup timers."""
    if state.powerups.wide_cursor_active:
        state.powerups.wide_cursor_frames -= 1
        if state.powerups.wide_cursor_frames <= 0:
            state.powerups.wide_cursor_active = False
            state.powerups.wide_cursor_lanes = 1

    if state.powerups.bounce_boost_active:
        state.powerups.bounce_boost_frames -= 1
        if state.powerups.bounce_boost_frames <= 0:
            state.powerups.bounce_boost_active = False
            state.powerups.bounce_boost_duration = 0

    if state.powerups.suction_active:
        state.powerups.suction_frames -= 1
        if state.powerups.suction_frames <= 0:
            state.powerups.suction_active = False
            state.powerups.suction_boost_duration = 0

    if state.powerups.tailwind_active:
        state.powerups.tailwind_frames -= 1
        if state.powerups.tailwind_frames <= 0:
            state.powerups.tailwind_active = False
            state.powerups.tailwind_up_bonus = 0
            state.powerups.tailwind_down_penalty = 0


def update_special_bird_states():
    """Update special bird state timers (speed boosts, scared, stealth, etc.)."""
    # Speed boosts
    for bird_idx in list(state.special.speed_boosts.keys()):
        if state.special.speed_boosts[bird_idx] > 0:
            state.special.speed_boosts[bird_idx] -= 1
            if state.special.speed_boosts[bird_idx] <= 0:
                del state.special.speed_boosts[bird_idx]
                if state.birds.colors[bird_idx] == BLUE:
                    _reset_bird_power(bird_idx)
        else:
            state.special.speed_boosts[bird_idx] += 1
            if state.special.speed_boosts[bird_idx] >= 0:
                del state.special.speed_boosts[bird_idx]

    # Scared birds
    for bird_idx in list(state.special.scared_birds.keys()):
        state.special.scared_birds[bird_idx] -= 1
        if state.special.scared_birds[bird_idx] <= 0:
            del state.special.scared_birds[bird_idx]

    # Stunned birds (from obstacle collision - short duration, no speed boost)
    for bird_idx in list(state.special.stunned_birds.keys()):
        state.special.stunned_birds[bird_idx] -= 1
        if state.special.stunned_birds[bird_idx] <= 0:
            del state.special.stunned_birds[bird_idx]

    # Stealth timers
    for bird_idx in list(state.special.stealth_timers.keys()):
        state.special.stealth_timers[bird_idx] -= 1
        if state.special.stealth_timers[bird_idx] <= 0:
            del state.special.stealth_timers[bird_idx]
            if bird_idx in state.special.stealth_prev_speeds:
                state.birds.speeds[bird_idx] = state.special.stealth_prev_speeds.pop(bird_idx)

    # Purple just-fired protection
    for i in range(constants.layout.num_balls):
        if state.special.purple_just_fired_frames[i] > 0:
            state.special.purple_just_fired_frames[i] -= 1


def update_purple_charging():
    """Update purple bird charging state machine."""
    for b in range(constants.layout.num_balls):
        ps = state.special.purple_state[b]

        if ps == 1:  # Primed
            # Check if still holding
            held_long_enough = state.game.frame_count > state.special.purple_primed_frame[b]
            if held_long_enough and not state.birds.lost[b] and state.birds.vy[b] == -1:
                state.special.purple_state[b] = 2
                state.special.purple_charge_started_frame[b] = state.game.frame_count

        elif ps == 2:  # Charging
            elapsed_frames = state.game.frame_count - state.special.purple_charge_started_frame[b]
            charge_seconds = elapsed_frames * constants.timing.base_sleep

            # Auto-fire at 3 seconds
            if charge_seconds >= 3:
                _fire_purple_projectile(b, 3)


def _fire_purple_projectile(bird_idx, charge_seconds):
    """Fire a purple charged projectile."""
    damage = int(pow(4, charge_seconds))
    lane = state.birds.random_lanes[bird_idx]

    state.special.red_projectiles.append({
        'x_pos': constants.layout.lane_positions[lane],
        'y_pos': state.birds.y[bird_idx],
        'lane': lane,
        'damage': damage,
        'powered': damage > 1,
        'owner': bird_idx,
        'speed': 4,
        'color': PURPLE
    })

    state.special.purple_just_fired_frames[bird_idx] = 3
    state.special.purple_state[bird_idx] = 0
    state.special.purple_charge_started_frame[bird_idx] = 0
    state.special.purple_primed_frame[bird_idx] = 0


def despawn_old_entities():
    """Remove entities that have been around too long."""
    now = time.time()

    # Bats older than 60 seconds
    for bat in state.enemies.bats[:]:
        if now - bat.get('spawn_ts', now) > 60:
            state.enemies.bats.remove(bat)

    # Loot older than 30 seconds
    for loot in state.items.loot_items[:]:
        if now - loot.get('spawn_ts', now) > 30:
            # Orange eggs kill their bird when they despawn
            if loot.get('type') == 'orange_egg' and loot.get('y_pos') == constants.layout.starting_line:
                lane_x = loot.get('x_pos')
                for li in range(constants.layout.num_lanes):
                    if constants.layout.lane_positions[li] == lane_x:
                        for bi in range(constants.layout.num_balls):
                            if (state.birds.random_lanes[bi] == li and
                                state.birds.colors[bi] == ORANGE and
                                state.birds.y[bi] == 999 and
                                not state.birds.lost[bi]):
                                state.birds.lost[bi] = True
                                state.birds.y[bi] = constants.layout.height - 1
                                state.game.lives -= 1
                                if state.game.lives <= 0:
                                    state.game.game_over = True
                                break
                        break
            state.items.loot_items.remove(loot)


def update_score_tick():
    """Award score based on active birds (called each frame)."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        # Only on move frames
        current_speed = state.birds.speeds[i]
        move_interval = max(1, 6 - current_speed)

        if state.game.frame_count % move_interval != 0:
            continue

        position_mult = 0.5 + (constants.layout.height - state.birds.y[i]) / constants.layout.height

        if state.birds.colors[i] == GOLD:
            score_val = 100
        else:
            score_val = current_speed

        add_score(score_val * position_mult, by_bird=i)


def calculate_frame_sleep():
    """Calculate the sleep duration for current frame."""
    level = compute_level_from_score(state.game.score)
    # Exponential speed increase: multiplier^level (e.g. 0.88^level)
    multiplier = getattr(constants.timing, 'frame_sleep_level_multiplier', 0.88)
    sleep_time = constants.timing.base_sleep * (multiplier ** level)
    return max(constants.timing.min_sleep, sleep_time)


# =============================================================================
# MAIN UPDATE FUNCTION
# =============================================================================

def update_all():
    """Run all game logic updates in correct order."""
    # Score tick
    update_score_tick()

    # Collisions
    check_bird_ceiling_bounce()
    check_bird_obstacle_collision()
    check_bird_bat_collision()
    check_projectile_collision()
    check_loot_collection()
    check_bat_obstacle_collision()
    check_bird_floor_collision()

    # Spawning
    spawn_obstacle()
    spawn_bat()
    process_spawn_queue()

    # Timer updates
    update_powerup_timers()
    update_special_bird_states()
    update_purple_charging()

    # Cleanup
    despawn_old_entities()
