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
    compute_prestige,
    add_score,
    update_momentum,
    award_xp,
    adjust_rarity_weights,
    choose_loot_type,
    get_scared_frames,
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


# Mapping from ANSI color codes to bird type names for audio
COLOR_TO_BIRD_TYPE = {
    YELLOW: 'YELLOW',
    RED: 'RED',
    BLUE: 'BLUE',
    PURPLE: 'PURPLE',
    WHITE: 'WHITE',
    ORANGE: 'ORANGE',
    GOLD: 'GOLD',
    PATCHWORK: 'PATCHWORK',
    COOKIE: 'COOKIE',
    CLOCKWORK: 'CLOCKWORK',
    STEALTH: 'STEALTH',
    DINOSAUR: 'DINOSAUR',
    GLITCH: 'GLITCH',
}


_last_bird_sync_frame = 0
_last_bird_set = None


def sync_active_birds_audio(force=False):
    """Sync the active bird types with the audio system for dynamic music."""
    global _last_bird_sync_frame, _last_bird_set

    if not AUDIO_AVAILABLE or not audio:
        return

    # Only sync periodically to avoid blocking
    # Unless force=True (used at game start)
    audio_sync_interval = getattr(constants.timing, 'audio_sync_interval', 60)
    if not force and state.game.frame_count - _last_bird_sync_frame < audio_sync_interval:
        return
    _last_bird_sync_frame = state.game.frame_count

    active_types = set()
    for i in range(len(state.birds.colors)):
        if not state.birds.lost[i]:
            color = state.birds.colors[i]
            bird_type = COLOR_TO_BIRD_TYPE.get(color)
            if bird_type:
                active_types.add(bird_type)

    # Only update if birds actually changed (or force)
    if force or active_types != _last_bird_set:
        _last_bird_set = active_types
        audio.update_active_birds(active_types)


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
    """Ritorna il set di lane occupate da un ostacolo basandosi sulla larghezza sprite."""
    obs_lane = obs['lane']
    # Usa sprite_width salvato nell'ostacolo, o calcola dalla sprite
    sprite_width = obs.get('sprite_width')
    if sprite_width is None:
        # Fallback: calcola dalla sprite del tier
        obs_tier = obs.get('tier', 1)
        sprite = get_biome_obstacles(state.game.level_group).get(obs_tier, OBSTACLE_SPRITE_T1)
        sprite_width = get_obstacle_sprite_width(sprite)

    return get_obstacle_hitbox_lanes(
        obs_lane,
        sprite_width,
        constants.layout.lane_positions,
        constants.layout.num_lanes
    )


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

            # Check if obstacle has a mature flower - apply effect before damage
            flower = obs.get('flower')
            from src.entities.sprites import FLOWER_MATURE_FRAME
            if flower and flower.get('active') and flower.get('frame', 0) >= FLOWER_MATURE_FRAME:
                _apply_flower_collision_effect(flower, i)

            if bird_color == ORANGE:
                obs['hp'] = 0
            else:
                obs['hp'] -= damage
                award_xp(i, damage)
                # Also damage flower if present
                if flower and flower.get('active') and flower.get('hp', 0) > 0:
                    flower['hp'] -= damage
                    if flower['hp'] <= 0:
                        flower['active'] = False

            # Try to spawn mini bat on each hit (tier 3+ only, if Y position ok)
            try_spawn_mini_bat_on_hit(obs)

            if obs['hp'] <= 0:
                tier = obs.get('tier', 1)
                xp_per_tier = getattr(constants.combat, 'obstacle_destroy_xp_per_tier', 5)
                score_per_tier = getattr(constants.combat, 'obstacle_destroy_score_per_tier', 50)
                award_xp(i, xp_per_tier * tier)
                add_score(tier * score_per_tier)
                # Handle mini bat hiding before removing obstacle
                handle_obstacle_destroyed(obs)
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

            # Apply armor damage reduction for armored bats
            is_armored = bat.get('armored', False)
            if is_armored and bird_color != ORANGE:
                armored_cfg = getattr(constants.bat_enemy, 'armored', None)
                if armored_cfg:
                    bat_tier = bat.get('tier', 1)
                    dmg_reduction_cfg = getattr(armored_cfg, 'damage_reduction_by_tier', None)
                    if dmg_reduction_cfg:
                        if isinstance(dmg_reduction_cfg, dict):
                            reduction = dmg_reduction_cfg.get(bat_tier, dmg_reduction_cfg.get(str(bat_tier), 0))
                        else:
                            reduction = getattr(dmg_reduction_cfg, str(bat_tier), 0)
                        damage = max(1, damage - reduction)  # Minimum 1 damage

            if bird_color == ORANGE:
                bat['hp'] = 0
            else:
                bat['hp'] -= damage
                award_xp(i, damage)

            # Check if diver bat in stunned/returning state (no scare)
            is_diver = bat.get('diver', False)
            diver_state = bat.get('diver_state', 'flying')
            diver_no_scare = is_diver and diver_state in ('stunned', 'returning')

            # Apply scared effect (unless stealth tangible or diver stunned/returning)
            is_stealth_tangible = bird_color == STEALTH and i in state.special.stealth_timers
            if not is_stealth_tangible and not diver_no_scare:
                bat_tier = bat.get('tier', 1)
                scared_duration = getattr(constants.combat, 'scared_duration', 2.0)
                state.special.scared_birds[i] = get_scared_frames(i, scared_duration)
                speed_boost_min_tier = getattr(constants.combat, 'speed_boost_min_tier', 3)
                if bat_tier >= speed_boost_min_tier:
                    speed_boost_duration = getattr(constants.combat, 'speed_boost_duration', 2.0)
                    state.special.speed_boosts[i] = int(speed_boost_duration / constants.timing.base_sleep)

                # Armored bats give additional scare speed boost
                if is_armored:
                    armored_cfg = getattr(constants.bat_enemy, 'armored', None)
                    if armored_cfg:
                        armor_scare_bonus = getattr(armored_cfg, 'scare_speed_bonus', 1)
                        armor_scare_duration = getattr(armored_cfg, 'scare_bonus_duration', 1.0)
                        armor_scare_frames = int(armor_scare_duration / constants.timing.base_sleep)
                        # Add to existing speed boost or create new one
                        current_boost = state.special.speed_boosts.get(i, 0)
                        state.special.speed_boosts[i] = max(current_boost, armor_scare_frames) + armor_scare_bonus

            # Diver bats in diving state give fall speed boost
            if is_diver and diver_state == 'diving':
                diver_cfg = getattr(constants.bat_enemy, 'diver', None)
                if diver_cfg:
                    dive_boost_speed = getattr(diver_cfg, 'dive_boost_speed', 1)
                    dive_boost_duration = getattr(diver_cfg, 'dive_boost_duration', 0.5)
                    dive_boost_frames = int(dive_boost_duration / constants.timing.base_sleep)
                    # Apply dive fall boost (separate from scared speed boost)
                    state.special.dive_fall_boosts[i] = {
                        'frames': dive_boost_frames,
                        'speed': dive_boost_speed
                    }

            if bat['hp'] <= 0:
                _handle_bat_death(bat, i)
            else:
                _set_ball_vy(i, 1)
                state.birds.y[i] = bat_bottom + 1
                if bird_color == BLUE:
                    _reset_bird_power(i)
            break


def _calculate_bird_damage(bird_idx):
    """Calculate damage a bird deals using formula:
    TOT = round(((GR * 0.1) + (DMG + DMGBOOST - DMGNERF)) * (SPD + SPDBOOST - SPDNERF))

    Where:
    - GR = gear/speed (state.game.speed, 1-10)
    - DMG = base damage from config (constants.birds.damage)
    - SPD = base speed from config (constants.birds.speed)
    - DMGBOOST/DMGNERF = damage modifiers
    - SPDBOOST/SPDNERF = speed modifiers
    """
    from src.entities.bird_types import get_bird_type_by_color

    bird_color = state.birds.colors[bird_idx]

    # Get bird type name for config lookup
    bird_type = get_bird_type_by_color(bird_color)
    if bird_type is None:
        # Fallback for special colors like STEALTH
        if bird_color == STEALTH:
            bird_type = 'STEALTH'
        else:
            bird_type = 'YELLOW'  # Default fallback

    # Get type name in lowercase for config lookup
    type_name = bird_type.lower()

    # Get base stats from config
    dmg_config = getattr(constants.birds, 'damage', {})
    spd_config = getattr(constants.birds, 'speed', {})

    # Handle both dict and namespace
    if hasattr(dmg_config, '__getitem__'):
        base_dmg = dmg_config.get(type_name, 1)
    else:
        base_dmg = getattr(dmg_config, type_name, 1)

    if hasattr(spd_config, '__getitem__'):
        base_spd = spd_config.get(type_name, 2)
    else:
        base_spd = getattr(spd_config, type_name, 2)

    # Get gear (speed level 1-10)
    gear = state.game.speed

    # Initialize boost/nerf values
    dmg_boost = 0
    dmg_nerf = 0
    spd_boost = 0
    spd_nerf = 0

    # Special case: Orange does instant kill (very high damage)
    if bird_color == ORANGE:
        return 9999

    # Special case: Glitch has random multiplier
    if bird_color == GLITCH:
        glitch_min = getattr(constants.combat, 'glitch_dmg_multiplier_min', 1)
        glitch_max = getattr(constants.combat, 'glitch_dmg_multiplier_max', 8)
        random_mult = random.randint(glitch_min, glitch_max)
        base_dmg *= random_mult

    # Special case: Stealth when tangible (in stealth_timers) gets damage boost
    if bird_color == STEALTH and bird_idx in state.special.stealth_timers:
        stealth_tangible_boost = getattr(constants.combat, 'stealth_tangible_dmg_boost', 4)
        dmg_boost += stealth_tangible_boost

    # Blue power gives speed boost
    if bird_color == BLUE and state.birds.power_used[bird_idx]:
        spd_boost += 1

    # Scared birds have speed nerf (optional - could be damage nerf)
    if bird_idx in state.special.scared_birds:
        spd_nerf += 1

    # Calculate final damage using formula
    # TOT = round(((GR - gear_offset) * gear_coeff + (DMG + DMGBOOST - DMGNERF)) * (SPD + SPDBOOST - SPDNERF))
    dmg_formula = getattr(constants.combat, 'damage_formula', None)
    gear_offset = getattr(dmg_formula, 'gear_offset', 3) if dmg_formula else 3
    gear_coeff = getattr(dmg_formula, 'gear_coefficient', 0.1) if dmg_formula else 0.1
    gear_bonus = (gear - gear_offset) * gear_coeff
    effective_dmg = base_dmg + dmg_boost - dmg_nerf
    effective_spd = base_spd + spd_boost - spd_nerf

    # Ensure minimum values
    effective_dmg = max(0, effective_dmg)
    effective_spd = max(1, effective_spd)

    total_damage = round((gear_bonus + effective_dmg) * effective_spd)

    # Minimum damage of 1
    return max(1, total_damage)


def _handle_bat_death(bat, killer_bird_idx):
    """Handle bat death: score, loot drop, achievements."""
    tier = bat.get('tier', 1)
    bat_xp_per_tier = getattr(constants.combat, 'bat_destroy_xp_per_tier', 5)
    award_xp(killer_bird_idx, bat_xp_per_tier * tier)
    add_score(bat.get('max_hp', 0))

    # Bats spawned by bosses NEVER drop loot (general rule)
    if not bat.get('from_boss'):
        # Drop loot at closest lane
        bat_center_x = bat['x_pos'] + 4
        closest_lane = min(range(constants.layout.num_lanes),
                           key=lambda l: abs(constants.layout.lane_positions[l] - bat_center_x))

        prestige = compute_prestige()
        base_weights = getattr(constants.loot, 'base_rarity_weights', [60, 25, 10, 5])
        if isinstance(base_weights, list):
            pass
        else:
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
    play_sfx('bat_death')  # Shrieking bat death sound!


def _handle_mini_bat_death(mini_bat, killer_bird_idx):
    """Handle mini bat (tier 0) death: score, loot drop, XP."""
    tier = mini_bat.get('tier', 0)
    bat_xp_per_tier = getattr(constants.combat, 'bat_destroy_xp_per_tier', 5)
    # Tier 0 gives less XP but still something
    award_xp(killer_bird_idx, max(1, bat_xp_per_tier * tier) if tier > 0 else 5)
    add_score(mini_bat.get('max_hp', 8))

    # Bats spawned by bosses NEVER drop loot (general rule)
    if not mini_bat.get('from_boss'):
        # Drop loot based on tier 0 loot weights
        loot_weights = constants.bat_enemy.loot_base_weights
        if isinstance(loot_weights, dict):
            tier_weights = loot_weights.get(0, loot_weights.get('0', [80, 15, 5, 0]))
        else:
            tier_weights = getattr(loot_weights, '0', [80, 15, 5, 0])

        # Adjust with prestige
        prestige = compute_prestige()
        adj_weights = adjust_rarity_weights(tier_weights, prestige)
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)

        # Drop loot at mini bat position (find closest lane)
        mb_x = mini_bat['x_pos']
        closest_lane = min(range(constants.layout.num_lanes),
                           key=lambda l: abs(constants.layout.lane_positions[l] - mb_x))

        state.items.loot_items.append({
            'x_pos': constants.layout.lane_positions[closest_lane],
            'y_pos': mini_bat['y_pos'],
            'type': loot_type,
            'rarity': rarity,
            'spawn_ts': time.time()
        })

    # Notify achievements (tier 0 bat)
    achievements.check_achievements_event('destroy_bat', state.game.frame_count, state.ui.notifications, tier=0)

    state.enemies.mini_bats.remove(mini_bat)
    play_sfx('bat_death')


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
                    xp_per_tier = getattr(constants.combat, 'obstacle_destroy_xp_per_tier', 5)
                    award_xp(owner, xp_per_tier * tier)
                score_per_tier = getattr(constants.combat, 'obstacle_destroy_score_per_tier', 50)
                add_score(tier * score_per_tier)
                state.enemies.obstacles.remove(obs)

            if proj in state.special.red_projectiles:
                state.special.red_projectiles.remove(proj)
            removed = True
            break

        if removed:
            continue

        # Check Tree Boss branch collision
        boss = state.enemies.boss
        if boss and boss.get('boss_type') == 'tree':
            branches = boss.get('branches', [])
            for branch in branches:
                if branch.get('destroyed'):
                    continue

                # Check if projectile is within branch bounds
                branch_left = branch['x_pos']
                branch_right = branch['x_pos'] + branch['sprite_width']
                branch_top = branch['y_pos']
                branch_bottom = branch['y_pos'] + branch['sprite_height']

                if (branch_left <= proj['x_pos'] <= branch_right and
                    branch_top <= proj['y_pos'] <= branch_bottom):

                    damage = proj.get('damage', 1)
                    owner = proj.get('owner')

                    # Damage flower first, then branch
                    flower = branch.get('flower')
                    if flower and flower.get('active') and flower.get('hp', 0) > 0:
                        flower['hp'] -= damage
                        if owner is not None:
                            award_xp(owner, damage)
                        if flower['hp'] <= 0:
                            flower['active'] = False
                            tree_boss_cfg = getattr(constants, 'tree_boss', None)
                            flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
                            respawn_delay = getattr(flowers_cfg, 'respawn_delay', 3.0) if flowers_cfg else 3.0
                            flower['respawn_timer'] = time.time() + respawn_delay
                    else:
                        # Damage branch
                        branch['hp'] -= damage
                        if owner is not None:
                            award_xp(owner, damage)
                        if branch['hp'] <= 0:
                            branch['destroyed'] = True
                            add_score(100)

                    if proj in state.special.red_projectiles:
                        state.special.red_projectiles.remove(proj)
                    removed = True
                    break

            if removed:
                continue


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
        'dinosaur_egg': DINOSAUR, 'glitch_egg': GLITCH
    }
    # Get speeds from config
    spd_config = getattr(constants.birds, 'speed', {})
    egg_to_bird = {
        'yellow_egg': 'yellow', 'red_egg': 'red', 'blue_egg': 'blue',
        'white_egg': 'white', 'purple_egg': 'purple', 'orange_egg': 'orange',
        'gold_egg': 'gold', 'patchwork_egg': 'patchwork', 'cookie_egg': 'cookie',
        'clockwork_egg': 'clockwork', 'stealth_egg': 'stealth',
        'dinosaur_egg': 'dinosaur', 'glitch_egg': 'glitch'
    }
    default_speeds = {
        'yellow': 2, 'red': 3, 'blue': 4, 'white': 4, 'purple': 3,
        'orange': 5, 'gold': 6, 'patchwork': 3, 'cookie': 3, 'clockwork': 2,
        'stealth': 3, 'dinosaur': 4, 'glitch': 3
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

    # Use milestone level (1-18) for spawning, not speed
    level = state.game.level
    level_group = state.game.level_group  # 1-6
    sub_level = ((level - 1) % 3) + 1     # 1, 2, or 3 within biome

    # Get spawn rate parameters from config
    spawning = constants.obstacle.spawning
    biome_base = getattr(spawning, 'biome_base', 40)
    biome_decay = getattr(spawning, 'biome_decay', 0.85)
    sublevel_decay = getattr(spawning, 'sublevel_decay', 0.9)
    min_spawn_rate = getattr(spawning, 'min_spawn_rate', 6)

    # Spawn rate formula from config
    base_spawn_rate = max(min_spawn_rate, int(biome_base * (biome_decay ** level_group) * (sublevel_decay ** (sub_level - 1))))
    state.enemies.obstacle_spawn_timer = base_spawn_rate

    # Get tier weights from config
    tier_weights = constants.obstacle.tier_weights
    if level <= 3:
        weights = getattr(tier_weights, 'level_1_3', [60, 28, 10, 2])
    elif level <= 6:
        weights = getattr(tier_weights, 'level_4_6', [45, 35, 15, 5])
    elif level <= 9:
        weights = getattr(tier_weights, 'level_7_9', [30, 35, 25, 10])
    elif level <= 12:
        weights = getattr(tier_weights, 'level_10_12', [20, 35, 30, 15])
    elif level <= 15:
        weights = getattr(tier_weights, 'level_13_15', [10, 30, 38, 22])
    else:
        weights = getattr(tier_weights, 'level_16_18', [5, 20, 45, 30])

    tier = random.choices([1, 2, 3, 4], weights=weights)[0]

    # Ottieni sprite del bioma per calcolare larghezza
    biome_obstacles_preview = get_biome_obstacles(level_group)
    new_sprite = biome_obstacles_preview.get(tier, OBSTACLE_SPRITE_T1)
    new_sprite_width = get_obstacle_sprite_width(new_sprite)

    # Mappa quali lane sono occupate (usa hitbox dinamica)
    occupied_lanes = set()
    for obs in state.enemies.obstacles:
        if obs['y_pos'] < 5:  # Solo ostacoli vicini al top
            occupied_lanes.update(_get_obstacle_lanes(obs))

    # Trova posizioni valide per il nuovo ostacolo
    valid_start_lanes = []
    for start_lane in range(constants.layout.num_lanes):
        # Calcola quali lane occuperebbe il nuovo ostacolo in questa posizione
        lanes_needed = get_obstacle_hitbox_lanes(
            start_lane,
            new_sprite_width,
            constants.layout.lane_positions,
            constants.layout.num_lanes
        )
        if not lanes_needed & occupied_lanes:
            valid_start_lanes.append(start_lane)

    if not valid_start_lanes:
        state.enemies.obstacle_spawn_timer = max(5, base_spawn_rate // 4)
        return

    # Permetti più ostacoli consecutivi ai livelli alti (level 1-18)
    consecutive_limit = 2 + level // 4  # 2 at lv1, 3 at lv4, 4 at lv8, 5 at lv12, 6 at lv16
    if len(state.enemies.spawn_queue) >= consecutive_limit:
        obstacle_count = sum(1 for item in state.enemies.spawn_queue[-consecutive_limit:]
                            if item.get('type') == 'obstacle')
        if obstacle_count >= consecutive_limit:
            state.enemies.obstacle_spawn_timer = max(5, base_spawn_rate // 4)
            return

    lane = random.choice(valid_start_lanes)

    # Get HP from config with level scaling
    hp_by_tier = constants.obstacle.hp_by_tier
    # Handle both dict and namespace access
    if isinstance(hp_by_tier, dict):
        base_hp = hp_by_tier.get(tier, hp_by_tier.get(str(tier), 5))
    else:
        base_hp = getattr(hp_by_tier, str(tier), 5)
    level_hp_mult = getattr(constants.obstacle, 'level_hp_multiplier', 0.1)
    level_multiplier = 1.0 + (level - 1) * level_hp_mult
    hp = int(base_hp * level_multiplier)

    # Seleziona sprite casuale (variante + eventuale flip)
    sprite, flipped = get_random_obstacle_sprite(level_group, tier, allow_flip=True)
    sprite_height = len(sprite)
    sprite_width = get_obstacle_sprite_width(sprite)

    # Spawn fuori schermo: y negativo così entra gradualmente
    start_y = -sprite_height + 1

    # Assign unique ID to obstacle
    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1

    state.enemies.spawn_queue.append({
        'type': 'obstacle',
        'data': {
            'id': obstacle_id,
            'lane': lane,
            'y_pos': start_y,
            'tier': tier,
            'hp': hp,
            'sprite_width': sprite_width,
            'sprite': sprite,  # Sprite specifica (variante + flip)
            'flipped': flipped,
        }
    })


def spawn_bat():
    """Potentially spawn a new bat."""
    state.enemies.bat_spawn_timer -= 1
    if state.enemies.bat_spawn_timer > 0:
        return

    # Use milestone level (1-18) for spawning, not speed
    level = state.game.level
    if level < 4:  # Bats start at level 2-1 (milestone 4)
        return

    # Get spawn rate from config
    spawn_rates = getattr(constants.bat_enemy, 'spawn_rate_by_level', None)
    if level <= 6:
        base_spawn_rate = getattr(spawn_rates, 'level_4_6', 200) if spawn_rates else 200
    elif level <= 9:
        base_spawn_rate = getattr(spawn_rates, 'level_7_9', 150) if spawn_rates else 150
    elif level <= 12:
        base_spawn_rate = getattr(spawn_rates, 'level_10_12', 100) if spawn_rates else 100
    elif level <= 15:
        base_spawn_rate = getattr(spawn_rates, 'level_13_15', 70) if spawn_rates else 70
    else:
        base_spawn_rate = getattr(spawn_rates, 'level_16_18', 50) if spawn_rates else 50

    state.enemies.bat_spawn_timer = base_spawn_rate

    # Get max bats from config
    max_bats_cfg = getattr(constants.bat_enemy, 'max_bats_by_level', None)
    if level <= 6:
        max_bats = getattr(max_bats_cfg, 'level_4_6', 1) if max_bats_cfg else 1
    elif level <= 9:
        max_bats = getattr(max_bats_cfg, 'level_7_9', 2) if max_bats_cfg else 2
    elif level <= 12:
        max_bats = getattr(max_bats_cfg, 'level_10_12', 3) if max_bats_cfg else 3
    elif level <= 15:
        max_bats = getattr(max_bats_cfg, 'level_13_15', 4) if max_bats_cfg else 4
    else:
        max_bats = getattr(max_bats_cfg, 'level_16_18', 5) if max_bats_cfg else 5

    if len(state.enemies.bats) >= max_bats:
        state.enemies.bat_spawn_timer = base_spawn_rate // 2
        return

    # Get tier weights from config
    tier_weights_cfg = getattr(constants.bat_enemy, 'tier_weights_by_level', None)
    if level <= 6:
        weights = getattr(tier_weights_cfg, 'level_4_6', [70, 25, 5, 0]) if tier_weights_cfg else [70, 25, 5, 0]
    elif level <= 9:
        weights = getattr(tier_weights_cfg, 'level_7_9', [50, 35, 12, 3]) if tier_weights_cfg else [50, 35, 12, 3]
    elif level <= 12:
        weights = getattr(tier_weights_cfg, 'level_10_12', [30, 40, 22, 8]) if tier_weights_cfg else [30, 40, 22, 8]
    elif level <= 15:
        weights = getattr(tier_weights_cfg, 'level_13_15', [15, 35, 35, 15]) if tier_weights_cfg else [15, 35, 35, 15]
    else:
        weights = getattr(tier_weights_cfg, 'level_16_18', [5, 25, 45, 25]) if tier_weights_cfg else [5, 25, 45, 25]
    tier = random.choices([1, 2, 3, 4], weights=weights)[0]

    # Get HP from config
    bat_hp_by_tier = constants.bat_enemy.hp_by_tier
    if isinstance(bat_hp_by_tier, dict):
        hp = bat_hp_by_tier.get(tier, bat_hp_by_tier.get(str(tier), 20))
    else:
        hp = getattr(bat_hp_by_tier, str(tier), 20)

    # Spawn position X
    x_pos = random.randint(0, constants.layout.width - 8)

    # Get target Y from config
    target_y_cfg = getattr(constants.bat_enemy, 'target_y_by_level', None)
    if level <= 6:
        y_range = getattr(target_y_cfg, 'level_4_6', None) if target_y_cfg else None
        target_y_min = y_range.get('min', 3) if isinstance(y_range, dict) else (getattr(y_range, 'min', 3) if y_range else 3)
        target_y_max = y_range.get('max', 8) if isinstance(y_range, dict) else (getattr(y_range, 'max', 8) if y_range else 8)
    elif level <= 9:
        y_range = getattr(target_y_cfg, 'level_7_9', None) if target_y_cfg else None
        target_y_min = y_range.get('min', 5) if isinstance(y_range, dict) else (getattr(y_range, 'min', 5) if y_range else 5)
        target_y_max = y_range.get('max', 12) if isinstance(y_range, dict) else (getattr(y_range, 'max', 12) if y_range else 12)
    elif level <= 12:
        y_range = getattr(target_y_cfg, 'level_10_12', None) if target_y_cfg else None
        target_y_min = y_range.get('min', 8) if isinstance(y_range, dict) else (getattr(y_range, 'min', 8) if y_range else 8)
        target_y_max = y_range.get('max', 16) if isinstance(y_range, dict) else (getattr(y_range, 'max', 16) if y_range else 16)
    elif level <= 15:
        y_range = getattr(target_y_cfg, 'level_13_15', None) if target_y_cfg else None
        target_y_min = y_range.get('min', 10) if isinstance(y_range, dict) else (getattr(y_range, 'min', 10) if y_range else 10)
        target_y_max = y_range.get('max', 20) if isinstance(y_range, dict) else (getattr(y_range, 'max', 20) if y_range else 20)
    else:
        y_range = getattr(target_y_cfg, 'level_16_18', None) if target_y_cfg else None
        target_y_min = y_range.get('min', 12) if isinstance(y_range, dict) else (getattr(y_range, 'min', 12) if y_range else 12)
        target_y_max = y_range.get('max', 23) if isinstance(y_range, dict) else (getattr(y_range, 'max', 23) if y_range else constants.layout.starting_line - 5)

    target_y = random.randint(target_y_min, min(target_y_max, constants.layout.starting_line - 3))

    # Check if bat should be armored or diver (mutually exclusive)
    armored = False
    diver = False

    # First check for diver (any tier)
    diver_cfg = getattr(constants.bat_enemy, 'diver', None)
    if diver_cfg:
        min_diver_tier = getattr(diver_cfg, 'min_tier', 1)
        if tier >= min_diver_tier:
            diver_prob_cfg = getattr(diver_cfg, 'spawn_probability_by_level', None)
            if diver_prob_cfg:
                if level <= 3:
                    diver_prob = getattr(diver_prob_cfg, 'level_1_3', 0.0)
                elif level <= 6:
                    diver_prob = getattr(diver_prob_cfg, 'level_4_6', 0.08)
                elif level <= 9:
                    diver_prob = getattr(diver_prob_cfg, 'level_7_9', 0.12)
                elif level <= 12:
                    diver_prob = getattr(diver_prob_cfg, 'level_10_12', 0.16)
                elif level <= 15:
                    diver_prob = getattr(diver_prob_cfg, 'level_13_15', 0.20)
                else:
                    diver_prob = getattr(diver_prob_cfg, 'level_16_18', 0.25)
                diver = random.random() < diver_prob

    # If not diver, check for spellcaster (tier 2+ only)
    spellcaster = False
    if not diver:
        spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
        if spellcaster_cfg:
            min_spell_tier = getattr(spellcaster_cfg, 'min_tier', 2)
            if tier >= min_spell_tier:
                spell_prob_cfg = getattr(spellcaster_cfg, 'spawn_probability_by_level', None)
                if spell_prob_cfg:
                    if level <= 3:
                        spell_prob = getattr(spell_prob_cfg, 'level_1_3', 0.0)
                    elif level <= 6:
                        spell_prob = getattr(spell_prob_cfg, 'level_4_6', 0.05)
                    elif level <= 9:
                        spell_prob = getattr(spell_prob_cfg, 'level_7_9', 0.08)
                    elif level <= 12:
                        spell_prob = getattr(spell_prob_cfg, 'level_10_12', 0.12)
                    elif level <= 15:
                        spell_prob = getattr(spell_prob_cfg, 'level_13_15', 0.15)
                    else:
                        spell_prob = getattr(spell_prob_cfg, 'level_16_18', 0.20)
                    spellcaster = random.random() < spell_prob

    # If not diver or spellcaster, check for armored (tier 2+ only)
    if not diver and not spellcaster:
        armored_cfg = getattr(constants.bat_enemy, 'armored', None)
        if armored_cfg:
            min_armor_tier = getattr(armored_cfg, 'min_tier', 2)
            if tier >= min_armor_tier:
                armor_prob_cfg = getattr(armored_cfg, 'spawn_probability_by_level', None)
                if armor_prob_cfg:
                    if level <= 3:
                        armor_prob = getattr(armor_prob_cfg, 'level_1_3', 0.0)
                    elif level <= 6:
                        armor_prob = getattr(armor_prob_cfg, 'level_4_6', 0.05)
                    elif level <= 9:
                        armor_prob = getattr(armor_prob_cfg, 'level_7_9', 0.10)
                    elif level <= 12:
                        armor_prob = getattr(armor_prob_cfg, 'level_10_12', 0.15)
                    elif level <= 15:
                        armor_prob = getattr(armor_prob_cfg, 'level_13_15', 0.20)
                    else:
                        armor_prob = getattr(armor_prob_cfg, 'level_16_18', 0.25)
                    armored = random.random() < armor_prob

    # Diver bats have different Y position (upper half of screen)
    final_target_y = target_y
    if diver and diver_cfg:
        y_range_cfg = getattr(diver_cfg, 'y_range_by_level', None)
        if y_range_cfg:
            if level <= 3:
                y_frac = getattr(y_range_cfg, 'level_1_3', None)
            elif level <= 6:
                y_frac = getattr(y_range_cfg, 'level_4_6', None)
            elif level <= 9:
                y_frac = getattr(y_range_cfg, 'level_7_9', None)
            elif level <= 12:
                y_frac = getattr(y_range_cfg, 'level_10_12', None)
            elif level <= 15:
                y_frac = getattr(y_range_cfg, 'level_13_15', None)
            else:
                y_frac = getattr(y_range_cfg, 'level_16_18', None)

            if y_frac:
                min_frac = y_frac.get('min', 0.10) if isinstance(y_frac, dict) else getattr(y_frac, 'min', 0.10)
                max_frac = y_frac.get('max', 0.30) if isinstance(y_frac, dict) else getattr(y_frac, 'max', 0.30)
                screen_height = constants.layout.starting_line
                y_min = int(screen_height * min_frac)
                y_max = int(screen_height * max_frac)
                final_target_y = random.randint(max(1, y_min), max(2, y_max))

    # Spellcasters are 3 lines tall, others are 2
    bat_sprite_height = 3 if spellcaster else 2
    start_y = -bat_sprite_height + 1

    bat_data = {
        'x_pos': x_pos,
        'y_pos': start_y,
        'direction': random.choice([-1, 1]),
        'tier': tier,
        'hp': hp,
        'max_hp': hp,
        'target_y': final_target_y,
        'spawn_ts': time.time(),
        'armored': armored,
        'diver': diver,
        'spellcaster': spellcaster,
    }

    # Add diver-specific fields
    if diver:
        bat_data['diver_state'] = 'flying'  # 'flying', 'diving', 'stunned', 'returning'
        bat_data['diver_home_y'] = final_target_y  # Remember home position
        bat_data['dive_start_y'] = None  # Y when dive started
        bat_data['stun_end_time'] = None  # When stun ends

    # Add spellcaster-specific fields
    if spellcaster:
        bat_data['spell_state'] = 'idle'  # 'idle', 'casting'
        bat_data['spell_cooldown'] = 0  # Time until can cast again
        bat_data['casting_end_time'] = None  # When casting animation ends
        # Determine known spells based on tier
        spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
        spells_by_tier = getattr(spellcaster_cfg, 'spells_by_tier', None) if spellcaster_cfg else None
        if spells_by_tier:
            if isinstance(spells_by_tier, dict):
                num_spells = spells_by_tier.get(tier, spells_by_tier.get(str(tier), 1))
            else:
                num_spells = getattr(spells_by_tier, str(tier), 1)
        else:
            num_spells = min(tier - 1, 3)  # Default: tier 2=1, tier 3=2, tier 4=3
        # Spells in order: silence, repugnant_wind, exile
        all_spells = ['silence', 'repugnant_wind', 'exile']
        bat_data['known_spells'] = all_spells[:num_spells]

    state.enemies.spawn_queue.append({
        'type': 'bat',
        'data': bat_data
    })


def process_spawn_queue():
    """Process the spawn queue to actually spawn entities."""
    from src.services import save_manager

    while state.enemies.spawn_queue:
        item = state.enemies.spawn_queue.pop(0)
        if item['type'] == 'obstacle':
            obstacle_data = item['data']

            # Check if swamp biome (level_group 4) - obstacles can have flowers
            if state.game.level_group == 4:
                _maybe_add_flower_to_obstacle(obstacle_data)

            state.enemies.obstacles.append(obstacle_data)
            # Track obstacle discovery by tier
            tier = obstacle_data.get('tier', 1)
            tier_names = {1: 'TREE', 2: 'ROCK', 3: 'CLOUD', 4: 'BARRIER'}
            save_manager.discover_obstacle(tier_names.get(tier, 'TREE'))
        elif item['type'] == 'bat':
            state.enemies.bats.append(item['data'])
            # Track bat discovery by tier
            tier = item['data'].get('tier', 1)
            tier_names = {1: 'BASIC', 2: 'FAST', 3: 'DIVE', 4: 'BOSS'}
            save_manager.discover_bat(tier_names.get(tier, 'BASIC'))


def _maybe_add_flower_to_obstacle(obstacle_data):
    """Maybe add a flower to a swamp obstacle based on probability."""
    from src.entities.sprites import SWAMP_OBSTACLE_FLOWER_POSITIONS

    tier = obstacle_data.get('tier', 1)
    flower_positions = SWAMP_OBSTACLE_FLOWER_POSITIONS.get(tier, [])

    # No flower positions for this tier
    if not flower_positions:
        return

    # Check bloom probability from config
    swamp_flowers_cfg = getattr(constants, 'swamp_flowers', None)
    bloom_prob = getattr(swamp_flowers_cfg, 'bloom_probability', 0.3) if swamp_flowers_cfg else 0.3

    if random.random() >= bloom_prob:
        return  # No flower spawned

    # Get flower settings from tree_boss config (shared)
    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
    flower_hp = getattr(flowers_cfg, 'hp', 10) if flowers_cfg else 10
    grow_interval = getattr(flowers_cfg, 'grow_interval', 2.0) if flowers_cfg else 2.0

    # Pick random flower position and type
    flower_pos = random.choice(flower_positions)
    flower_types = ['red', 'yellow', 'blue', 'green']
    flower_type = random.choice(flower_types)

    # Import mature frame constant
    from src.entities.sprites import FLOWER_MATURE_FRAME

    # Add flower to obstacle - spawn already bloomed so they have effect immediately
    obstacle_data['flower'] = {
        'type': flower_type,
        'frame': FLOWER_MATURE_FRAME,  # Already bloomed (obstacles get destroyed too fast otherwise)
        'hp': flower_hp,
        'max_hp': flower_hp,
        'grow_timer': time.time() + grow_interval,
        'active': True,
        'rel_x': flower_pos[0],  # Relative X position in obstacle sprite
        'rel_y': flower_pos[1],  # Relative Y position in obstacle sprite
    }


def update_obstacle_flowers():
    """Update flower growth on swamp obstacles."""
    # Only in swamp biome
    if state.game.level_group != 4:
        return

    now = time.time()
    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
    grow_interval = getattr(flowers_cfg, 'grow_interval', 2.0) if flowers_cfg else 2.0

    from src.entities.sprites import FLOWER_MATURE_FRAME

    for obs in state.enemies.obstacles:
        flower = obs.get('flower')
        if not flower or not flower.get('active'):
            continue

        # Check if flower should grow
        if flower['frame'] < FLOWER_MATURE_FRAME and now >= flower.get('grow_timer', 0):
            flower['frame'] += 1
            flower['grow_timer'] = now + grow_interval


# =============================================================================
# MOUNTAIN RANGE CLOUD BANKS
# =============================================================================

def spawn_cloud_bank():
    """Spawn cloud banks for Mountain Range biome (level group 6)."""
    # Only spawn in Mountain Range biome
    if state.game.level_group != 6:
        state.enemies.cloud_banks = []  # Clear clouds when leaving biome
        return

    state.enemies.cloud_spawn_timer -= 1
    if state.enemies.cloud_spawn_timer > 0:
        return

    # Spawn rate - clouds spawn occasionally
    state.enemies.cloud_spawn_timer = random.randint(80, 150)

    # Max clouds on screen
    if len(state.enemies.cloud_banks) >= 3:
        return

    # Cloud spans multiple lanes
    width = random.randint(8, 16)
    x_pos = random.randint(0, constants.layout.width - width)

    # Cloud height (2-4 rows)
    height = random.randint(2, 4)

    # Start above screen
    y_pos = -height

    state.enemies.cloud_banks.append({
        'x_pos': x_pos,
        'y_pos': y_pos,
        'width': width,
        'height': height,
        'opacity': random.choice([0.3, 0.5, 0.7])  # Varying opacity
    })


def update_cloud_banks():
    """Move cloud banks down and remove off-screen ones."""
    if state.game.level_group != 6:
        return

    # Move clouds down (slower than obstacles)
    if state.game.frame_count % 8 == 0:
        for cloud in state.enemies.cloud_banks:
            cloud['y_pos'] += 1

    # Remove clouds that are off screen
    state.enemies.cloud_banks = [
        cloud for cloud in state.enemies.cloud_banks
        if cloud['y_pos'] < constants.layout.height + 5
    ]


# =============================================================================
# MINI BATS - Small bats that hide in tier 3+ obstacles
# =============================================================================

def _get_mini_bat_config():
    """Get mini bat config from bat_enemy.mini_bat namespace."""
    return getattr(constants.bat_enemy, 'mini_bat', None)


def _get_tier3_plus_obstacles():
    """Get list of tier 3+ obstacles currently on screen."""
    mini_bat_cfg = _get_mini_bat_config()
    min_tier = getattr(mini_bat_cfg, 'min_obstacle_tier', 3) if mini_bat_cfg else 3
    return [obs for obs in state.enemies.obstacles if obs.get('tier', 1) >= min_tier]


def spawn_mini_bat_from_obstacle(obstacle):
    """Spawn a mini bat (tier 0) from an obstacle.

    Args:
        obstacle: The obstacle dict the mini bat emerges from
    """
    # Get HP from bat_enemy.hp_by_tier[0]
    hp_by_tier = constants.bat_enemy.hp_by_tier
    if isinstance(hp_by_tier, dict):
        hp = hp_by_tier.get(0, hp_by_tier.get('0', 8))
    else:
        hp = getattr(hp_by_tier, '0', 8)

    # Position: center of obstacle
    obs_x = constants.layout.lane_positions[obstacle['lane']]
    obs_y = obstacle['y_pos']

    obs_id = obstacle.get('id')
    mini_bat = {
        'x_pos': obs_x,
        'y_pos': obs_y,
        'direction': random.choice([-1, 1]),
        'tier': 0,  # Mini bat is tier 0
        'hp': hp,
        'max_hp': hp,
        'state': 'spawning',  # 'spawning', 'active', 'hiding'
        'anim_frame': 0,  # Animation frame counter (0-3 for spawn, then sprite frames)
        'anim_timer': 0,  # Timer for animation speed
        'source_obstacle_id': obs_id,
        'visited_obstacles': {obs_id} if obs_id is not None else set(),  # Track visited obstacles
    }

    state.enemies.mini_bats.append(mini_bat)


def spawn_jumpscare_bat_from_obstacle(obstacle):
    """Spawn a jumpscare bat (rare mini bat variant) from an obstacle.

    Jumpscare bats use Diver Bat sprites and do a scary face attack when they finish spawning.
    """
    hp_by_tier = constants.bat_enemy.hp_by_tier
    if isinstance(hp_by_tier, dict):
        hp = hp_by_tier.get(0, hp_by_tier.get('0', 8))
    else:
        hp = getattr(hp_by_tier, '0', 8)

    obs_x = constants.layout.lane_positions[obstacle['lane']]
    obs_y = obstacle['y_pos']
    obs_id = obstacle.get('id')

    jumpscare_cfg = getattr(constants.bat_enemy, 'jumpscare_bat', None)
    visible_duration = getattr(jumpscare_cfg, 'visible_duration', 3.0) if jumpscare_cfg else 3.0

    jumpscare_bat = {
        'x_pos': obs_x,
        'y_pos': obs_y,
        'lane': obstacle['lane'],
        'direction': random.choice([-1, 1]),
        'tier': 0,
        'hp': hp,
        'max_hp': hp,
        'state': 'spawning',
        'anim_frame': 0,
        'anim_timer': 0,
        'source_obstacle_id': obs_id,
        'visited_obstacles': {obs_id} if obs_id is not None else set(),
        'is_jumpscare': True,
        'scary_face_done': False,
        'visible_timer': 0,
        'visible_duration_frames': int(visible_duration / constants.timing.base_sleep),
    }

    # Add to mini_bats list (reuses existing system)
    state.enemies.mini_bats.append(jumpscare_bat)


def activate_jumpscare_scary_face(jumpscare_bat):
    """Activate the scary face attack on a jumpscare bat.

    Shows scary face sprite and causes fear to birds in affected lanes.
    """
    jumpscare_cfg = getattr(constants.bat_enemy, 'jumpscare_bat', None)
    fear_duration = getattr(jumpscare_cfg, 'fear_duration', 2.0) if jumpscare_cfg else 2.0
    affected_lanes = getattr(jumpscare_cfg, 'affected_lanes', 3) if jumpscare_cfg else 3

    bat_lane = jumpscare_bat['lane']
    half_range = affected_lanes // 2

    # Calculate affected lane range
    min_lane = max(0, bat_lane - half_range)
    max_lane = min(constants.layout.num_lanes - 1, bat_lane + half_range)

    # Apply fear to birds in affected lanes
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        bird_lane = state.birds.random_lanes[i]
        if min_lane <= bird_lane <= max_lane:
            state.special.scared_birds[i] = get_scared_frames(i, fear_duration)

    # Set scary face timer on bat
    scary_face_duration = getattr(jumpscare_cfg, 'scary_face_duration', 0.5) if jumpscare_cfg else 0.5
    jumpscare_bat['scary_face_timer'] = int(scary_face_duration / constants.timing.base_sleep)


def try_spawn_mini_bat_on_hit(obstacle):
    """Try to spawn a mini bat (tier 0) when a tier 3+ obstacle is hit.

    Called on each hit. Checks level, Y position and whether a mini bat already exists for this obstacle.
    """
    mini_bat_cfg = _get_mini_bat_config()
    if mini_bat_cfg is None:
        return False

    # Check minimum level requirement
    min_level = getattr(mini_bat_cfg, 'min_level', 4)
    if state.game.level < min_level:
        return False

    tier = obstacle.get('tier', 1)
    min_tier = getattr(mini_bat_cfg, 'min_obstacle_tier', 3)

    if tier < min_tier:
        return False

    # Don't spawn if obstacle is too high - configurable via min_y_fraction
    # min_y_fraction: 0.0 = top of screen, 1.0 = bottom
    min_y_fraction = getattr(mini_bat_cfg, 'min_y_fraction', 0.33)
    min_y_for_spawn = int(constants.layout.height * min_y_fraction)
    if obstacle['y_pos'] < min_y_for_spawn:
        return False

    obs_id = obstacle.get('id')

    # Check if this obstacle already has an active mini bat (don't spawn another)
    if obs_id is not None:
        for mb in state.enemies.mini_bats:
            if mb.get('source_obstacle_id') == obs_id:
                return False  # Already has a mini bat, don't spawn another

    # Check if this obstacle has hidden mini bats (100% spawn)
    if obs_id is not None and obs_id in state.enemies.hidden_mini_bats:
        hidden_list = state.enemies.hidden_mini_bats.pop(obs_id)
        for hidden_bat in hidden_list:
            # Re-emerge the hidden mini bat
            hidden_bat['x_pos'] = constants.layout.lane_positions[obstacle['lane']]
            hidden_bat['y_pos'] = obstacle['y_pos']
            hidden_bat['state'] = 'spawning'
            hidden_bat['anim_frame'] = 0
            hidden_bat['anim_timer'] = 0
            state.enemies.mini_bats.append(hidden_bat)
        return True

    # Random chance to spawn new mini bat - probability scales by level
    level = state.game.level
    spawn_prob_cfg = getattr(mini_bat_cfg, 'spawn_probability_by_level', None)

    if spawn_prob_cfg:
        # Get probability for current level range
        if level <= 3:
            spawn_prob = getattr(spawn_prob_cfg, 'level_1_3', 0.10)
        elif level <= 6:
            spawn_prob = getattr(spawn_prob_cfg, 'level_4_6', 0.20)
        elif level <= 9:
            spawn_prob = getattr(spawn_prob_cfg, 'level_7_9', 0.30)
        elif level <= 12:
            spawn_prob = getattr(spawn_prob_cfg, 'level_10_12', 0.40)
        elif level <= 15:
            spawn_prob = getattr(spawn_prob_cfg, 'level_13_15', 0.50)
        else:
            spawn_prob = getattr(spawn_prob_cfg, 'level_16_18', 0.60)
    else:
        # Fallback to old single value
        spawn_prob = getattr(mini_bat_cfg, 'spawn_probability', 0.3)

    if random.random() < spawn_prob:
        # Check if this should be a jumpscare bat instead
        jumpscare_cfg = getattr(constants.bat_enemy, 'jumpscare_bat', None)
        jumpscare_chance = getattr(jumpscare_cfg, 'spawn_chance', 0.15) if jumpscare_cfg else 0.15
        if random.random() < jumpscare_chance:
            spawn_jumpscare_bat_from_obstacle(obstacle)
        else:
            spawn_mini_bat_from_obstacle(obstacle)
        return True

    return False


def handle_obstacle_destroyed(obstacle):
    """Handle mini bat behavior when their host obstacle is destroyed.

    Mini bats will try to hide in another tier 3+ obstacle, or stay active if none available.
    """
    obs_id = obstacle.get('id')

    # Find mini bats that came from this obstacle and are still active
    affected_mini_bats = [
        mb for mb in state.enemies.mini_bats
        if mb.get('source_obstacle_id') == obs_id and mb['state'] == 'active'
    ]

    if not affected_mini_bats:
        return

    # Find other tier 3+ obstacles to hide in
    other_obstacles = [obs for obs in _get_tier3_plus_obstacles() if obs.get('id') != obs_id]

    if other_obstacles:
        # Mini bats start hiding animation
        for mb in affected_mini_bats:
            mb['state'] = 'hiding'
            mb['anim_frame'] = 3  # Start from last frame, go backwards
            mb['anim_timer'] = 0
            # Pick a random obstacle to hide in
            mb['target_obstacle_id'] = random.choice(other_obstacles).get('id')
    # else: mini bats stay active in their current position


def update_mini_bats():
    """Update mini bat states (animations, hiding logic)."""
    mini_bat_cfg = _get_mini_bat_config()
    anim_speed = getattr(mini_bat_cfg, 'anim_frames_per_step', 2) if mini_bat_cfg else 2

    # Get current tier 3+ obstacles
    tier3_obstacles = _get_tier3_plus_obstacles()

    for mb in state.enemies.mini_bats[:]:
        mb['anim_timer'] += 1

        if mb['state'] == 'spawning':
            # Spawn animation: · → • → * → O → sprite
            if mb['anim_timer'] >= anim_speed:
                mb['anim_timer'] = 0
                mb['anim_frame'] += 1
                if mb['anim_frame'] >= 4:  # Animation complete
                    mb['state'] = 'active'
                    mb['anim_frame'] = 0
                    # Jumpscare bat: activate scary face when spawn completes
                    if mb.get('is_jumpscare') and not mb.get('scary_face_done'):
                        activate_jumpscare_scary_face(mb)
                        mb['scary_face_done'] = True
                        mb['visible_timer'] = 0

        elif mb['state'] == 'hiding':
            # Hide animation: sprite → O → * → • → · → disappear
            if mb['anim_timer'] >= anim_speed:
                mb['anim_timer'] = 0
                mb['anim_frame'] -= 1
                if mb['anim_frame'] < 0:  # Animation complete, hide in obstacle
                    target_id = mb.get('target_obstacle_id')
                    if target_id is not None:
                        # Check if target obstacle still exists
                        target_exists = any(
                            obs.get('id') == target_id
                            for obs in state.enemies.obstacles
                        )
                        if target_exists:
                            # Add to visited obstacles before hiding
                            if 'visited_obstacles' not in mb:
                                mb['visited_obstacles'] = set()
                            mb['visited_obstacles'].add(target_id)
                            # Update source to new obstacle
                            mb['source_obstacle_id'] = target_id
                            # Hide in the obstacle
                            if target_id not in state.enemies.hidden_mini_bats:
                                state.enemies.hidden_mini_bats[target_id] = []
                            state.enemies.hidden_mini_bats[target_id].append(mb)
                            state.enemies.mini_bats.remove(mb)
                            continue

                    # Target doesn't exist anymore, stay active
                    mb['state'] = 'active'
                    mb['anim_frame'] = 0

        elif mb['state'] == 'active':
            source_id = mb.get('source_obstacle_id')
            visited = mb.get('visited_obstacles', set())

            # Jumpscare bat: decrement scary face timer
            if mb.get('scary_face_timer', 0) > 0:
                mb['scary_face_timer'] -= 1

            # Jumpscare bat: track visible time and hide after duration
            if mb.get('is_jumpscare') and mb.get('scary_face_done'):
                mb['visible_timer'] = mb.get('visible_timer', 0) + 1
                
                # Random chance to do another scary face while active
                if mb.get('scary_face_timer', 0) <= 0:
                    jumpscare_cfg = getattr(constants.bat_enemy, 'jumpscare_bat', None)
                    random_scream_chance = getattr(jumpscare_cfg, 'random_scream_chance', 0.01) if jumpscare_cfg else 0.01
                    if random.random() < random_scream_chance:
                        activate_jumpscare_scary_face(mb)
                
                if mb['visible_timer'] >= mb.get('visible_duration_frames', 100):
                    # Time to hide in another tier 3+ obstacle
                    available_obstacles = [
                        obs for obs in tier3_obstacles
                        if obs.get('id') not in visited
                    ]
                    if available_obstacles:
                        mb['state'] = 'hiding'
                        mb['anim_frame'] = 3
                        mb['anim_timer'] = 0
                        mb['target_obstacle_id'] = random.choice(available_obstacles).get('id')
                        mb['scary_face_done'] = False  # Reset for next appearance
                        continue

            # Check if source obstacle still exists
            source_exists = any(
                obs.get('id') == source_id
                for obs in state.enemies.obstacles
            ) if source_id is not None else False

            if not source_exists:
                # Source destroyed! Try to find a new tier 3+ obstacle to hide in
                # Exclude already visited obstacles
                available_obstacles = [
                    obs for obs in tier3_obstacles
                    if obs.get('id') not in visited
                ]
                if available_obstacles:
                    mb['state'] = 'hiding'
                    mb['anim_frame'] = 3
                    mb['anim_timer'] = 0
                    mb['target_obstacle_id'] = random.choice(available_obstacles).get('id')
                # else: no unvisited obstacles to hide in, stay active and vulnerable


def check_bird_mini_bat_collision():
    """Check bird-mini bat collisions."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_lane_x = constants.layout.lane_positions[bird_lane]
        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_color == STEALTH and i not in state.special.stealth_timers:
            continue

        bird_height = 3 if bird_color == DINOSAUR else 2

        for mb in state.enemies.mini_bats[:]:
            # Only collide with active mini bats
            if mb['state'] != 'active':
                continue

            # Mini bat is single line, ~10 chars wide
            mb_width = 10
            mb_left = mb['x_pos'] - mb_width // 2
            mb_right = mb['x_pos'] + mb_width // 2
            mb_y = mb['y_pos']

            lane_left = bird_lane_x - 2
            lane_right = bird_lane_x + 2

            horizontal_overlap = not (mb_right < lane_left or mb_left > lane_right)
            vertical_overlap = not (bird_y + bird_height < mb_y or bird_y > mb_y)

            if not (horizontal_overlap and vertical_overlap):
                continue

            # Hit mini bat
            damage = _calculate_bird_damage(i)

            if bird_color == ORANGE:
                mb['hp'] = 0
            else:
                mb['hp'] -= damage
                award_xp(i, damage)

            if mb['hp'] <= 0:
                # Mini bat destroyed - use same logic as regular bats
                _handle_mini_bat_death(mb, i)
            else:
                _set_ball_vy(i, 1)
                stun_frames = int(0.5 / constants.timing.base_sleep)  # Shorter stun
                state.special.stunned_birds[i] = stun_frames
                state.special.scared_birds[i] = stun_frames
                play_sfx('hit')
            break


# =============================================================================
# BOSS - End of biome bosses
# =============================================================================

def _get_boss_config():
    """Get boss configuration."""
    return getattr(constants, 'boss', None)


def _get_miles_to_next_level():
    """Calculate miles remaining until next level transition."""
    from src.functions import get_level_milestones
    milestones = get_level_milestones()
    current_level = state.game.level

    if current_level >= len(milestones):
        return float('inf')  # Max level reached

    next_threshold = milestones[current_level - 1] if current_level <= len(milestones) else milestones[-1]
    return max(0, next_threshold - state.game.miles)


def should_spawn_boss():
    """Check if boss should spawn (end of biome level, near transition)."""
    # Already spawned or defeated this level?
    if state.enemies.boss_spawned or state.enemies.boss is not None:
        return False

    # Check special boss levels first (wind, jelly, tree)
    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    wind_boss_level = getattr(wind_boss_cfg, 'level', 6) if wind_boss_cfg else 6

    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    jelly_boss_level = getattr(jelly_boss_cfg, 'level', 9) if jelly_boss_cfg else 9

    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    tree_boss_level = getattr(tree_boss_cfg, 'level', 12) if tree_boss_cfg else 12

    is_special_boss_level = (state.game.level == wind_boss_level or
                             state.game.level == jelly_boss_level or
                             state.game.level == tree_boss_level)

    # Get normal boss config
    boss_cfg = _get_boss_config()

    # Check if current level is a boss level (including special boss levels)
    boss_levels = getattr(boss_cfg, 'boss_levels', [3, 6, 9, 12, 15, 18]) if boss_cfg else [3, 6, 9, 12, 15, 18]

    # Level must be in boss_levels OR be a special boss level
    if state.game.level not in boss_levels and not is_special_boss_level:
        return False

    # For normal bosses, we need the config
    if not is_special_boss_level and boss_cfg is None:
        return False

    # Get milestones to calculate level progress
    from src.functions import get_level_milestones
    milestones = get_level_milestones()
    current_level = state.game.level

    # Get the threshold for ENTERING current level (start of this level)
    level_start_miles = milestones[current_level - 2] if current_level >= 2 else 0
    # Get the threshold for LEAVING current level (end of this level)
    level_end_miles = milestones[current_level - 1] if current_level <= len(milestones) else milestones[-1]

    # Miles traveled within THIS level
    miles_in_level = state.game.miles - level_start_miles
    # Total miles in this level
    level_length = level_end_miles - level_start_miles
    # Miles remaining in this level
    miles_remaining = level_end_miles - state.game.miles

    # Check if close enough to level transition
    # For special bosses, use their own config or default
    if is_special_boss_level:
        if state.game.level == jelly_boss_level:
            spawn_miles_before = getattr(jelly_boss_cfg, 'spawn_miles_before_transition', 1) if jelly_boss_cfg else 1
        elif state.game.level == tree_boss_level:
            spawn_miles_before = getattr(tree_boss_cfg, 'spawn_miles_before_transition', 3) if tree_boss_cfg else 3
        else:
            spawn_miles_before = getattr(wind_boss_cfg, 'spawn_miles_before_transition', 1) if wind_boss_cfg else 1
    else:
        spawn_miles_before = getattr(boss_cfg, 'spawn_miles_before_transition', 1)

    # Boss spawns when:
    # 1. We have progressed into the level (not at start)
    # 2. Miles remaining is less than spawn_miles_before
    return miles_in_level > 0 and miles_remaining <= spawn_miles_before


def spawn_boss():
    """Spawn the boss for current biome."""
    # Check if this is a Wind Boss level
    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    wind_boss_level = getattr(wind_boss_cfg, 'level', 6) if wind_boss_cfg else 6

    if state.game.level == wind_boss_level:
        spawn_wind_boss()
        return

    # Check if this is a Jelly Boss level
    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    jelly_boss_level = getattr(jelly_boss_cfg, 'level', 9) if jelly_boss_cfg else 9

    if state.game.level == jelly_boss_level:
        spawn_jelly_boss()
        return

    # Check if this is a Tree Boss level
    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    tree_boss_level = getattr(tree_boss_cfg, 'level', 12) if tree_boss_cfg else 12

    if state.game.level == tree_boss_level:
        spawn_tree_boss()
        return

    boss_cfg = _get_boss_config()
    if boss_cfg is None:
        return

    hp = getattr(boss_cfg, 'hp', 300)

    # Boss spawns at center of screen, above view
    boss_sprite_height = 3  # Boss is 3 lines tall
    boss_sprite_width = 19  # Width of boss sprite
    base_x = (constants.layout.width - boss_sprite_width) // 2

    state.enemies.boss = {
        'x_pos': base_x,
        'base_x_pos': base_x,  # Center position for oscillation
        'y_pos': -boss_sprite_height,  # Start above screen
        'hp': hp,
        'max_hp': hp,
        'state': 'descending',  # 'descending', 'active', 'screaming', 'dying', 'dead'
        'scream_cooldown': 0,  # Frames until can scream again
        'scream_timer': 0,  # Frames remaining in current scream
        'anim_frame': 0,  # Animation frame counter
        'oscillation_dir': 1,  # Direction of oscillation (1 = right, -1 = left)
        'spawn_ts': time.time(),
        'boss_type': 'normal',  # Mark as normal boss
    }
    state.enemies.boss_spawned = True
    # Clear other enemies when boss appears for dramatic effect
    state.enemies.bats = []
    state.enemies.mini_bats = []


def spawn_wind_boss():
    """Spawn the Wind Boss for level 2-3."""
    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    hp = getattr(wind_boss_cfg, 'hp', 120) if wind_boss_cfg else 120

    # Wind boss is wider (up to 26 chars) and taller (5 lines)
    boss_sprite_height = 5
    boss_sprite_width = 26
    base_x = (constants.layout.width - boss_sprite_width) // 2

    state.enemies.boss = {
        'x_pos': base_x,
        'base_x_pos': base_x,
        'y_pos': -boss_sprite_height,
        'hp': hp,
        'max_hp': hp,
        'state': 'descending',
        'anim_frame': 0,  # Index into animation sequence (0-9)
        'anim_timer': 0,  # Timer for animation steps
        'oscillation_dir': 1,
        'spawn_ts': time.time(),
        'boss_type': 'wind',
        'wind_phase': 'tailwind',  # 'tailwind' during pull up, 'headwind' during push down
    }
    state.enemies.boss_spawned = True
    state.enemies.bats = []
    state.enemies.mini_bats = []


def spawn_jelly_boss():
    """Spawn the Jelly Boss for level 3-3."""
    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    hp = getattr(jelly_boss_cfg, 'hp', 400) if jelly_boss_cfg else 400

    # Jelly boss is 6 lines tall
    boss_sprite_height = 6
    boss_sprite_width = 23  # Width of jelly boss sprite
    base_x = (constants.layout.width - boss_sprite_width) // 2

    # Target Y at 1/4 from top
    target_y_frac = getattr(jelly_boss_cfg, 'target_y_fraction', 0.25) if jelly_boss_cfg else 0.25
    target_y = int(constants.layout.starting_line * target_y_frac)

    state.enemies.boss = {
        'x_pos': base_x,
        'base_x_pos': base_x,
        'y_pos': -boss_sprite_height,
        'target_y': target_y,
        'hp': hp,
        'max_hp': hp,
        'state': 'descending',
        'anim_frame': 0,  # Index into animation sequence (0-9)
        'anim_timer': 0,  # Timer for animation steps
        'oscillation_dir': 1,
        'spawn_ts': time.time(),
        'boss_type': 'jelly',
        'spawned_bats': 0,  # Number of bats spawned
        'bat_spawn_anim': None,  # Active spawn animation
    }
    state.enemies.boss_spawned = True
    # Don't clear bats for jelly boss - it spawns bats!


def spawn_tree_boss():
    """Spawn the Tree Boss for level 4-3 (Dark Swamp).

    The Tree Boss is a giant tree spanning the entire screen with:
    - Background tree (rendered faint, decorative)
    - 5 foreground branches (tangible, birds collide with them)
    - Flowers that grow on branches with special effects
    """
    tree_boss_cfg = getattr(constants, 'tree_boss', None)

    # Get branch config
    branches_cfg = getattr(tree_boss_cfg, 'branches', None) if tree_boss_cfg else None
    base_hp = getattr(branches_cfg, 'base_hp', 50) if branches_cfg else 50

    # Branch positions calculated so numbered areas in branches overlap with tree
    # x = tree_col - branch_col (where digit appears)
    # tree_row = tree_digit_row - branch_digit_row (where branch starts) + 1
    #
    # Calculated positions:
    # Branch 1: tree "1" at col 18 row 15, branch "1" at col 9 row 3 → x=9, tree_row=13
    # Branch 2: tree "2" at col 26 row 13, branch "2" at col 0 row 3 → x=26, tree_row=11
    # Branch 3: tree "3" at col 10 row 8, branch "3" at col 6 row 3 → x=4, tree_row=6
    # Branch 4: tree "4" at col 23 row 8, branch "4" at col 1 row 5 → x=22, tree_row=4
    # Branch 5: tree "5" at col 34 row 7, branch "5" at col 1 row 0 → x=33, tree_row=8
    branch_positions = [
        {'x': 11, 'tree_row': 13, 'sprite_idx': 0},  # Branch 1 - covers lanes 1,2,3,4
        {'x': 28, 'tree_row': 11, 'sprite_idx': 1},  # Branch 2 - covers lanes 6,7,8
        {'x': 5, 'tree_row': 6, 'sprite_idx': 2},    # Branch 3 - covers lanes 0,1,2,3
        {'x': 25, 'tree_row': 4, 'sprite_idx': 3},   # Branch 4 - covers lanes 5,6
        {'x': 33, 'tree_row': 8, 'sprite_idx': 4},   # Branch 5 - covers lanes 7,8
    ]

    # Import branch sprites and background tree for size calculation
    from src.entities.sprites import TREE_BOSS_BRANCHES, TREE_BOSS_BACKGROUND

    # Calculate background tree height (needed for branch positioning)
    bg_height = len(TREE_BOSS_BACKGROUND)

    # Create branches with calculated positions
    branches = []
    flower_types = ['red', 'yellow', 'blue', 'green']
    screen_width = constants.layout.width
    screen_height = constants.layout.starting_line

    for i, pos in enumerate(branch_positions):
        # Get position from branch_positions (absolute tree coordinates)
        x_pos = pos['x']
        tree_row = pos['tree_row']
        sprite_idx = pos['sprite_idx']

        sprite = TREE_BOSS_BRANCHES[sprite_idx]
        sprite_width = max(len(line) for line in sprite)
        sprite_height = len(sprite)

        # Branch y position is relative to tree background
        # When bg_y_offset = -bg_height, tree top is above screen
        # Branch starts at tree_row within the tree sprite
        # y_pos = bg_y_offset + tree_row = -bg_height + tree_row
        y_pos = -bg_height + tree_row
        # target_y is where the branch will be when tree is fully scrolled
        # Final bg_y_offset = starting_line - bg_height
        # So branch final y = (starting_line - bg_height) + tree_row = starting_line - bg_height + tree_row
        target_y = tree_row  # This is the row within visible screen when tree stops

        # Calculate which lanes this branch covers (based on target position)
        lanes_covered = set()
        for lane_idx, lane_x in enumerate(constants.layout.lane_positions):
            if x_pos - 2 <= lane_x <= x_pos + sprite_width + 2:
                lanes_covered.add(lane_idx)

        # Initialize flower (random type, random position on 'o' marker)
        flower_type = random.choice(flower_types)
        flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
        flower_hp = getattr(flowers_cfg, 'hp', 10) if flowers_cfg else 10

        # Get flower spawn positions for this branch (use sprite_idx to match sprite)
        from src.entities.sprites import TREE_BOSS_BRANCH_FLOWER_POSITIONS
        if sprite_idx < len(TREE_BOSS_BRANCH_FLOWER_POSITIONS):
            flower_positions = TREE_BOSS_BRANCH_FLOWER_POSITIONS[sprite_idx]
        else:
            flower_positions = [(sprite_width // 2, 0)]  # Default: center-top

        # Pick random flower position
        flower_pos = random.choice(flower_positions)

        # Get grow interval from config
        grow_interval = getattr(flowers_cfg, 'grow_interval', 2.0) if flowers_cfg else 2.0

        branches.append({
            'id': i,
            'x_pos': x_pos,
            'y_pos': y_pos,
            'target_y': target_y,  # Final position (descends until here)
            'sprite': sprite,
            'sprite_idx': sprite_idx,
            'sprite_width': sprite_width,
            'sprite_height': sprite_height,
            'hp': base_hp,
            'max_hp': base_hp,
            'lanes_covered': lanes_covered,
            'destroyed': False,
            'flower': {
                'type': flower_type,
                'frame': 0,  # Growth frame (0-5, 6 total frames)
                'hp': flower_hp,
                'max_hp': flower_hp,
                'grow_timer': None,  # Will be set when tree stops moving
                'active': True,  # Flower exists
                'rel_x': flower_pos[0],  # Relative X position in branch sprite
                'rel_y': flower_pos[1],  # Relative Y position in branch sprite
            },
            'flower_positions': flower_positions,  # All possible positions for respawn
        })

    # Background tree starting position (above screen) - bg_height already calculated above
    state.enemies.boss = {
        'x_pos': 0,
        'y_pos': 0,
        'hp': 1,  # Tree boss HP is based on branches, not central HP
        'max_hp': 1,
        'state': 'active',
        'spawn_ts': time.time(),
        'boss_type': 'tree',
        'branches': branches,
        'bg_y_offset': -bg_height,  # Background tree starts above screen
    }
    state.enemies.boss_spawned = True
    # Clear normal enemies for boss fight
    state.enemies.bats = []
    state.enemies.obstacles = []


def update_boss():
    """Update boss state and behavior."""
    boss = state.enemies.boss
    if boss is None:
        return

    # Route to appropriate update function based on boss type
    boss_type = boss.get('boss_type', 'normal')
    if boss_type == 'wind':
        update_wind_boss()
        return
    if boss_type == 'jelly':
        update_jelly_boss()
        return
    if boss_type == 'tree':
        update_tree_boss()
        return

    boss_cfg = _get_boss_config()
    if boss_cfg is None:
        return

    boss_state = boss['state']

    if boss_state == 'descending':
        # Move boss down until fully visible
        descent_speed = getattr(boss_cfg, 'descent_speed', 8)
        if state.game.frame_count % descent_speed == 0:
            boss['y_pos'] += 1
            # Stop when fully on screen (3 lines visible)
            if boss['y_pos'] >= 2:
                boss['state'] = 'active'
                boss['y_pos'] = 2  # Lock position

    elif boss_state == 'active':
        # Animation frame cycling
        if state.game.frame_count % 6 == 0:
            boss['anim_frame'] = (boss['anim_frame'] + 1) % 2

        # Subtle left/right oscillation
        oscillation_speed = getattr(boss_cfg, 'oscillation_speed', 12)
        oscillation_range = getattr(boss_cfg, 'oscillation_range', 2)
        if state.game.frame_count % oscillation_speed == 0:
            base_x = boss['base_x_pos']
            current_offset = boss['x_pos'] - base_x
            direction = boss.get('oscillation_dir', 1)

            # Move in current direction
            new_offset = current_offset + direction

            # Reverse direction at boundaries
            if new_offset >= oscillation_range:
                new_offset = oscillation_range
                boss['oscillation_dir'] = -1
            elif new_offset <= -oscillation_range:
                new_offset = -oscillation_range
                boss['oscillation_dir'] = 1

            boss['x_pos'] = base_x + new_offset

        # Decrement scream cooldown
        if boss['scream_cooldown'] > 0:
            boss['scream_cooldown'] -= 1

        # Random chance to scream
        if boss['scream_cooldown'] == 0:
            scream_cfg = getattr(boss_cfg, 'scream', None)
            prob_per_second = getattr(scream_cfg, 'probability_per_second', 0.15) if scream_cfg else 0.15
            prob_per_frame = prob_per_second * constants.timing.base_sleep

            if random.random() < prob_per_frame:
                _boss_start_scream(boss)

    elif boss_state == 'screaming':
        # Scream animation
        boss['scream_timer'] -= 1
        if boss['scream_timer'] <= 0:
            boss['state'] = 'active'
            # Set cooldown
            scream_cfg = getattr(boss_cfg, 'scream', None)
            cooldown_sec = getattr(scream_cfg, 'cooldown_seconds', 3.0) if scream_cfg else 3.0
            boss['scream_cooldown'] = int(cooldown_sec / constants.timing.base_sleep)

    elif boss_state == 'dying':
        # Convert to falling obstacle (tier 4)
        _convert_boss_to_obstacle(boss)
        state.enemies.boss = None
        state.enemies.boss_defeated = True


def _boss_start_scream(boss):
    """Start boss scream attack."""
    boss['state'] = 'screaming'
    boss['scream_timer'] = 15  # Scream duration in frames

    # Play scream SFX
    play_sfx('boss_scream')

    # Apply scare effect to all birds below the boss
    boss_cfg = _get_boss_config()
    scream_cfg = getattr(boss_cfg, 'scream', None)
    scare_duration = getattr(scream_cfg, 'scare_duration', 1.5) if scream_cfg else 1.5
    scare_frames = int(scare_duration / constants.timing.base_sleep)

    boss_bottom = boss['y_pos'] + 3  # Boss is 3 lines tall

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        bird_y = state.birds.y[i]

        # Only affect birds below the boss
        if bird_y > boss_bottom:
            # Bounce bird down
            if state.birds.vy[i] == -1:
                _set_ball_vy(i, 1)

            # Apply scare effect (like tier 1 bat)
            state.special.scared_birds[i] = scare_frames


def update_wind_boss():
    """Update Wind Boss state and behavior."""
    boss = state.enemies.boss
    if boss is None:
        return

    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    boss_state = boss['state']

    if boss_state == 'descending':
        descent_speed = getattr(wind_boss_cfg, 'descent_speed', 8) if wind_boss_cfg else 8
        if state.game.frame_count % descent_speed == 0:
            boss['y_pos'] += 1
            if boss['y_pos'] >= 2:
                boss['state'] = 'active'
                boss['y_pos'] = 2

    elif boss_state == 'active':
        # Animation cycling through wing flap sequence
        anim_speed = getattr(wind_boss_cfg, 'anim_frames_per_step', 8) if wind_boss_cfg else 8
        boss['anim_timer'] = boss.get('anim_timer', 0) + 1

        if boss['anim_timer'] >= anim_speed:
            boss['anim_timer'] = 0
            boss['anim_frame'] = (boss['anim_frame'] + 1) % 10  # 10 frames in sequence

            # Determine wind phase based on animation frame
            # Frame 0 = max_up → headwind starts (obnoxious wind)
            # Frame 5 = max_down → tailwind starts
            if boss['anim_frame'] >= 5:
                boss['wind_phase'] = 'tailwind'
            else:
                boss['wind_phase'] = 'headwind'

        # Apply wind effects to all birds
        _apply_wind_boss_effect(boss)

        # Subtle oscillation
        oscillation_speed = getattr(wind_boss_cfg, 'oscillation_speed', 12) if wind_boss_cfg else 12
        oscillation_range = getattr(wind_boss_cfg, 'oscillation_range', 2) if wind_boss_cfg else 2
        if state.game.frame_count % oscillation_speed == 0:
            base_x = boss['base_x_pos']
            current_offset = boss['x_pos'] - base_x
            direction = boss.get('oscillation_dir', 1)
            new_offset = current_offset + direction
            if new_offset >= oscillation_range:
                new_offset = oscillation_range
                boss['oscillation_dir'] = -1
            elif new_offset <= -oscillation_range:
                new_offset = -oscillation_range
                boss['oscillation_dir'] = 1
            boss['x_pos'] = base_x + new_offset

    elif boss_state == 'dying':
        _convert_wind_boss_to_obstacle(boss)
        state.enemies.boss = None
        state.enemies.boss_defeated = True


def _apply_wind_boss_effect(boss):
    """Apply tailwind or headwind effect from Wind Boss with gradual intensity."""
    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    wind_phase = boss.get('wind_phase', 'tailwind')
    anim_frame = boss.get('anim_frame', 0)

    if wind_phase == 'tailwind':
        # Tailwind: frames 5-9 (max_down to pull_up_4)
        # Frame 5 = intensity 0, frame 9 = intensity 4 (max)
        intensity = anim_frame - 5  # 0 to 4
        max_intensity = 4
        
        tw_cfg = getattr(wind_boss_cfg, 'tailwind', None) if wind_boss_cfg else None
        up_min = getattr(tw_cfg, 'up_bonus_min', 1) if tw_cfg else 1
        up_max = getattr(tw_cfg, 'up_bonus_max', 3) if tw_cfg else 3
        down_min = getattr(tw_cfg, 'down_penalty_min', 0) if tw_cfg else 0
        down_max = getattr(tw_cfg, 'down_penalty_max', 2) if tw_cfg else 2
        
        # Interpolate based on intensity
        t = intensity / max_intensity if max_intensity > 0 else 0
        up_bonus = int(up_min + (up_max - up_min) * t)
        down_penalty = int(down_min + (down_max - down_min) * t)
        
        state.powerups.wind_boss_up_bonus = up_bonus
        state.powerups.wind_boss_down_penalty = down_penalty
    else:
        # Headwind: frames 0-4 (max_up to push_down_4)
        # Frame 0 = intensity 0, frame 4 = intensity 4 (max)
        intensity = anim_frame  # 0 to 4
        max_intensity = 4
        
        hw_cfg = getattr(wind_boss_cfg, 'headwind', None) if wind_boss_cfg else None
        up_min = getattr(hw_cfg, 'up_penalty_min', 1) if hw_cfg else 1
        up_max = getattr(hw_cfg, 'up_penalty_max', 2) if hw_cfg else 2
        down_min = getattr(hw_cfg, 'down_bonus_min', 1) if hw_cfg else 1
        down_max = getattr(hw_cfg, 'down_bonus_max', 3) if hw_cfg else 3
        
        # Interpolate based on intensity
        t = intensity / max_intensity if max_intensity > 0 else 0
        up_penalty = int(up_min + (up_max - up_min) * t)
        down_bonus = int(down_min + (down_max - down_min) * t)
        
        # Negative values = headwind
        state.powerups.wind_boss_up_bonus = -up_penalty
        state.powerups.wind_boss_down_penalty = -down_bonus


def _convert_wind_boss_to_obstacle(boss):
    """Convert dead Wind Boss to a falling obstacle."""
    boss_cfg = _get_boss_config()
    wind_boss_cfg = getattr(constants, 'wind_boss', None)

    corpse_cfg = getattr(boss_cfg, 'corpse', None)
    hp = getattr(corpse_cfg, 'hp', 64) if corpse_cfg else 64

    boss_center_x = boss['x_pos'] + 13  # Wind boss is ~26 chars wide
    closest_lane = min(range(constants.layout.num_lanes),
                       key=lambda l: abs(constants.layout.lane_positions[l] - boss_center_x))

    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1

    state.enemies.obstacles.append({
        'id': obstacle_id,
        'lane': closest_lane,
        'x_pos': boss['x_pos'],
        'y_pos': boss['y_pos'],
        'tier': 5,
        'hp': hp,
        'max_hp': hp,
        'sprite_width': 26,
        'is_boss_corpse': True,
        'is_wind_boss_corpse': True,
    })

    # Clear wind effects
    state.powerups.wind_boss_up_bonus = 0
    state.powerups.wind_boss_down_penalty = 0

    # Award score and XP
    score = getattr(wind_boss_cfg, 'score', 1200) if wind_boss_cfg else 1200
    xp = getattr(wind_boss_cfg, 'xp', 120) if wind_boss_cfg else 120
    add_score(score)

    for i in range(constants.layout.num_balls):
        if not state.birds.lost[i]:
            award_xp(i, xp // max(1, sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])))

    # Drop loot
    loot_cfg = getattr(boss_cfg, 'loot', None)
    loot_count = getattr(loot_cfg, 'count', 3) if loot_cfg else 3
    loot_tier = getattr(loot_cfg, 'tier', 3) if loot_cfg else 3

    # Get tier loot weights from bat_enemy config
    loot_weights = constants.bat_enemy.loot_base_weights
    if isinstance(loot_weights, dict):
        tier_weights = loot_weights.get(loot_tier, loot_weights.get(str(loot_tier), [30, 35, 25, 10]))
    else:
        tier_weights = getattr(loot_weights, str(loot_tier), [30, 35, 25, 10])

    prestige = compute_prestige()
    adj_weights = adjust_rarity_weights(tier_weights, prestige)

    for i in range(loot_count):
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)
        
        # Spread loot across nearby lanes
        lane_offset = i - loot_count // 2
        loot_lane = max(0, min(constants.layout.num_lanes - 1, closest_lane + lane_offset))
        
        state.items.loot_items.append({
            'x_pos': constants.layout.lane_positions[loot_lane],
            'y_pos': boss['y_pos'] + 2,
            'type': loot_type,
            'rarity': rarity,
            'spawn_ts': time.time()
        })


def update_jelly_boss():
    """Update Jelly Boss state and behavior."""
    boss = state.enemies.boss
    if boss is None:
        return

    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    boss_state = boss['state']

    if boss_state == 'descending':
        descent_speed = getattr(jelly_boss_cfg, 'descent_speed', 8) if jelly_boss_cfg else 8
        target_y = boss.get('target_y', 5)
        if state.game.frame_count % descent_speed == 0:
            boss['y_pos'] += 1
            if boss['y_pos'] >= target_y:
                boss['state'] = 'active'
                boss['y_pos'] = target_y

    elif boss_state == 'active':
        # Animation cycling through 10 frames
        anim_speed = getattr(jelly_boss_cfg, 'anim_frames_per_step', 30) if jelly_boss_cfg else 30
        boss['anim_timer'] = boss.get('anim_timer', 0) + 1

        if boss['anim_timer'] >= anim_speed:
            boss['anim_timer'] = 0
            prev_frame = boss['anim_frame']
            boss['anim_frame'] = (boss['anim_frame'] + 1) % 10  # 10 frames in sequence

            # Check if we just reached frame 8 (spawn frame, 1-indexed = frame index 7)
            spawn_frame = getattr(jelly_boss_cfg, 'spawn_frame', 8) if jelly_boss_cfg else 8
            spawn_frame_idx = spawn_frame - 1  # Convert to 0-indexed
            max_concurrent = getattr(jelly_boss_cfg, 'max_spawned_bats', 5) if jelly_boss_cfg else 5

            # Count currently ALIVE bats spawned by this boss (not total ever spawned)
            alive_boss_bats = sum(1 for bat in state.enemies.bats if bat.get('from_boss'))

            if boss['anim_frame'] == spawn_frame_idx and alive_boss_bats < max_concurrent:
                # Start bat spawn animation (o -> O -> () -> bat)
                boss['bat_spawn_anim'] = {
                    'active': True,
                    'frame': 0,  # Animation frame (0=o, 1=O, 2=(), 3=spawn bat)
                    'timer': 0,
                    'x_pos': boss['x_pos'] + 11,  # Center of boss head
                    'y_pos': boss['y_pos'] - 1,  # One row ABOVE boss (not inside)
                    'char': 'o',  # Starting character
                }

        # Update bat spawn animation if active
        _update_jelly_bat_spawn_anim(boss)

        # Oscillation movement
        oscillation_speed = getattr(jelly_boss_cfg, 'oscillation_speed', 10) if jelly_boss_cfg else 10
        oscillation_range = getattr(jelly_boss_cfg, 'oscillation_range', 3) if jelly_boss_cfg else 3
        if state.game.frame_count % oscillation_speed == 0:
            base_x = boss['base_x_pos']
            current_offset = boss['x_pos'] - base_x
            direction = boss.get('oscillation_dir', 1)
            new_offset = current_offset + direction
            if new_offset >= oscillation_range:
                new_offset = oscillation_range
                boss['oscillation_dir'] = -1
            elif new_offset <= -oscillation_range:
                new_offset = -oscillation_range
                boss['oscillation_dir'] = 1
            boss['x_pos'] = base_x + new_offset

    elif boss_state == 'dying':
        _convert_jelly_boss_to_obstacle(boss)
        state.enemies.boss = None
        state.enemies.boss_defeated = True


def _update_jelly_bat_spawn_anim(boss):
    """Update the bat spawn animation from jelly boss (o -> O -> () -> bat)."""
    anim = boss.get('bat_spawn_anim')
    if anim is None or not anim.get('active'):
        return

    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    anim_duration = getattr(jelly_boss_cfg, 'spawn_anim_duration', 0.5) if jelly_boss_cfg else 0.5
    # ~5 fps, so for 0.5s total with 4 frames = ~0.6 game frames per step
    # But let's use at least 1 frame per step
    frames_per_anim_step = max(1, int(anim_duration * 5 / 4))  # 5 fps, 4 animation steps

    anim['timer'] += 1
    if anim['timer'] >= frames_per_anim_step:
        anim['timer'] = 0
        anim['frame'] += 1

        # Update character based on frame: 0=o, 1=O, 2=(), 3=spawn bat
        if anim['frame'] == 1:
            anim['char'] = 'O'
        elif anim['frame'] == 2:
            anim['char'] = '()'
        elif anim['frame'] >= 3:
            # Animation complete, spawn the bat
            _spawn_bat_from_jelly_boss(boss, anim)
            boss['bat_spawn_anim'] = None
            boss['spawned_bats'] = boss.get('spawned_bats', 0) + 1


def _spawn_bat_from_jelly_boss(boss, anim):
    """Spawn an actual bat from the jelly boss animation."""
    # Choose a random bat type based on current level
    level = state.game.level

    # Get tier weights from config (same logic as spawn_bat)
    tier_weights_cfg = getattr(constants.bat_enemy, 'tier_weights_by_level', None)
    if level <= 6:
        weights = getattr(tier_weights_cfg, 'level_4_6', [70, 25, 5, 0]) if tier_weights_cfg else [70, 25, 5, 0]
    elif level <= 9:
        weights = getattr(tier_weights_cfg, 'level_7_9', [50, 35, 12, 3]) if tier_weights_cfg else [50, 35, 12, 3]
    elif level <= 12:
        weights = getattr(tier_weights_cfg, 'level_10_12', [30, 40, 22, 8]) if tier_weights_cfg else [30, 40, 22, 8]
    elif level <= 15:
        weights = getattr(tier_weights_cfg, 'level_13_15', [15, 35, 35, 15]) if tier_weights_cfg else [15, 35, 35, 15]
    else:
        weights = getattr(tier_weights_cfg, 'level_16_18', [5, 25, 45, 25]) if tier_weights_cfg else [5, 25, 45, 25]
    tier = random.choices([1, 2, 3, 4], weights=weights)[0]

    # Get HP from config
    bat_hp_by_tier = constants.bat_enemy.hp_by_tier
    if isinstance(bat_hp_by_tier, dict):
        hp = bat_hp_by_tier.get(tier, bat_hp_by_tier.get(str(tier), 20))
    else:
        hp = getattr(bat_hp_by_tier, str(tier), 20)

    # Determine special bat types (same logic as spawn_bat)
    armored = False
    diver = False
    spellcaster = False

    # Check for diver (any tier)
    diver_cfg = getattr(constants.bat_enemy, 'diver', None)
    if diver_cfg:
        min_diver_tier = getattr(diver_cfg, 'min_tier', 1)
        if tier >= min_diver_tier:
            diver_prob_cfg = getattr(diver_cfg, 'spawn_probability_by_level', None)
            if diver_prob_cfg:
                if level <= 3:
                    diver_prob = getattr(diver_prob_cfg, 'level_1_3', 0.0)
                elif level <= 6:
                    diver_prob = getattr(diver_prob_cfg, 'level_4_6', 0.08)
                elif level <= 9:
                    diver_prob = getattr(diver_prob_cfg, 'level_7_9', 0.12)
                elif level <= 12:
                    diver_prob = getattr(diver_prob_cfg, 'level_10_12', 0.16)
                elif level <= 15:
                    diver_prob = getattr(diver_prob_cfg, 'level_13_15', 0.20)
                else:
                    diver_prob = getattr(diver_prob_cfg, 'level_16_18', 0.25)
                diver = random.random() < diver_prob

    # If not diver, check for spellcaster (tier 2+ only)
    if not diver:
        spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
        if spellcaster_cfg:
            min_spell_tier = getattr(spellcaster_cfg, 'min_tier', 2)
            if tier >= min_spell_tier:
                spell_prob_cfg = getattr(spellcaster_cfg, 'spawn_probability_by_level', None)
                if spell_prob_cfg:
                    if level <= 3:
                        spell_prob = getattr(spell_prob_cfg, 'level_1_3', 0.0)
                    elif level <= 6:
                        spell_prob = getattr(spell_prob_cfg, 'level_4_6', 0.05)
                    elif level <= 9:
                        spell_prob = getattr(spell_prob_cfg, 'level_7_9', 0.08)
                    elif level <= 12:
                        spell_prob = getattr(spell_prob_cfg, 'level_10_12', 0.12)
                    elif level <= 15:
                        spell_prob = getattr(spell_prob_cfg, 'level_13_15', 0.15)
                    else:
                        spell_prob = getattr(spell_prob_cfg, 'level_16_18', 0.20)
                    spellcaster = random.random() < spell_prob

    # If not diver or spellcaster, check for armored (tier 2+ only)
    if not diver and not spellcaster:
        armored_cfg = getattr(constants.bat_enemy, 'armored', None)
        if armored_cfg:
            min_armor_tier = getattr(armored_cfg, 'min_tier', 2)
            if tier >= min_armor_tier:
                armor_prob_cfg = getattr(armored_cfg, 'spawn_probability_by_level', None)
                if armor_prob_cfg:
                    if level <= 3:
                        armor_prob = getattr(armor_prob_cfg, 'level_1_3', 0.0)
                    elif level <= 6:
                        armor_prob = getattr(armor_prob_cfg, 'level_4_6', 0.05)
                    elif level <= 9:
                        armor_prob = getattr(armor_prob_cfg, 'level_7_9', 0.10)
                    elif level <= 12:
                        armor_prob = getattr(armor_prob_cfg, 'level_10_12', 0.15)
                    elif level <= 15:
                        armor_prob = getattr(armor_prob_cfg, 'level_13_15', 0.20)
                    else:
                        armor_prob = getattr(armor_prob_cfg, 'level_16_18', 0.25)
                    armored = random.random() < armor_prob

    # Create the bat at the animation position
    bat_data = {
        'x_pos': anim['x_pos'] - 4,  # Center the bat sprite
        'y_pos': anim['y_pos'],
        'direction': random.choice([-1, 1]),
        'tier': tier,
        'hp': hp,
        'max_hp': hp,
        'target_y': boss['y_pos'] + 8,  # Target below the boss
        'spawn_ts': time.time(),
        'armored': armored,
        'diver': diver,
        'spellcaster': spellcaster,
        'from_boss': True,  # Mark as spawned from boss (no loot drop)
        'descending_past_boss': True,  # Still passing in front of boss
    }

    # Add diver-specific fields
    if diver:
        bat_data['diver_state'] = 'flying'
        bat_data['diver_home_y'] = bat_data['target_y']
        bat_data['dive_start_y'] = None
        bat_data['stun_end_time'] = None

    # Add spellcaster-specific fields
    if spellcaster:
        bat_data['spell_state'] = 'idle'
        bat_data['spell_cooldown'] = 0
        bat_data['casting_end_time'] = None
        # Determine known spells based on tier
        spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
        spells_by_tier = getattr(spellcaster_cfg, 'spells_by_tier', None) if spellcaster_cfg else None
        if spells_by_tier:
            if isinstance(spells_by_tier, dict):
                num_spells = spells_by_tier.get(tier, spells_by_tier.get(str(tier), 1))
            else:
                num_spells = getattr(spells_by_tier, str(tier), 1)
        else:
            num_spells = min(tier - 1, 3)
        all_spells = ['silence', 'repugnant_wind', 'exile']
        bat_data['known_spells'] = all_spells[:num_spells]

    # Add to spawn queue
    state.enemies.spawn_queue.append({
        'type': 'bat',
        'data': bat_data
    })


def _convert_jelly_boss_to_obstacle(boss):
    """Convert dead Jelly Boss to a falling obstacle."""
    boss_cfg = _get_boss_config()
    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)

    corpse_cfg = getattr(jelly_boss_cfg, 'corpse', None) if jelly_boss_cfg else None
    hp = getattr(corpse_cfg, 'hp', 80) if corpse_cfg else 80

    boss_center_x = boss['x_pos'] + 11  # Jelly boss is ~23 chars wide
    closest_lane = min(range(constants.layout.num_lanes),
                       key=lambda l: abs(constants.layout.lane_positions[l] - boss_center_x))

    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1

    state.enemies.obstacles.append({
        'id': obstacle_id,
        'lane': closest_lane,
        'x_pos': boss['x_pos'],
        'y_pos': boss['y_pos'],
        'tier': 5,
        'hp': hp,
        'max_hp': hp,
        'sprite_width': 23,
        'is_boss_corpse': True,
        'is_jelly_boss_corpse': True,
    })

    # Award score and XP
    score = getattr(jelly_boss_cfg, 'score', 1500) if jelly_boss_cfg else 1500
    xp = getattr(jelly_boss_cfg, 'xp', 150) if jelly_boss_cfg else 150
    add_score(score)

    for i in range(constants.layout.num_balls):
        if not state.birds.lost[i]:
            award_xp(i, xp // max(1, sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])))

    # Drop loot
    loot_cfg = getattr(boss_cfg, 'loot', None)
    loot_count = getattr(loot_cfg, 'count', 3) if loot_cfg else 3
    loot_tier = getattr(loot_cfg, 'tier', 3) if loot_cfg else 3

    loot_weights = constants.bat_enemy.loot_base_weights
    if isinstance(loot_weights, dict):
        tier_weights = loot_weights.get(loot_tier, loot_weights.get(str(loot_tier), [30, 35, 25, 10]))
    else:
        tier_weights = getattr(loot_weights, str(loot_tier), [30, 35, 25, 10])

    prestige = compute_prestige()
    adj_weights = adjust_rarity_weights(tier_weights, prestige)

    for i in range(loot_count):
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)

        lane_offset = i - loot_count // 2
        loot_lane = max(0, min(constants.layout.num_lanes - 1, closest_lane + lane_offset))

        state.items.loot_items.append({
            'x_pos': constants.layout.lane_positions[loot_lane],
            'y_pos': boss['y_pos'] + 3,
            'type': loot_type,
            'rarity': rarity,
            'spawn_ts': time.time()
        })


def update_tree_boss():
    """Update Tree Boss state: flower growth, effects, check win condition."""
    boss = state.enemies.boss
    if boss is None or boss.get('boss_type') != 'tree':
        return

    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
    grow_interval = getattr(flowers_cfg, 'grow_interval', 2.0) if flowers_cfg else 2.0
    respawn_delay = getattr(flowers_cfg, 'respawn_delay', 3.0) if flowers_cfg else 3.0
    flower_hp = getattr(flowers_cfg, 'hp', 10) if flowers_cfg else 10

    now = time.time()
    branches = boss.get('branches', [])

    # Check if boss is already defeated and scrolling down
    if boss.get('state') == 'scrolling_down':
        _tree_boss_defeated(boss)
        return

    # Check if all branches destroyed (win condition)
    alive_branches = [b for b in branches if not b.get('destroyed')]
    if not alive_branches:
        _tree_boss_defeated(boss)
        return

    # Move tree (background + branches) down together, solidly connected
    # bg_y_offset is the Y position of the TOP of the tree sprite
    # Tree stops when fully visible on screen (configurable offset from top)
    from src.entities.sprites import TREE_BOSS_BACKGROUND
    bg_height = len(TREE_BOSS_BACKGROUND)
    stop_offset = getattr(tree_boss_cfg, 'stop_offset', 0) if tree_boss_cfg else 0
    target_bg_y = stop_offset  # Stop position (negative = higher up)

    current_bg_y = boss.get('bg_y_offset', 0)
    tree_is_moving = current_bg_y < target_bg_y

    if state.game.frame_count % 5 == 0 and tree_is_moving:
        # Move everything down by 1
        boss['bg_y_offset'] = current_bg_y + 1

        # Move ALL branches down together with the tree (solidali)
        for branch in branches:
            branch['y_pos'] += 1

    # Update each branch's flower
    # Import mature frame constant
    from src.entities.sprites import FLOWER_MATURE_FRAME

    for branch in alive_branches:
        flower = branch.get('flower')
        if not flower:
            continue

        if flower.get('active'):
            # Flowers only start growing AFTER tree has stopped moving
            if tree_is_moving:
                continue

            # Initialize grow_timer when tree stops (first time)
            if flower.get('grow_timer') is None:
                flower['grow_timer'] = now + grow_interval

            # Flower is alive - check if it should grow
            # 6 frames total (0-5), mature at frame 5
            if flower['frame'] < FLOWER_MATURE_FRAME and now >= flower.get('grow_timer', 0):
                flower['frame'] += 1
                flower['grow_timer'] = now + grow_interval

                # If flower just matured (frame 5), apply its effect
                if flower['frame'] == FLOWER_MATURE_FRAME:
                    _apply_mature_flower_effect(branch, flower)
        else:
            # Flower is dead - check if it should respawn (only when tree stopped)
            if tree_is_moving:
                continue

            if now >= flower.get('respawn_timer', 0):
                # Respawn new flower with random type at random position
                flower_types = ['red', 'yellow', 'blue', 'green']
                flower['type'] = random.choice(flower_types)
                flower['frame'] = 0
                flower['hp'] = flower_hp
                flower['max_hp'] = flower_hp
                flower['grow_timer'] = now + grow_interval
                flower['active'] = True
                # Pick new random position from branch's available positions
                flower_positions = branch.get('flower_positions', [(0, 0)])
                new_pos = random.choice(flower_positions)
                flower['rel_x'] = new_pos[0]
                flower['rel_y'] = new_pos[1]


def _apply_mature_flower_effect(branch, flower):
    """Apply the effect of a mature (frame 5) flower to its lanes."""
    # Yellow, blue, and green effects are applied on collision, not passively
    pass


def _handle_tree_branch_hit(branch, bird_idx):
    """Handle a bird hitting a tree branch.

    Returns True if the hit was processed, False otherwise.
    """
    if branch.get('destroyed'):
        return False

    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    branches_cfg = getattr(tree_boss_cfg, 'branches', None) if tree_boss_cfg else None
    on_hit_cfg = getattr(branches_cfg, 'on_hit', None) if branches_cfg else None
    flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None

    # Calculate damage
    damage = _calculate_bird_damage(bird_idx)

    flower = branch.get('flower')
    # Only apply effects if flower is active AND fully mature (frame 5)
    from src.entities.sprites import FLOWER_MATURE_FRAME
    flower_was_mature = flower and flower.get('active') and flower.get('frame', 0) >= FLOWER_MATURE_FRAME

    # Damage flower first, then branch
    if flower and flower.get('active') and flower.get('hp', 0) > 0:
        flower['hp'] -= damage
        if flower['hp'] <= 0:
            # Flower destroyed - will respawn later
            flower['active'] = False
            respawn_delay = getattr(flowers_cfg, 'respawn_delay', 3.0) if flowers_cfg else 3.0
            flower['respawn_timer'] = time.time() + respawn_delay
    else:
        # No flower or flower dead - damage branch
        branch['hp'] -= damage
        if branch['hp'] <= 0:
            branch['destroyed'] = True
            add_score(100)  # Score for destroying branch

    # Apply effects on hit

    # 1. Bounce bird down
    state.birds.vy[bird_idx] = 1

    # 2. Stun bird briefly (can't bounce immediately)
    stun_duration = getattr(on_hit_cfg, 'stun_duration', 1.0) if on_hit_cfg else 1.0
    stun_frames = int(stun_duration / constants.timing.base_sleep)
    state.special.stunned_birds[bird_idx] = stun_frames  # Simple frame counter stun

    # 3. Fall speed boost (+1 for 1 second)
    fall_boost_duration = getattr(on_hit_cfg, 'fall_boost_duration', 1.0) if on_hit_cfg else 1.0
    fall_boost_speed = getattr(on_hit_cfg, 'fall_boost_speed', 1) if on_hit_cfg else 1
    boost_frames = int(fall_boost_duration / constants.timing.base_sleep)
    state.special.dive_fall_boosts[bird_idx] = {
        'frames': boost_frames,
        'speed': fall_boost_speed,
    }

    # 3. Jumpscare bat spawn (probability)
    jumpscare_prob = getattr(on_hit_cfg, 'jumpscare_probability', 0.3) if on_hit_cfg else 0.3
    if random.random() < jumpscare_prob:
        _spawn_jumpscare_bat_from_branch(branch)

    # 4. Apply flower effects if flower was mature
    if flower_was_mature:
        _apply_flower_collision_effect(flower, bird_idx)

    return True


def _apply_flower_collision_effect(flower, bird_idx):
    """Apply flower effect when bird collides with branch that has mature flower."""
    flower_type = flower.get('type')
    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None

    if flower_type == 'red':
        # Red flower: chance to bleed bird
        red_cfg = getattr(flowers_cfg, 'red', None) if flowers_cfg else None
        probability = getattr(red_cfg, 'probability', 0.4) if red_cfg else 0.4

        if random.random() < probability:
            bleed_duration = getattr(red_cfg, 'bleed_duration', 5.0) if red_cfg else 5.0
            lives = getattr(red_cfg, 'lives', 3) if red_cfg else 3
            state.special.bleeding_birds[bird_idx] = {
                'end_time': time.time() + bleed_duration,
                'lives_needed': lives,
                'lives_lost': 0,
            }

    elif flower_type == 'yellow':
        # Yellow flower: chance to stun bird
        yellow_cfg = getattr(flowers_cfg, 'yellow', None) if flowers_cfg else None
        probability = getattr(yellow_cfg, 'probability', 0.4) if yellow_cfg else 0.4

        if random.random() < probability:
            stun_duration = getattr(yellow_cfg, 'stun_duration', 3.0) if yellow_cfg else 3.0
            state.special.stunned_birds[bird_idx] = {
                'end_time': time.time() + stun_duration,
                'type': 'flower',  # Mark as flower stun (different from obstacle stun)
            }

    elif flower_type == 'blue':
        # Blue flower: chance to freeze bird
        blue_cfg = getattr(flowers_cfg, 'blue', None) if flowers_cfg else None
        probability = getattr(blue_cfg, 'probability', 0.4) if blue_cfg else 0.4

        if random.random() < probability:
            thaw_min = getattr(blue_cfg, 'thaw_attempts_min', 3) if blue_cfg else 3
            thaw_max = getattr(blue_cfg, 'thaw_attempts_max', 5) if blue_cfg else 5
            thaw_attempts = random.randint(thaw_min, thaw_max)
            state.special.frozen_birds[bird_idx] = {
                'thaw_attempts_needed': thaw_attempts,
                'thaw_attempts_done': 0,
            }

    elif flower_type == 'green':
        # Green flower: chance to poison bird
        green_cfg = getattr(flowers_cfg, 'green', None) if flowers_cfg else None
        probability = getattr(green_cfg, 'probability', 0.3) if green_cfg else 0.3

        if random.random() < probability:
            poison_duration = getattr(green_cfg, 'poison_duration', 20.0) if green_cfg else 20.0
            cure_min = getattr(green_cfg, 'cure_attempts_min', 2) if green_cfg else 2
            cure_max = getattr(green_cfg, 'cure_attempts_max', 4) if green_cfg else 4
            cure_attempts = random.randint(cure_min, cure_max)
            state.special.poisoned_birds[bird_idx] = {
                'death_time': time.time() + poison_duration,
                'cure_attempts_needed': cure_attempts,
                'cure_attempts_done': 0,
            }


def _spawn_jumpscare_bat_from_branch(branch):
    """Spawn a jumpscare bat near the branch."""
    # Spawn a mini bat as jumpscare
    x_pos = branch['x_pos'] + branch['sprite_width'] // 2
    y_pos = branch['y_pos']

    # Find closest lane to bat x position
    closest_lane = 0
    min_dist = float('inf')
    for lane_idx, lane_x in enumerate(constants.layout.lane_positions):
        dist = abs(lane_x - x_pos)
        if dist < min_dist:
            min_dist = dist
            closest_lane = lane_idx

    mini_bat = {
        'x_pos': x_pos,
        'y_pos': y_pos,
        'direction': random.choice([-1, 1]),
        'tier': 0,
        'hp': 8,
        'max_hp': 8,
        'target_y': y_pos + 5,
        'spawn_ts': time.time(),
        'is_jumpscare': True,
        'lane': closest_lane,  # Required for activate_jumpscare_scary_face
        'from_boss': True,  # Spawned from boss - no loot drop
        # Required fields for update_mini_bats
        'state': 'spawning',
        'anim_timer': 0,
        'anim_frame': 0,
        'visited_obstacles': set(),
    }
    state.enemies.mini_bats.append(mini_bat)


def _tree_boss_defeated(boss):
    """Handle Tree Boss defeat - all branches destroyed. Start scrolling down."""
    # Mark as defeated but don't remove yet - will scroll down
    if boss.get('state') != 'scrolling_down':
        tree_boss_cfg = getattr(constants, 'tree_boss', None)

        # Award score and XP
        score = getattr(tree_boss_cfg, 'score', 2000) if tree_boss_cfg else 2000
        xp = getattr(tree_boss_cfg, 'xp', 200) if tree_boss_cfg else 200
        add_score(score)

        for i in range(constants.layout.num_balls):
            if not state.birds.lost[i]:
                award_xp(i, xp // max(1, sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])))

        # Drop loot (spread across screen)
        loot_count = 5  # One per branch destroyed
        prestige = compute_prestige()
        base_weights = getattr(constants.loot, 'base_rarity_weights', [60, 25, 10, 5])
        if not isinstance(base_weights, list):
            base_weights = [60, 25, 10, 5]
        adj_weights = adjust_rarity_weights(base_weights, prestige)

        for i in range(loot_count):
            rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
            loot_type = choose_loot_type(rarity)

            lane = i % constants.layout.num_lanes
            state.items.loot_items.append({
                'x_pos': constants.layout.lane_positions[lane],
                'y_pos': 5 + i * 3,
                'type': loot_type,
                'rarity': rarity,
                'spawn_ts': time.time()
            })

        # Clear frozen/poisoned/bleeding birds
        state.special.frozen_birds.clear()
        state.special.poisoned_birds.clear()
        state.special.bleeding_birds.clear()

        # Mark boss as scrolling down (defeated but still visible)
        boss['state'] = 'scrolling_down'
        state.enemies.boss_defeated = True
        return

    # Already scrolling down - continue scrolling
    from src.entities.sprites import TREE_BOSS_BACKGROUND
    bg_height = len(TREE_BOSS_BACKGROUND)

    # Scroll tree down every few frames
    if state.game.frame_count % 3 == 0:
        boss['bg_y_offset'] = boss.get('bg_y_offset', 0) + 1

    # Check if tree has scrolled completely off screen
    if boss.get('bg_y_offset', 0) > constants.layout.height:
        # Tree is off screen - now fully clear the boss
        state.enemies.boss = None


def _convert_boss_to_obstacle(boss):
    """Convert dead boss to a falling obstacle using BOSS_DEAD sprite."""
    boss_cfg = _get_boss_config()

    # Get corpse HP from config (special boss corpse, not tier 4)
    corpse_cfg = getattr(boss_cfg, 'corpse', None)
    hp = getattr(corpse_cfg, 'hp', 64) if corpse_cfg else 64

    # Find closest lane to boss center
    boss_center_x = boss['x_pos'] + 9  # Boss is ~19 chars wide
    closest_lane = min(range(constants.layout.num_lanes),
                       key=lambda l: abs(constants.layout.lane_positions[l] - boss_center_x))

    # Assign unique ID
    obstacle_id = state.enemies.obstacle_id_counter
    state.enemies.obstacle_id_counter += 1

    state.enemies.obstacles.append({
        'id': obstacle_id,
        'lane': closest_lane,
        'x_pos': boss['x_pos'],  # Keep exact X position for BOSS_DEAD sprite
        'y_pos': boss['y_pos'],
        'tier': 5,  # Special tier for boss corpse (not regular 1-4)
        'hp': hp,
        'max_hp': hp,
        'sprite_width': 19,  # Full boss sprite width
        'is_boss_corpse': True,  # Mark as boss corpse for special rendering
    })

    # Award score and XP for defeating boss
    score = getattr(boss_cfg, 'score', 1000)
    xp = getattr(boss_cfg, 'xp', 100)
    add_score(score)

    # Award XP to all active birds
    for i in range(constants.layout.num_balls):
        if not state.birds.lost[i]:
            award_xp(i, xp // max(1, sum(1 for j in range(constants.layout.num_balls) if not state.birds.lost[j])))

    # Drop loot - boss drops 3 items with tier 3 weights
    loot_cfg = getattr(boss_cfg, 'loot', None)
    loot_count = getattr(loot_cfg, 'count', 3) if loot_cfg else 3
    loot_tier = getattr(loot_cfg, 'tier', 3) if loot_cfg else 3

    # Get tier 3 loot weights from bat_enemy config
    loot_weights = constants.bat_enemy.loot_base_weights
    if isinstance(loot_weights, dict):
        tier_weights = loot_weights.get(loot_tier, loot_weights.get(str(loot_tier), [30, 35, 25, 10]))
    else:
        tier_weights = getattr(loot_weights, str(loot_tier), [30, 35, 25, 10])

    # Adjust with prestige
    prestige = compute_prestige()
    adj_weights = adjust_rarity_weights(tier_weights, prestige)

    # Spawn loot items spread across lanes near boss
    for i in range(loot_count):
        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
        loot_type = choose_loot_type(rarity)

        # Spread loot across nearby lanes
        lane_offset = i - loot_count // 2
        loot_lane = max(0, min(constants.layout.num_lanes - 1, closest_lane + lane_offset))

        state.items.loot_items.append({
            'x_pos': constants.layout.lane_positions[loot_lane],
            'y_pos': boss['y_pos'] + 1,  # Just below boss
            'type': loot_type,
            'rarity': rarity,
            'spawn_ts': time.time()
        })


def _check_bird_tree_branch_collision():
    """Check bird collisions with Tree Boss branches."""
    boss = state.enemies.boss
    if boss is None or boss.get('boss_type') != 'tree':
        return

    branches = boss.get('branches', [])

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        # Skip frozen birds (they don't collide normally)
        if i in state.special.frozen_birds:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_lane_x = constants.layout.lane_positions[bird_lane]
        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_color == STEALTH and i not in state.special.stealth_timers:
            continue

        bird_height = 3 if bird_color == DINOSAUR else 2

        # Check each branch for collision
        for branch in branches:
            if branch.get('destroyed'):
                continue

            branch_left = branch['x_pos']
            branch_right = branch['x_pos'] + branch['sprite_width']
            branch_top = branch['y_pos']
            branch_bottom = branch['y_pos'] + branch['sprite_height']

            lane_left = bird_lane_x - 2
            lane_right = bird_lane_x + 2

            horizontal_overlap = not (branch_right < lane_left or branch_left > lane_right)
            vertical_overlap = not (bird_y + bird_height < branch_top or bird_y > branch_bottom)

            if horizontal_overlap and vertical_overlap:
                # Hit branch!
                _handle_tree_branch_hit(branch, i)
                play_sfx('hit')
                break  # Only hit one branch per frame per bird


def check_bird_boss_collision():
    """Check bird-boss collisions."""
    boss = state.enemies.boss
    if boss is None or boss['state'] in ('dying', 'dead'):
        return

    # Special handling for Tree Boss (collision with branches)
    if boss.get('boss_type') == 'tree':
        _check_bird_tree_branch_collision()
        return

    boss_cfg = _get_boss_config()
    if boss_cfg is None:
        return

    # Boss hitbox
    boss_left = boss['x_pos']
    boss_right = boss['x_pos'] + 19  # Boss sprite width
    boss_top = boss['y_pos']
    boss_bottom = boss['y_pos'] + 3  # Boss is 3 lines tall

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_lane_x = constants.layout.lane_positions[bird_lane]
        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_color == STEALTH and i not in state.special.stealth_timers:
            continue

        bird_height = 3 if bird_color == DINOSAUR else 2

        lane_left = bird_lane_x - 2
        lane_right = bird_lane_x + 2

        horizontal_overlap = not (boss_right < lane_left or boss_left > lane_right)
        vertical_overlap = not (bird_y + bird_height < boss_top or bird_y > boss_bottom)

        if not (horizontal_overlap and vertical_overlap):
            continue

        # Hit boss!
        damage = _calculate_bird_damage(i)

        # Apply armor reduction
        armor_reduction = getattr(boss_cfg, 'armor_reduction', 1)
        if bird_color != ORANGE:
            damage = max(1, damage - armor_reduction)

        if bird_color == ORANGE:
            boss['hp'] -= boss['max_hp'] // 4  # Orange does 25% of max HP
        else:
            boss['hp'] -= damage
            award_xp(i, damage)

        # Boss scream if hit causes scare
        scare_frames = int(1.0 / constants.timing.base_sleep)
        state.special.scared_birds[i] = scare_frames

        if boss['hp'] <= 0:
            boss['state'] = 'dying'
            play_sfx('boss_death')
        else:
            _set_ball_vy(i, 1)
            state.birds.y[i] = boss_bottom + 1
            if bird_color == BLUE:
                _reset_bird_power(i)
            play_sfx('hit')
        break


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

    if state.powerups.timelapse_active:
        # Use real time instead of frame count
        if time.time() >= state.powerups.timelapse_end_time:
            state.powerups.timelapse_active = False
            state.powerups.timelapse_slowdown = 1.0


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

    # Stunned birds (from obstacle collision or flower)
    now = time.time()
    for bird_idx in list(state.special.stunned_birds.keys()):
        stun_info = state.special.stunned_birds[bird_idx]
        if isinstance(stun_info, dict):
            # Time-based stun (from flower)
            if now >= stun_info.get('end_time', 0):
                del state.special.stunned_birds[bird_idx]
        else:
            # Frame-based stun (from obstacle collision)
            state.special.stunned_birds[bird_idx] -= 1
            if state.special.stunned_birds[bird_idx] <= 0:
                del state.special.stunned_birds[bird_idx]

    # Dive fall boosts (from diver bats)
    for bird_idx in list(state.special.dive_fall_boosts.keys()):
        boost_info = state.special.dive_fall_boosts[bird_idx]
        boost_info['frames'] -= 1
        if boost_info['frames'] <= 0:
            del state.special.dive_fall_boosts[bird_idx]

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

    # Poisoned birds - check death timer
    now = time.time()
    for bird_idx in list(state.special.poisoned_birds.keys()):
        poison_info = state.special.poisoned_birds[bird_idx]
        death_time = poison_info.get('death_time', 0)
        if now >= death_time:
            # Bird dies from poison!
            if not state.birds.lost[bird_idx]:
                state.birds.lost[bird_idx] = True
                state.birds.y[bird_idx] = constants.layout.height - 1
                state.game.lives -= 1
                if state.game.lives <= 0:
                    state.game.game_over = True
            # Remove from poisoned dict
            del state.special.poisoned_birds[bird_idx]

    # Bleeding birds - check if bleed expired (bird survives if timer runs out)
    for bird_idx in list(state.special.bleeding_birds.keys()):
        bleed_info = state.special.bleeding_birds[bird_idx]
        end_time = bleed_info.get('end_time', 0)
        if now >= end_time:
            # Bleed expired - bird survives!
            del state.special.bleeding_birds[bird_idx]


def update_spell_effects():
    """Update spell effects from spellcaster bats."""
    now = time.time()

    # Update silenced lanes (remove expired)
    for lane in list(state.spells.silenced_lanes.keys()):
        if now >= state.spells.silenced_lanes[lane]['end_time']:
            del state.spells.silenced_lanes[lane]

    # Update repugnant wind lanes (remove expired)
    for lane in list(state.spells.repugnant_wind_lanes.keys()):
        if now >= state.spells.repugnant_wind_lanes[lane]['end_time']:
            del state.spells.repugnant_wind_lanes[lane]

    # Process pending exile swaps
    for exile in state.spells.pending_exiles[:]:
        if now >= exile['swap_time']:
            _execute_exile_swap(exile)
            state.spells.pending_exiles.remove(exile)


def _execute_exile_swap(exile):
    """Execute an exile swap between birds."""
    bird_a_idx = exile['bird_a_idx']
    bird_b_idx = exile['bird_b_idx']
    empty_lane = exile.get('empty_lane')

    # Validate bird A still exists
    if state.birds.lost[bird_a_idx]:
        return

    if empty_lane is not None:
        # Swap bird A to empty lane
        state.birds.random_lanes[bird_a_idx] = empty_lane
        state.birds.cols[bird_a_idx] = constants.layout.lane_positions[empty_lane]
    elif bird_b_idx is not None and not state.birds.lost[bird_b_idx]:
        # Swap lanes between bird A and bird B
        lane_a = state.birds.random_lanes[bird_a_idx]
        lane_b = state.birds.random_lanes[bird_b_idx]

        state.birds.random_lanes[bird_a_idx] = lane_b
        state.birds.random_lanes[bird_b_idx] = lane_a
        state.birds.cols[bird_a_idx] = constants.layout.lane_positions[lane_b]
        state.birds.cols[bird_b_idx] = constants.layout.lane_positions[lane_a]


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


# =============================================================================
# CAVE PORTALS (Biome 5)
# =============================================================================

def spawn_portal_pair():
    """Spawn a pair of portals in the cave biome - FIXED positions, no scrolling."""
    if state.game.level_group != 5:
        return

    state.enemies.portal_spawn_timer -= 1
    if state.enemies.portal_spawn_timer > 0:
        return

    # Random spawn interval (rare)
    state.enemies.portal_spawn_timer = random.randint(300, 500)

    # Portal sprite is 5 wide, 3 tall
    portal_width = 5
    portal_height = 3

    # Game area dimensions
    game_height = constants.layout.height
    num_lanes = constants.layout.num_lanes
    lane_positions = constants.layout.lane_positions

    # Pick two different lanes with at least 1 lane between them
    max_attempts = 30
    for _ in range(max_attempts):
        lane1 = random.randint(0, num_lanes - 1)
        lane2 = random.randint(0, num_lanes - 1)

        # At least 2 lanes apart (so 1 lane in between)
        if abs(lane1 - lane2) >= 2:
            break
    else:
        return  # Couldn't find valid lanes

    # Center portals on their lanes
    x1 = lane_positions[lane1] - portal_width // 2
    x2 = lane_positions[lane2] - portal_width // 2

    # Random y positions - max 2/3 of screen height from top
    max_y = (game_height * 2) // 3
    y1 = random.randint(3, max_y - portal_height)
    y2 = random.randint(3, max_y - portal_height)

    # Create portal pair
    pair_id = state.enemies.portal_pair_counter
    state.enemies.portal_pair_counter += 1

    # Duration: how long portals stay on screen (in frames)
    duration = random.randint(200, 400)
    expire_frame = state.game.frame_count + duration

    portal_a = {
        'x_pos': x1,
        'y_pos': y1,
        'pair_id': pair_id,
        'portal_idx': 0,
        'lane': lane1,
        'width': portal_width,
        'height': portal_height,
        'expire_frame': expire_frame,
    }

    portal_b = {
        'x_pos': x2,
        'y_pos': y2,
        'pair_id': pair_id,
        'portal_idx': 1,
        'lane': lane2,
        'width': portal_width,
        'height': portal_height,
        'expire_frame': expire_frame,
    }

    state.enemies.portals.append(portal_a)
    state.enemies.portals.append(portal_b)


def update_portals():
    """Update portals - fixed position, handle teleportation/destruction."""
    if state.game.level_group != 5:
        # Clear portals when not in cave biome
        if state.enemies.portals:
            _return_birds_to_home_lanes()
            state.enemies.portals = []
        return

    # Spawn new portal pairs
    spawn_portal_pair()

    # Remove expired portals - when a portal pair expires, return birds to home lanes
    expired_pairs = set()
    for portal in state.enemies.portals[:]:
        if state.game.frame_count >= portal.get('expire_frame', float('inf')):
            expired_pairs.add(portal['pair_id'])
            state.enemies.portals.remove(portal)

    # If any portals expired, check if we need to return birds to home lanes
    if expired_pairs:
        _return_birds_to_home_lanes()

    # Check bird-portal collisions (teleportation)
    _check_bird_portal_teleport()

    # Check obstacle-portal collisions (destruction)
    _check_obstacle_portal_destruction()


def _return_birds_to_home_lanes():
    """Return all birds to their home lanes (where they belong when no portals exist)."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        home_lane = state.birds.home_lanes[i]
        current_lane = state.birds.random_lanes[i]

        if current_lane != home_lane:
            # Return bird to home lane
            state.birds.random_lanes[i] = home_lane
            state.birds.cols[i] = constants.layout.lane_positions[home_lane]


def _get_portal_pair(portal):
    """Get the paired portal for a given portal."""
    pair_id = portal['pair_id']
    portal_idx = portal['portal_idx']
    other_idx = 1 - portal_idx  # 0 -> 1, 1 -> 0

    for p in state.enemies.portals:
        if p['pair_id'] == pair_id and p['portal_idx'] == other_idx:
            return p
    return None


def _check_bird_portal_teleport():
    """Check if any birds CROSS through a portal and teleport them.

    A bird crosses a portal when:
    - Going UP (vy=-1): bird enters portal from below and exits above
    - Going DOWN (vy=+1): bird enters portal from above and exits below

    We detect crossing by checking if the bird is in the portal's lane
    and its y position crosses the portal boundary in the direction of movement.
    """
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        bird_lane = state.birds.random_lanes[i]
        bird_y = state.birds.y[i]
        bird_vy = state.birds.vy[i]  # -1 = up, +1 = down

        for portal in state.enemies.portals:
            portal_lane = portal['lane']

            # Bird must be in the same lane as the portal
            if bird_lane != portal_lane:
                continue

            py = portal['y_pos']
            ph = portal['height']

            # Portal vertical bounds
            portal_top = py
            portal_bottom = py + ph - 1

            # Check if bird is crossing through the portal
            # Bird is "inside" portal vertically if portal_top <= bird_y <= portal_bottom
            if portal_top <= bird_y <= portal_bottom:
                # Find paired portal
                other_portal = _get_portal_pair(portal)
                if other_portal is None:
                    continue

                # Teleport to other portal based on direction
                new_lane = other_portal['lane']
                other_ph = other_portal['height']

                if bird_vy == -1:
                    # Going UP: exit ABOVE the other portal
                    new_y = other_portal['y_pos'] - 1
                    # Home lane stays the same (bird will come back down through this portal)
                else:
                    # Going DOWN: exit BELOW the other portal
                    new_y = other_portal['y_pos'] + other_ph
                    # Update home_lane - bird is now "homed" to the destination lane
                    state.birds.home_lanes[i] = new_lane

                # Update bird position
                state.birds.cols[i] = constants.layout.lane_positions[new_lane]
                state.birds.random_lanes[i] = new_lane
                state.birds.y[i] = new_y
                # vy stays the same - bird continues in same direction!

                break


def _find_closest_lane(x_pos):
    """Find the closest lane to an x position."""
    lane_positions = constants.layout.lane_positions
    min_dist = float('inf')
    closest_lane = 0

    for lane_idx, lane_x in enumerate(lane_positions):
        dist = abs(x_pos - lane_x)
        if dist < min_dist:
            min_dist = dist
            closest_lane = lane_idx

    return closest_lane


def _check_obstacle_portal_destruction():
    """Check if obstacles touch portals and destroy them."""
    for portal in state.enemies.portals:
        px = portal['x_pos']
        py = portal['y_pos']
        pw = portal['width']
        ph = portal['height']

        for obs in state.enemies.obstacles[:]:
            # Calculate obstacle x position from lane (centered on lane)
            obs_lane = obs.get('lane', 0)
            sprite = obs.get('sprite')
            if sprite:
                sprite_width = max(len(line) for line in sprite)
            else:
                sprite_width = obs.get('sprite_width', 5)

            # Obstacle is centered on lane
            lane_x = constants.layout.lane_positions[obs_lane]
            ox = lane_x - sprite_width // 2
            oy = obs['y_pos']
            ow = sprite_width
            oh = len(sprite) if sprite else obs.get('sprite_height', 3)

            # Check overlap
            if (ox < px + pw and ox + ow > px and
                oy < py + ph and oy + oh > py):
                # Destroy obstacle
                state.enemies.obstacles.remove(obs)
                break  # One obstacle per portal per frame


def despawn_old_entities():
    """Remove entities that have been around too long."""
    now = time.time()

    # Bats despawn after configured time (armored bats stay longer)
    bat_despawn = getattr(constants.loot, 'bat_despawn_time', 60)
    armored_cfg = getattr(constants.bat_enemy, 'armored', None)
    armored_despawn = getattr(armored_cfg, 'despawn_time', 150) if armored_cfg else 150

    for bat in state.enemies.bats[:]:
        is_armored = bat.get('armored', False)
        despawn_time = armored_despawn if is_armored else bat_despawn
        if now - bat.get('spawn_ts', now) > despawn_time:
            state.enemies.bats.remove(bat)

    # Loot despawn after configured time
    loot_despawn = getattr(constants.loot, 'loot_despawn_time', 30)
    for loot in state.items.loot_items[:]:
        if now - loot.get('spawn_ts', now) > loot_despawn:
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


def _compute_score_position_multiplier(y_pos):
    """Compute SCORE multiplier based on Y position.

    Returns multiplier for score calculation:
    - x0.5 at starting_line (bottom)
    - x1.0 at breakeven height (configurable, default 0.33)
    - x2.0 at ceiling (top)
    """
    starting_line = constants.layout.starting_line
    ceiling = 1

    # Get breakeven height from config (0.0 = bottom, 1.0 = top)
    breakeven_fraction = getattr(constants.score, 'score_breakeven_height', 0.33)
    breakeven_point = starting_line - (starting_line - ceiling) * breakeven_fraction

    if y_pos >= starting_line:
        return 0.5
    elif y_pos >= breakeven_point:
        t = (starting_line - y_pos) / (starting_line - breakeven_point)
        return 0.5 + t * 0.5
    elif y_pos > ceiling:
        t = (breakeven_point - y_pos) / (breakeven_point - ceiling)
        return 1.0 + t * 1.0
    else:
        return 2.0


def _compute_momentum_factor(y_pos):
    """Compute MOMENTUM factor based on Y position (center of mass).

    Returns factor for momentum change:
    - -1.0 at starting_line (bottom) → momentum decreases
    -  0.0 at zero height (configurable, default 0.33)
    - +2.0 at ceiling (top) → momentum increases fast
    """
    starting_line = constants.layout.starting_line
    ceiling = 1

    # Get zero height from config (0.0 = bottom, 1.0 = top)
    zero_fraction = getattr(constants.speed, 'momentum_zero_height', 0.33)
    zero_point = starting_line - (starting_line - ceiling) * zero_fraction

    if y_pos >= starting_line:
        return -1.0
    elif y_pos >= zero_point:
        # Between starting_line and zero point: -1.0 -> 0.0
        t = (starting_line - y_pos) / (starting_line - zero_point)
        return -1.0 + t * 1.0
    elif y_pos > ceiling:
        # Between zero point and ceiling: 0.0 -> +2.0
        t = (zero_point - y_pos) / (zero_point - ceiling)
        return t * 2.0
    else:
        return 2.0


def _compute_center_of_mass():
    """Calculate center of mass (weighted average Y position of active birds).

    Weight = bird speed. Returns None if no active birds.
    """
    total_weight = 0.0
    weighted_sum = 0.0

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        bird_y = state.birds.y[i]
        # Skip dormant birds
        if bird_y >= constants.layout.height:
            continue

        weight = max(1, state.birds.speeds[i])
        weighted_sum += bird_y * weight
        total_weight += weight

    if total_weight <= 0:
        return None

    return weighted_sum / total_weight


def update_score_tick():
    """Award score and momentum based on active birds (called each frame).

    SCORE = sum of (speed × type × grade) × score_mult × level_mult × prestige
    MOMENTUM = momentum_factor only (from center of mass)
    """
    from src.functions import compute_grade_from_xp

    # Calculate center of mass once
    center_y = _compute_center_of_mass()
    if center_y is None:
        return  # No active birds

    # Score multiplier: 0.5 (bottom) to 2.0 (top)
    score_mult = _compute_score_position_multiplier(center_y)

    # Momentum factor: -1.0 (bottom) to +2.0 (top), 0 at 1/3 height
    momentum_factor = _compute_momentum_factor(center_y)

    # Level multiplier (higher levels = more points)
    level = state.game.level
    level_mult = 1.0 + (level - 1) * 0.1  # Level 1 = 1.0, Level 18 = 2.7

    # Type multipliers (some birds are worth more)
    type_multipliers = {
        GOLD: 10.0,      # Gold birds are score machines
        DINOSAUR: 2.0,   # Dinosaur is strong
        WHITE: 1.5,      # White is fast
        ORANGE: 0.5,     # Orange sacrifices for damage
        STEALTH: 1.2,    # Stealth is sneaky
        GLITCH: 1.0,     # Glitch is random (handled separately)
    }

    # Grade values
    grade_values = {'D': 1.0, 'C1': 1.1, 'C2': 1.2, 'B1': 1.3, 'B2': 1.4, 'A1': 1.5, 'A2': 1.6, 'S': 2.0}

    # Calculate total score from all active birds
    total_base_score = 0.0

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        current_speed = state.birds.speeds[i]
        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # Skip orange birds in dormant state (y=999)
        if bird_y >= constants.layout.height:
            continue

        # Only on move frames (based on bird speed)
        move_interval = max(1, 6 - current_speed)
        if state.game.frame_count % move_interval != 0:
            continue

        # Type multiplier
        type_mult = type_multipliers.get(bird_color, 1.0)

        # Glitch has random multiplier
        if bird_color == GLITCH:
            glitch_min = getattr(constants.combat, 'glitch_dmg_multiplier_min', 1)
            glitch_max = getattr(constants.combat, 'glitch_dmg_multiplier_max', 8)
            type_mult = random.uniform(glitch_min * 0.5, glitch_max * 0.5)

        # Grade multiplier based on bird's XP
        bird_xp = state.birds.per_bird_xp[i]
        grade_label, _ = compute_grade_from_xp(bird_xp)
        grade_mult = grade_values.get(grade_label, 1.0)

        # Gold bird special handling
        if bird_color == GOLD:
            base_score = getattr(constants.loot, 'gold_bird_score_per_tick', 100)
        else:
            base_score = current_speed * type_mult * grade_mult

        # SCORE: base × score_mult × level_mult (prestige applied in add_score)
        final_score = base_score * score_mult * level_mult
        add_score(final_score, by_bird=i)

    # MOMENTUM: depends ONLY on center of mass (momentum_factor: -1 to +2)
    update_momentum(momentum_factor)


def calculate_frame_sleep():
    """Calculate the sleep duration for current frame.

    Note: This is now a legacy function. The main game loop uses
    calculate_frames_per_update() based on state.game.speed instead.
    """
    # Use speed-based calculation (interpolated between speed 1 and speed 10)
    speed = state.game.speed
    min_speed = getattr(constants.speed, 'min_speed', 1)
    max_speed = getattr(constants.speed, 'max_speed', 10)
    sleep_at_1 = getattr(constants.speed, 'frame_sleep_at_speed_1', 0.18)
    sleep_at_10 = getattr(constants.speed, 'frame_sleep_at_speed_10', 0.02)

    t = (speed - min_speed) / (max_speed - min_speed) if max_speed > min_speed else 0
    t = max(0, min(1, t))
    sleep_time = sleep_at_1 - t * (sleep_at_1 - sleep_at_10)

    # Apply timelapse slowdown if active
    if state.powerups.timelapse_active:
        sleep_time *= state.powerups.timelapse_slowdown

    return max(constants.timing.min_sleep, sleep_time)


# =============================================================================
# MAIN UPDATE FUNCTION
# =============================================================================

def update_all():
    """Run all game logic updates in correct order."""
    # Score tick
    update_score_tick()

    # Boss spawn check
    if should_spawn_boss():
        spawn_boss()

    # Collisions
    check_bird_ceiling_bounce()
    check_bird_obstacle_collision()
    check_bird_bat_collision()
    check_bird_mini_bat_collision()
    check_bird_boss_collision()  # Boss collision
    check_projectile_collision()
    check_loot_collection()
    check_bat_obstacle_collision()
    check_bird_floor_collision()

    # Spawning (don't spawn enemies while boss is active)
    if state.enemies.boss is None:
        spawn_obstacle()
        spawn_bat()
    spawn_cloud_bank()  # Mountain Range clouds
    process_spawn_queue()

    # Update cloud banks (Mountain Range foreground)
    update_cloud_banks()

    # Update mini bats (animations, hiding logic)
    update_mini_bats()

    # Update obstacle flowers (swamp biome)
    update_obstacle_flowers()

    # Update boss (movement, scream attacks)
    update_boss()

    # Timer updates
    update_powerup_timers()
    update_special_bird_states()
    update_spell_effects()  # Spellcaster bat effects
    update_purple_charging()
    update_portals()  # Cave biome portals

    # Cleanup
    despawn_old_entities()

    # Sync bird types with audio (dynamic music)
    sync_active_birds_audio()
