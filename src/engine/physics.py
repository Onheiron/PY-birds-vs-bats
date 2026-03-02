#!/usr/bin/env python3
"""
Physics module for BVB game.
Handles movement of all game entities: birds, projectiles, enemies, loot.
"""

import random

from src.core import state
from src.core import constants
from src.entities.sprites import CLOCKWORK, GLITCH


def _set_ball_vy(idx, val):
    """Safely set vertical velocity for bird idx."""
    if 0 <= idx < constants.layout.num_balls:
        if state.special.purple_state[idx] == 2:
            return
        if state.special.purple_just_fired_frames[idx] > 0:
            return
        state.birds.vy[idx] = val


def _reset_bird_power(idx):
    """Reset bird power state."""
    state.birds.power_used[idx] = False
    state.birds.power_uses[idx] = 0


def update_bird_positions():
    """Update vertical positions of all birds based on their speed and velocity."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        # FROZEN BIRDS: speed penalty, always falling (like stun but with button counter)
        freeze_speed_penalty = 0
        if i in state.special.frozen_birds:
            tree_boss_cfg = getattr(constants, 'tree_boss', None)
            flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
            blue_cfg = getattr(flowers_cfg, 'blue', None) if flowers_cfg else None
            freeze_speed_penalty = getattr(blue_cfg, 'speed_penalty', 3) if blue_cfg else 3
            state.birds.vy[i] = 1  # Always falling while frozen

        # STUNNED BIRDS (from flower): speed penalty, always falling
        stun_speed_penalty = 0
        if i in state.special.stunned_birds:
            stun_info = state.special.stunned_birds[i]
            # Only apply speed penalty for flower stuns (dict with 'type': 'flower')
            if isinstance(stun_info, dict) and stun_info.get('type') == 'flower':
                tree_boss_cfg = getattr(constants, 'tree_boss', None)
                flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
                yellow_cfg = getattr(flowers_cfg, 'yellow', None) if flowers_cfg else None
                stun_speed_penalty = getattr(yellow_cfg, 'speed_penalty', 3) if yellow_cfg else 3
                state.birds.vy[i] = 1  # Always falling while stunned

        # POISONED BIRDS: speed penalty
        poison_speed_penalty = 0
        if i in state.special.poisoned_birds:
            tree_boss_cfg = getattr(constants, 'tree_boss', None)
            flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
            green_cfg = getattr(flowers_cfg, 'green', None) if flowers_cfg else None
            poison_speed_penalty = getattr(green_cfg, 'speed_penalty', 1) if green_cfg else 1

        # BLEEDING BIRDS: speed penalty from config
        bleed_speed_penalty = 0
        if i in state.special.bleeding_birds:
            tree_boss_cfg = getattr(constants, 'tree_boss', None)
            flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
            red_cfg = getattr(flowers_cfg, 'red', None) if flowers_cfg else None
            bleed_speed_penalty = getattr(red_cfg, 'speed_penalty', 1) if red_cfg else 1

        # Skip charging or just-fired purple birds
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        # GLITCH random speed each frame
        if state.birds.colors[i] == GLITCH:
            state.birds.speeds[i] = random.randint(
                constants.glitch.speed.min,
                constants.glitch.speed.max
            )

        current_speed = state.birds.speeds[i]

        # Apply speed boosts
        if i in state.special.speed_boosts:
            if state.special.speed_boosts[i] > 0 and state.birds.vy[i] == -1:
                current_speed += 1
            elif state.special.speed_boosts[i] < 0 and state.birds.vy[i] == 1:
                current_speed = max(1, current_speed - 1)

        # Apply scared speed boost when falling
        if i in state.special.scared_birds and state.birds.vy[i] == 1:
            current_speed += 1

        # Apply dive fall boost when falling (from diver bats)
        if i in state.special.dive_fall_boosts and state.birds.vy[i] == 1:
            boost_info = state.special.dive_fall_boosts[i]
            current_speed += boost_info.get('speed', 1)

        # Get bird lane for wind effects
        bird_lane = state.birds.random_lanes[i]

        # Apply tailwind
        if state.powerups.tailwind_active:
            up_bonus = state.powerups.tailwind_up_bonus
            down_pen = state.powerups.tailwind_down_penalty
            if state.birds.vy[i] == -1 and up_bonus > 0:
                current_speed = min(6, current_speed + up_bonus)
            elif state.birds.vy[i] == 1 and down_pen > 0:
                current_speed = max(1, current_speed - down_pen)

        # Apply TWISTER local tailwind (affects only birds in specific lanes)
        import time as time_module
        now = time_module.time()
        for twister_idx, tw_info in list(state.special.twister_tailwind.items()):
            if now >= tw_info['end_time']:
                # Expired, clean up
                del state.special.twister_tailwind[twister_idx]
                continue
            # Check if this bird is in one of the affected lanes
            if bird_lane in tw_info['lanes']:
                tw_up_bonus = getattr(constants.twister, 'tailwind_up_bonus', 2)
                tw_down_pen = getattr(constants.twister, 'tailwind_down_penalty', 1)
                if state.birds.vy[i] == -1 and tw_up_bonus > 0:
                    current_speed = min(6, current_speed + tw_up_bonus)
                elif state.birds.vy[i] == 1 and tw_down_pen > 0:
                    current_speed = max(1, current_speed - tw_down_pen)
                break  # Only one twister tailwind applies at a time

        # Apply Wind Boss effect
        wind_up = state.powerups.wind_boss_up_bonus
        wind_down = state.powerups.wind_boss_down_penalty
        if wind_up != 0 or wind_down != 0:
            if state.birds.vy[i] == -1:  # Going up
                if wind_up > 0:  # Tailwind: boost up
                    current_speed = min(6, current_speed + wind_up)
                elif wind_up < 0:  # Headwind: nerf up
                    current_speed = max(1, current_speed + wind_up)  # wind_up is negative
            elif state.birds.vy[i] == 1:  # Going down
                if wind_down < 0:  # Headwind: boost down (wind_down is negative, so abs)
                    current_speed = min(6, current_speed + abs(wind_down))
                elif wind_down > 0:  # Tailwind: nerf down
                    current_speed = max(1, current_speed - wind_down)

        # Apply repugnant wind (reverse tailwind from spellcaster bats)
        if bird_lane in state.spells.repugnant_wind_lanes:
            wind_info = state.spells.repugnant_wind_lanes[bird_lane]
            speed_boost = wind_info.get('speed_boost', 1)
            speed_nerf = wind_info.get('speed_nerf', 1)
            # Reverse of tailwind: boost fall, nerf rise
            if state.birds.vy[i] == 1 and speed_boost > 0:
                current_speed = min(6, current_speed + speed_boost)
            elif state.birds.vy[i] == -1 and speed_nerf > 0:
                current_speed = max(1, current_speed - speed_nerf)

        # Apply stun speed penalty
        if stun_speed_penalty > 0:
            current_speed = max(1, current_speed - stun_speed_penalty)

        # Apply poison speed penalty
        if poison_speed_penalty > 0:
            current_speed = max(1, current_speed - poison_speed_penalty)

        # Apply bleed speed penalty
        if bleed_speed_penalty > 0:
            current_speed = max(1, current_speed - bleed_speed_penalty)

        # Apply freeze speed penalty
        if freeze_speed_penalty > 0:
            current_speed = max(1, current_speed - freeze_speed_penalty)

        # CLOCKWORK discharged: falls fast when charge is 0
        if state.birds.colors[i] == CLOCKWORK and state.birds.vy[i] == 1:
            charge = state.special.clockwork_charge.get(i)
            if charge is not None and charge == 0:
                current_speed = 6  # Max speed fall

        # Calculate move interval (higher speed = more frequent movement)
        move_interval = max(1, 6 - current_speed)

        # Move bird
        if state.game.frame_count % move_interval == 0:
            # CLOCKWORK auto-bounce at starting line
            if (state.birds.colors[i] == CLOCKWORK and
                state.birds.vy[i] == 1 and
                state.birds.y[i] + state.birds.vy[i] >= constants.layout.starting_line):
                charge = state.special.clockwork_charge.get(i)
                if charge is None:
                    charge = constants.clockwork.initial_charge
                    state.special.clockwork_charge[i] = charge
                if charge > 0:
                    state.birds.y[i] = constants.layout.starting_line
                    _set_ball_vy(i, -1)
                    _reset_bird_power(i)
                    continue

            state.birds.y[i] += state.birds.vy[i]


def update_projectile_positions():
    """Update positions of all projectiles."""
    for proj in state.special.red_projectiles[:]:
        move_steps = max(1, proj.get('speed', 1))

        for _ in range(move_steps):
            proj['y_pos'] -= 1

            if proj['y_pos'] < 0:
                if proj in state.special.red_projectiles:
                    state.special.red_projectiles.remove(proj)
                break


def update_cave_shimmer():
    """Update cave shimmer effect - all background chars flicker randomly.

    Only active in biome 5 (The Void Cave).
    Uses a simple phase counter that the renderer uses to compute brightness.
    """
    if state.game.level_group != 5:
        if state.ui.cave_shimmer:
            state.ui.cave_shimmer = {}
        return

    # Store current phase for renderer to use
    # Phase increments every 3 frames for smooth animation
    if 'phase' not in state.ui.cave_shimmer:
        state.ui.cave_shimmer['phase'] = 0

    if state.game.frame_count % 5 == 0:
        state.ui.cave_shimmer['phase'] = (state.ui.cave_shimmer['phase'] + 1) % 1000


def update_obstacle_positions():
    """Update positions of all obstacles."""
    # Update cave shimmer effect (biome 5)
    update_cave_shimmer()

    # Parallax background layers - different scroll speeds
    # Layer 1 (bg_offset): Slowest - every 15 frames (3x slower than obstacles)
    # Layer 2 (bg_mid_offset): Medium - every 8 frames (~1.6x slower than obstacles)
    # Layer 3 (obstacles): Fastest - every 5 frames (current speed)
    if state.game.frame_count % 15 == 0:
        state.ui.bg_offset += 1
    if state.game.frame_count % 8 == 0:
        state.ui.bg_mid_offset += 1

    for obs in state.enemies.obstacles[:]:
        # Stationary obstacles (from Owl Boss overgrowth) don't move
        if obs.get('stationary'):
            # Remove stationary obstacles if owl boss is dead
            boss = state.enemies.boss
            if boss is None or boss.get('boss_type') != 'owl' or boss.get('state') in ('dying', 'dead'):
                state.enemies.obstacles.remove(obs)
            continue

        # Obstacles move at speed 1 (every 5 frames)
        if state.game.frame_count % 5 == 0:
            obs['y_pos'] += 1

        # Remove if reached floor or starting line
        if obs['y_pos'] >= constants.layout.starting_line - 1:
            state.enemies.obstacles.remove(obs)
        elif obs['y_pos'] >= constants.layout.height:
            state.enemies.obstacles.remove(obs)


def update_right_panel_barriers():
    """Update decorative barriers in right panel (spawn and move)."""
    # Panel inner width is SIDE_PANEL_WIDTH - 2 = 18 chars
    # Sprite widths: tier 1 = 5 chars, tier 2 = 7 chars
    PANEL_INNER_WIDTH = 18

    # Spawn new barriers periodically
    state.enemies.right_panel_barrier_timer -= 1
    if state.enemies.right_panel_barrier_timer <= 0:
        # Reset timer (random interval)
        state.enemies.right_panel_barrier_timer = random.randint(30, 80)

        # Spawn a new decorative barrier
        tier = random.choice([1, 2])  # Only small barriers for right panel
        sprite_height = 3 if tier == 1 else 5
        sprite_width = 5 if tier == 1 else 7

        # Random x position that keeps sprite within panel bounds
        max_x_offset = max(0, PANEL_INNER_WIDTH - sprite_width)
        x_offset = random.randint(0, max_x_offset)

        state.enemies.right_panel_barriers.append({
            'y_pos': -sprite_height,
            'tier': tier,
            'x_offset': x_offset
        })

    # Move barriers down
    if state.game.frame_count % 5 == 0:
        for barrier in state.enemies.right_panel_barriers[:]:
            barrier['y_pos'] += 1
            # Remove if past screen
            if barrier['y_pos'] >= constants.layout.height:
                state.enemies.right_panel_barriers.remove(barrier)


def update_bat_positions():
    """Update positions of all bats (horizontal wave + vertical descent)."""
    import time as time_module

    for bat in state.enemies.bats[:]:
        is_armored = bat.get('armored', False)
        is_diver = bat.get('diver', False)
        is_spellcaster = bat.get('spellcaster', False)

        # Handle diver bat behavior
        if is_diver:
            _update_diver_bat(bat)
            continue  # Diver bats have their own movement logic

        # Handle spellcaster bat behavior (still moves normally but can cast)
        if is_spellcaster:
            _update_spellcaster_bat(bat)
            # Continue with normal movement below

        # Get movement modifiers for armored bats
        horiz_interval = 3  # Normal: move every 3 frames
        move_distance = 2   # Normal: 2 pixels per move
        if is_armored:
            armored_cfg = getattr(constants.bat_enemy, 'armored', None)
            if armored_cfg:
                speed_mult = getattr(armored_cfg, 'movement_speed_mult', 0.6)
                range_mult = getattr(armored_cfg, 'movement_range_mult', 0.7)
                # Slower = higher interval (move less often)
                horiz_interval = max(3, int(3 / speed_mult))
                # Less distance per move
                move_distance = max(1, int(2 * range_mult))

        # Horizontal movement
        if state.game.frame_count % horiz_interval == 0:
            next_x = bat['x_pos'] + bat['direction'] * move_distance
            can_move = _check_bat_can_move(bat, next_x)

            if can_move:
                bat['x_pos'] = next_x
                # Bounce off walls
                if bat['x_pos'] <= 0:
                    bat['x_pos'] = 0
                    bat['direction'] = 1
                elif bat['x_pos'] >= constants.layout.width - 8:
                    bat['x_pos'] = constants.layout.width - 8
                    bat['direction'] = -1
            else:
                bat['direction'] *= -1

        # Vertical descent (same speed as obstacles, armored slightly slower)
        vert_interval = 6 if is_armored else 5
        if state.game.frame_count % vert_interval == 0:
            if bat['y_pos'] < bat['target_y']:
                bat['y_pos'] += 1


def _update_diver_bat(bat):
    """Update diver bat behavior: flying, diving, stunned, returning."""
    import time as time_module

    diver_cfg = getattr(constants.bat_enemy, 'diver', None)
    if diver_cfg is None:
        return

    diver_state = bat.get('diver_state', 'flying')

    # Normal horizontal movement (same as regular bats)
    horiz_interval = 3
    move_distance = 2

    if state.game.frame_count % horiz_interval == 0:
        next_x = bat['x_pos'] + bat['direction'] * move_distance
        can_move = _check_bat_can_move(bat, next_x)

        if can_move:
            bat['x_pos'] = next_x
            if bat['x_pos'] <= 0:
                bat['x_pos'] = 0
                bat['direction'] = 1
            elif bat['x_pos'] >= constants.layout.width - 8:
                bat['x_pos'] = constants.layout.width - 8
                bat['direction'] = -1
        else:
            bat['direction'] *= -1

    # State-specific vertical movement
    if diver_state == 'flying':
        # Descend to target Y if not there yet
        if state.game.frame_count % 5 == 0:
            if bat['y_pos'] < bat['target_y']:
                bat['y_pos'] += 1

        # Check if should start diving
        dive_prob_per_sec = getattr(diver_cfg, 'dive_probability_per_second', 0.20)
        base_sleep = getattr(constants.timing, 'base_sleep', 0.033)
        dive_prob_per_frame = dive_prob_per_sec * base_sleep

        if bat['y_pos'] >= bat['target_y'] and random.random() < dive_prob_per_frame:
            bat['diver_state'] = 'diving'
            bat['dive_start_y'] = bat['y_pos']

    elif diver_state == 'diving':
        # Fast descent (faster than obstacles)
        dive_speed = getattr(diver_cfg, 'dive_speed', 2)
        dive_distance = getattr(diver_cfg, 'dive_distance', 10)

        if state.game.frame_count % dive_speed == 0:
            bat['y_pos'] += 1

        # Check if dive is complete
        dive_start = bat.get('dive_start_y', bat.get('diver_home_y', 5))
        if bat['y_pos'] >= dive_start + dive_distance or bat['y_pos'] >= constants.layout.starting_line - 3:
            # End dive, become stunned
            bat['diver_state'] = 'stunned'
            stun_duration = getattr(diver_cfg, 'stun_duration', 1.5)
            bat['stun_end_time'] = time_module.time() + stun_duration

    elif diver_state == 'stunned':
        # Wait for stun to end
        stun_end = bat.get('stun_end_time', 0)
        if time_module.time() >= stun_end:
            bat['diver_state'] = 'returning'

    elif diver_state == 'returning':
        # Slow rise back to home position
        return_speed = getattr(diver_cfg, 'return_speed', 6)

        if state.game.frame_count % return_speed == 0:
            home_y = bat.get('diver_home_y', bat['target_y'])
            if bat['y_pos'] > home_y:
                bat['y_pos'] -= 1
            else:
                # Back home, can fly again
                bat['diver_state'] = 'flying'
                bat['dive_start_y'] = None


def _update_spellcaster_bat(bat):
    """Update spellcaster bat behavior: casting spells."""
    import time as time_module

    spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
    if spellcaster_cfg is None:
        return

    spell_state = bat.get('spell_state', 'idle')
    now = time_module.time()

    # Check if currently casting
    if spell_state == 'casting':
        casting_end = bat.get('casting_end_time', 0)
        if now >= casting_end:
            # Casting finished, apply the spell effect
            _apply_spell_effect(bat)
            bat['spell_state'] = 'idle'
            # Set cooldown
            cooldown = getattr(spellcaster_cfg, 'cast_cooldown', 3.0)
            bat['spell_cooldown'] = now + cooldown
        return

    # Check if on cooldown
    if now < bat.get('spell_cooldown', 0):
        return

    # Check if should start casting (bat must be on screen and at target Y)
    if bat['y_pos'] < 0 or bat['y_pos'] < bat['target_y']:
        return

    # Get cast probability based on level
    level = state.game.level
    cast_prob_cfg = getattr(spellcaster_cfg, 'cast_probability_by_level', None)
    if cast_prob_cfg:
        if level <= 3:
            cast_prob_per_sec = getattr(cast_prob_cfg, 'level_1_3', 0.0)
        elif level <= 6:
            cast_prob_per_sec = getattr(cast_prob_cfg, 'level_4_6', 0.10)
        elif level <= 9:
            cast_prob_per_sec = getattr(cast_prob_cfg, 'level_7_9', 0.15)
        elif level <= 12:
            cast_prob_per_sec = getattr(cast_prob_cfg, 'level_10_12', 0.20)
        elif level <= 15:
            cast_prob_per_sec = getattr(cast_prob_cfg, 'level_13_15', 0.25)
        else:
            cast_prob_per_sec = getattr(cast_prob_cfg, 'level_16_18', 0.30)
    else:
        cast_prob_per_sec = 0.15

    # Convert to per-frame probability
    base_sleep = getattr(constants.timing, 'base_sleep', 0.033)
    cast_prob_per_frame = cast_prob_per_sec * base_sleep

    if random.random() < cast_prob_per_frame:
        # Start casting
        bat['spell_state'] = 'casting'
        casting_duration = getattr(spellcaster_cfg, 'casting_duration', 0.5)
        bat['casting_end_time'] = now + casting_duration
        # Choose a random spell from known spells
        known_spells = bat.get('known_spells', ['silence'])
        bat['current_spell'] = random.choice(known_spells)


def _apply_spell_effect(bat):
    """Apply the effect of the spell the bat just cast."""
    import time as time_module

    spell = bat.get('current_spell', 'silence')
    tier = bat.get('tier', 2)
    spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
    if spellcaster_cfg is None:
        return

    # Get lanes affected by this spell (based on bat position)
    affected_lanes = _get_bat_affected_lanes(bat)
    now = time_module.time()

    if spell == 'silence':
        # Disable powers in affected lanes
        silence_cfg = getattr(spellcaster_cfg, 'silence', None)
        duration_by_tier = getattr(silence_cfg, 'duration_by_tier', None) if silence_cfg else None
        if duration_by_tier:
            if isinstance(duration_by_tier, dict):
                duration = duration_by_tier.get(tier, duration_by_tier.get(str(tier), 3.0))
            else:
                duration = getattr(duration_by_tier, str(tier), 3.0)
        else:
            duration = 3.0

        for lane in affected_lanes:
            state.spells.silenced_lanes[lane] = {
                'end_time': now + duration,
                'caster_tier': tier
            }

    elif spell == 'repugnant_wind':
        # Reverse tailwind in affected lanes
        wind_cfg = getattr(spellcaster_cfg, 'repugnant_wind', None)
        duration_by_tier = getattr(wind_cfg, 'duration_by_tier', None) if wind_cfg else None
        if duration_by_tier:
            if isinstance(duration_by_tier, dict):
                duration = duration_by_tier.get(tier, duration_by_tier.get(str(tier), 3.0))
            else:
                duration = getattr(duration_by_tier, str(tier), 3.0)
        else:
            duration = 3.0

        speed_boost = getattr(wind_cfg, 'speed_boost', 1) if wind_cfg else 1
        speed_nerf = getattr(wind_cfg, 'speed_nerf', 1) if wind_cfg else 1

        for lane in affected_lanes:
            state.spells.repugnant_wind_lanes[lane] = {
                'end_time': now + duration,
                'speed_boost': speed_boost,
                'speed_nerf': speed_nerf
            }

    elif spell == 'exile':
        # Swap birds: highest damage potential in affected lanes <-> lowest outside
        _cast_exile_spell(affected_lanes)


def _get_bat_affected_lanes(bat):
    """Get the lanes affected by a bat's spell (based on bat position)."""
    bat_left = bat['x_pos']
    bat_right = bat['x_pos'] + 8  # Bat sprite width

    affected_lanes = []
    for lane_idx in range(constants.layout.num_lanes):
        lane_x = constants.layout.lane_positions[lane_idx]
        # Check if lane overlaps with bat
        lane_left = lane_x - 2
        lane_right = lane_x + 2
        if not (bat_right < lane_left or bat_left > lane_right):
            affected_lanes.append(lane_idx)

    return affected_lanes


def _calculate_bird_damage_potential(bird_idx):
    """Calculate a bird's damage potential for exile spell targeting."""
    if state.birds.lost[bird_idx]:
        return -1  # Lost birds have no potential

    # Simple formula: speed * (1 if moving up else 0.5) + tier bonus
    from src.entities.sprites import ORANGE, DINOSAUR, PURPLE

    color = state.birds.colors[bird_idx]
    speed = state.birds.speeds[bird_idx]
    vy = state.birds.vy[bird_idx]

    # Base potential from speed and direction
    direction_mult = 1.5 if vy == -1 else 0.5
    potential = speed * direction_mult

    # Color bonuses for high-damage birds
    if color == ORANGE:
        potential += 10  # One-hit kill bird
    elif color == DINOSAUR:
        potential += 5  # Multi-hit bird
    elif color == PURPLE:
        potential += 3  # Charging bird

    return potential


def _cast_exile_spell(affected_lanes):
    """Cast exile spell: swap highest damage bird in lanes with lowest outside."""
    import time as time_module

    # Find bird with highest damage potential in affected lanes
    best_bird_idx = None
    best_potential = -1

    for bird_idx in range(constants.layout.num_balls):
        if state.birds.lost[bird_idx]:
            continue
        bird_lane = state.birds.random_lanes[bird_idx]
        if bird_lane in affected_lanes:
            potential = _calculate_bird_damage_potential(bird_idx)
            if potential > best_potential:
                best_potential = potential
                best_bird_idx = bird_idx

    if best_bird_idx is None:
        return  # No bird to exile

    # Find bird with lowest damage potential outside affected lanes (or empty lane)
    worst_bird_idx = None
    worst_potential = float('inf')
    empty_lane = None

    for bird_idx in range(constants.layout.num_balls):
        if state.birds.lost[bird_idx]:
            continue
        bird_lane = state.birds.random_lanes[bird_idx]
        if bird_lane not in affected_lanes:
            potential = _calculate_bird_damage_potential(bird_idx)
            if potential < worst_potential:
                worst_potential = potential
                worst_bird_idx = bird_idx

    # Also check for empty lanes outside affected lanes
    occupied_lanes = set()
    for bird_idx in range(constants.layout.num_balls):
        if not state.birds.lost[bird_idx]:
            occupied_lanes.add(state.birds.random_lanes[bird_idx])

    for lane_idx in range(constants.layout.num_lanes):
        if lane_idx not in affected_lanes and lane_idx not in occupied_lanes:
            empty_lane = lane_idx
            break  # Empty lane counts as lowest potential

    # Schedule the swap
    spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
    exile_cfg = getattr(spellcaster_cfg, 'exile', None) if spellcaster_cfg else None
    swap_delay = getattr(exile_cfg, 'swap_delay', 0.3) if exile_cfg else 0.3

    now = time_module.time()
    state.spells.pending_exiles.append({
        'swap_time': now + swap_delay,
        'bird_a_idx': best_bird_idx,
        'bird_b_idx': worst_bird_idx,  # Can be None if swapping to empty lane
        'empty_lane': empty_lane if worst_bird_idx is None or (empty_lane is not None and worst_potential > 0) else None
    })


def _check_bat_can_move(bat, next_x):
    """Check if bat can move to next_x position."""
    # Check collision with other bats
    for other_bat in state.enemies.bats:
        if other_bat is bat:
            continue
        other_left = other_bat['x_pos']
        other_right = other_bat['x_pos'] + 8
        next_left = next_x
        next_right = next_x + 8

        if not (next_right < other_left or next_left > other_right):
            return False

    # Check collision with birds
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue

        bird_lane_x = constants.layout.lane_positions[state.birds.random_lanes[i]]
        bird_y = state.birds.y[i]

        # Bat horizontal range
        bat_left = next_x
        bat_right = next_x + 8

        # Lane range
        lane_left = bird_lane_x - 2
        lane_right = bird_lane_x + 2

        horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)

        if horizontal_overlap and abs(bird_y - bat['y_pos']) < 8:
            return False

    return True


def update_loot_positions():
    """Update positions of loot items (they don't move, but could in future)."""
    # Currently loot items are stationary until collected or despawned
    pass


def update_mini_bat_positions():
    """Update positions of mini bats (horizontal movement only)."""
    for mb in state.enemies.mini_bats[:]:
        # Only move active mini bats
        if mb['state'] != 'active':
            continue

        # Horizontal movement every 4 frames (slightly slower than regular bats)
        if state.game.frame_count % 4 == 0:
            mb['x_pos'] += mb['direction'] * 2

            # Bounce off walls
            if mb['x_pos'] <= 2:
                mb['x_pos'] = 2
                mb['direction'] = 1
            elif mb['x_pos'] >= constants.layout.width - 12:
                mb['x_pos'] = constants.layout.width - 12
                mb['direction'] = -1


def update_glitch_chaos():
    """Apply GLITCH chaos behaviors: random direction flip, lane swap, cursor nudge, duplicate."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.colors[i] != GLITCH:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        # 1% chance to flip direction
        if random.random() < constants.glitch.flip_chance:
            state.birds.vy[i] = -state.birds.vy[i]

        # 1% chance to swap lanes with another bird
        if random.random() < constants.glitch.swap_chance:
            others = [j for j in range(constants.layout.num_balls) if j != i and not state.birds.lost[j]]
            if others:
                j = random.choice(others)
                state.birds.random_lanes[i], state.birds.random_lanes[j] = \
                    state.birds.random_lanes[j], state.birds.random_lanes[i]
                state.birds.cols[i] = constants.layout.lane_positions[state.birds.random_lanes[i]]
                state.birds.cols[j] = constants.layout.lane_positions[state.birds.random_lanes[j]]

        # 1% chance to nudge player cursor
        if random.random() < constants.glitch.nudge_chance:
            delta = random.choice([-1, 1])
            state.player.lane = max(0, min(constants.layout.num_lanes - 1, state.player.lane + delta))

        # 1% chance to duplicate into another lane
        if random.random() < constants.glitch.duplicate_chance:
            _glitch_duplicate(i)


def _glitch_duplicate(source_idx):
    """GLITCH duplicates into a random lane."""
    target_lane = random.randint(0, constants.layout.num_lanes - 1)
    target_idx = None

    for idx in range(constants.layout.num_balls):
        if state.birds.random_lanes[idx] == target_lane:
            target_idx = idx
            break

    if target_idx is None:
        return

    from src.entities.sprites import GLITCH as GLITCH_COLOR

    if state.birds.lost[target_idx]:
        # Resurrect as GLITCH
        state.birds.lost[target_idx] = False
        state.birds.colors[target_idx] = GLITCH_COLOR
        state.birds.speeds[target_idx] = random.randint(constants.glitch.speed.min, constants.glitch.speed.max)
        state.birds.y[target_idx] = constants.layout.starting_line
        state.birds.vy[target_idx] = -1
        state.birds.per_bird_xp[target_idx] = 0
        state.birds.transformed[target_idx] = False
        state.birds.cols[target_idx] = constants.layout.lane_positions[target_lane]
    else:
        # Replace existing bird
        state.birds.colors[target_idx] = GLITCH_COLOR
        state.birds.speeds[target_idx] = random.randint(constants.glitch.speed.min, constants.glitch.speed.max)
        state.birds.per_bird_xp[target_idx] = 0
        state.birds.y[target_idx] = constants.layout.starting_line
        state.birds.vy[target_idx] = -1
        state.birds.transformed[target_idx] = False
        state.birds.cols[target_idx] = constants.layout.lane_positions[target_lane]


def update_all():
    """Update all physics in the correct order."""
    update_glitch_chaos()
    update_bird_positions()
    update_projectile_positions()
    update_obstacle_positions()
    update_bat_positions()
    update_mini_bat_positions()
    update_loot_positions()
    update_right_panel_barriers()
