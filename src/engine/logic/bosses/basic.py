"""Default end-of-biome boss (scream attack)."""

import random

from src.core import constants, state
from src.engine import clock
from src.engine.birds import scare_bird_ticks, set_ball_vy
from src.engine.logic.bosses.common import convert_boss_to_obstacle, get_boss_config
from src.services.sound import play_sfx


def _boss_start_scream(boss):
    """Start boss scream attack."""
    boss['state'] = 'screaming'
    boss['scream_timer'] = 15  # Scream duration in frames

    # Play scream SFX
    play_sfx('boss_scream')

    # Apply scare effect to all birds below the boss
    boss_cfg = get_boss_config()
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
                set_ball_vy(i, 1)

            # Apply scare effect (like tier 1 bat)
            scare_bird_ticks(i, scare_frames)


def spawn_basic_boss():
    """Spawn the default boss: it descends, oscillates and screams."""
    boss_cfg = get_boss_config()
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
        'spawn_ts': clock.now(),
        'boss_type': 'normal',  # Mark as normal boss
    }
    state.enemies.boss_spawned = True
    # Clear other enemies when boss appears for dramatic effect
    state.enemies.bats = []
    state.enemies.mini_bats = []


def update_basic_boss():
    """Update the default boss (movement, animation, scream attacks, death)."""
    boss = state.enemies.boss
    boss_cfg = get_boss_config()
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
        convert_boss_to_obstacle(boss)
        state.enemies.boss = None
        state.enemies.boss_defeated = True
