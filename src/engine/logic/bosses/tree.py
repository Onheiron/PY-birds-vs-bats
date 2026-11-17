"""Tree Boss (Dark Swamp)."""

import random

from src.core import constants, state
from src.engine import bird_kinds, clock
from src.engine.logic.bosses.common import scaled_hp
from src.engine.logic.damage import calculate_bird_damage
from src.engine.logic.drops import drop_loot
from src.engine.logic.flowers import apply_flower_collision_effect, apply_mature_flower_effect
from src.engine.loot_tables import choose_loot_type, roll_drop_rarity
from src.engine.progression import add_score, award_xp, hp_scale
from src.entities.sprites import (
    FLOWER_MATURE_FRAME,
    TREE_BOSS_BACKGROUND,
    TREE_BOSS_BRANCH_FLOWER_POSITIONS,
    TREE_BOSS_BRANCHES,
)
from src.services.sound import play_sfx


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
    base_hp = scaled_hp(base_hp)

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
        {'x': 5, 'tree_row': 6, 'sprite_idx': 2},  # Branch 3 - covers lanes 0,1,2,3
        {'x': 25, 'tree_row': 4, 'sprite_idx': 3},  # Branch 4 - covers lanes 5,6
        {'x': 33, 'tree_row': 8, 'sprite_idx': 4},  # Branch 5 - covers lanes 7,8
    ]

    # Import branch sprites and background tree for size calculation

    # Calculate background tree height (needed for branch positioning)
    bg_height = len(TREE_BOSS_BACKGROUND)

    # Create branches with calculated positions
    branches = []
    flower_types = ['red', 'yellow', 'blue', 'green']

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

        if sprite_idx < len(TREE_BOSS_BRANCH_FLOWER_POSITIONS):
            flower_positions = TREE_BOSS_BRANCH_FLOWER_POSITIONS[sprite_idx]
        else:
            flower_positions = [(sprite_width // 2, 0)]  # Default: center-top

        # Pick random flower position
        flower_pos = random.choice(flower_positions)

        # Get grow interval from config
        getattr(flowers_cfg, 'grow_interval', 2.0) if flowers_cfg else 2.0

        branches.append(
            {
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
            }
        )

    # Background tree starting position (above screen) - bg_height already calculated above
    state.enemies.boss = {
        'x_pos': 0,
        'y_pos': 0,
        'hp': 1,  # Tree boss HP is based on branches, not central HP
        'max_hp': 1,
        'state': 'active',
        'spawn_ts': clock.now(),
        'boss_type': 'tree',
        'branches': branches,
        'bg_y_offset': -bg_height,  # Background tree starts above screen
    }
    state.enemies.boss_spawned = True
    # Clear normal enemies for boss fight
    state.enemies.bats = []
    state.enemies.obstacles = []


def update_tree_boss():
    """Update Tree Boss state: flower growth, effects, check win condition."""
    boss = state.enemies.boss
    if boss is None or boss.get('boss_type') != 'tree':
        return

    tree_boss_cfg = getattr(constants, 'tree_boss', None)
    flowers_cfg = getattr(tree_boss_cfg, 'flowers', None) if tree_boss_cfg else None
    grow_interval = getattr(flowers_cfg, 'grow_interval', 2.0) if flowers_cfg else 2.0
    getattr(flowers_cfg, 'respawn_delay', 3.0) if flowers_cfg else 3.0
    flower_hp = getattr(flowers_cfg, 'hp', 10) if flowers_cfg else 10

    now = clock.now()
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

    len(TREE_BOSS_BACKGROUND)
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
                    apply_mature_flower_effect(branch, flower)
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
    damage = calculate_bird_damage(bird_idx, 'elite')

    flower = branch.get('flower')
    # Only apply effects if flower is active AND fully mature (frame 5)

    flower_was_mature = flower and flower.get('active') and flower.get('frame', 0) >= FLOWER_MATURE_FRAME

    # Damage flower first, then branch
    if flower and flower.get('active') and flower.get('hp', 0) > 0:
        flower['hp'] -= damage
        if flower['hp'] <= 0:
            # Flower destroyed - will respawn later
            flower['active'] = False
            respawn_delay = getattr(flowers_cfg, 'respawn_delay', 3.0) if flowers_cfg else 3.0
            flower['respawn_timer'] = clock.now() + respawn_delay
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
        apply_flower_collision_effect(flower, bird_idx)

    return True


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
        'hp': 8 * hp_scale(),
        'max_hp': 8 * hp_scale(),
        'target_y': y_pos + 5,
        'spawn_ts': clock.now(),
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
        for i in range(loot_count):
            rarity = roll_drop_rarity('boss')
            loot_type = choose_loot_type(rarity)

            lane = i % constants.layout.num_lanes
            drop_loot(
                {
                    'x_pos': constants.layout.lane_positions[lane],
                    'y_pos': 5 + i * 3,
                    'type': loot_type,
                    'rarity': rarity,
                    'spawn_ts': clock.now(),
                },
                'boss',
            )

        # Clear frozen/poisoned/bleeding birds
        state.special.frozen_birds.clear()
        state.special.poisoned_birds.clear()
        state.special.bleeding_birds.clear()

        # Mark boss as scrolling down (defeated but still visible)
        boss['state'] = 'scrolling_down'
        state.enemies.boss_defeated = True
        return

    # Already scrolling down - continue scrolling

    len(TREE_BOSS_BACKGROUND)

    # Scroll tree down every few frames
    if state.game.frame_count % 3 == 0:
        boss['bg_y_offset'] = boss.get('bg_y_offset', 0) + 1

    # Check if tree has scrolled completely off screen
    if boss.get('bg_y_offset', 0) > constants.layout.height:
        # Tree is off screen - now fully clear the boss
        state.enemies.boss = None


def check_bird_tree_branch_collision():
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

        state.birds.colors[i]
        bird_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_kinds.is_intangible(i):
            continue

        bird_height = bird_kinds.height(i)

        # Check each branch for collision
        for branch in branches:
            if branch.get('destroyed'):
                continue

            branch_left = branch['x_pos']
            branch_right = branch['x_pos'] + branch['sprite_width']
            branch_top = branch['y_pos']
            branch_bottom = branch['y_pos'] + branch['sprite_height']

            lane_left, lane_right = bird_kinds.hit_span(i)

            horizontal_overlap = not (branch_right < lane_left or branch_left > lane_right)
            vertical_overlap = not (bird_y + bird_height < branch_top or bird_y > branch_bottom)

            if horizontal_overlap and vertical_overlap:
                # Hit branch!
                _handle_tree_branch_hit(branch, i)
                play_sfx('hit')
                break  # Only hit one branch per frame per bird
