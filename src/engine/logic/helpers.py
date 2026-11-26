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


def claim_free_lane(idx):
    """Before a lost slot comes back to life: if a living bird is in its lane, move the slot
    to the free lane closest to the flock (swapping with the empty slot there), so no two
    birds ever share a lane."""
    birds = state.birds
    n = constants.layout.num_balls
    alive = [birds.random_lanes[i] for i in range(n) if i != idx and not birds.lost[i]]
    lane = birds.random_lanes[idx]
    if lane not in alive:
        birds.cols[idx] = constants.layout.lane_positions[lane]
        return lane
    free = [x for x in range(constants.layout.num_lanes) if x not in alive]
    if not free:
        return None
    centre = sum(alive) / len(alive)
    new = min(free, key=lambda x: (min(abs(x - a) for a in alive), abs(x - centre)))
    for j in range(n):  # the empty slot holding that lane takes the old one
        if j != idx and birds.lost[j] and birds.random_lanes[j] == new:
            birds.random_lanes[j] = birds.home_lanes[j] = lane
            birds.cols[j] = constants.layout.lane_positions[lane]
    birds.random_lanes[idx] = birds.home_lanes[idx] = new
    birds.cols[idx] = constants.layout.lane_positions[new]
    return new
