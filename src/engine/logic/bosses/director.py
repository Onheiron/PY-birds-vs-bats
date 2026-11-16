"""Boss lifecycle: spawn conditions, dispatch and collisions."""

from src.core import constants
from src.core import state
from src.functions import add_score
from src.functions import award_xp
import random
import time
from src.entities.sprites import BLUE, DINOSAUR, ORANGE, STEALTH
from src.engine.logic.bosses.basic import _boss_start_scream
from src.engine.logic.bosses.common import _convert_boss_to_obstacle, _get_boss_config
from src.engine.logic.bosses.jelly import spawn_jelly_boss, update_jelly_boss
from src.engine.logic.bosses.owl import spawn_owl_boss, update_owl_boss
from src.engine.logic.bosses.tree import _check_bird_tree_branch_collision, spawn_tree_boss, update_tree_boss
from src.engine.logic.bosses.wind import spawn_wind_boss, update_wind_boss
from src.engine.logic.damage import _calculate_bird_damage
from src.engine.logic.helpers import _reset_bird_power, _set_ball_vy
from src.engine.logic.sfx import play_sfx


def should_spawn_boss():
    """Check if boss should spawn (end of biome level, near transition)."""
    # Already spawned or defeated this level?
    if state.enemies.boss_spawned or state.enemies.boss is not None:
        return False

    # Check special boss levels first (wind, jelly, tree, owl)
    wind_boss_cfg = getattr(constants, 'wind_boss', None)
    wind_boss_level = getattr(wind_boss_cfg, 'level', 6) if wind_boss_cfg else 6

    jelly_boss_cfg = getattr(constants, 'jelly_boss', None)
    jelly_boss_level = getattr(jelly_boss_cfg, 'level', 9) if jelly_boss_cfg else 9

    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    tree_boss_level = getattr(tree_boss_cfg, 'level', 12) if tree_boss_cfg else 12

    owl_boss_cfg = getattr(constants, 'owl_boss', None)
    owl_boss_level = getattr(owl_boss_cfg, 'level', 15) if owl_boss_cfg else 15

    is_special_boss_level = (state.game.level == wind_boss_level or
                             state.game.level == jelly_boss_level or
                             state.game.level == tree_boss_level or
                             state.game.level == owl_boss_level)

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
        elif state.game.level == owl_boss_level:
            spawn_miles_before = getattr(owl_boss_cfg, 'spawn_miles_before_transition', 3) if owl_boss_cfg else 3
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

    # Check if this is an Owl Boss level
    owl_boss_cfg = getattr(constants, 'owl_boss', None)
    owl_boss_level = getattr(owl_boss_cfg, 'level', 15) if owl_boss_cfg else 15

    if state.game.level == owl_boss_level:
        spawn_owl_boss()
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
    if boss_type == 'owl':
        update_owl_boss()
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


def check_bird_boss_collision():
    """Check bird-boss collisions."""
    boss = state.enemies.boss
    if boss is None or boss['state'] in ('dying', 'dead'):
        return

    # Special handling for Tree Boss (collision with branches)
    if boss.get('boss_type') == 'tree':
        _check_bird_tree_branch_collision()
        return

    # Get boss config based on type
    boss_type = boss.get('boss_type', 'normal')
    if boss_type == 'owl':
        boss_cfg = getattr(constants, 'owl_boss', None)
        boss_width = 15  # Owl boss hitbox width (wider than sprite for easier hits)
        boss_height = 6  # Owl boss hitbox height (slightly taller)
    elif boss_type == 'wind':
        boss_cfg = getattr(constants, 'wind_boss', None)
        boss_width = 26
        boss_height = 5
    elif boss_type == 'jelly':
        boss_cfg = getattr(constants, 'jelly_boss', None)
        boss_width = 23
        boss_height = 6
    else:
        boss_cfg = _get_boss_config()
        boss_width = 19
        boss_height = 3

    if boss_cfg is None:
        return

    # Boss hitbox
    boss_left = boss['x_pos']
    boss_right = boss['x_pos'] + boss_width
    boss_top = boss['y_pos']
    boss_bottom = boss['y_pos'] + boss_height

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
            boss['hp'] -= 32  # Orange does fixed 32 damage to bosses
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


def check_bird_meteor_collision():
    """Check bird-meteor collisions (Owl Boss meteors)."""
    boss = state.enemies.boss
    if boss is None or boss.get('boss_type') != 'owl':
        return

    owl_meteors = boss.get('owl_meteors', [])
    if not owl_meteors:
        return

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

        for meteor in owl_meteors:
            meteor_x = meteor['x_pos']
            meteor_y = meteor['y_pos']
            meteor_width = meteor.get('width', 6)

            # Meteor hitbox
            meteor_left = meteor_x - meteor_width // 2
            meteor_right = meteor_x + meteor_width // 2
            meteor_top = meteor_y
            meteor_bottom = meteor_y + 4  # Meteor is ~4 lines tall

            lane_left = bird_lane_x - 2
            lane_right = bird_lane_x + 2

            horizontal_overlap = not (meteor_right < lane_left or meteor_left > lane_right)
            vertical_overlap = not (bird_y + bird_height < meteor_top or bird_y > meteor_bottom)

            if not (horizontal_overlap and vertical_overlap):
                continue

            # Hit meteor!
            damage = _calculate_bird_damage(i)

            if bird_color == ORANGE:
                meteor['hp'] = 0  # Orange destroys meteor
            else:
                meteor['hp'] = meteor.get('hp', 1) - damage
                award_xp(i, damage)

            if meteor['hp'] <= 0:
                # Meteor destroyed
                add_score(100)
                play_sfx('destroy')
            else:
                # Bounce bird down
                _set_ball_vy(i, 1)
                state.birds.y[i] = meteor_bottom + 1
                # Stun bird briefly
                stun_frames = int(0.5 / constants.timing.base_sleep)
                state.special.stunned_birds[i] = stun_frames
                state.special.scared_birds[i] = stun_frames
                if bird_color == BLUE:
                    _reset_bird_power(i)
                play_sfx('hit')
            break
