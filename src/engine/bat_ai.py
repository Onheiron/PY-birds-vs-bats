"""Bat movement and behaviours: divers, spellcasters and their spells."""

import random
import time as time

from src.core import constants, state
from src.engine import bird_kinds, clock, enemy_stats
from src.engine.logic import afflictions
from src.entities.sprites import DINOSAUR, ORANGE, PURPLE


def update_bat_positions():
    """Update positions of all bats (horizontal wave + vertical descent)."""

    for bat in state.enemies.bats[:]:
        is_armored = bat.get('armored', False)
        is_diver = bat.get('diver', False)
        is_spellcaster = bat.get('spellcaster', False)

        # Frozen bats move at a fraction of their speed
        slow = afflictions.slow_factor(bat)
        if slow < 1 and state.game.frame_count % max(1, round(1 / slow)) != 0:
            continue

        # Handle diver bat behavior
        if is_diver:
            _update_diver_bat(bat)
            continue  # Diver bats have their own movement logic

        # Handle spellcaster bat behavior (still moves normally but can cast)
        if is_spellcaster:
            _update_spellcaster_bat(bat)
            # Continue with normal movement below

        # Get movement modifiers for armored bats
        # Normal: 2 columns every 3 ticks; the speed stat changes how often it moves
        speed = enemy_stats.get(bat, 'speed')
        horiz_interval = 3 if speed == 1 else max(1, int(3 / speed + 1e-9))
        move_distance = 2
        if is_armored:
            armored_cfg = getattr(constants.bat_enemy, 'armored', None)
            if armored_cfg:
                # Less distance per move
                move_distance = max(1, int(2 * getattr(armored_cfg, 'movement_range_mult', 0.7)))

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

        # Vertical descent (same speed as obstacles; armored bats are slower)
        vert_interval = max(1, int(enemy_stats.get(bat, 'descent_interval')))
        if state.game.frame_count % vert_interval == 0:
            if bat['y_pos'] < bat['target_y']:
                bat['y_pos'] += 1


def _update_diver_bat(bat):
    """Update diver bat behavior: flying, diving, stunned, returning."""

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
            bat['stun_end_time'] = clock.now() + stun_duration

    elif diver_state == 'stunned':
        # Wait for stun to end
        stun_end = bat.get('stun_end_time', 0)
        if clock.now() >= stun_end:
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

    spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
    if spellcaster_cfg is None:
        return

    spell_state = bat.get('spell_state', 'idle')
    now = clock.now()

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

    spell = bat.get('current_spell', 'silence')
    tier = bat.get('tier', 2)
    spellcaster_cfg = getattr(constants.bat_enemy, 'spellcaster', None)
    if spellcaster_cfg is None:
        return

    # Get lanes affected by this spell (based on bat position)
    affected_lanes = _get_bat_affected_lanes(bat)
    now = clock.now()

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
            state.spells.silenced_lanes[lane] = {'end_time': now + duration, 'caster_tier': tier}

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
                'speed_nerf': speed_nerf,
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

    now = clock.now()
    state.spells.pending_exiles.append(
        {
            'swap_time': now + swap_delay,
            'bird_a_idx': best_bird_idx,
            'bird_b_idx': worst_bird_idx,  # Can be None if swapping to empty lane
            'empty_lane': empty_lane
            if worst_bird_idx is None or (empty_lane is not None and worst_potential > 0)
            else None,
        }
    )


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

        bird_y = state.birds.y[i]

        # Bat horizontal range
        bat_left = next_x
        bat_right = next_x + 8

        # Lane range
        lane_left, lane_right = bird_kinds.hit_span(i)

        horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)

        if horizontal_overlap and abs(bird_y - bat['y_pos']) < 8:
            return False

    return True
