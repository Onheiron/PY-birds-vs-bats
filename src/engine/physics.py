"""Movement of birds, projectiles, obstacles, loot and scenery."""

from src.core import constants
from src.core import state
from src.engine.birds import reset_bird_power
from src.engine.birds import set_ball_vy
from src.entities.sprites import CLOCKWORK
from src.entities.sprites import GLITCH
import random
from src.engine.bat_ai import update_bat_positions
from src.engine.glitch import update_glitch_chaos


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
                    set_ball_vy(i, -1)
                    reset_bird_power(i)
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
