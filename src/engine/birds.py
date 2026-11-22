"""Bird helpers: velocity, powers, lanes, transformations and shuffling."""

import random

from src.core import constants, state
from src.engine import stats
from src.engine.grades import compute_grade_from_xp
from src.entities.bird_types import get_bird_type_by_color, get_default_speed
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
    """Ticks a scare lasts: scaled by fear_duration_mult, cut by fear_duration_cut (never below 1 s)."""
    seconds = float(base_seconds) * stats.bird(bird_idx, 'fear_duration_mult')
    cut = stats.bird(bird_idx, 'fear_duration_cut')
    if cut:
        seconds = max(1, seconds - cut)
    return max(1, int(seconds / constants.timing.base_sleep))


def _resists_fear(bird_idx):
    immunity = stats.bird(bird_idx, 'fear_immunity')
    return immunity > 0 and random.random() < immunity


def scare_bird(bird_idx, seconds, push=1):
    """Scare a bird for ``seconds`` (its fear stats apply). False if it shrugged it off.

    ``push``: how much faster (speed points) it falls while scared (the scarer's fear_push).
    """
    if _resists_fear(bird_idx):
        return False
    state.special.scared_birds[bird_idx] = get_scared_frames(bird_idx, seconds)
    state.special.scared_push[bird_idx] = push
    return True


def scare_bird_ticks(bird_idx, ticks):
    """Scare for a fixed number of ticks (screams): only immunity and the duration multiplier apply."""
    if _resists_fear(bird_idx):
        return False
    mult = stats.bird(bird_idx, 'fear_duration_mult')
    state.special.scared_birds[bird_idx] = ticks if mult == 1 else max(1, int(ticks * mult))
    state.special.scared_push[bird_idx] = 1
    return True


def stun_bird(bird_idx, seconds):
    """Bounce-off stun after hitting something that survived (scaled by impact_stun)."""
    frames = int(seconds * stats.bird(bird_idx, 'impact_stun') / constants.timing.base_sleep)
    state.special.stunned_birds[bird_idx] = frames
    state.special.scared_birds[bird_idx] = frames
    return frames


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
        target_speed = get_default_speed('WHITE')
    elif old == RED:
        target_color = ORANGE
        target_speed = get_default_speed('ORANGE')
    elif old == YELLOW:
        target_color = GOLD
        target_speed = get_default_speed('GOLD')

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
            target_speed = get_default_speed(get_bird_type_by_color(dead_bird_color))

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
