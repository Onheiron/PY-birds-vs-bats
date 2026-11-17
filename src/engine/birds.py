"""Bird helpers: velocity, powers, lanes, transformations and shuffling."""

from src.core import constants, state
from src.engine.grades import compute_grade_from_xp
from src.entities.bird_types import get_bird_type_by_color
from src.entities.sprites import (
    BLUE,
    GOLD,
    ORANGE,
    RED,
    WHITE,
    YELLOW,
)

try:
    from src.entities import bird_types
except ImportError:
    bird_types = None


def set_ball_vy(idx, val):
    """Safely set vertical velocity for bird idx.

    Respects purple bird charging state.
    """
    if not (0 <= idx < constants.layout.num_balls):
        return
    if state.special.purple_state[idx] == 2:
        return
    if state.special.purple_just_fired_frames[idx] > 0:
        return
    state.birds.vy[idx] = val


def reset_bird_power(idx):
    """Reset bird power state."""
    state.birds.power_used[idx] = False
    state.birds.power_uses[idx] = 0


def allow_consume_power(idx, allowed_uses=1):
    """Return True and consume one use if bird may use its power."""
    if state.birds.power_uses[idx] < allowed_uses:
        state.birds.power_uses[idx] += 1
        state.birds.power_used[idx] = True
        return True
    return False


def get_scared_frames(bird_idx, base_seconds=2.0):
    """Calculate frames for scared state, reduced for higher grades."""
    label, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
    if not label.startswith('D') and not label.startswith('C'):
        base_seconds = max(1, base_seconds - 1.0)
    return max(1, int(float(base_seconds) / constants.timing.base_sleep))


def transform_bird_to_s(bi):
    """Transform bird to S-grade color if it reached S grade.

    Mappings: BLUE->WHITE, RED->ORANGE, YELLOW->GOLD
    If limit reached, bird is put in pending_transform state.
    """
    bi = int(bi)
    if bi < 0 or bi >= constants.layout.num_balls:
        return

    if state.birds.transformed[bi]:
        return

    label, _ = compute_grade_from_xp(state.birds.per_bird_xp[bi])
    if label != 'S':
        return

    old = state.birds.colors[bi]
    target_color = None
    target_speed = None

    if old == BLUE:
        target_color = WHITE
        target_speed = 4
    elif old == RED:
        target_color = ORANGE
        target_speed = 5
    elif old == YELLOW:
        target_color = GOLD
        target_speed = 5

    if target_color is None:
        state.birds.transformed[bi] = True
        return

    # Check if rare bird of this type already exists (max 1 per rare type)
    cnt = sum(
        1
        for j in range(constants.layout.num_balls)
        if not state.birds.lost[j] and state.birds.colors[j] == target_color
    )
    if cnt >= 1:
        # Can't transform yet - put in pending state
        state.birds.pending_transform[bi] = target_color
        return

    # Transform!
    state.birds.colors[bi] = target_color
    if target_speed:
        state.birds.speeds[bi] = target_speed
    state.birds.transformed[bi] = True
    state.birds.pending_transform[bi] = None


def check_pending_transforms(dead_bird_color):
    """When a rare bird dies, check if any pending birds can now transform.

    Args:
        dead_bird_color: The color of the bird that just died (WHITE, ORANGE, GOLD)
    """
    # Only care about rare bird deaths
    if dead_bird_color not in (WHITE, ORANGE, GOLD):
        return

    # Find a bird waiting to transform to this color
    for bi in range(constants.layout.num_balls):
        if state.birds.lost[bi]:
            continue
        if state.birds.pending_transform[bi] == dead_bird_color:
            # This bird was waiting - transform it now!
            if dead_bird_color == WHITE:
                target_speed = 4
            elif dead_bird_color == ORANGE:
                target_speed = 5
            elif dead_bird_color == GOLD:
                target_speed = 6
            else:
                target_speed = None

            state.birds.colors[bi] = dead_bird_color
            if target_speed:
                state.birds.speeds[bi] = target_speed
            state.birds.transformed[bi] = True
            state.birds.pending_transform[bi] = None
            return  # Only transform one


def find_bird_in_lane(lane):
    """Return bird index for given lane, or -1 if not found."""
    if lane in state.birds.random_lanes:
        return state.birds.random_lanes.index(lane)
    return -1


def get_affected_lanes():
    """Return lanes affected by cursor (considers wide cursor)."""
    if state.powerups.wide_cursor_active:
        lanes = []
        half_width = state.powerups.wide_cursor_lanes // 2
        for offset in range(-half_width, half_width + 1):
            lane = state.player.lane + offset
            if 0 <= lane < constants.layout.num_lanes:
                lanes.append(lane)
        return lanes
    return [state.player.lane]


def get_color_name(bird_color):
    """Map bird color to its lowercase type name ('yellow', 'rock', ...)."""
    bird_type = get_bird_type_by_color(bird_color)
    return bird_type.lower() if bird_type else 'unknown'


def is_orange_egg_state(bird_idx):
    """Check if bird is in orange egg dormant state."""
    return (
        state.birds.colors[bird_idx] == ORANGE and state.birds.speeds[bird_idx] == 0 and state.birds.y[bird_idx] == 999
    )
