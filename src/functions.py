#!/usr/bin/env python3
"""
Core utility functions for BVB game.
Contains essential game functions used across modules.
"""

import sys
import os
import random
import threading

if os.name == 'nt':
    import msvcrt
else:
    import tty
    import termios
    import fcntl

from src.entities.sprites import *
from src.core import constants
from src.core import state
from src.services import achievements

try:
    from src.entities import bird_types
except ImportError:
    bird_types = None

try:
    from src.services import firebase_client
except ImportError:
    firebase_client = None

# Audio module (optional) - imported late to avoid circular imports
_audio_module = None

def _get_audio():
    """Lazy load audio module."""
    global _audio_module
    if _audio_module is None:
        try:
            from src.services import audio
            _audio_module = audio if audio.is_audio_available() else False
        except ImportError:
            _audio_module = False
    return _audio_module if _audio_module else None


# Terminal settings for setup/cleanup
_old_settings = None
_old_flags = None


# =============================================================================
# TERMINAL SETUP / CLEANUP
# =============================================================================

def setup():
    """Initialize terminal for game (hide cursor, raw mode)."""
    global _old_settings, _old_flags
    print("\033[?25l", end="", flush=True)  # Hide cursor
    if os.name != 'nt':
        _old_settings = termios.tcgetattr(sys.stdin)
        _old_flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        tty.setraw(sys.stdin.fileno())
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, _old_flags | os.O_NONBLOCK)
    os.system('cls' if os.name == 'nt' else 'clear')


def cleanup():
    """Restore terminal to normal state."""
    global _old_settings, _old_flags

    if os.name != 'nt':
        fd = sys.stdin.fileno()

        # FIRST: Restore stdin to blocking mode (before termios!)
        if _old_flags is not None:
            try:
                fcntl.fcntl(fd, fcntl.F_SETFL, _old_flags)
            except Exception:
                pass

        # SECOND: Restore stdout to blocking mode
        try:
            stdout_fd = sys.stdout.fileno()
            stdout_flags = fcntl.fcntl(stdout_fd, fcntl.F_GETFL)
            fcntl.fcntl(stdout_fd, fcntl.F_SETFL, stdout_flags & ~os.O_NONBLOCK)
        except Exception:
            pass

        # THIRD: Restore terminal to cooked mode
        if _old_settings is not None:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, _old_settings)
            except Exception:
                pass

        # FALLBACK: If all else fails, use stty sane
        try:
            os.system('stty sane 2>/dev/null')
        except Exception:
            pass

    # Show cursor and clear screen
    try:
        os.write(sys.stdout.fileno(), b"\033[?25h\033[2J\033[H")
    except Exception:
        pass

    # Cleanup firebase if available
    if firebase_client:
        for attr in ('close', 'session', 'pool', 'requests_session'):
            obj = getattr(firebase_client, attr, None)
            if callable(obj):
                try:
                    obj()
                except Exception:
                    pass
            elif obj and hasattr(obj, 'close'):
                try:
                    obj.close()
                except Exception:
                    pass


# =============================================================================
# THREADING UTILITIES
# =============================================================================

def safe_call(func, *args, **kwargs):
    """Safely call a function, catching all exceptions."""
    try:
        func(*args, **kwargs)
    except:
        pass


def background_call(func, *args, **kwargs):
    """Execute function in background thread."""
    try:
        t = threading.Thread(target=safe_call, args=(func,) + args, kwargs=kwargs, daemon=True)
        t.start()
    except:
        pass


# =============================================================================
# BIRD STATE HELPERS
# =============================================================================

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


# =============================================================================
# LEVEL & GRADE CALCULATIONS
# =============================================================================

def calculate_gear_threshold(gear):
    """Calculate momentum threshold for given gear level (1-10)."""
    base = float(constants.progression.level_score_base)
    factor = float(constants.progression.level_score_factor)
    return int(base ** (factor ** (gear + 1)))


def compute_grade_from_xp(xp):
    """Return (grade_label, color) tuple for given XP value."""
    xp = int(float(xp))

    base = float(constants.progression.xp_base)
    factor = float(constants.progression.grade_exp_factor)

    if xp < int(base):
        return ('D', GREEN)

    labels = ['C1', 'C2', 'B1', 'B2', 'A1', 'A2', 'S']
    exps = [factor ** n for n in range(len(labels))]
    thresholds = [int(round(base ** e)) for e in exps]

    for lbl, thr in reversed(list(zip(labels, thresholds))):
        if xp >= thr:
            prefix = lbl[0]
            color_map = {'D': GREEN, 'C': ORANGE, 'B': WHITE, 'A': GOLD, 'S': RED}
            return (lbl, color_map.get(prefix, DARK_GRAY))

    return ('C1', ORANGE)


# =============================================================================
# SPEED / MILES / LEVEL SYSTEM
# =============================================================================

def compute_gear_from_momentum(momentum):
    """Compute gear level (1-10) from momentum.

    Gear controls game speed. Uses exponential progression.
    """
    max_gear = getattr(constants.speed, 'max_speed', 10)

    gear = 1
    while momentum >= calculate_gear_threshold(gear + 1):
        gear += 1
        if gear >= max_gear:
            break
    return gear


def get_mph_for_speed(speed_level):
    """Get miles per hour for a given speed level.

    At speed 1: 40 mph
    At speed 5: 200 mph
    At speed 10: 400 mph
    """
    mph_per_level = getattr(constants.speed, 'mph_per_level', 40)
    return speed_level * mph_per_level


def get_level_milestones():
    """Get list of 18 level milestones in miles.

    Returns list of cumulative distances: [3, 7, 12, 18, 25, 33, ...]
    """
    total_levels = getattr(constants.levels, 'total_levels', 18)
    starting_distance = getattr(constants.levels, 'starting_distance', 3)
    increment_start = getattr(constants.levels, 'distance_increment_start', 4)

    milestones = []
    current = 0
    increment = starting_distance

    for _ in range(total_levels):
        current += increment
        milestones.append(current)
        increment += 1

    return milestones


def compute_level_from_miles(miles):
    """Compute level (1-18) from miles traveled.

    Returns (level_number, group, sub) where:
    - level_number: 1-18
    - group: 1-6
    - sub: 1-3
    """
    milestones = get_level_milestones()
    levels_per_group = getattr(constants.levels, 'levels_per_group', 3)

    level = 1
    for i, threshold in enumerate(milestones):
        if miles >= threshold:
            level = i + 2  # Level 2 at first milestone, etc.
        else:
            break

    # Cap at max level
    level = min(level, len(milestones))

    # Calculate group and sub-level
    group = ((level - 1) // levels_per_group) + 1
    sub = ((level - 1) % levels_per_group) + 1

    return level, group, sub


def format_level_display(level, group, sub):
    """Format level for display as 'G-S' (e.g., '2-3')."""
    return f"{group}-{sub}"


def update_miles(delta_time):
    """Update miles traveled based on current speed and elapsed time.

    Args:
        delta_time: Time elapsed in seconds since last update

    Returns:
        True if level changed, False otherwise
    """
    if delta_time <= 0:
        return False

    # Get current speed and calculate mph
    mph = get_mph_for_speed(state.game.speed)

    # Convert mph to miles per second and add
    miles_per_second = mph / 3600.0
    state.game.miles += miles_per_second * delta_time

    # Check if level changed
    old_level = state.game.level
    new_level, new_group, new_sub = compute_level_from_miles(state.game.miles)

    if new_level != old_level:
        state.game.level = new_level
        state.game.level_group = new_group
        state.game.level_sub = new_sub
        return True

    return False


def update_gear():
    """Update gear based on current momentum.

    Returns:
        True if gear changed, False otherwise
    """
    old_gear = state.game.speed
    new_gear = compute_gear_from_momentum(state.game.momentum)

    if new_gear != old_gear:
        state.game.speed = new_gear
        return True

    return False


def get_frame_sleep_for_speed(speed_level):
    """Get frame sleep time for given speed level.

    Interpolates between frame_sleep_at_speed_1 and frame_sleep_at_speed_10.
    """
    min_speed = getattr(constants.speed, 'min_speed', 1)
    max_speed = getattr(constants.speed, 'max_speed', 10)
    sleep_at_1 = getattr(constants.speed, 'frame_sleep_at_speed_1', 0.18)
    sleep_at_10 = getattr(constants.speed, 'frame_sleep_at_speed_10', 0.02)

    # Normalize speed to 0-1 range
    t = (speed_level - min_speed) / (max_speed - min_speed) if max_speed > min_speed else 0
    t = max(0, min(1, t))

    # Linear interpolation
    return sleep_at_1 + t * (sleep_at_10 - sleep_at_1)


# =============================================================================
# SCORE & PRESTIGE
# =============================================================================

def compute_prestige():
    """Compute prestige multiplier based on active bird grades."""
    total = 1.0

    for i in range(len(state.birds.per_bird_xp)):
        if state.birds.lost[i]:
            continue

        # GLITCH birds contribute random prestige
        if state.birds.colors[i] == GLITCH:
            total += float(random.randint(1, 7))
            continue

        label, _ = compute_grade_from_xp(state.birds.per_bird_xp[i])
        add = constants.prestige.modifiers.get(label, 0.0)
        total += add

    return float(total)


def add_score(amount, by_bird=None):
    """Add score (always increases). Used for leaderboard/achievements.

    This function ONLY affects score. Momentum is handled separately by update_momentum().
    """
    amt = float(amount)
    prestige = compute_prestige()
    score_amount = amt * prestige

    state.game.score += score_amount * 0.2

    if by_bird is not None and 0 <= int(by_bird) < len(state.birds.per_bird_xp):
        xp_award = int(max(0, int(amount)))
        state.birds.per_bird_xp[int(by_bird)] += xp_award
        transform_bird_to_s(int(by_bird))

    achievements.check_achievements_event(
        'score', state.game.frame_count, state.ui.notifications,
        firebase_client=firebase_client, background_call=background_call,
        score=state.game.score
    )


def update_momentum(momentum_factor):
    """Update momentum based on center of mass momentum factor.

    momentum_factor: -1.0 (bottom) to +2.0 (top), 0 at 1/3 height
    NO prestige, NO other factors - ONLY center of mass affects momentum.
    """
    gain_mult = getattr(constants.speed, 'momentum_gain_multiplier', 1.0)

    # Apply momentum factor directly (already centered at 0)
    delta = momentum_factor * gain_mult
    state.game.momentum += delta

    # Clamp to minimum
    state.game.momentum = max(1.0, state.game.momentum)

    gear_changed = update_gear()

    if gear_changed:
        audio = _get_audio()
        if audio:
            audio.update_music_for_level(state.game.speed)
            audio.update_game_speed(
                state.game.speed,
                base_sleep=getattr(constants.speed, 'frame_sleep_at_speed_1', 0.18),
                multiplier=1.0,
                min_sleep=getattr(constants.speed, 'frame_sleep_at_speed_10', 0.02)
            )


def award_xp(bird_idx, xp_amount):
    """Credit XP to a bird without affecting score."""
    bi = int(bird_idx)
    if bi < 0 or bi >= len(state.birds.per_bird_xp):
        return
    state.birds.per_bird_xp[bi] += int(max(0, int(xp_amount)))
    transform_bird_to_s(bi)


def deduct_momentum(amount):
    """Deduct momentum safely (used for swaps). Score is NOT affected."""
    old_momentum = state.game.momentum
    state.game.momentum = max(0, state.game.momentum - amount)

    # Update gear if momentum changed significantly
    gear_changed = update_gear()

    if gear_changed:
        audio = _get_audio()
        if audio:
            audio.update_music_for_level(state.game.speed)
            audio.update_game_speed(
                state.game.speed,
                base_sleep=getattr(constants.speed, 'frame_sleep_at_speed_1', 0.18),
                multiplier=1.0,
                min_sleep=getattr(constants.speed, 'frame_sleep_at_speed_10', 0.02)
            )


def adjust_rarity_weights(base_weights, prestige):
    """Adjust loot rarity weights based on prestige."""
    factor = 1.0 + float(prestige) * float(constants.prestige.rarity_factor)
    new = [float(w) * factor for w in base_weights]
    total = sum(new)

    if total <= 0.0:
        n = len(base_weights)
        return [100.0 / n] * n

    if total > 100.0:
        excess = total - 100.0
        for i in range(len(new)):
            if excess <= 0:
                break
            take = min(excess, new[i])
            new[i] -= take
            excess -= take
    elif total < 100.0:
        new[0] += 100.0 - total

    tot = sum(new)
    if abs(tot - 100.0) > 1e-6 and tot > 0:
        new = [w * 100.0 / tot for w in new]

    return new


# =============================================================================
# SCARED FRAMES
# =============================================================================

def get_scared_frames(bird_idx, base_seconds=2.0):
    """Calculate frames for scared state, reduced for higher grades."""
    label, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
    if not label.startswith('D') and not label.startswith('C'):
        base_seconds = max(1, base_seconds - 1.0)
    return max(1, int(float(base_seconds) / constants.timing.base_sleep))


# =============================================================================
# BIRD TRANSFORMATION
# =============================================================================

def transform_bird_to_s(bi):
    """Transform bird to S-grade color if it reached S grade.

    Mappings: BLUE->WHITE, RED->ORANGE, YELLOW->GOLD
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
        target_speed = 6

    if target_color is None:
        state.birds.transformed[bi] = True
        return

    # Check spawn limits
    limit = constants.transform.limits.get(target_color)
    if limit is not None:
        cnt = sum(1 for j in range(constants.layout.num_balls)
                  if not state.birds.lost[j] and state.birds.colors[j] == target_color)
        if cnt >= limit and state.birds.colors[bi] != target_color:
            state.birds.transformed[bi] = True
            return

    state.birds.colors[bi] = target_color
    if target_speed:
        state.birds.speeds[bi] = target_speed
    state.birds.transformed[bi] = True


# =============================================================================
# SHUFFLE
# =============================================================================

def perform_shuffle(count):
    """Shuffle birds toward center lanes."""
    center = 4
    moved_indices = set()
    used_lost_slots = set()

    for _ in range(max(0, int(count))):
        living = [i for i in range(constants.layout.num_balls) if not state.birds.lost[i]]
        living_available = [i for i in living if i not in moved_indices]

        if len(living_available) <= 1:
            break

        # Pick bird farthest from center
        living_sorted = sorted(living_available,
                              key=lambda i: abs(state.birds.random_lanes[i] - center),
                              reverse=True)
        src_idx = living_sorted[0]
        src_lane = state.birds.random_lanes[src_idx]

        # Try to find empty lane closest to center
        lost_slots = [i for i in range(constants.layout.num_balls)
                      if state.birds.lost[i] and i not in used_lost_slots]

        if lost_slots:
            empty_lanes = sorted([state.birds.random_lanes[i] for i in lost_slots],
                                key=lambda l: abs(l - center))
            target_lane = empty_lanes[0]
            target_idx = next((li for li in lost_slots
                              if state.birds.random_lanes[li] == target_lane), None)

            if target_idx is not None:
                _swap_lanes(src_idx, target_idx)
                moved_indices.add(src_idx)
                moved_indices.add(target_idx)
                used_lost_slots.add(target_idx)
                continue

        # Try inner living bird
        inner = [i for i in living if i != src_idx and i not in moved_indices
                 and abs(state.birds.random_lanes[i] - center) < abs(src_lane - center)]

        if inner:
            tgt_idx = sorted(inner, key=lambda i: abs(state.birds.random_lanes[i] - center))[0]
            _swap_lanes(src_idx, tgt_idx)
            moved_indices.add(src_idx)
            moved_indices.add(tgt_idx)
            continue

        # Fallback: random swap
        others = [i for i in living if i != src_idx and i not in moved_indices]
        if not others:
            break
        other = random.choice(others)
        _swap_lanes(src_idx, other)
        moved_indices.add(src_idx)
        moved_indices.add(other)


def _swap_lanes(idx1, idx2):
    """Helper to swap lane assignments and reset positions."""
    state.birds.random_lanes[idx1], state.birds.random_lanes[idx2] = \
        state.birds.random_lanes[idx2], state.birds.random_lanes[idx1]

    state.birds.cols[idx1] = constants.layout.lane_positions[state.birds.random_lanes[idx1]]
    state.birds.cols[idx2] = constants.layout.lane_positions[state.birds.random_lanes[idx2]]

    for idx in [idx1, idx2]:
        if not state.birds.lost[idx]:
            state.birds.y[idx] = constants.layout.starting_line
            set_ball_vy(idx, -1)
            reset_bird_power(idx)


# =============================================================================
# LOOT SELECTION
# =============================================================================

def choose_loot_type(rarity):
    """Choose a loot type based on rarity and game state."""
    # Count empty bird slots
    num_empty = sum(1 for i in range(constants.layout.num_balls) if state.birds.lost[i])

    # Get egg probability
    egg_prob = 0.0
    if num_empty > 0:
        if num_empty in constants.eggs.drop_probs:
            egg_prob = float(constants.eggs.drop_probs[num_empty])
        else:
            int_keys = sorted([k for k in constants.eggs.drop_probs.keys() if isinstance(k, int)])
            if int_keys:
                egg_prob = float(constants.eggs.drop_probs[int_keys[-1]])

    # Loot pools
    loot_pools = {
        'common': ['wide_cursor', 'tailwind', 'shuffle'],
        'uncommon': ['wide_cursor+', 'tailwind+', 'shuffle'],
        'rare': ['wide_cursor++', 'tailwind++', 'shuffle+'],
        'epic': ['wide_cursor_max', 'tailwind_max', 'shuffle++']
    }

    # Decide egg or powerup
    if random.random() < egg_prob:
        return _choose_egg(rarity)
    else:
        pool = loot_pools.get(rarity, loot_pools['common'])
        return random.choice(pool)


def _choose_egg(rarity):
    """Choose an egg type based on rarity."""
    rarity_data = constants.eggs.rarity_candidates.get(rarity, {})
    candidates = list(rarity_data.keys()) if isinstance(rarity_data, dict) else []

    if not candidates:
        defaults = {
            'common': ['yellow_egg', 'red_egg', 'blue_egg'],
            'uncommon': ['blue_egg', 'patchwork_egg', 'purple_egg'],
            'rare': ['white_egg', 'orange_egg', 'gold_egg'],
            'epic': ['dinosaur_egg', 'glitch_egg']
        }
        candidates = defaults.get(rarity, ['yellow_egg'])

    raw_weights = rarity_data if isinstance(rarity_data, dict) else {}
    weights = [float(raw_weights.get(e, 1.0)) for e in candidates]

    # Filter by spawn limits
    def allowed(egg_name):
        if not bird_types:
            return True
        bcol = getattr(bird_types, 'EGG_TO_COLOR', {}).get(egg_name)
        if bcol is None:
            return True
        limit = getattr(bird_types, 'COLOR_LIMITS', {}).get(bcol)
        if limit is None:
            return True
        cnt = sum(1 for i in range(constants.layout.num_balls)
                  if not state.birds.lost[i] and state.birds.colors[i] == bcol)
        return cnt < limit

    allowed_candidates = [(e, w) for e, w in zip(candidates, weights) if allowed(e)]

    if allowed_candidates:
        eggs, weights = zip(*allowed_candidates)
        return random.choices(list(eggs), weights=list(weights))[0]

    return 'yellow_egg'


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

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
    """Map bird color to simple name string."""
    color_map = {
        YELLOW: 'yellow', RED: 'red', BLUE: 'blue', WHITE: 'white',
        PURPLE: 'purple', ORANGE: 'orange', STEALTH: 'stealth',
        CLOCKWORK: 'clockwork', GOLD: 'gold', PATCHWORK: 'patchwork',
        COOKIE: 'cookie', DINOSAUR: 'dinosaur', GLITCH: 'glitch'
    }
    return color_map.get(bird_color, 'unknown')


def is_orange_egg_state(bird_idx):
    """Check if bird is in orange egg dormant state."""
    return (state.birds.colors[bird_idx] == ORANGE and
            state.birds.speeds[bird_idx] == 0 and
            state.birds.y[bird_idx] == 999)
