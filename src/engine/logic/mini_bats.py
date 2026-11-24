"""Mini bats and jumpscare bats hiding inside obstacles."""

import random

from src.core import constants, state
from src.engine import bird_kinds, clock, enemy_stats
from src.engine.birds import scare_bird, set_ball_vy, stun_bird
from src.engine.logic.damage import calculate_bird_damage, handle_mini_bat_death
from src.engine.progression import award_damage_xp
from src.entities.sprites import ORANGE
from src.services.sound import play_sfx


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

    state.enemies.mini_bats.append(enemy_stats.equip_bat(mini_bat))


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
        'visible_seconds': visible_duration,  # out for this long after its scream (game seconds)
    }

    # Add to mini_bats list (reuses existing system)
    state.enemies.mini_bats.append(enemy_stats.equip_bat(jumpscare_bat))


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
            scare_bird(i, fear_duration * enemy_stats.get(jumpscare_bat, 'fear_strength'))

    # Set scary face timer on bat
    scary_face_duration = getattr(jumpscare_cfg, 'scary_face_duration', 0.5) if jumpscare_cfg else 0.5
    # In game seconds: a count of ticks would last less the higher the gear
    jumpscare_bat['scary_face_until'] = clock.now() + scary_face_duration


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

    # Chance to let a new mini bat out: the world's mini_bat (bat_enemy.worlds)
    spawn_prob = float(enemy_stats.world_table().get('mini_bat', 0.0) or 0.0)

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
        mb for mb in state.enemies.mini_bats if mb.get('source_obstacle_id') == obs_id and mb['state'] == 'active'
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
                        mb['visible_until'] = clock.now() + mb.get('visible_seconds', 3.0)

        elif mb['state'] == 'hiding':
            # Hide animation: sprite → O → * → • → · → disappear
            if mb['anim_timer'] >= anim_speed:
                mb['anim_timer'] = 0
                mb['anim_frame'] -= 1
                if mb['anim_frame'] < 0:  # Animation complete, hide in obstacle
                    target_id = mb.get('target_obstacle_id')
                    if target_id is not None:
                        # Check if target obstacle still exists
                        target_exists = any(obs.get('id') == target_id for obs in state.enemies.obstacles)
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

            # Jumpscare bat: out for visible_seconds after its scream, then hides again
            if mb.get('is_jumpscare') and mb.get('scary_face_done'):
                # Random chance to do another scary face while active
                if clock.now() >= mb.get('scary_face_until', 0):
                    jumpscare_cfg = getattr(constants.bat_enemy, 'jumpscare_bat', None)
                    random_scream_chance = (
                        getattr(jumpscare_cfg, 'random_scream_chance', 0.01) if jumpscare_cfg else 0.01
                    )
                    if random.random() < random_scream_chance:
                        activate_jumpscare_scary_face(mb)

                if clock.now() >= mb.get('visible_until', clock.now() + 3.0):
                    # Time to hide in another tier 3+ obstacle
                    available_obstacles = [obs for obs in tier3_obstacles if obs.get('id') not in visited]
                    if available_obstacles:
                        mb['state'] = 'hiding'
                        mb['anim_frame'] = 3
                        mb['anim_timer'] = 0
                        mb['target_obstacle_id'] = random.choice(available_obstacles).get('id')
                        mb['scary_face_done'] = False  # Reset for next appearance
                        continue

            # Check if source obstacle still exists
            source_exists = (
                any(obs.get('id') == source_id for obs in state.enemies.obstacles) if source_id is not None else False
            )

            if not source_exists:
                # Source destroyed! Try to find a new tier 3+ obstacle to hide in
                # Exclude already visited obstacles
                available_obstacles = [obs for obs in tier3_obstacles if obs.get('id') not in visited]
                if available_obstacles:
                    mb['state'] = 'hiding'
                    mb['anim_frame'] = 3
                    mb['anim_timer'] = 0
                    mb['target_obstacle_id'] = random.choice(available_obstacles).get('id')


def check_bird_mini_bat_collision():
    """Check bird-mini bat collisions."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i] or state.birds.vy[i] != -1:
            continue

        # Skip charging purple
        if state.special.purple_state[i] == 2 or state.special.purple_just_fired_frames[i] > 0:
            continue

        bird_color = state.birds.colors[i]
        bird_y = state.birds.y[i]

        # STEALTH passes through unless tangible
        if bird_kinds.is_intangible(i):
            continue

        bird_height = bird_kinds.height(i)

        for mb in state.enemies.mini_bats[:]:
            # Only collide with active mini bats
            if mb['state'] != 'active':
                continue

            # Mini bat is single line, ~10 chars wide
            mb_width = 10
            mb_left = mb['x_pos'] - mb_width // 2
            mb_right = mb['x_pos'] + mb_width // 2
            mb_y = mb['y_pos']

            lane_left, lane_right = bird_kinds.hit_span(i)

            horizontal_overlap = not (mb_right < lane_left or mb_left > lane_right)
            vertical_overlap = not (bird_y + bird_height < mb_y or bird_y > mb_y)

            if not (horizontal_overlap and vertical_overlap):
                continue

            # Hit mini bat
            damage = calculate_bird_damage(i)

            if bird_color == ORANGE:
                mb['hp'] = 0
            else:
                damage = enemy_stats.mitigate(mb, damage, 'contact', bird=i)
                mb['hp'] -= damage
                award_damage_xp(i, damage)

            if mb['hp'] <= 0:
                # Mini bat destroyed - use same logic as regular bats
                handle_mini_bat_death(mb, i)
            else:
                set_ball_vy(i, 1)
                stun_bird(i, 0.5)  # Shorter stun
                play_sfx('hit')
            break
