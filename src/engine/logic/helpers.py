"""Small bird helpers shared by the logic modules."""

from src.core import constants, state
from src.entities.sprites import (
    OBSTACLE_SPRITE_T1,
    get_biome_obstacles,
    get_obstacle_hitbox_lanes,
    get_obstacle_sprite_width,
)


def get_obstacle_lanes(obs):
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
        obs_lane, sprite_width, constants.layout.lane_positions, constants.layout.num_lanes
    )


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
