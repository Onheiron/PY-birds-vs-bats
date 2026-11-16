"""GLITCH bird chaos: random teleports and duplication."""

from src.core import constants
from src.core import state
from src.entities.sprites import GLITCH
import random


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
