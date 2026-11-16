"""Swamp flowers growing on obstacles and Tree Boss branches."""

import random
import time

from src.core import constants, state


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


def _apply_mature_flower_effect(branch, flower):
    """Apply the effect of a mature (frame 5) flower to its lanes."""
    # Yellow, blue, and green effects are applied on collision, not passively


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
