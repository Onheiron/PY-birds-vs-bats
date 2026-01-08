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

        # Apply tailwind
        if state.powerups.tailwind_active:
            up_bonus = state.powerups.tailwind_up_bonus
            down_pen = state.powerups.tailwind_down_penalty
            if state.birds.vy[i] == -1 and up_bonus > 0:
                current_speed = min(6, current_speed + up_bonus)
            elif state.birds.vy[i] == 1 and down_pen > 0:
                current_speed = max(1, current_speed - down_pen)

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


def update_obstacle_positions():
    """Update positions of all obstacles."""
    # Parallax background layers - different scroll speeds
    # Layer 1 (bg_offset): Slowest - every 15 frames (3x slower than obstacles)
    # Layer 2 (bg_mid_offset): Medium - every 8 frames (~1.6x slower than obstacles)
    # Layer 3 (obstacles): Fastest - every 5 frames (current speed)
    if state.game.frame_count % 15 == 0:
        state.ui.bg_offset += 1
    if state.game.frame_count % 8 == 0:
        state.ui.bg_mid_offset += 1

    for obs in state.enemies.obstacles[:]:
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
    for bat in state.enemies.bats[:]:
        # Horizontal movement every 3 frames
        if state.game.frame_count % 3 == 0:
            next_x = bat['x_pos'] + bat['direction'] * 2
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

        # Vertical descent (same speed as obstacles)
        if state.game.frame_count % 5 == 0:
            if bat['y_pos'] < bat['target_y']:
                bat['y_pos'] += 1


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
    update_loot_positions()
    update_right_panel_barriers()
