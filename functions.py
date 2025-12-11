#!/usr/bin/env python3
import sys
import time
import os
import random
    
if os.name == 'nt':
    import msvcrt
else:
    import tty
    import termios
    import fcntl

from sprites import *

import constants
import functions
import achievements
import state

try:
    import yaml
except Exception:
    yaml = None
try:
    import jsonschema
except Exception:
    jsonschema = None
try:
    import firebase_client
except Exception:
    firebase_client = None

import threading

# Module-level variables for terminal settings (used by setup/cleanup)
old_settings = None
old_flags = None

#!/usr/bin/env python3
"""
Utility functions for BVB game.
All functions accept a 'ctx' parameter containing game state and globals.
"""

def safe_call(func, *a, **kw):
    """Safely call a function, catching all exceptions."""
    try:
        func(*a, **kw)
    except Exception:
        pass

def background_call(func, *a, **kw):
    """Execute function in background thread."""
    try:
        t = threading.Thread(target=safe_call, args=(func,)+a, kwargs=kw, daemon=True)
        t.start()
    except Exception:
        pass

def calculate_level_threshold(level, ctx):
    """Calculate score threshold for given level."""
    try:
        base = float(ctx.get('LEVEL_SCORE_BASE', 500.0))
        factor = float(ctx.get('LEVEL_SCORE_FACTOR', 1.07))
        return int(base ** (factor ** (level + 1)))
    except Exception:
        return int(500 ** (1.07 ** (level + 1)))

def compute_level_from_score(score, ctx):
    """Compute current level from score."""
    lvl = 1
    try:
        while score >= calculate_level_threshold(lvl, ctx):
            lvl += 1
    except Exception:
        pass
    return lvl

def compute_grade_from_xp(xp, ctx):
    """Map XP to a grade (D, C1, C2, B1, B2, A1, A2, S) with colour."""
    try:
        xp = int(float(xp))
    except Exception:
        xp = 0
    
    # Use configurable progression constants
    try:
        base = float(ctx.get('XP_BASE', 500.0))
        factor = float(ctx.get('GRADE_EXP_FACTOR', 1.07))
    except Exception:
        base = 500.0
        factor = 1.07
    
    # Color constants
    GREEN = "\033[32m"
    ORANGE = "\033[38;5;208m"
    WHITE = "\033[37m"
    GOLD = "\033[38;5;220m"
    RED = "\033[31m"
    DARK_GRAY = "\033[90m"
    
    # If below base, D
    if xp < int(base):
        return ('D', GREEN)
    
    # Build thresholds for C1, C2, B1, B2, A1, A2, S using configurable factor
    labels = ['C1', 'C2', 'B1', 'B2', 'A1', 'A2', 'S']
    exps = [(factor ** n) for n in range(len(labels))]
    thresholds = [int(round(base ** e)) for e in exps]
    
    # Find highest label satisfied
    for lbl, thr in reversed(list(zip(labels, thresholds))):
        if xp >= thr:
            # Map letter to colour by prefix
            prefix = lbl[0]
            color_map = {'D': GREEN, 'C': ORANGE, 'B': WHITE, 'A': GOLD, 'S': RED}
            return (lbl, color_map.get(prefix, DARK_GRAY))
    
    # If not matched, fallback to C1
    return ('C1', ORANGE)

def compute_prestige(ctx):
    """Compute prestige based on bird grades."""
    try:
        per_bird_xp = ctx.get('per_bird_xp', [])
        grade_value_map = {
            'D': 0, 'C1': 1, 'C2': 2,
            'B1': 3, 'B2': 4,
            'A1': 5, 'A2': 6,
            'S': 7
        }
        total = 0
        for xp in per_bird_xp:
            grade, _ = compute_grade_from_xp(xp, ctx)
            total += grade_value_map.get(grade, 0)
        return total
    except Exception:
        return 0

def adjust_rarity_weights(base_weights, prestige):
    """
    Adjust rarity weights based on prestige.
    Higher prestige shifts distribution toward rarer items.
    """
    try:
        if prestige <= 0:
            return base_weights
        # Each prestige point shifts 1% from common to uncommon, uncommon to rare, rare to epic
        shift = min(prestige, 30)  # Cap at 30% shift
        adjusted = base_weights.copy()
        
        # Common loses, uncommon gains
        if len(adjusted) >= 2:
            loss = adjusted[0] * (shift / 100.0)
            adjusted[0] -= loss
            adjusted[1] += loss * 0.7  # 70% goes to uncommon
            if len(adjusted) >= 3:
                adjusted[2] += loss * 0.25  # 25% to rare
            if len(adjusted) >= 4:
                adjusted[3] += loss * 0.05  # 5% to epic
        
        return adjusted
    except Exception:
        return base_weights

def get_scared_frames(bird_idx, base_seconds, ctx):
    """Calculate scared duration in frames."""
    try:
        base_sleep = ctx.get('base_sleep', 0.2)
        return int(base_seconds / base_sleep)
    except Exception:
        return int(base_seconds / 0.2)
    

# Loot selection logic with dynamic egg probability and new eggs
def choose_loot_type(rarity):
    # Count empty lanes (no bird)
    empty_lanes = [lane for lane in range(constants.NUM_LANES) if lane not in state.random_lanes or all(state.ball_lost[idx] or state.random_lanes[idx] != lane for idx in range(constants.NUM_BALLS))]
    num_empty = len(empty_lanes)
    # Egg probability by empty lanes (configurable EGG_PROBS)
    # Support either dict {empty_count: prob} or legacy list/tuple.
    egg_prob = 0.0
    if num_empty == 0:
        egg_prob = 0.0
    elif num_empty in constants.EGG_PROBS:
        egg_prob = float(constants.EGG_PROBS[num_empty])
    else:
        # Fallback: choose the highest defined key
        int_keys = sorted([k for k in constants.EGG_PROBS.keys() if isinstance(k, int)])
        egg_prob = float(constants.EGG_PROBS[int_keys[-1]])
        
    # Loot pool by rarity 
    if rarity == 'common':
        loot_pool = ['egg', 'wide_cursor', 'tailwind', 'shuffle']
    elif rarity == 'uncommon':
        loot_pool = ['egg', 'wide_cursor+', 'tailwind+', 'shuffle']
    elif rarity == 'rare':
        loot_pool = ['egg', 'wide_cursor++', 'tailwind++', 'shuffle+']
    else:  # epic
        loot_pool = ['egg', 'wide_cursor_max', 'tailwind_max', 'shuffle++']
    # Decide whether to drop an egg (based on empty lanes)
    if random.random() < egg_prob:
        # Egg selection by rarity (rare tier may include gold_egg)
        # We must respect on-field limits per bird TYPE to avoid overspawning

        def allowed(egg_name):
            bcol = constants.EGG_TO_COLOR.get(egg_name)
            if bcol is None:
                return True
            limit = constants.COLOR_LIMITS.get(bcol)
            if limit is None:
                return True
            # Count active birds of that color
            cnt = sum(1 for i in range(constants.NUM_BALLS) if not state.ball_lost[i] and state.ball_colors[i] == bcol)
            return cnt < limit

        # Candidate eggs and their base weights per rarity (weights are configurable)
        if rarity == 'common':
            rarity_data = constants.RARITY_EGGS_CANDIDATES.get('common', {})
            candidates = list(rarity_data.keys()) if isinstance(rarity_data, dict) else ['yellow_egg', 'red_egg', 'blue_egg']
            raw_weights = rarity_data if isinstance(rarity_data, dict) else constants.RARITY_WEIGHTS.get('common', {})
        elif rarity == 'uncommon':
            rarity_data = constants.RARITY_EGGS_CANDIDATES.get('uncommon', {})
            candidates = list(rarity_data.keys()) if isinstance(rarity_data, dict) else ['blue_egg', 'patchwork_egg', 'purple_egg']
            raw_weights = rarity_data if isinstance(rarity_data, dict) else constants.RARITY_WEIGHTS.get('uncommon', {})
        elif rarity == 'rare':
            rarity_data = constants.RARITY_EGGS_CANDIDATES.get('rare', {})
            candidates = list(rarity_data.keys()) if isinstance(rarity_data, dict) else ['white_egg', 'orange_egg', 'gold_egg']
            raw_weights = rarity_data if isinstance(rarity_data, dict) else constants.RARITY_WEIGHTS.get('rare', {})
        else:
            rarity_data = constants.RARITY_EGGS_CANDIDATES.get('epic', {})
            candidates = list(rarity_data.keys()) if isinstance(rarity_data, dict) else ['dinosaur_egg', 'glitch_egg']
            raw_weights = rarity_data if isinstance(rarity_data, dict) else constants.RARITY_WEIGHTS.get('epic', {})

        # Normalize raw_weights: support either dict {item: weight} or legacy list/tuple
        weights = [float(raw_weights.get(e, 1.0)) for e in candidates]

        # Filter by allowed eggs based on current field counts
        allowed_candidates = []
        allowed_weights = []
        for e, w in zip(candidates, weights):
            if allowed(e):
                allowed_candidates.append(e)
                allowed_weights.append(w)

        # If there are allowed egg candidates, pick one with weights
        if allowed_candidates:
            # Use random.choices to pick respecting weights
            return random.choices(allowed_candidates, weights=allowed_weights)[0]

        # No egg candidate is allowed due to on-field limits — fallback to non-egg loot
        non_egg = [p for p in loot_pool if p != 'egg']
        if not non_egg:
            # As ultimate fallback, return a safe common egg
            return 'yellow_egg'
        return random.choice(non_egg)
    else:
        # Return a non-egg loot (power-up)
        non_egg = [p for p in loot_pool if p != 'egg']
        if not non_egg:
            return 'yellow_egg'
        return random.choice(non_egg)

# Note: Most constants are now imported from constants.py at the top of the file
# Only special computed values and functions remain here

# Initialize all game state
state.init()


def set_ball_vy(idx, val):
    """Safely set vertical velocity for bird idx.

    When a PURPLE bird is actively charging (purple_state== 2) or is in the
    immediate post-fire protection window (state.purple_just_fired_frames > 0), we
    must avoid overwriting its stored vertical velocity to prevent flips and
    unintended motion. This helper centralizes that guard.
    """
    try:
        if 0 <= int(idx) < constants.NUM_BALLS:
            if state.purple_state[idx] == 2 or (state.purple_just_fired_frames and state.purple_just_fired_frames[idx] > 0):
                return
            state.ball_vy[idx] = val
    except Exception:
        try:
            # best-effort fallback
            state.ball_vy[idx] = val
        except Exception:
            pass

def reset_bird_power(idx):
    state.bird_power_used[idx] = False
    state.bird_power_uses[idx] = 0

def allow_consume_power(idx, allowed_uses=1):
    """Return True and consume one use if bird idx may use its power.

    allowed_uses is normally 1; for A-grade birds allowed_uses will be 2.
    """
    if state.bird_power_uses[idx] < allowed_uses:
        state.bird_power_uses[idx] += 1
        state.bird_power_used[idx] = True
        return True


def get_scared_frames(bird_idx, base_seconds=2.0):
    """Return number of frames for state.scared_birds for bird_idx.

    Base_seconds is the default duration in seconds. Birds with grade B1 or
    better (B1+, i.e. B1/B2/A1/A2/S) have the duration reduced by 1 second.
    Result is at least 1 frame.
    """
    label, _ = compute_grade_from_xp(state.per_bird_xp[bird_idx])
    # reduce by 1 second worth of frames if grade is B1 or better
    if not label.startswith('D') and not label.startswith('C'):
        base_seconds = max(1, base_seconds - 1.0)

    return max(1, int(float(base_seconds) / constants.BASE_SLEEP))


def transform_bird_to_s(bi):
    """If bird bi reached S grade, transform its color and mark it so it won't produce eggs.

    Mapping implemented:
      BLUE -> WHITE
      RED  -> ORANGE
      YELLOW -> GOLD

    This function is idempotent and safe to call repeatedly.
    """
    bi = int(bi)
    if bi < 0 or bi >= constants.NUM_BALLS:
        return

    if state.transformed_s[bi]:
        return

    label, _ = compute_grade_from_xp(state.per_bird_xp[bi])

    if label == 'S':
        old = state.ball_colors[bi]
        # Decide target color and speed
        target_color = None
        target_speed = None
        if old == BLUE:
            target_color = WHITE
            target_speed = int(constants.BALL_SPEEDS_DEFAULT.get('WHITE', 4))
        elif old == RED:
            target_color = ORANGE
            target_speed = int(constants.BALL_SPEEDS_DEFAULT.get('ORANGE', 5))
        elif old == YELLOW:
            target_color = GOLD
            target_speed = int(constants.BALL_SPEEDS_DEFAULT.get('GOLD', 6))
        # If we have a mapping, check limits before applying
        if target_color is not None:
            limit = constants.TRANSFORM_LIMITS.get(target_color, None)
            # Count active birds of target color (exclude this bird if it is not yet that color)
            cnt = 0
            for j in range(constants.NUM_BALLS):
                try:
                    if not state.ball_lost[j] and state.ball_colors[j] == target_color:
                        cnt += 1
                except Exception:
                    continue
            # If this bird itself is already the target color, include it in the count
            if state.ball_colors[bi] == target_color and not state.ball_lost[bi]:
                # cnt already includes it; nothing else to do
                pass

            # If limit is None (unlimited) or cnt < limit we can transform
            if limit is None or cnt < limit or (state.ball_colors[bi] == target_color):
                state.ball_colors[bi] = target_color
                if target_speed is not None:
                    state.ball_speeds[bi] = target_speed
                state.transformed_s[bi] = True
        else:
            state.transformed_s[bi] = True

def perform_shuffle(count: int):
    """Perform up to `count` smart swaps to compact birds toward the center.
    Algorithm (greedy):
    - Prefer moving outer birds into empty lanes close to center (lost slots)
    - If no empty lanes, swap an outer bird with an inner bird (closer to center)
    - If no better candidate exists, swap with a random other bird
    """
    center = 4
    moved_indices = set()
    used_lost_slots = set()
    for _ in range(max(0, int(count))):
        # Living bird indices not yet moved in this shuffle
        living = [i for i in range(constants.NUM_BALLS) if not state.ball_lost[i]]
        living_available = [i for i in living if i not in moved_indices]
        if len(living_available) <= 1:
            break

        # Pick the living bird farthest from center among those not yet moved
        living_sorted = sorted(living_available, key=lambda i: abs(state.random_lanes[i] - center), reverse=True)
        src_idx = living_sorted[0]
        src_lane = state.random_lanes[src_idx]

        # Find lost slots (empty lanes) and prefer the empty lane closest to center
        lost_slots = [i for i in range(constants.NUM_BALLS) if state.ball_lost[i] and i not in used_lost_slots]
        if lost_slots:
            empty_lanes = sorted([state.random_lanes[i] for i in lost_slots], key=lambda l: abs(l - center))
            target_lane = empty_lanes[0]
            # find the lost slot index that holds this lane (and not used yet)
            target_lost_idx = next((li for li in lost_slots if state.random_lanes[li] == target_lane), None)
            if target_lost_idx is not None:
                # Swap lanes between the source bird and the lost slot
                state.random_lanes[src_idx], state.random_lanes[target_lost_idx] = state.random_lanes[target_lost_idx], state.random_lanes[src_idx]
                # Update rendering columns and reset moved bird to starting line facing up
                state.ball_cols[src_idx] = constants.LANE_POSITIONS[state.random_lanes[src_idx]]
                state.ball_y[src_idx] = constants.STARTING_LINE
                set_ball_vy(src_idx, -1)
                reset_bird_power(src_idx)
                state.ball_cols[target_lost_idx] = constants.LANE_POSITIONS[state.random_lanes[target_lost_idx]]
                # Mark both slot and source as used so we don't move them twice
                moved_indices.add(src_idx)
                used_lost_slots.add(target_lost_idx)
                moved_indices.add(target_lost_idx)
                continue

        # No empty lanes: try to find an inner living bird to swap with
        inner_candidates = [i for i in living if i != src_idx and i not in moved_indices and abs(state.random_lanes[i] - center) < abs(src_lane - center)]
        if inner_candidates:
            # Choose the one closest to center
            tgt_idx = sorted(inner_candidates, key=lambda i: abs(state.random_lanes[i] - center))[0]
            state.random_lanes[src_idx], state.random_lanes[tgt_idx] = state.random_lanes[tgt_idx], state.random_lanes[src_idx]
            # Update both moved birds' rendering cols and reset positions to starting line
            state.ball_cols[src_idx] = constants.LANE_POSITIONS[state.random_lanes[src_idx]]
            state.ball_y[src_idx] = constants.STARTING_LINE
            set_ball_vy(src_idx, -1)
            reset_bird_power(src_idx)
            state.ball_cols[tgt_idx] = constants.LANE_POSITIONS[state.random_lanes[tgt_idx]]
            state.ball_y[tgt_idx] = constants.STARTING_LINE
            set_ball_vy(tgt_idx, -1)
            reset_bird_power(tgt_idx)
            # Mark moved indices so we don't select them again
            moved_indices.add(src_idx)
            moved_indices.add(tgt_idx)
            continue

        # Fallback: swap with a random different living bird
        other_candidates = [i for i in living if i != src_idx and i not in moved_indices]
        if not other_candidates:
            # nothing left to pick uniquely
            break
        other = random.choice(other_candidates)
        state.random_lanes[src_idx], state.random_lanes[other] = state.random_lanes[other], state.random_lanes[src_idx]
        state.ball_cols[src_idx] = constants.LANE_POSITIONS[state.random_lanes[src_idx]]
        state.ball_y[src_idx] = constants.STARTING_LINE
        set_ball_vy(src_idx, -1)
        reset_bird_power(src_idx)
        state.ball_cols[other] = constants.LANE_POSITIONS[state.random_lanes[other]]
        state.ball_y[other] = constants.STARTING_LINE
        set_ball_vy(other, -1)
        reset_bird_power(other)
        moved_indices.add(src_idx)
        moved_indices.add(other)

def calculate_level_threshold(level):
    """Calculate score threshold for given level"""
    # Use configurable game level progression constants
    base = float(constants.LEVEL_SCORE_BASE)
    factor = float(constants.LEVEL_SCORE_FACTOR)
    return int(base ** (factor ** (level + 1)))

# ---------------- Level-from-state.score helpers ----------------
def compute_level_from_score(sc):
    # Start from state.level 1 and find highest state.level such that state.score >= threshold
    lvl = 1
    while True:
        next_thr = calculate_level_threshold(lvl + 1)
        if sc >= next_thr:
            lvl += 1
            continue
        break
    return lvl

def compute_grade_from_xp(xp):
    """Return a (symbol, color) tuple for the given XP value.

    Small, deterministic mapping so the floor shows the bird's current grade.
    """
    xp = int(float(xp))

    # Use configurable progression constants
    base = float(constants.XP_BASE)
    factor = float(constants.GRADE_EXP_FACTOR)

    # If below base, D
    if xp < int(base):
        return ('D', GREEN)

    # Build thresholds for C1, C2, B1, B2, A1, A2, S using configurable factor
    labels = ['C1', 'C2', 'B1', 'B2', 'A1', 'A2', 'S']
    exps = [ (factor ** n) for n in range(len(labels)) ]
    thresholds = [ int(round(base ** e)) for e in exps ]

    # Find highest label satisfied
    for lbl, thr in reversed(list(zip(labels, thresholds))):
        if xp >= thr:
            # Map letter to colour by prefix
            prefix = lbl[0]
            color_map = {'D': GREEN, 'C': ORANGE, 'B': WHITE, 'A': GOLD, 'S': RED}
            return (lbl, color_map.get(prefix, DARK_GRAY))

    # If not matched, fallback to C1
    return ('C1', ORANGE)


def add_score(amount, by_bird=None):
    """Add to global state.score. If by_bird is provided (bird index), also award XP to that bird.

    amount may be non-integer; XP is credited as int(amount).
    """

    # Defensive parsing of amount: preserve original for XP awarding
    raw_amount = amount
    # Try to interpret as float for state.score math
    amt = float(amount)

    # Compute prestige multiplier (based on birds currently on field)
    prestige = compute_prestige()

    # Add multiplied state.score (only state.score is affected by prestige)
    state.score += amt * prestige

    # Award XP when we know which bird earned it (bird index), also award XP to that bird.
    if by_bird is not None and 0 <= int(by_bird) < len(state.per_bird_xp):
        # simple XP model: 1 XP per point of raw amount
        xp_award = int(max(0, int(raw_amount)))
        state.per_bird_xp[int(by_bird)] += xp_award
        # Check for S-grade transformation after XP award
        transform_bird_to_s(int(by_bird))

    achievements.check_achievements_event('score', score=state.score, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=functions.background_call)

def award_xp(bird_idx, xp_amount):
    """Best-effort: credit XP to a bird without affecting global state.score.

    bird_idx may be invalid; this function is defensive.
    """
    bi = int(bird_idx)
    if bi < 0 or bi >= len(state.per_bird_xp):
        return
    state.per_bird_xp[bi] += int(max(0, int(xp_amount)))
    # After awarding XP, check for S-grade transformation
    transform_bird_to_s(bi)

def compute_prestige():
    """Compute prestige multiplier based on grades of birds currently on the field.

    Base prestige is 1. For each active (not-lost) bird, add the modifier for its grade:
      D: 0
      C1: 0.03125
      C2: 0.0625
      B1: 0.125
      B2: 0.25
      A1: 0.5
      A2: 1
      S: 5

    Returns a float >= 1.0
    """
    total = 1.0

    for i in range(len(state.per_bird_xp)):
        # Skip lost birds
        if state.ball_lost[i]:
                continue
        # GLITCH birds contribute a random prestige between 1 and 7 each computation
        if state.ball_colors[i] == GLITCH:
            try:
                total += float(random.randint(1, 7))
                continue
            except Exception:
                # fallback to normal mapping
                pass

        label, _ = compute_grade_from_xp(state.per_bird_xp[i])

        # If compute_grade returned multi-char like 'C1' handle it, otherwise
        # accept single-letter 'D'/'S'
        add = constants.PRESTIGE_MODIFIERS.get(label, 0.0)
        # If label is like 'C' fallback to C1 modifier (defensive)
        if add == 0.0 and isinstance(label, str) and len(label) == 1:
            add = constants.PRESTIGE_MODIFIERS.get(label, 0.0)
        total += add

    return float(total)


def adjust_rarity_weights(base_weights, prestige):
    """Adjust and normalize rarity weights according to prestige.

    Algorithm:
    - Multiply each base weight by factor = (1 + prestige * 0.1).
    - If the total exceeds 100, remove the excess starting from the most
      common bucket (index 0) so higher rarities are preserved.
    - If the total is below 100, add the missing amount to the common bucket.
    Returns a new list of floats that sum to 100.
    """
    factor = 1.0 + float(prestige) * float(constants.PRESTIGE_RARITY_FACTOR)

    new = [float(w) * factor for w in base_weights]
    total = sum(new)

    # Defensive: if total is essentially zero, fallback to equal distribution
    if total <= 0.0:
        n = len(base_weights)
        return [100.0 / n] * n

    # If total greater than 100, subtract excess from common-first
    if total > 100.0:
        excess = total - 100.0
        for i in range(len(new)):
            if excess <= 0:
                break
            take = min(excess, new[i])
            new[i] -= take
            excess -= take
    elif total < 100.0:
        # Add deficit to common to ensure sum == 100
        deficit = 100.0 - total
        new[0] += deficit

    # Final normalization (small float rounding adjustments)
    tot = sum(new)
    if abs(tot - 100.0) > 1e-6 and tot > 0:
        scale = 100.0 / tot
        new = [w * scale for w in new]

    return new


def deduct_score(amount):

    state.score -= amount
    if state.score < 0:
        state.score = 0
    # Re-evaluate state.score-based achievements when state.score changes
    achievements.check_achievements_event('score', score=state.score, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=functions.background_call)

def cleanup():
    global old_settings, old_flags
    print("\033[?25h", end="", flush=True)
    # Music engine removed: nothing to stop here
    # Attempt to cleanly shutdown any network/client resources (best-effort).
    # This prevents urllib3/requests atexit callbacks from raising during interpreter shutdown.
    if firebase_client:
        # Prefer an explicit close() method if provided by the firebase wrapper
        closer = getattr(firebase_client, 'close', None)
        if callable(closer):
            closer()
        # Try common session attributes that wrappers might expose
        sess = getattr(firebase_client, 'session', None)
        if sess is not None:
            sess.close()

        pool = getattr(firebase_client, 'pool', None)
        if pool is not None:
            pool.close()

        # As a last resort, attempt to close any 'requests' Session attributes
        for name in ('requests_session', 'req_session', 'session'):
            s = getattr(firebase_client, name, None)
            if s is not None:
                s.close()

    if os.name != 'nt' and old_settings is not None:
        try:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            fcntl.fcntl(sys.stdin, fcntl.F_SETFL, old_flags)
        except Exception:
            pass
    
    os.system('cls' if os.name == 'nt' else 'clear')

def setup():
    global old_settings, old_flags
    print("\033[?25l", end="", flush=True)
    if os.name != 'nt':
        old_settings = termios.tcgetattr(sys.stdin)
        old_flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        tty.setraw(sys.stdin.fileno())
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)
    os.system('cls' if os.name == 'nt' else 'clear')

# --- Gestione auto-bounce CLOCKWORK ---
def handle_clockwork_auto_bounce():
    # Bounce esattamente dove spawnano gli uccelli (constants.STARTING_LINE)
    for i, c in enumerate(state.ball_colors):
        # Treat CLOCKWORK birds as special: only auto-bounce if they still have charge > 0
        if c == CLOCKWORK and not state.ball_lost[i] and state.ball_vy[i] == 1 and state.ball_y[i] >= constants.STARTING_LINE:
            charge = state.clockwork_charge.get(i, None)
            # If charge is None, initialize to configured initial charge (safe fallback)
            if charge is None:
                charge = constants.clockwork.initial_charge
                state.clockwork_charge[i] = constants.clockwork.initial_charge
            if charge > 0:
                state.ball_y[i] = constants.STARTING_LINE
                set_ball_vy(i, -1)
                reset_bird_power(i)
            # if charge == 0, let it fall through (no auto-bounce)


def get_affected_lanes():
    """Return list of lanes affected by current cursor (considers wide cursor powerup)."""
    if state.powerups['wide_cursor_active']:
        lanes = []
        half_width = state.powerups['wide_cursor_lanes'] // 2
        for offset in range(-half_width, half_width + 1):
            lane = state.player_lane + offset
            if 0 <= lane <= 8:
                lanes.append(lane)
        return lanes
    else:
        return [state.player_lane]


def find_bird_in_lane(lane):
    """Return bird index for given lane, or -1 if no bird found."""
    return state.random_lanes.index(lane) if lane in state.random_lanes else -1


def is_orange_egg_state(bird_idx):
    """Check if bird is in orange egg dormant state."""
    return (state.ball_colors[bird_idx] == ORANGE and 
            state.ball_speeds[bird_idx] == 0 and 
            state.ball_y[bird_idx] == 999)


def try_glitch_bounce(bird_idx):
    """Attempt to bounce GLITCH bird (has chance to ignore). Returns True if bounced."""
    if state.ball_colors[bird_idx] == GLITCH:
        if random.random() < float(constants.glitch.bounce_ignore_chance):
            return False  # ignored bounce
        else:
            functions.set_ball_vy(bird_idx, -1)
            return True
    else:
        functions.set_ball_vy(bird_idx, -1)
        return True


def get_color_name(bird_color):
    """Map bird color escape code to simple name string."""
    color_map = {
        YELLOW: 'yellow',
        RED: 'red',
        BLUE: 'blue',
        WHITE: 'white',
        PURPLE: 'purple',
        ORANGE: 'orange',
        STEALTH: 'stealth',
        CLOCKWORK: 'clockwork',
        GOLD: 'gold',
        PATCHWORK: 'patchwork',
        COOKIE: 'cookie',
        DINOSAUR: 'dinosaur',
        GLITCH: 'glitch'
    }
    return color_map.get(bird_color, 'unknown')


def reset_bird_to_start(bird_idx):
    """Reset bird to starting line position facing up."""
    state.ball_y[bird_idx] = constants.STARTING_LINE
    functions.set_ball_vy(bird_idx, -1)
    functions.reset_bird_power(bird_idx)


def bounce_bird(bird_idx, apply_boost=False):
    """Bounce a bird up and optionally apply bounce boost."""
    functions.set_ball_vy(bird_idx, -1)
    functions.reset_bird_power(bird_idx)
    
    # Handle CLOCKWORK charge restoration
    if state.ball_colors[bird_idx] == CLOCKWORK:
        c = state.clockwork_charge.get(bird_idx, None)
        if c is None:
            state.clockwork_charge[bird_idx] = constants.clockwork.initial_charge
            c = constants.clockwork.initial_charge
        if c == 0:
            state.clockwork_charge[bird_idx] = 1
            state.ball_speeds[bird_idx] = 1
    
    # Apply bounce boost if active
    if apply_boost and state.powerups['bounce_boost_active'] and bird_idx not in state.speed_boosts:
        boost_frames = int(state.powerups['bounce_boost_duration'] / constants.BASE_SLEEP)
        state.speed_boosts[bird_idx] = boost_frames
    
    # Record bounce action for combos
    achievements.append_recent_action('bounce', lane=state.random_lanes[bird_idx], 
                                     color=state.ball_colors[bird_idx], frame_count=state.frame_count)

def can_bird_bounce(bird_idx):
    """Check if bird can be bounced (not scared, except PURPLE)."""
    if bird_idx in state.scared_birds and state.ball_colors[bird_idx] != PURPLE:
        return False
    return True


def update_orange_egg_lane(bird_idx, new_lane):
    """Update orange egg loot position when bird lane changes."""
    if is_orange_egg_state(bird_idx):
        old_lane = state.random_lanes[bird_idx]
        for loot in state.loot_items:
            if (loot['type'] == 'orange_egg' and 
                loot['x_pos'] == constants.LANE_POSITIONS[old_lane]):
                loot['x_pos'] = constants.LANE_POSITIONS[new_lane]
                break


def swap_bird_lanes(bird_idx1, bird_idx2):
    """Swap lane assignments for two birds and update positions."""
    # Update orange egg positions before swap
    update_orange_egg_lane(bird_idx1, state.random_lanes[bird_idx2])
    update_orange_egg_lane(bird_idx2, state.random_lanes[bird_idx1])
    
    # Swap lanes
    state.random_lanes[bird_idx1], state.random_lanes[bird_idx2] = \
        state.random_lanes[bird_idx2], state.random_lanes[bird_idx1]
    
    # Update column positions
    state.ball_cols[bird_idx1] = constants.LANE_POSITIONS[state.random_lanes[bird_idx1]]
    state.ball_cols[bird_idx2] = constants.LANE_POSITIONS[state.random_lanes[bird_idx2]]
    
    # Reset birds to start if not lost and not in egg state
    for bird_idx in [bird_idx1, bird_idx2]:
        if not state.ball_lost[bird_idx] and not is_orange_egg_state(bird_idx):
            reset_bird_to_start(bird_idx)


def find_adjacent_birds(bird_lane, offsets=[-1, 1]):
    """Find birds in adjacent lanes. Returns list of (lane, bird_idx) tuples."""
    adjacent = []
    for offset in offsets:
        adj_lane = bird_lane + offset
        if 0 <= adj_lane < 9:
            bird_idx = find_bird_in_lane(adj_lane)
            if bird_idx >= 0:
                adjacent.append((adj_lane, bird_idx))
    return adjacent

def spawn_bird_from_egg(bird_color, loot_type):
    """Spawn a new bird from an egg in the first available empty slot.
    
    Args:
        bird_color: The color constant for the bird (e.g., YELLOW, RED, BLUE)
        loot_type: The egg type string (e.g., 'yellow_egg', 'clockwork_egg')
    
    Returns:
        True if bird was spawned, False if no empty slots available
    """
    for idx in range(constants.NUM_BALLS):
        if state.ball_lost[idx]:
            state.ball_lost[idx] = False
            state.ball_colors[idx] = bird_color
            
            # Get color name for speed lookup
            cname = constants.COLOR_NAME_MAP.get(bird_color, loot_type.replace('_egg', '').upper())
            state.ball_speeds[idx] = int(constants.BALL_SPEEDS_DEFAULT.get(cname, 3))
            
            # Special initialization for CLOCKWORK birds
            if bird_color == CLOCKWORK:
                state.clockwork_charge[idx] = constants.clockwork.initial_charge
            
            # Position bird at starting line facing up
            state.ball_y[idx] = constants.STARTING_LINE
            set_ball_vy(idx, -1)
            
            # Restore life and handle S-grade transformation
            state.lives += 1
            state.transformed_s[idx] = False
            transform_bird_to_s(idx)
            
            return True
    return False