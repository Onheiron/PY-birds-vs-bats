#!/usr/bin/env python3
PURPLE = "\033[38;5;135m"  # Viola
ORANGE = "\033[38;5;208m"  # Arancione
PATCHWORK = "\033[38;5;202m"  # Patchwork bird color (distinct escape)
import sys
import time
import os
import random
try:
    import firebase_client
except Exception:
    firebase_client = None
import threading


def _safe_call(func, *a, **kw):
    try:
        func(*a, **kw)
    except Exception:
        pass


def background_call(func, *a, **kw):
    try:
        t = threading.Thread(target=_safe_call, args=(func,)+a, kwargs=kw, daemon=True)
        t.start()
    except Exception:
        pass
# Loot selection logic with dynamic egg probability and new eggs
def choose_loot_type(rarity):
    # Count empty lanes (no bird)
    empty_lanes = [lane for lane in range(9) if lane not in random_lanes or all(ball_lost[idx] or random_lanes[idx] != lane for idx in range(NUM_BALLS))]
    num_empty = len(empty_lanes)
    # Egg probability by empty lanes
    egg_probs = [0, 0.25, 0.35, 0.45, 0.55]
    egg_prob = egg_probs[num_empty] if num_empty <= 4 else 0.55
    # If no empty lane, egg_prob = 0
    if num_empty == 0:
        egg_prob = 0
    # Loot pool by rarity
    if rarity == 'common':
        loot_pool = ['egg', 'wide_cursor', 'tailwind', 'shuffle']
    elif rarity == 'uncommon':
        loot_pool = ['egg', 'wide_cursor+', 'tailwind+', 'shuffle+']
    elif rarity == 'rare':
        loot_pool = ['egg', 'wide_cursor++', 'tailwind++', 'shuffle++']
    else:  # epic
        loot_pool = ['egg', 'wide_cursor_max', 'tailwind_max', 'shuffle_max']
    # Decide whether to drop an egg (based on empty lanes)
    if random.random() < egg_prob:
        # Egg selection by rarity (rare tier may include gold_egg)
        # We must respect on-field limits per bird TYPE to avoid overspawning
        # Map egg name -> bird color constant
        egg_to_color = {
            'yellow_egg': YELLOW,
            'red_egg': RED,
            'blue_egg': BLUE,
            'white_egg': WHITE,
            'clockwork_egg': CLOCKWORK,
            'gold_egg': GOLD,
            'stealth_egg': STEALTH,
            'patchwork_egg': PATCHWORK,
            'purple_egg': PURPLE,
            'orange_egg': ORANGE,
        }

        # Limits by category (None = unlimited)
        color_limits = {
            YELLOW: None,
            RED: None,
            BLUE: None,
            PATCHWORK: 2,
            PURPLE: 2,
            CLOCKWORK: 2,
            GOLD: 1,
            STEALTH: 1,
            WHITE: 1,
            ORANGE: 1,
        }

        def allowed(egg_name):
            try:
                bcol = egg_to_color.get(egg_name)
                if bcol is None:
                    return True
                limit = color_limits.get(bcol)
                if limit is None:
                    return True
                # Count active birds of that color
                cnt = sum(1 for i in range(NUM_BALLS) if not ball_lost[i] and ball_colors[i] == bcol)
                return cnt < limit
            except Exception:
                return True

        # Candidate eggs and their base weights per rarity
        if rarity == 'common':
            candidates = ['yellow_egg', 'clockwork_egg']
            weights = [70, 30]
        elif rarity == 'uncommon':
            candidates = ['red_egg', 'blue_egg', 'patchwork_egg', 'purple_egg']
            weights = [30, 30, 20, 20]
        elif rarity == 'rare':
            candidates = ['blue_egg', 'clockwork_egg', 'gold_egg', 'stealth_egg']
            weights = [40, 30, 15, 15]
        else:
            candidates = ['white_egg', 'orange_egg']
            weights = [50, 50]

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
if os.name == 'nt':
    import msvcrt
else:
    import tty
    import termios
    import fcntl

# Configuration
# Game box: 9 lanes × 5 chars wide = 45 chars width
# Height set to fit in standard terminal (including header and footer)
WIDTH = 45
HEIGHT = 30  # Actual game area, total display ~40 lines
NUM_BALLS = 9  # Total birds: 2 blue + 3 red + 4 yellow

# Bird sprites - two frames for animation (compact version)
BIRD_UP_1 = [
    " . ",
    '/W\\',
]
BIRD_UP_2 = [
    "_._",
    " W ",
]
BIRD_DOWN_1 = [
    "\\M/",
    " ' ",
]
BIRD_DOWN_2 = [
    "_M_",
    " ' ",
]

# PATCHWORK bird sprites - mixes characters (. ' \ / M W) across frames
BIRD_PATCH_UP_1 = [
    " . ",
    "\\M/",
]
BIRD_PATCH_UP_2 = [
    " ' ",
    "/W\\",
]
BIRD_PATCH_DOWN_1 = [
    "\\M/",
    " ' ",
]
BIRD_PATCH_DOWN_2 = [
    "/W\\",
    " . ",
]

# ANSI colors
RED = "\033[31m"
GREEN = "\033[32m"
BLUE = "\033[34m"
CYAN = "\033[96m"  # Light blue for blue bird power
YELLOW = "\033[38;5;220m"  # Darker yellow (256-color palette)
WHITE = "\033[97m"  # Bright white for legendary birds
# Use explicit 256/truecolor escapes to ensure consistent dark gray and black
DARK_GRAY = "\033[38;5;240m"  # Dark gray (visible on dark backgrounds)
CLOCKWORK = "\033[38;5;244m"  # Medium grey (CLOCKWORK color)
RESET = "\033[0m"
GOLD = "\033[38;5;228m"  # Bold truecolor gold (very bright) - falls back on terminals without truecolor
# Use 256-color black to ensure compatibility (some terminals don't honor truecolor)
BLACK = "\033[38;5;16m"
STEALTH = "STEALTH"  # Sentinel for stealth bird type (rendered specially)

# Game version (update this when releasing a new build)
GAME_VERSION = "0.5.0"

# Obstacle tiers: brown to bright green (4 tiers)
# HP: 4, 6, 10, 16
OBSTACLE_TIER1 = "\033[38;5;94m"   # Dark brown (low saturation, low brightness)
OBSTACLE_TIER2 = "\033[38;5;100m"  # Brown-olive (moving towards green)
OBSTACLE_TIER3 = "\033[38;5;106m"  # Olive-green (medium green)
OBSTACLE_TIER4 = "\033[38;5;46m"   # Bright lime green (high saturation, high brightness)

# Bat tiers: dark blue-purple to shocking bright purple (4 tiers)
# HP: 32, 64, 128, 256
BAT_TIER1 = "\033[38;5;54m"   # Dark blue-purple (low saturation, low brightness)
BAT_TIER2 = "\033[38;5;92m"   # Medium purple (increased saturation)
BAT_TIER3 = "\033[38;5;129m"  # Bright purple (high saturation)
BAT_TIER4 = "\033[38;5;201m"  # Shocking magenta-purple (maximum saturation and brightness)

# Bat sprites - two frames for animation (compact version)
BAT_FRAME_1 = [
    " _ ^^ _",
    "/|(;;)|\\",
]
BAT_FRAME_2 = [
    "__ ^^ __",
    " /(;;)\\",
]

# Background pattern
BG_PATTERN = "/\\/\\/\\"

# Obstacle sprites - single line, compact
OBSTACLE_SPRITE = [
    "***"
]

# Color helpers: map HP ratio to RGB truecolor escape
def _rgb_escape(r: int, g: int, b: int) -> str:
    # Decide if terminal likely supports truecolor (COLORTERM hint).
    try:
        ct = os.environ.get('COLORTERM', '').lower()
    except Exception:
        ct = ''
    truecolor = ct in ('truecolor', '24bit')

    # Clamp values
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))

    if truecolor:
        return f"\033[38;2;{r};{g};{b}m"

    # Fallback to 256-color approximation: map RGB -> 6x6x6 cube index
    def _rgb_to_256(rr, gg, bb):
        # map 0-255 -> 0-5
        r6 = int(rr * 5 / 255)
        g6 = int(gg * 5 / 255)
        b6 = int(bb * 5 / 255)
        return 16 + (36 * r6) + (6 * g6) + b6

    code = _rgb_to_256(r, g, b)
    return f"\033[38;5;{code}m"

def _color_from_hp(base_rgb: tuple, hp: int, max_hp: int) -> str:
    hp_percentage = hp / max_hp if max_hp > 0 else 0
    try:
        r = int(base_rgb[0] * hp_percentage)
        g = int(base_rgb[1] * hp_percentage)
        b = int(base_rgb[2] * hp_percentage)
    except Exception:
        r = g = b = 0
    return _rgb_escape(r, g, b)


def _render_patchwork_line(line: str) -> str:
    """Return a string where each character in `line` is colored in a repeating patchwork pattern.

    The returned string does NOT include a cursor positioning escape; caller should place it.
    A final RESET is appended.
    """
    try:
        patch_colors = [RED, YELLOW, BLUE, GREEN, PURPLE, ORANGE, GOLD, CYAN, WHITE]
        parts = []
        for i, ch in enumerate(line):
            # Color each character; keep spacing visible (coloring spaces is acceptable here)
            parts.append(f"{patch_colors[i % len(patch_colors)]}{ch}")
        return "".join(parts) + RESET
    except Exception:
        # Fallback: return unmodified line with default reset
        return line + RESET


def _render_clockwork_line(line: str, charge: int, blink_on: bool) -> str:
    """Render a single sprite line for CLOCKWORK birds.

    Only the characters '.' and "'" are colored according to charge and blink state.
    Other characters are rendered in the CLOCKWORK base color. A RESET is appended.
    """
    try:
        # Determine the active highlight color based on charge
        if charge is None:
            charge = 2
        if charge > 1:
            hl = GREEN
        elif charge == 1:
            hl = YELLOW
        else:
            hl = RED

        parts = []
        for ch in line:
            if ch in ('.', "'"):
                # Blink: when blink_on is False render as dark gray, else use highlight
                parts.append((hl if blink_on else DARK_GRAY) + ch)
            else:
                parts.append(CLOCKWORK + ch)
        return "".join(parts) + RESET
    except Exception:
        return CLOCKWORK + line + RESET

# Base colors (full HP)
_BATS_BASE_RGB = (255, 0, 255)   # magenta FF00FF
_OBST_BASE_RGB = (0, 255, 0)     # green 00FF00

# Obstacle max HP by tier (used for color scaling)
_OBST_MAX_HP_BY_TIER = {1: 4, 2: 6, 3: 10, 4: 16}

# Lane positions - tight spacing, 3 chars wide + 1 char gap = 4 chars per lane
# Total: 9 lanes × 4 = 36 chars, centered in 45-char width: start at position 5
LANE_POSITIONS = [5, 9, 13, 17, 21, 25, 29, 33, 37]  # 9 lanes centered in game box

# Ball positions and velocities
ball_colors = [YELLOW, YELLOW, YELLOW, YELLOW, RED, RED, RED, BLUE, BLUE]  # 4 yellow, 3 red, 2 blue

# Randomize which bird goes to which lane
random.seed()
random_lanes = list(range(9))  # [0, 1, 2, 3, 4, 5, 6, 7, 8]
random.shuffle(random_lanes)  # Shuffle to randomize

ball_cols = [LANE_POSITIONS[random_lanes[i]] for i in range(NUM_BALLS)]
# All birds start at the same height, near the bottom (4 lines from bottom)
STARTING_LINE = HEIGHT - 4
ball_y = [STARTING_LINE] * NUM_BALLS
ball_vy = [-1] * NUM_BALLS
ball_lost = [False] * NUM_BALLS
bird_power_used = [False] * NUM_BALLS  # Track if bird used its special power while rising

# Assign speeds based on color (higher = faster)
# Blue: 4 (fastest), Red: 3, Yellow: 2, Obstacles: 1 (slowest)
ball_speeds = []
for color in ball_colors:
    if color == YELLOW:
        ball_speeds.append(2)  # Slower
    elif color == RED or color == PURPLE:
        ball_speeds.append(3)  # Fast
    elif color == BLUE:
        ball_speeds.append(4)  # Fastest
    elif color == WHITE:
        ball_speeds.append(4)  # Same as blue
    elif color == CLOCKWORK:
        ball_speeds.append(2)  # Come il giallo (CLOCKWORK)
    elif color == ORANGE:
        ball_speeds.append(5)  # Arancione = velocità 5
    elif color == PATCHWORK:
        ball_speeds.append(3)  # Patchwork bird = speed 3
    elif color == GOLD:
        ball_speeds.append(6)  # Gold special bird = velocità 6
    elif color == STEALTH:
        ball_speeds.append(3)  # Stealth bird = speed 3
    else:
        ball_speeds.append(2)  # Default per colori non previsti

# Red bird projectiles - list of {x_pos, y_pos, lane}
red_projectiles = []

# Background scroll offset
bg_offset = 0

# Obstacles - list of {lane, y_pos, tier, hp}
# tier: 1 (dark green, low HP), 2 (medium green, medium HP), 3 (bright green, high HP)
# HP determines how much damage before breaking
obstacles = []
obstacle_spawn_timer = 0

# Bats - list of {x_pos, y_pos, tier, hp, max_hp, direction, target_y}
# Bats move horizontally and can be hit by birds from adjacent lanes
bats = []
bat_spawn_timer = 0

# Loot items - list of {x_pos, y_pos, type}
loot_items = []

# Spawn queue - entities waiting to spawn when screen is not too crowded
spawn_queue = []

# Entity limit to prevent buffer overflow
MAX_ENTITIES = 50  # Max total entities on screen (excluding birds) - greatly increased due to compact sprites

# Speed boosts - track which birds have temp speed boosts {bird_index: remaining_frames}
speed_boosts = {}

# Scared birds - track which birds are scared {bird_index: remaining_frames}
# Scared birds: +1 speed when falling down, cannot be bounced up
scared_birds = {}
# Stealth timers - when a stealth bird activates its power it becomes tangible for N frames
stealth_timers = {}
# Store previous speeds for stealth birds when their power makes them temporarily faster
stealth_prev_speeds = {}
# Clockwork bird charge state: maps bird_index -> charge (int)
clockwork_charge = {}

# Power-ups state (using dict to avoid scope issues)
powerups = {
    'wide_cursor_active': False,
    'wide_cursor_frames': 0,
    'wide_cursor_lanes': 1,
    'bounce_boost_active': False,
    'bounce_boost_frames': 0,
    'bounce_boost_duration': 0,
    'suction_active': False,
    'suction_frames': 0,
    'suction_boost_duration': 0
}

# Tailwind power-up state (tiered). When active it boosts rising birds and
# penalizes falling birds. Values stored here and used per-frame.
powerups.setdefault('tailwind_active', False)
powerups.setdefault('tailwind_frames', 0)
powerups.setdefault('tailwind_up_bonus', 0)
powerups.setdefault('tailwind_down_penalty', 0)


def perform_shuffle(count: int):
    """Perform up to `count` smart swaps to compact birds toward the center.
    Algorithm (greedy):
    - Prefer moving outer birds into empty lanes close to center (lost slots)
    - If no empty lanes, swap an outer bird with an inner bird (closer to center)
    - If no better candidate exists, swap with a random other bird
    """
    try:
        center = 4
        moved_indices = set()
        used_lost_slots = set()
        for _ in range(max(0, int(count))):
            # Living bird indices not yet moved in this shuffle
            living = [i for i in range(NUM_BALLS) if not ball_lost[i]]
            living_available = [i for i in living if i not in moved_indices]
            if len(living_available) <= 1:
                break

            # Pick the living bird farthest from center among those not yet moved
            living_sorted = sorted(living_available, key=lambda i: abs(random_lanes[i] - center), reverse=True)
            src_idx = living_sorted[0]
            src_lane = random_lanes[src_idx]

            # Find lost slots (empty lanes) and prefer the empty lane closest to center
            lost_slots = [i for i in range(NUM_BALLS) if ball_lost[i] and i not in used_lost_slots]
            if lost_slots:
                empty_lanes = sorted([random_lanes[i] for i in lost_slots], key=lambda l: abs(l - center))
                target_lane = empty_lanes[0]
                # find the lost slot index that holds this lane (and not used yet)
                target_lost_idx = next((li for li in lost_slots if random_lanes[li] == target_lane), None)
                if target_lost_idx is not None:
                    # Swap lanes between the source bird and the lost slot
                    random_lanes[src_idx], random_lanes[target_lost_idx] = random_lanes[target_lost_idx], random_lanes[src_idx]
                    # Update rendering columns and reset moved bird to starting line facing up
                    try:
                        ball_cols[src_idx] = LANE_POSITIONS[random_lanes[src_idx]]
                        ball_y[src_idx] = STARTING_LINE
                        ball_vy[src_idx] = -1
                        bird_power_used[src_idx] = False
                    except Exception:
                        pass
                    try:
                        ball_cols[target_lost_idx] = LANE_POSITIONS[random_lanes[target_lost_idx]]
                    except Exception:
                        pass
                    # Mark both slot and source as used so we don't move them twice
                    moved_indices.add(src_idx)
                    used_lost_slots.add(target_lost_idx)
                    moved_indices.add(target_lost_idx)
                    continue

            # No empty lanes: try to find an inner living bird to swap with
            inner_candidates = [i for i in living if i != src_idx and i not in moved_indices and abs(random_lanes[i] - center) < abs(src_lane - center)]
            if inner_candidates:
                # Choose the one closest to center
                tgt_idx = sorted(inner_candidates, key=lambda i: abs(random_lanes[i] - center))[0]
                random_lanes[src_idx], random_lanes[tgt_idx] = random_lanes[tgt_idx], random_lanes[src_idx]
                try:
                    # Update both moved birds' rendering cols and reset positions to starting line
                    ball_cols[src_idx] = LANE_POSITIONS[random_lanes[src_idx]]
                    ball_y[src_idx] = STARTING_LINE
                    ball_vy[src_idx] = -1
                    bird_power_used[src_idx] = False
                except Exception:
                    pass
                try:
                    ball_cols[tgt_idx] = LANE_POSITIONS[random_lanes[tgt_idx]]
                    ball_y[tgt_idx] = STARTING_LINE
                    ball_vy[tgt_idx] = -1
                    bird_power_used[tgt_idx] = False
                except Exception:
                    pass
                # Mark moved indices so we don't select them again
                moved_indices.add(src_idx)
                moved_indices.add(tgt_idx)
                continue

            # Fallback: swap with a random different living bird
            try:
                other_candidates = [i for i in living if i != src_idx and i not in moved_indices]
                if not other_candidates:
                    # nothing left to pick uniquely
                    break
                other = random.choice(other_candidates)
                random_lanes[src_idx], random_lanes[other] = random_lanes[other], random_lanes[src_idx]
                try:
                    ball_cols[src_idx] = LANE_POSITIONS[random_lanes[src_idx]]
                    ball_y[src_idx] = STARTING_LINE
                    ball_vy[src_idx] = -1
                    bird_power_used[src_idx] = False
                except Exception:
                    pass
                try:
                    ball_cols[other] = LANE_POSITIONS[random_lanes[other]]
                    ball_y[other] = STARTING_LINE
                    ball_vy[other] = -1
                    bird_power_used[other] = False
                except Exception:
                    pass
                moved_indices.add(src_idx)
                moved_indices.add(other)
            except Exception:
                # Nothing left to do
                break
    except Exception:
        # Defensive: don't allow shuffle to crash the game
        pass

# Score system
score = 0
level = 1
lives = 5
game_over = False
swaps_used = 0
paused = False

def calculate_level_threshold(level):
    """Calculate score threshold for given level"""
    # Progressione più rapida ma equilibrata che continua all'infinito
    # Level 1: 1000
    # Level 2: 2500
    # Level 3: 5000
    # Level 4: 8500
    # Level 5: 13000
    # Level 6: 19000
    # Level 7: 27000
    # ecc...
    if level == 1:
        return 1000
    
    # Formula: ogni livello richiede (livello * 1500) punti in più rispetto al precedente
    total = 1000
    for i in range(2, level + 1):
        total += i * 1200
    return int(total)


# ---------------- Achievements ----------------
# Achievements are unlocked by events (score, swaps, loot, destroys).
achievements = {}
notifications = []  # list of (text, expire_frame)
# Notification display time in seconds (each achievement shown one at a time)
notification_duration_seconds = 3.0

# Additional achievement tracking state
power_usage_counters = {}        # e.g. {'power_yellow': 3}
recent_powers = []              # list of (power_name, frame_count) for synergy detection
top50_hold_frames = 0
top30_hold_frames = 0
original_alive_frames = 0
original_indices = list(range(NUM_BALLS))  # track which slots are the original birds
# Bat destroy counters (total + per-tier)
bat_destroy_counters = {'total': 0, 'tier1': 0, 'tier2': 0, 'tier3': 0, 'tier4': 0}

# Recent atomic actions for combo detection: list of dicts {action, frame, lane, color}
recent_actions = []
# Prevents repeating the same combo too frequently: map combo_id -> expire_frame
combo_cooldowns = {}

# Combo detection configuration
COMBO_WINDOW_FRAMES = 200  # time window to look back for sequences
YELLOW_BLUE_CHAIN_WINDOW = 60  # tighter window for the yellow->blue bounce chain

def init_achievements():
    """Define achievements with simple goals."""
    global achievements
    achievements = {
        # score milestones
        'score_1k': {'name': 'Novice', 'desc': 'Reach 1,000 points', 'unlocked': False, 'type': 'score', 'goal': 1000},
        'score_5k': {'name': 'Expert', 'desc': 'Reach 5,000 points', 'unlocked': False, 'type': 'score', 'goal': 5000},
        'score_20k': {'name': 'Veteran', 'desc': 'Reach 20,000 points', 'unlocked': False, 'type': 'score', 'goal': 20000},
        'score_70k': {'name': 'Legend', 'desc': 'Reach 70,000 points', 'unlocked': False, 'type': 'score', 'goal': 70000},
        # swaps
        'swap_1': {'name': 'Swapping Lanes', 'desc': 'Use swap once', 'unlocked': False, 'type': 'counter', 'key': 'swaps', 'goal': 1, 'progress': 0},
        'swap_10': {'name': 'Rearranger', 'desc': 'Use swap 10 times', 'unlocked': False, 'type': 'counter', 'key': 'swaps', 'goal': 10, 'progress': 0},
        'swap_100': {'name': 'OCD', 'desc': 'Use swap 100 times', 'unlocked': False, 'type': 'counter', 'key': 'swaps', 'goal': 100, 'progress': 0},
        # collect special eggs
        'collect_purple': {'name': 'The Fearless', 'desc': 'Collect a purple egg', 'unlocked': False, 'type': 'collect', 'loot': 'purple_egg'},
        'collect_clockwork': {'name': 'The Bot', 'desc': 'Collect a clockwork egg', 'unlocked': False, 'type': 'collect', 'loot': 'clockwork_egg'},
        'collect_white': {'name': 'The Phantom', 'desc': 'Collect a white egg', 'unlocked': False, 'type': 'collect', 'loot': 'white_egg'},
        'collect_orange': {'name': 'The Phoenix', 'desc': 'Collect an orange egg', 'unlocked': False, 'type': 'collect', 'loot': 'orange_egg'},
        # destroy counters
        'destroy_bat_orange': {'name': 'Phoenix Fire', 'desc': 'Destroy a bat with an orange bird', 'unlocked': False, 'type': 'special', 'event': 'destroy_bat_with_orange'},
        'destroy_obstacle_10': {'name': 'Breaker I', 'desc': 'Destroy 10 obstacles', 'unlocked': False, 'type': 'counter', 'key': 'obstacles_destroyed', 'goal': 10, 'progress': 0},
        'destroy_obstacle_100': {'name': 'Breaker II', 'desc': 'Destroy 100 obstacles', 'unlocked': False, 'type': 'counter', 'key': 'obstacles_destroyed', 'goal': 100, 'progress': 0},
        # power usage progressive achievements (per power)
        'power_yellow_1': {'name': 'Chirp', 'desc': 'Use Yellow power once', 'unlocked': False, 'type': 'counter', 'key': 'power_yellow', 'goal': 1, 'progress': 0},
        'power_yellow_10': {'name': 'Mockingbird', 'desc': 'Use Yellow power 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_yellow', 'goal': 10, 'progress': 0},
        'power_red_1': {'name': 'Ember', 'desc': 'Use Red power once', 'unlocked': False, 'type': 'counter', 'key': 'power_red', 'goal': 1, 'progress': 0},
        'power_red_10': {'name': 'Flame', 'desc': 'Use Red power 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_red', 'goal': 10, 'progress': 0},
        'power_blue_1': {'name': 'Sprint', 'desc': 'Use Blue power once', 'unlocked': False, 'type': 'counter', 'key': 'power_blue', 'goal': 1, 'progress': 0},
        'power_blue_10': {'name': 'Haste', 'desc': 'Use Blue power 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_blue', 'goal': 10, 'progress': 0},
        'power_white_1': {'name': 'Encourage!', 'desc': 'Use White power once', 'unlocked': False, 'type': 'counter', 'key': 'power_white', 'goal': 1, 'progress': 0},
        'power_white_10': {'name': 'Brave Bird', 'desc': 'Use White power 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_white', 'goal': 10, 'progress': 0},
        # synergies
        'synergy_pair': {'name': 'Get Along', 'desc': 'Trigger two different powers in quick succession', 'unlocked': False, 'type': 'special', 'event': 'synergy_pair'},
        'synergy_triple': {'name': 'Frenship Is Magic', 'desc': 'Trigger three different powers in quick succession', 'unlocked': False, 'type': 'special', 'event': 'synergy_triple'},
        # area hold achievements (frames)
        'hold_top50_200': {'name': 'High Skies', 'desc': 'Keep all birds in top 50% for a while', 'unlocked': False, 'type': 'area', 'key': 'top50', 'goal': 200},
        'hold_top30_400': {'name': 'Heavenly', 'desc': 'Keep all birds in top 30% for longer', 'unlocked': False, 'type': 'area', 'key': 'top30', 'goal': 400},
        # original birds survival
        'original_alive_300': {'name': 'Careful', 'desc': 'Keep original birds alive for some time', 'unlocked': False, 'type': 'original', 'goal': 300},
        'original_alive_700': {'name': 'Responsible', 'desc': 'Keep original birds alive for a long time', 'unlocked': False, 'type': 'original', 'goal': 700},
        'original_alive_2000': {'name': 'Survivalist', 'desc': 'Keep original birds alive for a very long time', 'unlocked': False, 'type': 'original', 'goal': 2000},
        # counts of single color
        'count_yellow_5': {'name': 'Yellow Flock', 'desc': 'Have 5 yellow birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'YELLOW', 'goal': 5},
        'count_yellow_7': {'name': 'Yellow Horde', 'desc': 'Have 7 yellow birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'YELLOW', 'goal': 7},
        'count_all_9': {'name': 'Nine of a Kind', 'desc': 'Have all 9 birds of the same color', 'unlocked': False, 'type': 'color_count_all', 'goal': 9},
        # Additional color-count achievements for other colors
        'count_red_5': {'name': 'Red Flock', 'desc': 'Have 5 red birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'RED', 'goal': 5},
        'count_red_7': {'name': 'Red Horde', 'desc': 'Have 7 red birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'RED', 'goal': 7},
        'count_blue_5': {'name': 'Blue Flock', 'desc': 'Have 5 blue birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'BLUE', 'goal': 5},
        'count_blue_7': {'name': 'Blue Horde', 'desc': 'Have 7 blue birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'BLUE', 'goal': 7},
        'count_white_5': {'name': 'White Flock', 'desc': 'Have 5 white birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'WHITE', 'goal': 5},
        'count_white_7': {'name': 'White Horde', 'desc': 'Have 7 white birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'WHITE', 'goal': 7},
        'count_clockwork_5': {'name': 'Clockwork Flock', 'desc': 'Have 5 clockwork birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'CLOCKWORK', 'goal': 5},
        'count_clockwork_7': {'name': 'Clockwork Horde', 'desc': 'Have 7 clockwork birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'CLOCKWORK', 'goal': 7},
        'count_purple_5': {'name': 'Purple Flock', 'desc': 'Have 5 purple birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'PURPLE', 'goal': 5},
        'count_purple_7': {'name': 'Purple Horde', 'desc': 'Have 7 purple birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'PURPLE', 'goal': 7},
        'count_orange_5': {'name': 'Orange Flock', 'desc': 'Have 5 orange birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'ORANGE', 'goal': 5},
        'count_orange_7': {'name': 'Orange Horde', 'desc': 'Have 7 orange birds on screen', 'unlocked': False, 'type': 'color_count', 'key': 'ORANGE', 'goal': 7},
        # Collect blue egg achievement (others already present)
        'collect_blue': {'name': 'Baby Blue', 'desc': 'Collect a blue egg', 'unlocked': False, 'type': 'collect', 'loot': 'blue_egg'},
        # Bat kills (total)
        'destroy_bat_10': {'name': 'Bat Slayer I', 'desc': 'Destroy 10 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed', 'goal': 10, 'progress': 0},
        'destroy_bat_100': {'name': 'Bat Slayer II', 'desc': 'Destroy 100 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed', 'goal': 100, 'progress': 0},
        # Per-tier bat kill achievements (tier-specific keys)
        'destroy_bat_t1_10': {'name': 'Tier1 Slayer', 'desc': 'Destroy 10 tier1 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier1', 'goal': 10, 'progress': 0},
        'destroy_bat_t2_10': {'name': 'Tier2 Slayer', 'desc': 'Destroy 10 tier2 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier2', 'goal': 10, 'progress': 0},
        'destroy_bat_t3_10': {'name': 'Tier3 Slayer', 'desc': 'Destroy 10 tier3 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier3', 'goal': 10, 'progress': 0},
        'destroy_bat_t4_1': {'name': 'Tier4 Hunter', 'desc': 'Destroy 1 tier4 bat', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier4', 'goal': 1, 'progress': 0},
        'destroy_bat_t4_10': {'name': 'Tier4 Slayer', 'desc': 'Destroy 10 tier4 bats', 'unlocked': False, 'type': 'counter', 'key': 'bats_destroyed_tier4', 'goal': 10, 'progress': 0},
        # Power usage achievements for cursor and new powers (tailwind, shuffle)
        'power_wide_cursor_1': {'name': 'Cursor Novice', 'desc': 'Use Wide Cursor once', 'unlocked': False, 'type': 'counter', 'key': 'power_wide_cursor', 'goal': 1, 'progress': 0},
        'power_wide_cursor_10': {'name': 'Cursor Expert', 'desc': 'Use Wide Cursor 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_wide_cursor', 'goal': 10, 'progress': 0},
        # Replaced bounce/suction achievements with tailwind and shuffle
        'power_tailwind_1': {'name': 'Tailwind Novice', 'desc': 'Use Tailwind once', 'unlocked': False, 'type': 'counter', 'key': 'power_tailwind', 'goal': 1, 'progress': 0},
        'power_tailwind_10': {'name': 'Tailwind Expert', 'desc': 'Use Tailwind 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_tailwind', 'goal': 10, 'progress': 0},
        'power_shuffle_1': {'name': 'Shuffle Novice', 'desc': 'Use Shuffle once', 'unlocked': False, 'type': 'counter', 'key': 'power_shuffle', 'goal': 1, 'progress': 0},
        'power_shuffle_10': {'name': 'Shuffle Expert', 'desc': 'Use Shuffle 10 times', 'unlocked': False, 'type': 'counter', 'key': 'power_shuffle', 'goal': 10, 'progress': 0},
        # Area hold smaller tiers
        'hold_top50_100': {'name': 'Sky Keepers I', 'desc': 'Keep all birds in top 50% for 100 frames', 'unlocked': False, 'type': 'area', 'key': 'top50', 'goal': 100},
        'hold_top30_200': {'name': 'Cloud Nine I', 'desc': 'Keep all birds in top 30% for 200 frames', 'unlocked': False, 'type': 'area', 'key': 'top30', 'goal': 200},
        # Configuration synergies and complex combos (special events to be emitted)
        'synergy_adjacent_red': {'name': 'Crimson Link', 'desc': 'Trigger adjacent red synergy', 'unlocked': False, 'type': 'special', 'event': 'synergy_adjacent_red'},
        'combo_fire_suction_bounce_fire': {'name': 'Elemental Chain', 'desc': 'Perform Fire → Suction → Bounce → Fire combo', 'unlocked': False, 'type': 'special', 'event': 'combo_fire_suction_bounce_fire'},
        'combo_yellow_blue_bounce_chain': {'name': 'Fearless Flip', 'desc': 'Perform the Yellow→Blue bounce chain combo', 'unlocked': False, 'type': 'special', 'event': 'combo_yellow_blue_bounce_chain'},
    }


def add_notification(text):
    """Add a short on-screen notification for a few frames."""
    # Compute duration in frames from seconds using current base_sleep
    try:
        frames = int(notification_duration_seconds / base_sleep)
        if frames <= 0:
            frames = 1
    except Exception:
        # Fallback to a sensible default if base_sleep not available yet
        frames = 40
    notifications.append((text, frame_count + frames))


def unlock_achievement(aid):
    global achievements
    a = achievements.get(aid)
    if not a or a.get('unlocked'):
        return False
    a['unlocked'] = True
    add_notification(f"Achievement unlocked: {a['name']}")
    # Try to sync/unlock achievement for remote user
    try:
        if firebase_client:
            try:
                background_call(firebase_client.unlock_achievement, aid)
            except Exception:
                pass
            try:
                background_call(firebase_client.log_event, 'achievement_unlocked', {'id': aid, 'name': a.get('name')})
            except Exception:
                pass
    except Exception:
        # defensive: don't let analytics break gameplay
        pass
    return True


def check_achievements_event(event, **kwargs):
    """Handle simple achievement triggers.

    event: 'score', 'swap', 'collect', 'destroy_bat', 'destroy_obstacle', 'destroy_bat_with_orange'
    """
    global achievements
    if event == 'score':
        sc = kwargs.get('score', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'score' and not a.get('unlocked'):
                if sc >= a.get('goal', 0):
                    unlock_achievement(aid)

    elif event == 'swap':
        swaps = kwargs.get('swaps', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'counter' and a.get('key') == 'swaps' and not a.get('unlocked'):
                if swaps >= a.get('goal', 0):
                    unlock_achievement(aid)

    elif event == 'collect':
        loot = kwargs.get('loot')
        for aid, a in achievements.items():
            if a.get('type') == 'collect' and not a.get('unlocked'):
                if a.get('loot') == loot:
                    unlock_achievement(aid)

    elif event == 'destroy_bat':
        # track a simple counter for obstacle/bat destroys if defined
        tier = kwargs.get('tier')
        # increment global counters
        try:
            bat_destroy_counters['total'] += 1
            if tier in (1, 2, 3, 4):
                bat_destroy_counters[f'tier{tier}'] += 1
        except Exception:
            pass

        for aid, a in achievements.items():
            if a.get('type') == 'counter' and not a.get('unlocked'):
                # generic total bat counter
                if a.get('key') == 'bats_destroyed':
                    a['progress'] = a.get('progress', 0) + 1
                    if a['progress'] >= a.get('goal', 0):
                        unlock_achievement(aid)
                # per-tier counters (keys like 'bats_destroyed_tier1')
                if tier in (1, 2, 3, 4) and a.get('key') == f'bats_destroyed_tier{tier}':
                    a['progress'] = a.get('progress', 0) + 1
                    if a['progress'] >= a.get('goal', 0):
                        unlock_achievement(aid)

    elif event == 'destroy_obstacle':
        for aid, a in achievements.items():
            if a.get('type') == 'counter' and a.get('key') == 'obstacles_destroyed' and not a.get('unlocked'):
                a['progress'] = a.get('progress', 0) + 1
                if a['progress'] >= a.get('goal', 0):
                    unlock_achievement(aid)

    elif event == 'power_used':
        # kwargs: power (string, lowercase color name)
        power = kwargs.get('power')
        lane = kwargs.get('lane')
        if not power:
            return
        key = f'power_{power}'
        # increment any matching counter achievements
        for aid, a in achievements.items():
            if a.get('type') == 'counter' and a.get('key') == key and not a.get('unlocked'):
                a['progress'] = a.get('progress', 0) + 1
                if a['progress'] >= a.get('goal', 0):
                    unlock_achievement(aid)

        # record recent powers for synergy detection
        recent_powers.append((power, frame_count))
        # keep recent_powers short (last 300 frames)
        recent_powers[:] = [(p, f) for (p, f) in recent_powers if frame_count - f <= 300]

        # detect pair/triple synergies
        distinct = set(p for (p, f) in recent_powers)
        if len(distinct) >= 2:
            check_achievements_event('synergy', combo=distinct)
        if len(distinct) >= 3:
            check_achievements_event('synergy', combo=distinct)

        # Also record fire actions for combo detection when appropriate
        # Treat red/purple powers as 'fire'
        if power in ('red', 'purple'):
            try:
                append_recent_action('fire', lane=lane, color=power.upper())
            except NameError:
                pass

    elif event == 'synergy':
        combo = kwargs.get('combo', set())
        # unlock pair/triple
        if len(combo) >= 3:
            for aid, a in achievements.items():
                if a.get('type') == 'special' and a.get('event') == 'synergy_triple' and not a.get('unlocked'):
                    unlock_achievement(aid)
        elif len(combo) >= 2:
            for aid, a in achievements.items():
                if a.get('type') == 'special' and a.get('event') == 'synergy_pair' and not a.get('unlocked'):
                    unlock_achievement(aid)

    elif event == 'area_hold':
        # kwargs: area ('top50'|'top30'), frames
        area = kwargs.get('area')
        frames = kwargs.get('frames', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'area' and a.get('key') == area and not a.get('unlocked'):
                if frames >= a.get('goal', 0):
                    unlock_achievement(aid)

    elif event == 'original_survive':
        frames = kwargs.get('frames', 0)
        for aid, a in achievements.items():
            if a.get('type') == 'original' and not a.get('unlocked'):
                if frames >= a.get('goal', 0):
                    unlock_achievement(aid)

    elif event == 'color_count':
        # kwargs: color (variable name string like 'YELLOW'), count
        color = kwargs.get('color')
        count = kwargs.get('count', 0)
        # check color_count achievements
        for aid, a in achievements.items():
            if a.get('type') == 'color_count' and a.get('key') == color and not a.get('unlocked'):
                if count >= a.get('goal', 0):
                    unlock_achievement(aid)
        # check all-same color
        if count >= 9:
            for aid, a in achievements.items():
                if a.get('type') == 'color_count_all' and not a.get('unlocked'):
                    if a.get('goal', 0) <= count:
                        unlock_achievement(aid)

    elif event == 'destroy_bat_with_orange':
        for aid, a in achievements.items():
            if a.get('type') == 'special' and a.get('event') == 'destroy_bat_with_orange' and not a.get('unlocked'):
                unlock_achievement(aid)


# ---------------- Combo detection (simple sequence detectors) ----------------
def append_recent_action(action, lane=None, color=None):
    """Append an atomic action for combo detection and prune old actions."""
    global recent_actions, frame_count
    recent_actions.append({'action': action, 'frame': frame_count, 'lane': lane, 'color': color})
    # prune to window
    recent_actions[:] = [a for a in recent_actions if frame_count - a['frame'] <= COMBO_WINDOW_FRAMES]
    # run detection
    detect_combos()


def detect_combos():
    """Look for configured combos in recent_actions and unlock achievements."""
    global recent_actions, combo_cooldowns, frame_count, achievements
    now = frame_count

    # Helper to unlock a special achievement by its event name
    def unlock_special(event_name, cooldown_frames):
        if combo_cooldowns.get(event_name, 0) > now:
            return False
        unlocked_any = False
        for aid, a in achievements.items():
            if a.get('type') == 'special' and a.get('event') == event_name and not a.get('unlocked'):
                unlock_achievement(aid)
                unlocked_any = True
        if unlocked_any:
            combo_cooldowns[event_name] = now + cooldown_frames
        return unlocked_any

    # Build a simple list of (action, frame, lane, color)
    seq = [(a['action'], a['frame'], a.get('lane'), a.get('color')) for a in recent_actions]

    # Combo A: fire -> suction -> bounce -> fire (in order, within window)
    pattern = ['fire', 'suction', 'bounce', 'fire']
    # find subsequence
    idx = 0
    positions = []
    for i, (act, fr, ln, clr) in enumerate(seq):
        if act == pattern[idx]:
            positions.append(i)
            idx += 1
            if idx == len(pattern):
                break
    if idx == len(pattern):
        start_frame = seq[positions[0]][1]
        end_frame = seq[positions[-1]][1]
        if end_frame - start_frame <= COMBO_WINDOW_FRAMES:
            unlock_special('combo_fire_suction_bounce_fire', COMBO_WINDOW_FRAMES)

    # Combo B: yellow bounce then adjacent blue bounce shortly after
    for i, a in enumerate(recent_actions):
        if a['action'] == 'bounce' and (a.get('color') == 'YELLOW' or a.get('color') == 'yellow' or a.get('color') is None):
            for j in range(i + 1, len(recent_actions)):
                b = recent_actions[j]
                if b['action'] == 'bounce' and (b.get('color') == 'BLUE' or b.get('color') == 'blue' or b.get('color') is None):
                    lane_a = a.get('lane') or 0
                    lane_b = b.get('lane') or 0
                    if abs(lane_a - lane_b) == 1 and (b['frame'] - a['frame']) <= YELLOW_BLUE_CHAIN_WINDOW:
                        unlock_special('combo_yellow_blue_bounce_chain', YELLOW_BLUE_CHAIN_WINDOW)
                        return



# ---------------- Level-from-score helpers ----------------
def compute_level_from_score(sc):
    # Start from level 1 and find highest level such that score >= threshold
    lvl = 1
    while True:
        next_thr = calculate_level_threshold(lvl + 1)
        if sc >= next_thr:
            lvl += 1
            continue
        break
    return lvl


def add_score(amount):
    global score
    score += amount
    check_achievements_event('score', score=score)


def deduct_score(amount):
    global score
    score -= amount
    if score < 0:
        score = 0
    # Re-evaluate score-based achievements when score changes
    check_achievements_event('score', score=score)

# Player
player_lane = 2
selected_lane = None  # Lane selected when space is pressed
last_space_state = False  # Track last frame's space state for edge detection

# Frame counter and speed settings
frame_count = 0
base_sleep = 0.2  # Starting speed
min_sleep = 0.02   # Maximum speed (lower = faster)

def cleanup():
    try:
        print("\033[?25h", end="", flush=True)
    except BlockingIOError:
        pass
    # Music engine removed: nothing to stop here
    if os.name != 'nt':
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, old_flags)
    os.system('cls' if os.name == 'nt' else 'clear')

def setup():
    print("\033[?25l", end="", flush=True)
    if os.name != 'nt':
        global old_settings, old_flags
        old_settings = termios.tcgetattr(sys.stdin)
        old_flags = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
        tty.setraw(sys.stdin.fileno())
        fcntl.fcntl(sys.stdin, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)
    os.system('cls' if os.name == 'nt' else 'clear')

def get_key():
    """Non-blocking key read for Windows and Unix"""
    if os.name == 'nt':
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'\xe0':  # Arrow key prefix
                key = msvcrt.getch()
                if key == b'K':  # Left
                    return 'LEFT'
                elif key == b'M':  # Right
                    return 'RIGHT'
                elif key == b'H':  # Up
                    return 'UP'
                elif key == b'P':  # Down
                    return 'DOWN'
            elif key == b' ':  # Space
                return 'SPACE'
            elif key == b'\x03':  # Ctrl+C
                return 'QUIT'
            return None
        return None
    else:
        # Unix/macOS version - truly non-blocking with fcntl
        try:
            key = sys.stdin.read(1)
            if key == '\x1b':  # Escape sequence
                # Try to read the rest of the sequence
                seq = key
                try:
                    seq += sys.stdin.read(2)
                except:
                    pass
                if seq == '\x1b[D':
                    return 'LEFT'
                elif seq == '\x1b[C':
                    return 'RIGHT'
                elif seq == '\x1b[A':
                    return 'UP'
                elif seq == '\x1b[B':
                    return 'DOWN'
            elif key == ' ':  # Space
                return 'SPACE'
            elif key == '\x03' or key == 'q':  # Ctrl+C or 'q'
                return 'QUIT'
            else:
                # Return other printable characters (letters, digits, etc.) so
                # the main loop can handle toggles like 'm' for music.
                try:
                    if key and len(key) == 1:
                        return key
                except Exception:
                    pass
        except:
            pass
        return None

# --- Colore e sprite CLOCKWORK ---
CLOCKWORK_BIRD_UP_1 = BIRD_UP_1
CLOCKWORK_BIRD_UP_2 = BIRD_UP_2
CLOCKWORK_BIRD_DOWN_1 = BIRD_DOWN_1
CLOCKWORK_BIRD_DOWN_2 = BIRD_DOWN_2

# --- Gestione auto-bounce CLOCKWORK ---
def handle_clockwork_auto_bounce():
    # Bounce esattamente dove spawnano gli uccelli (STARTING_LINE)
    for i, c in enumerate(ball_colors):
        # Treat CLOCKWORK birds as special: only auto-bounce if they still have charge > 0
        try:
            if c == CLOCKWORK and not ball_lost[i] and ball_vy[i] == 1 and ball_y[i] >= STARTING_LINE:
                charge = clockwork_charge.get(i, None)
                # If charge is None, initialize to 2 (safe fallback)
                if charge is None:
                    charge = 2
                    clockwork_charge[i] = 2
                if charge > 0:
                    ball_y[i] = STARTING_LINE
                    ball_vy[i] = -1
                    bird_power_used[i] = False
                # if charge == 0, let it fall through (no auto-bounce)
        except Exception:
            # Defensive: in case of malformed data, skip
            pass

try:
    setup()
    init_achievements()
    # Track start time for the play session (used for reporting total play time)
    try:
        game_start_time = time.time()
    except Exception:
        game_start_time = None
    # Initialize Firebase client (best-effort)
    try:
        if firebase_client:
            try:
                # init synchronously (fast local file read); defer network calls
                try:
                    firebase_client.init_from_env()
                except Exception:
                    # initialization failed - continue without remote
                    raise
                # perform network calls in background to avoid blocking startup
                try:
                    background_call(firebase_client.sign_in_anonymous)
                except Exception:
                    pass
                try:
                    background_call(firebase_client.log_event, 'session_start', {'client': 'terminal'})
                except Exception:
                    pass
                # Inform player (best-effort)
                try:
                    add_notification('Firebase: enabled')
                except Exception:
                    pass
            except Exception:
                # don't fail startup on network/auth issues
                try:
                    add_notification('Firebase: disabled')
                except Exception:
                    pass
    except Exception:
        pass
    # Music engine support removed from this file.
    # No music engine will be started from the game process.

    # Pre-build static parts
    ceiling = "=" * WIDTH
    floor = ceiling
    
    while True:
        # Handle input
        key = get_key()

        # Detect space key press (edge detection)
        space_pressed_this_frame = (key == 'SPACE')
        space_just_pressed = space_pressed_this_frame and not last_space_state
        last_space_state = space_pressed_this_frame

        # When paused, ignore all input except P (toggle pause) and QUIT.
        # Also prevent SPACE edge from triggering while paused.
        if paused:
            if key and key not in ('P', 'p', 'QUIT'):
                key = None
                space_pressed_this_frame = False
                space_just_pressed = False

        if key:
            if key == 'SPACE' and space_just_pressed:
                # Space pressed - toggle swap mode or execute swap
                if selected_lane is None:
                    # Enter swap mode - select current lane
                    selected_lane = player_lane
                elif selected_lane == player_lane:
                    # Pressed on same lane - cancel swap mode
                    selected_lane = None

                else:
                    # Different lane - execute swap (costs 200 * level points)
                    swap_cost = 200 * level
                    if score >= swap_cost:
                        current_lane = player_lane

                        # Find bird indices for both lanes
                        bird_in_selected = random_lanes.index(selected_lane) if selected_lane in random_lanes else -1
                        bird_in_current = random_lanes.index(current_lane) if current_lane in random_lanes else -1

                        # Swap if both birds exist (even if one or both are dead)
                        if bird_in_selected >= 0 and bird_in_current >= 0:
                            # Deduct cost (use helper so level recompute/achievements can react)
                            deduct_score(swap_cost)
                            # track swap usage for achievements
                            swaps_used += 1
                            check_achievements_event('swap', swaps=swaps_used)

                            # Prima di swappare, controlla se uno dei due è arancione in stato uovo
                            # Stato uovo: ball_colors == ORANGE, ball_speeds == 0, ball_y == 999
                            # Sposta l'uovo arancione nella nuova lane
                            for idx, bird_idx in [(bird_in_selected, bird_in_current), (bird_in_current, bird_in_selected)]:
                                if ball_colors[idx] == ORANGE and ball_speeds[idx] == 0 and ball_y[idx] == 999:
                                    # Trova l'uovo arancione in loot_items
                                    old_lane = random_lanes[idx]
                                    new_lane = random_lanes[bird_idx]
                                    for loot in loot_items:
                                        if loot['type'] == 'orange_egg' and loot['x_pos'] == LANE_POSITIONS[old_lane]:
                                            loot['x_pos'] = LANE_POSITIONS[new_lane]
                                            break

                            # Swap their lane assignments
                            random_lanes[bird_in_selected], random_lanes[bird_in_current] = random_lanes[bird_in_current], random_lanes[bird_in_selected]

                            ball_cols[bird_in_selected] = LANE_POSITIONS[random_lanes[bird_in_selected]]
                            ball_cols[bird_in_current] = LANE_POSITIONS[random_lanes[bird_in_current]]

                            # Se l'uccello NON è arancione in stato uovo, lo rimetti in gioco
                            if not ball_lost[bird_in_selected]:
                                if not (ball_colors[bird_in_selected] == ORANGE and ball_speeds[bird_in_selected] == 0 and ball_y[bird_in_selected] == 999):
                                    ball_y[bird_in_selected] = STARTING_LINE
                                    ball_vy[bird_in_selected] = -1
                            if not ball_lost[bird_in_current]:
                                if not (ball_colors[bird_in_current] == ORANGE and ball_speeds[bird_in_current] == 0 and ball_y[bird_in_current] == 999):
                                    ball_y[bird_in_current] = STARTING_LINE
                                    ball_vy[bird_in_current] = -1

                        # Always reset swap mode after attempting swap (whether successful or not)
                        selected_lane = None

            elif key == 'p' or key == 'P':
                # Toggle pause (top-level handler)
                try:
                    paused = not paused
                    if paused:
                        add_notification('PAUSED')
                    else:
                        add_notification('RESUMED')
                except Exception:
                    paused = False
            elif key == 'LEFT':
                player_lane = max(0, player_lane - 1)
            elif key == 'RIGHT':
                player_lane = min(8, player_lane + 1)  # 9 lanes: 0-8
            elif key == 'UP':
                # Determine which lanes to affect based on wide cursor
                if powerups['wide_cursor_active']:
                    # Wide cursor affects multiple lanes
                    lanes_to_affect = []
                    half_width = powerups['wide_cursor_lanes'] // 2
                    for offset in range(-half_width, half_width + 1):
                        lane = player_lane + offset
                        if 0 <= lane <= 8:
                            lanes_to_affect.append(lane)
                else:
                    lanes_to_affect = [player_lane]

                # Process each affected lane
                for lane in lanes_to_affect:
                    bird_in_lane = random_lanes.index(lane) if lane in random_lanes else -1
                    if bird_in_lane >= 0 and not ball_lost[bird_in_lane]:
                        if ball_colors[bird_in_lane] == ORANGE and ball_speeds[bird_in_lane] == 0:
                            if random.random() > 0.05:  # 5% chance to recover
                                continue
                            lane = random_lanes[bird_in_lane]
                            ball_y[bird_in_lane] = STARTING_LINE
                            ball_vy[bird_in_lane] = -1
                            bird_power_used[bird_in_lane] = False
                            ball_speeds[bird_in_lane] = 5
                            item = next((li for li in loot_items
                                        if li.get('type') == 'orange_egg' and li.get('x_pos') == LANE_POSITIONS[lane]
                                        and li.get('y_pos') == STARTING_LINE and li.get('rarity') == 'epic'), None)
                            if item is not None:
                                loot_items.remove(item)   # rimuove la prima occorrenza dell'oggetto trovato
                        # Can't bounce scared birds
                        elif bird_in_lane in scared_birds and ball_colors[bird_in_lane] != PURPLE:
                            continue  # Scared bird ignores bounce command (tranne purple)
                        elif ball_vy[bird_in_lane] == 1:  # Moving down - bounce it up
                            ball_vy[bird_in_lane] = -1
                            bird_power_used[bird_in_lane] = False  # Reset power when bird starts rising
                            # Special: if this is a CLOCKWORK bird in freefall (charge == 0),
                            # bouncing it restores charge to 1 and sets its speed accordingly.
                            try:
                                if ball_colors[bird_in_lane] == CLOCKWORK:
                                    c = clockwork_charge.get(bird_in_lane, None)
                                    if c is None:
                                        # initialize if missing
                                        clockwork_charge[bird_in_lane] = 2
                                        c = 2
                                    if c == 0:
                                        clockwork_charge[bird_in_lane] = 1
                                        # speed equals charge when >0
                                        ball_speeds[bird_in_lane] = 1
                            except Exception:
                                pass
                            # Apply bounce boost if active
                            if powerups['bounce_boost_active'] and bird_in_lane not in speed_boosts:
                                boost_frames = int(powerups['bounce_boost_duration'] / base_sleep)
                                speed_boosts[bird_in_lane] = boost_frames
                            # record bounce action for combo detection
                            try:
                                append_recent_action('bounce', lane=random_lanes[bird_in_lane], color=ball_colors[bird_in_lane])
                            except NameError:
                                pass
                        elif ball_vy[bird_in_lane] == -1:  # Already moving up - activate special power
                            # Only use power once per ascent
                            if not bird_power_used[bird_in_lane]:
                                bird_power_used[bird_in_lane] = True
                                bird_color = ball_colors[bird_in_lane]
                                # Notify achievements about power use
                                # map color escape to simple name
                                if bird_color == YELLOW:
                                    p_name = 'yellow'
                                elif bird_color == RED:
                                    p_name = 'red'
                                elif bird_color == BLUE:
                                    p_name = 'blue'
                                elif bird_color == WHITE:
                                    p_name = 'white'
                                elif bird_color == PURPLE:
                                    p_name = 'purple'
                                elif bird_color == ORANGE:
                                    p_name = 'orange'
                                elif bird_color == STEALTH:
                                    p_name = 'stealth'
                                else:
                                    p_name = 'unknown'
                                bird_lane = random_lanes[bird_in_lane]
                                check_achievements_event('power_used', power=p_name, lane=bird_lane)

                                if bird_color == YELLOW:
                                    # Yellow power: Slow down adjacent falling birds by -1
                                    # EXCEPT for other yellow birds - bounce them instead
                                    affected_count = 0
                                    for adj_offset in [-1, 1]:
                                        adj_lane = bird_lane + adj_offset
                                        if 0 <= adj_lane < 9:
                                            # Find which bird is in the adjacent lane
                                            adj_bird = -1
                                            for idx in range(NUM_BALLS):
                                                if random_lanes[idx] == adj_lane:
                                                    adj_bird = idx
                                                    break

                                            if adj_bird >= 0 and not ball_lost[adj_bird]:
                                                # Check if bird is falling (moving down)
                                                if ball_vy[adj_bird] == 1:
                                                    if ball_colors[adj_bird] == YELLOW or ball_colors[adj_bird] == PATCHWORK:
                                                        # Yellow bird - bounce it up instead of slowing
                                                        ball_vy[adj_bird] = -1
                                                        bird_power_used[adj_bird] = False  # Reset power for bounced yellow
                                                        affected_count += 1
                                                        try:
                                                            append_recent_action('bounce', lane=adj_lane, color=ball_colors[adj_bird])
                                                        except NameError:
                                                            pass
                                                    else:
                                                        # Non-yellow bird - apply slow effect
                                                        speed_boosts[adj_bird] = -int(3.0 / base_sleep)  # 3 seconds of slow
                                                        affected_count += 1
                                                

                                elif bird_color == RED or bird_color == PURPLE:
                                    # Red/Purple power: Launch projectile
                                    # Count adjacent red/purple/PATCHWORK birds moving up for damage bonus
                                    damage_bonus = 0
                                    for adj_offset in [-1, 1]:
                                        adj_lane = bird_lane + adj_offset
                                        if 0 <= adj_lane < 9:
                                            for idx in range(NUM_BALLS):
                                                if random_lanes[idx] == adj_lane and not ball_lost[idx]:
                                                    if (ball_colors[idx] == RED or ball_colors[idx] == PURPLE or ball_colors[idx] == PATCHWORK) and ball_vy[idx] == -1:
                                                        damage_bonus += 1
                                                    break
                                    red_projectiles.append({
                                        'x_pos': LANE_POSITIONS[bird_lane],
                                        'y_pos': ball_y[bird_in_lane],
                                        'lane': bird_lane,
                                        'damage': 1 + damage_bonus,
                                        'powered': damage_bonus > 0
                                    })

                                elif bird_color == BLUE:
                                    # Blue power: Speed boost + extra damage flag
                                    boost_frames = int(3.0 / base_sleep)
                                    speed_boosts[bird_in_lane] = boost_frames
                                    # Mark this bird as having blue power active (for extra damage)
                                    if bird_in_lane not in speed_boosts:
                                        speed_boosts[bird_in_lane] = boost_frames

                                elif bird_color == WHITE:
                                    # White power: Affect 4 adjacent lanes (2 left + 2 right)
                                    for adj_offset in [-2, -1, 1, 2]:
                                        adj_lane = bird_lane + adj_offset
                                        if 0 <= adj_lane < 9:
                                            # Find which bird is in the adjacent lane
                                            adj_bird = -1
                                            for idx in range(NUM_BALLS):
                                                if random_lanes[idx] == adj_lane:
                                                    adj_bird = idx
                                                    break

                                            if adj_bird >= 0 and not ball_lost[adj_bird]:
                                                if ball_vy[adj_bird] == 1:
                                                    # Bird is falling - bounce it up
                                                    # But don't bounce scared birds (PURPLE exception)
                                                    if adj_bird in scared_birds and ball_colors[adj_bird] != PURPLE:
                                                        # ignore bounce for scared bird
                                                        pass
                                                    else:
                                                        ball_vy[adj_bird] = -1
                                                        bird_power_used[adj_bird] = False  # Reset their power
                                                        try:
                                                            append_recent_action('bounce', lane=adj_lane, color=ball_colors[adj_bird])
                                                        except NameError:
                                                            pass
                                                elif ball_vy[adj_bird] == -1:
                                                    # Bird is rising - activate its power (if not already used)
                                                    if not bird_power_used[adj_bird]:
                                                        bird_power_used[adj_bird] = True
                                                        adj_bird_color = ball_colors[adj_bird]
                                                        # Notify achievements about adjacent bird power use
                                                        if adj_bird_color == YELLOW:
                                                            p_name = 'yellow'
                                                        elif adj_bird_color == RED:
                                                            p_name = 'red'
                                                        elif adj_bird_color == BLUE:
                                                            p_name = 'blue'
                                                        elif adj_bird_color == WHITE:
                                                            p_name = 'white'
                                                        elif adj_bird_color == PURPLE:
                                                            p_name = 'purple'
                                                        elif adj_bird_color == ORANGE:
                                                            p_name = 'orange'
                                                        else:
                                                            p_name = 'unknown'
                                                        check_achievements_event('power_used', power=p_name, lane=adj_lane)
                                                        adj_bird_lane = random_lanes[adj_bird]

                                                        # Execute the bird's power based on its color
                                                        if adj_bird_color == YELLOW:
                                                            # Yellow power on adjacent bird - bounces yellows, slows others
                                                            for y_offset in [-1, 1]:
                                                                y_lane = adj_bird_lane + y_offset
                                                                if 0 <= y_lane < 9:
                                                                    y_bird = -1
                                                                    for idx2 in range(NUM_BALLS):
                                                                        if random_lanes[idx2] == y_lane:
                                                                            y_bird = idx2
                                                                            break
                                                                    if y_bird >= 0 and not ball_lost[y_bird] and ball_vy[y_bird] == 1:
                                                                        # Respect scared state: scared birds ignore bounces (except PURPLE)
                                                                        if y_bird in scared_birds and ball_colors[y_bird] != PURPLE:
                                                                            # do nothing to scared bird
                                                                            pass
                                                                        else:
                                                                            if ball_colors[y_bird] == YELLOW:
                                                                                # Bounce yellow bird
                                                                                ball_vy[y_bird] = -1
                                                                                bird_power_used[y_bird] = False
                                                                            else:
                                                                                # Slow non-yellow bird
                                                                                speed_boosts[y_bird] = -int(3.0 / base_sleep)

                                                        elif adj_bird_color == RED:
                                                            # Red power on adjacent bird
                                                            # Count adjacent red birds moving up for damage bonus
                                                            damage_bonus = 0
                                                            for adj_offset2 in [-1, 1]:
                                                                adj_lane2 = adj_bird_lane + adj_offset2
                                                                if 0 <= adj_lane2 < 9:
                                                                    for idx2 in range(NUM_BALLS):
                                                                        if random_lanes[idx2] == adj_lane2 and not ball_lost[idx2]:
                                                                            if ball_colors[idx2] == RED and ball_vy[idx2] == -1:
                                                                                damage_bonus += 1
                                                                            break

                                                            red_projectiles.append({
                                                                'x_pos': LANE_POSITIONS[adj_bird_lane],
                                                                'y_pos': ball_y[adj_bird],
                                                                'lane': adj_bird_lane,
                                                                'damage': 1 + damage_bonus,
                                                                'powered': damage_bonus > 0
                                                            })

                                                        elif adj_bird_color == BLUE:
                                                            # Blue power on adjacent bird
                                                            boost_frames = int(5.0 / base_sleep)
                                                            speed_boosts[adj_bird] = boost_frames
                                elif bird_color == CLOCKWORK:
                                    # CLOCKWORK power: increase charge up to max 3.
                                    try:
                                        cur = clockwork_charge.get(bird_in_lane, 2)
                                        if cur is None:
                                            cur = 2
                                        newc = min(3, cur + 1)
                                        clockwork_charge[bird_in_lane] = newc
                                        # When charge > 0, speed mirrors charge
                                        if newc > 0:
                                            ball_speeds[bird_in_lane] = newc
                                    except Exception:
                                        pass
                                elif bird_color == STEALTH:
                                    # Stealth power: become tangible for a short duration and deal heavy damage
                                    # bird_power_used[bird_in_lane] is already True
                                    stealth_timers[bird_in_lane] = max(1, int(2.0 / base_sleep))
                                    # Save previous speed and apply temporary speed boost to 6
                                    try:
                                        stealth_prev_speeds[bird_in_lane] = ball_speeds[bird_in_lane]
                                        ball_speeds[bird_in_lane] = 6
                                    except Exception:
                                        pass
                                    try:
                                        append_recent_action('stealth', lane=bird_lane, color=STEALTH)
                                    except NameError:
                                        pass
            elif key == 'DOWN':
                # Suction: pull bird down if moving up
                if powerups['suction_active']:
                    # Determine affected lanes (support wide cursor)
                    if powerups['wide_cursor_active']:
                        half_width = powerups['wide_cursor_lanes'] // 2
                        lanes_to_affect = []
                        for offset in range(-half_width, half_width + 1):
                            lane = player_lane + offset
                            if 0 <= lane < 9:
                                lanes_to_affect.append(lane)
                    else:
                        lanes_to_affect = [player_lane]

                    for lane in lanes_to_affect:
                        bird_in_lane = random_lanes.index(lane) if lane in random_lanes else -1
                        if bird_in_lane >= 0 and not ball_lost[bird_in_lane]:
                            if ball_vy[bird_in_lane] == -1:  # Moving up - pull it down
                                ball_vy[bird_in_lane] = 1
                                # Apply suction boost if configured
                                if powerups['suction_boost_duration'] > 0 and bird_in_lane not in speed_boosts:
                                    boost_frames = int(powerups['suction_boost_duration'] / base_sleep)
                                    speed_boosts[bird_in_lane] = boost_frames
                                # record suction action for combo detection
                                try:
                                    append_recent_action('suction', lane=random_lanes[bird_in_lane], color=ball_colors[bird_in_lane])
                                except NameError:
                                    pass
            elif key == 'QUIT':
                break

        # Build output buffer (don't clear screen, just reposition)
        output = "\033[2J\033[H"  # Clear screen and move to home
        
        # Recompute level from current score so spending points can LOWER the level
        level = compute_level_from_score(score)

        # Draw simple header with score, level, and lives
        next_level_score = calculate_level_threshold(level + 1)
        lives_display = "●" * lives + "◌" * (5 - lives)
        output += f"\033[1;1HSCORE: {int(score)}  |  LEVEL: {level}  |  NEXT: {next_level_score}  |  LIVES: {lives_display}\n"
        output += f"\033[2;1H{ceiling}\n"
        # Render single queued notification at the bottom (replace help/commands area)
        active_notifications = [n for n in notifications if n[1] > frame_count]
        if active_notifications:
            text, exp = active_notifications[0]
            footer_y = HEIGHT + 3  # bottom area after game box
            # Truncate to width to avoid wrapping
            display_text = text[:WIDTH]
            output += f"\033[{footer_y};1H{YELLOW}{display_text}{RESET}\n"
        # Prune expired notifications (keep order)
        notifications[:] = active_notifications
        
        # Draw starting line (dashed line near bottom)
        starting_line_y = STARTING_LINE + 2  # +2 for header offset
        if 3 <= starting_line_y < HEIGHT + 2:
            # When tailwind is active, render the starting line as blue carets '^'
            if powerups.get('tailwind_active'):
                dashed_line = "^ " * (WIDTH // 2)
                output += f"\033[{starting_line_y};1H{BLUE}{dashed_line[:WIDTH]}{RESET}"
            else:
                dashed_line = "- " * (WIDTH // 2)  # Create dashed pattern
                output += f"\033[{starting_line_y};1H{DARK_GRAY}{dashed_line[:WIDTH]}{RESET}"
            
            # Show power-up indicators on affected lanes
            # Calculate which lanes are affected by cursor
            if powerups['wide_cursor_active']:
                half_width = powerups['wide_cursor_lanes'] // 2
                lanes_to_check = []
                for offset in range(-half_width, half_width + 1):
                    lane = player_lane + offset
                    if 0 <= lane < 9:
                        lanes_to_check.append(lane)
            else:
                lanes_to_check = [player_lane]
            
            # Draw indicators on the starting line for each affected lane
            for lane in lanes_to_check:
                lane_x = LANE_POSITIONS[lane]
                bird_in_lane = random_lanes.index(lane) if lane in random_lanes else -1
                
                if bird_in_lane >= 0 and not ball_lost[bird_in_lane]:
                    # Bounce boost: show blue ^ if bird is falling
                    if powerups['bounce_boost_active'] and ball_vy[bird_in_lane] == 1:
                        output += f"\033[{starting_line_y};{lane_x}H{BLUE}\033[1m^{RESET}"
                    # Suction: show red v if bird is rising
                    elif powerups['suction_active'] and ball_vy[bird_in_lane] == -1:
                        output += f"\033[{starting_line_y};{lane_x}H{RED}\033[1mv{RESET}"
        
        # Draw obstacles
        for obs in obstacles:
            # Color based on remaining HP (scale from base green to black)
            try:
                max_hp = _OBST_MAX_HP_BY_TIER.get(obs.get('tier', 1), obs.get('hp', 1))
            except Exception:
                max_hp = obs.get('hp', 1)
            obs_color = _color_from_hp(_OBST_BASE_RGB, obs.get('hp', 0), max_hp)

            # Draw sprite - single line, no HP display
            for line_idx, line in enumerate(OBSTACLE_SPRITE):
                y_pos = obs['y_pos'] + line_idx + 2  # +2 for header offset
                if 3 <= y_pos < HEIGHT + 2:
                    x_pos = LANE_POSITIONS[obs['lane']] - 1  # Center 3-char sprite
                    output += f"\033[{y_pos};{x_pos}H{obs_color}{line}{RESET}"
        
        # Draw bats
        for bat in bats:
            # Color based on remaining HP (scale from magenta to black)
            bat_hp = bat.get('hp', 0)
            bat_max = bat.get('max_hp', bat_hp if bat_hp > 0 else 1)
            bat_color = _color_from_hp(_BATS_BASE_RGB, bat_hp, bat_max)

            # Choose sprite frame based on animation
            bat_sprite = BAT_FRAME_1 if (frame_count // 3) % 2 == 0 else BAT_FRAME_2
            
            # Draw bat - no HP display
            for line_idx, line in enumerate(bat_sprite):
                y_pos = bat['y_pos'] + line_idx + 2  # +2 for header offset
                if 3 <= y_pos < HEIGHT + 2:
                    output += f"\033[{y_pos};{bat['x_pos']}H{bat_color}{line}{RESET}"
        
        # Draw loot items
        for loot in loot_items:
            y_pos = loot['y_pos'] + 2  # +2 for header offset
            if 3 <= y_pos < HEIGHT + 2:
                loot_type = loot['type']
                rarity = loot['rarity']
                
                # Determine color based on rarity
                if rarity == 'common':
                    power_color = YELLOW
                elif rarity == 'uncommon':
                    power_color = RED
                elif rarity == 'rare':
                    power_color = BLUE
                else:  # legendary
                    power_color = WHITE
                
                # Eggs - colored by bird type
                if loot_type == 'yellow_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{YELLOW}⬯{RESET}"
                elif loot_type == 'red_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{RED}⬯{RESET}"
                elif loot_type == 'blue_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{BLUE}⬯{RESET}"
                elif loot_type == 'white_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{WHITE}⬯{RESET}"
                elif loot_type == 'clockwork_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{CLOCKWORK}⬯{RESET}"
                elif loot_type == 'gold_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{GOLD}⬯{RESET}"
                elif loot_type == 'stealth_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{DARK_GRAY}⬯{RESET}"
                elif loot_type == 'patchwork_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{PATCHWORK}⬯{RESET}"
                elif loot_type == 'orange_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{ORANGE}⬯{RESET}"
                # Cursor power-ups
                elif 'wide_cursor' in loot_type:
                    output += f"\033[{y_pos};{loot['x_pos']}H{power_color}↔{RESET}"
                # Bounce boost power-ups
                elif 'bounce_boost' in loot_type:
                    output += f"\033[{y_pos};{loot['x_pos']}H{power_color}↺{RESET}"
                # Suction power-ups
                elif 'suction' in loot_type:
                    output += f"\033[{y_pos};{loot['x_pos']}H{power_color}⥥{RESET}"
                # Tailwind power-ups (tiered)
                elif 'tailwind' in loot_type:
                    # Use a decorative wind/ornament symbol
                    output += f"\033[{y_pos};{loot['x_pos']}H{power_color}༄{RESET}"
                # Shuffle power-ups (tiered)
                elif 'shuffle' in loot_type:
                    # Use the chosen decorative shuffle icon
                    output += f"\033[{y_pos};{loot['x_pos']}H{power_color}𖦹{RESET}"
        
        # Draw red projectiles
        for proj in red_projectiles:
            y_pos = proj['y_pos'] + 2  # +2 for header offset
            if 3 <= y_pos < HEIGHT + 2:
                # Use • for powered (bonus damage), ⋅ for base
                symbol = "•" if proj.get('powered', False) else "⋅"
                output += f"\033[{y_pos};{proj['x_pos']}H{RED}{symbol}{RESET}"
        
        # Draw active birds
        for b in range(NUM_BALLS):
            if not ball_lost[b]:
                # Check if bird is slowed by yellow power (negative speed_boosts AND moving down)
                is_slowed = b in speed_boosts and speed_boosts[b] < 0 and ball_vy[b] == 1
                
                # Choose sprite based on direction and animate with frame counter
                # Special: CLOCKWORK animation depends on charge:
                #  - charge > 1: normal period
                #  - charge == 1: slower period
                #  - charge == 0: frozen (single frame)
                # Freeze animation if bird is slowed (external slow effect)
                if ball_vy[b] == -1:  # Moving up
                    if ball_colors[b] == CLOCKWORK:
                        try:
                            c = clockwork_charge.get(b, 2)
                        except Exception:
                            c = 2
                        if c == 0:
                            sprite = BIRD_UP_2  # frozen
                        elif c == 1:
                            sprite = BIRD_UP_1 if (frame_count // 6) % 2 == 0 else BIRD_UP_2
                        else:
                            sprite = BIRD_UP_1 if (frame_count // 3) % 2 == 0 else BIRD_UP_2
                    else:
                        sprite = BIRD_UP_1 if (frame_count // 3) % 2 == 0 else BIRD_UP_2
                else:  # Moving down
                    if is_slowed:
                        sprite = BIRD_DOWN_2 # Frozen frame when slowed
                    else:
                        if ball_colors[b] == CLOCKWORK:
                            try:
                                c = clockwork_charge.get(b, 2)
                            except Exception:
                                c = 2
                            if c == 0:
                                sprite = BIRD_DOWN_2  # frozen
                            elif c == 1:
                                sprite = BIRD_DOWN_1 if (frame_count // 6) % 2 == 0 else BIRD_DOWN_2
                            else:
                                sprite = BIRD_DOWN_1 if (frame_count // 3) % 2 == 0 else BIRD_DOWN_2
                        else:
                            sprite = BIRD_DOWN_1 if (frame_count // 3) % 2 == 0 else BIRD_DOWN_2
                
                # Choose color - handle STEALTH specially, blue birds turn cyan when power is active
                if ball_colors[b] == STEALTH:
                    # Tangible when a stealth timer is active for this bird
                    tangible = b in stealth_timers and stealth_timers.get(b, 0) > 0
                    # Pulse between DARK_GRAY (visible) and ANSI "conceal" (invisible) over a period
                    # This makes the bird actually invisible on terminals that support SGR 8.
                    try:
                        # Use a faster visible pulse (~0.5s cycle) so the change is noticeable
                        period = max(4, int(2 / base_sleep))
                    except Exception:
                        period = 8
                    phase = (frame_count % period) / period
                    # Use DARK_GRAY for first half, ANSI conceal for second half (hidden/invisible)
                    # If the terminal doesn't support conceal, it'll appear as no-op; we can add
                    # a fallback later if needed.
                    color = DARK_GRAY if phase < 0.5 else "\033[8m"
                    # When tangible, show as a brighter color so the player clearly sees the effect
                    if tangible:
                        color = WHITE
                elif ball_colors[b] == BLUE and bird_power_used[b]:
                    color = CYAN  # Light blue when power active
                else:
                    color = ball_colors[b]
                
                # Draw each line of the bird (centered)
                for line_idx, line in enumerate(sprite):
                    y_pos = ball_y[b] + line_idx + 2  # +2 for header offset
                    if 3 <= y_pos < HEIGHT + 2:
                        # Center sprites - new sprites are 3 chars wide
                        x_offset = 1  # Offset for 3-char wide sprite
                        # CLOCKWORK: special per-char coloring and blinking for '.' and '\''
                        if ball_colors[b] == CLOCKWORK:
                            try:
                                c = clockwork_charge.get(b, 2)
                            except Exception:
                                c = 2
                            try:
                                blink_period = max(1, int(0.6 / base_sleep))
                            except Exception:
                                blink_period = 3
                            blink_on = ((frame_count // blink_period) % 2) == 0
                            colored = _render_clockwork_line(line, c, blink_on)
                            output += f"\033[{y_pos};{ball_cols[b]-x_offset}H{colored}"
                        elif ball_colors[b] == PATCHWORK:
                            # Render each character with a different color pattern
                            colored = _render_patchwork_line(line)
                            output += f"\033[{y_pos};{ball_cols[b]-x_offset}H{colored}"
                        else:
                            output += f"\033[{y_pos};{ball_cols[b]-x_offset}H{color}{line}{RESET}"
        
        # Check for level up
        if score >= calculate_level_threshold(level):
            level += 1
        
        # Calculate current speed based on level - more aggressive speed increase
        try:
            base_frame_sleep = base_sleep * (0.88 ** level)
            # slow-motion removed: main loop sleep is not modified by powerups
            current_sleep = max(min_sleep, base_frame_sleep)
        except Exception:
            current_sleep = max(min_sleep, base_sleep * (0.88 ** level))  # Fallback
        # Music engine integration removed from main loop
        
        # Draw floor and player
        output += f"\033[{HEIGHT+2};1H{floor}\n"
        
        # Draw lost balls on floor as gray X
        for b in range(NUM_BALLS):
            if ball_lost[b]:
                output += f"\033[{HEIGHT+2};{ball_cols[b]}H\033[90mX{RESET}"
        
        # Draw player cursor - large and bright for visibility
        cursor_x = LANE_POSITIONS[player_lane] - 1  # Center on lane
        # Change cursor color when in swap mode (lane selected)
        cursor_color = YELLOW if selected_lane is not None else GREEN
        
        # Draw wide cursor if active
        if powerups['wide_cursor_active']:
            half_width = powerups['wide_cursor_lanes'] // 2
            cursor_str = ""
            for offset in range(-half_width, half_width + 1):
                lane = player_lane + offset
                if 0 <= lane < 9:
                    lane_x = LANE_POSITIONS[lane] - 1
                    if lane == player_lane:
                        # Main cursor
                        cursor_str += f"\033[{HEIGHT+3};{lane_x}H{cursor_color}\033[1m[^]{RESET}"
                    else:
                        # Extended cursor wings
                        cursor_str += f"\033[{HEIGHT+3};{lane_x}H{cursor_color}\033[1m[-]{RESET}"
            output += cursor_str + "\n"
        else:
            # Normal cursor
            output += f"\033[{HEIGHT+3};{cursor_x}H{cursor_color}\033[1m[^]{RESET}\n"  # Bold cursor
        
        # Highlight selected lane if in swap mode
        if selected_lane is not None:
            selected_x = LANE_POSITIONS[selected_lane] - 1
            output += f"\033[{HEIGHT+3};{selected_x}H{YELLOW}\033[1m[*]{RESET}"  # Mark selected lane
        
        # Count active balls
        active_balls = sum(1 for lost in ball_lost if not lost)
        swap_hint = " | Press SPACE again to swap or cancel" if selected_lane is not None else ""
        output += f"\033[{HEIGHT+4};1HUse ← → to move, ↑ to bounce, Ctrl+C to quit | Birds: {active_balls}/{NUM_BALLS}{swap_hint}"
        
        # If paused, render a PAUSED overlay (keep input responsive)
        if paused:
            try:
                pause_y = 2 + (HEIGHT // 2)
                pause_x = max(1, (WIDTH // 2) - 3)
                output += f"\033[{pause_y};{pause_x}H{YELLOW}\033[1mPAUSED{RESET}"
            except Exception:
                pass

        # Write all at once - handle blocking errors gracefully
        try:
            sys.stdout.write(output)
            sys.stdout.flush()
        except BlockingIOError:
            # If output buffer is full, skip this frame
            pass

        # If paused, skip per-frame updates but sleep to avoid tight-loop
        if paused:
            try:
                time.sleep(current_sleep)
            except Exception:
                pass
            continue
        
        # Update ball positions
        frame_count += 1
        obstacle_spawn_timer += 1
        bat_spawn_timer += 1
        # CLOCKWORK decay: every 30s reduce charge by 1 (per bird)
        try:
            decay_frames = max(1, int(30.0 / base_sleep))
            if decay_frames > 0 and frame_count % decay_frames == 0:
                for i in range(NUM_BALLS):
                    try:
                        if ball_colors[i] == CLOCKWORK and not ball_lost[i]:
                            c = clockwork_charge.get(i, None)
                            if c is None:
                                c = 2
                                clockwork_charge[i] = 2
                            if c > 0:
                                clockwork_charge[i] = c - 1
                                newc = clockwork_charge[i]
                                if newc > 0:
                                    ball_speeds[i] = newc
                                else:
                                    # Enter freefall: set very fast falling speed and ensure bird is falling
                                    ball_speeds[i] = 6
                                    ball_vy[i] = 1
                                    add_notification('Clockwork freefall!')
                    except Exception:
                        pass
        except Exception:
            pass
        # --- Per-frame achievement-related checks ---
        # Area hold: check if all active birds are in top X% areas
        # top50: y <= HEIGHT * 0.5, top30: y <= HEIGHT * 0.3
        try:
            active_idxs = [i for i in range(NUM_BALLS) if not ball_lost[i]]
            if active_idxs:
                top50_y = int(HEIGHT * 0.5)
                top30_y = int(HEIGHT * 0.3)
                all_top50 = all(ball_y[i] <= top50_y for i in active_idxs)
                all_top30 = all(ball_y[i] <= top30_y for i in active_idxs)

                if all_top50:
                    top50_hold_frames += 1
                else:
                    top50_hold_frames = 0

                if all_top30:
                    top30_hold_frames += 1
                else:
                    top30_hold_frames = 0

                # Fire area_hold events
                check_achievements_event('area_hold', area='top50', frames=top50_hold_frames)
                check_achievements_event('area_hold', area='top30', frames=top30_hold_frames)

            # Original birds alive tracking
            originals_alive = all(not ball_lost[idx] for idx in original_indices)
            if originals_alive:
                original_alive_frames += 1
            else:
                original_alive_frames = 0
            check_achievements_event('original_survive', frames=original_alive_frames)

            # Color counts
            color_map = {
                'YELLOW': YELLOW,
                'RED': RED,
                'BLUE': BLUE,
                'WHITE': WHITE,
                'CLOCKWORK': CLOCKWORK,
                'PURPLE': PURPLE,
                'ORANGE': ORANGE,
                'GOLD': GOLD,
            }
            for cname, cval in color_map.items():
                count = sum(1 for i in range(NUM_BALLS) if not ball_lost[i] and ball_colors[i] == cval)
                check_achievements_event('color_count', color=cname, count=count)
        except Exception:
            # Non-fatal: achievements shouldn't crash the game
            pass
        
        # Count current entities on screen (excluding birds)
        active_birds = sum(1 for lost in ball_lost if not lost)
        current_entities = len(obstacles) + len(bats) + active_birds
        
        # Try to spawn from queue if we're under the entity limit
        if current_entities < MAX_ENTITIES and spawn_queue:
            entity = spawn_queue.pop(0)
            if entity['type'] == 'bat':
                # stamp a spawn timestamp for despawn logic
                try:
                    entity['data']['spawn_ts'] = time.time()
                except Exception:
                    pass
                bats.append(entity['data'])
            elif entity['type'] == 'obstacle':
                obstacles.append(entity['data'])
        
        # Queue bat spawns - spawn rate reduced to make bats rarer
        # Spawn less often and allow up to 3 bats on screen
        if len(bats) < 2 and bat_spawn_timer > random.randint(120, 220):
            bat_spawn_timer = 0
            
            # Calculate target Y position based on level
            # Lower levels: bats stop higher (around 5-8)
            # Higher levels: bats stop lower (max half screen = 12)
            if level <= 3:
                target_y = random.randint(5, 8)
            elif level <= 6:
                target_y = random.randint(8, 10)
            else:
                target_y = random.randint(10, 12)  # Max at half screen
            
            # Tier selection increases with level (4 tiers now)
            if level <= 2:
                tier = random.choices([1, 2, 3, 4], weights=[70, 20, 8, 2])[0]
            elif level <= 4:
                tier = random.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]
            elif level <= 7:
                tier = random.choices([1, 2, 3, 4], weights=[30, 35, 25, 10])[0]
            else:
                tier = random.choices([1, 2, 3, 4], weights=[15, 30, 35, 20])[0]
            
            # HP progression: 16, 32, 64, 128
            if tier == 1:
                hp = 16
            elif tier == 2:
                hp = 32
            elif tier == 3:
                hp = 64
            else:  # tier 4
                hp = 128
            
            # Try to find a spawn position that doesn't overlap with existing bats
            max_attempts = 20
            spawn_x = None
            for attempt in range(max_attempts):
                # Spawn within game box: bats are 8 chars wide, need margin
                candidate_x = random.randint(1, WIDTH - 9)  # Keep bat fully inside box
                # Check if this position overlaps with any existing bat
                overlaps = False
                for existing_bat in bats:
                    # Bats are 8 chars wide - need at least 15 chars separation
                    if abs(candidate_x - existing_bat['x_pos']) < 15:
                        overlaps = True
                        break
                
                # Also check overlap with spawn queue
                for queued in spawn_queue:
                    if queued['type'] == 'bat':
                        if abs(candidate_x - queued['data']['x_pos']) < 15:
                            overlaps = True
                            break
                
                if not overlaps:
                    spawn_x = candidate_x
                    break
            
            # If we couldn't find a good position, DON'T SPAWN
            if spawn_x is None:
                bat_spawn_timer = 50  # Wait a bit before trying again
            else:
                # Check if last 2 items in queue are bats - if so, skip this spawn
                can_add = True
                if len(spawn_queue) >= 2:
                    if spawn_queue[-1]['type'] == 'bat' and spawn_queue[-2]['type'] == 'bat':
                        can_add = False
                        bat_spawn_timer = 20  # Retry soon
                
                if can_add:
                    # Found a good position - queue the bat
                    direction = random.choice([-1, 1])  # -1 = left, 1 = right
                    
                    spawn_queue.append({
                        'type': 'bat',
                        'data': {
                            'x_pos': spawn_x,
                            'y_pos': 1,  # Start from top like obstacles
                            'target_y': target_y,  # Stop at this Y position
                            'tier': tier,
                            'hp': hp,
                            'max_hp': hp,
                            'direction': direction,
                            'wave_offset': random.randint(0, 10)
                        }
                    })
        
        # Queue obstacle spawns - much more aggressive spawn rate
        base_spawn_rate = max(15, 60 - (level * 4))  # Much faster spawning
        spawn_variance = max(10, 30 - (level * 2))
        
        if obstacle_spawn_timer > random.randint(base_spawn_rate - spawn_variance, base_spawn_rate + spawn_variance):
            obstacle_spawn_timer = 0
            
            # Get list of active lanes (where birds are still alive)
            active_lanes = [random_lanes[i] for i in range(NUM_BALLS) if not ball_lost[i]]
            
            # Only spawn obstacle if there are active lanes
            if active_lanes:
                # Filter out lanes occupied by bats
                available_lanes = []
                for lane_idx in active_lanes:
                    lane_x = LANE_POSITIONS[lane_idx]
                    lane_left = lane_x - 2
                    lane_right = lane_x + 2
                    
                    # Check if any bat overlaps with this lane
                    bat_in_lane = False
                    for bat in bats:
                        bat_left = bat['x_pos']
                        bat_right = bat['x_pos'] + 8
                        if not (bat_right < lane_left or bat_left > lane_right):
                            bat_in_lane = True
                            break
                    
                    if not bat_in_lane:
                        available_lanes.append(lane_idx)
                
                # If no lanes available (all have bats), skip this spawn
                if not available_lanes:
                    obstacle_spawn_timer = max(5, base_spawn_rate // 2)
                else:
                    # Only spawn in lanes without obstacles
                    lanes_without_obstacles = []
                    for lane_idx in available_lanes:
                        has_obstacle = any(obs['lane'] == lane_idx for obs in obstacles)
                        if not has_obstacle:
                            lanes_without_obstacles.append(lane_idx)
                    
                    # Only spawn if there's at least one free lane
                    if not lanes_without_obstacles:
                        # All available lanes have obstacles - skip spawn
                        obstacle_spawn_timer = max(5, base_spawn_rate // 2)
                    else:
                        # Choose a free lane
                        lane = random.choice(lanes_without_obstacles)
                    
                        # Tier distribution changes with level - higher tiers become MORE common (4 tiers)
                        if level <= 2:
                            tier = random.choices([1, 2, 3, 4], weights=[70, 20, 8, 2])[0]
                        elif level <= 4:
                            tier = random.choices([1, 2, 3, 4], weights=[55, 28, 13, 4])[0]
                        elif level <= 7:
                            tier = random.choices([1, 2, 3, 4], weights=[35, 35, 20, 10])[0]
                        else:
                            tier = random.choices([1, 2, 3, 4], weights=[20, 30, 30, 20])[0]
                        
                        # HP based on tier: 4, 6, 10, 16
                        if tier == 1:
                            hp = 4
                        elif tier == 2:
                            hp = 6
                        elif tier == 3:
                            hp = 10
                        else:  # tier 4
                            hp = 16
                        
                        # Check if last 2 items in queue are obstacles - if so, skip this spawn
                        can_add = True
                        if len(spawn_queue) >= 2:
                            if spawn_queue[-1]['type'] == 'obstacle' and spawn_queue[-2]['type'] == 'obstacle':
                                can_add = False
                                obstacle_spawn_timer = max(5, base_spawn_rate // 2)  # Retry sooner
                        
                        if can_add:
                            spawn_queue.append({
                                'type': 'obstacle',
                                'data': {'lane': lane, 'y_pos': 1, 'tier': tier, 'hp': hp}
                            })
        
        # Move obstacles down - always speed 1 (slowest)
        for obs in obstacles[:]:
            if frame_count % (6 - 1) == 0:  # Speed 1: move every 5 frames
                obs['y_pos'] += 1
            
            # Auto-remove obstacles when they reach the line above the starting line
            if obs['y_pos'] >= STARTING_LINE - 1:
                obstacles.remove(obs)
            elif obs['y_pos'] >= HEIGHT:
                obstacles.remove(obs)
        
        # Move bats horizontally and vertically (wave motion)
        for bat in bats[:]:
            if frame_count % 3 == 0:  # Bats move every 3 frames
                # Calculate next horizontal position
                next_x = bat['x_pos'] + bat['direction'] * 2
                
                # Check if bat would overlap with another bat at next position
                can_move = True
                
                # Check collision with other bats
                for other_bat in bats:
                    if other_bat is bat:
                        continue
                    # Bats are 8 chars wide - check overlap
                    other_left = other_bat['x_pos']
                    other_right = other_bat['x_pos'] + 8
                    next_left = next_x
                    next_right = next_x + 8
                    
                    # Check horizontal overlap
                    if not (next_right < other_left or next_left > other_right):
                        can_move = False
                        break
                
                # Check collision with birds
                if can_move:
                    for i in range(NUM_BALLS):
                        if not ball_lost[i]:
                            # Get bird's LANE position - birds are in lanes!
                            bird_lane_x = LANE_POSITIONS[random_lanes[i]]
                            # Each lane is effectively a column - if bat enters lane, block it
                            bird_y = ball_y[i]
                            
                            # Predict bird's next movement
                            current_speed = ball_speeds[i]
                            if i in speed_boosts:
                                current_speed += 1
                            move_interval = max(1, 6 - current_speed)
                            
                            # Check if bird will move this frame
                            if frame_count % move_interval == 0:
                                next_bird_y = bird_y + ball_vy[i]
                            else:
                                next_bird_y = bird_y
                            
                            # Bat horizontal range at next position (8 chars wide)
                            bat_left = next_x
                            bat_right = next_x + 8
                            bat_top = bat['y_pos']
                            bat_bottom = bat['y_pos'] + 2
                            
                            # If bat overlaps with bird's lane AT ALL, block movement
                            # Lane is centered at bird_lane_x, 5 chars wide (±2 from center)
                            lane_left = bird_lane_x - 2
                            lane_right = bird_lane_x + 2
                            
                            # Check if bat would enter this lane
                            horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)
                            
                            if horizontal_overlap:
                                # Check if bird is anywhere near bat vertically (give margin)
                                if abs(bird_y - bat['y_pos']) < 8 or abs(next_bird_y - bat['y_pos']) < 8:
                                    can_move = False
                                    break
                
                if can_move:
                    bat['x_pos'] = next_x
                    # Bounce off walls (bats are 8 chars wide)
                    if bat['x_pos'] <= 0:
                        bat['x_pos'] = 0
                        bat['direction'] = 1
                    elif bat['x_pos'] >= WIDTH - 8:
                        bat['x_pos'] = WIDTH - 8
                        bat['direction'] = -1
                else:
                    # Can't move, reverse direction
                    bat['direction'] *= -1
            
            # Move bat downward at speed 1 until it reaches target_y
            if frame_count % (6 - 1) == 0:  # Speed 1: move every 5 frames (same as obstacles)
                if bat['y_pos'] < bat['target_y']:
                    bat['y_pos'] += 1
        
        # Check bat-obstacle collisions and remove obstacles
        for bat in bats:
            bat_left = bat['x_pos']
            bat_right = bat['x_pos'] + 8  # Bats are 8 chars wide
            bat_top = bat['y_pos']
            bat_bottom = bat['y_pos'] + 1  # Bats are 2 lines tall
            
            for obs in obstacles[:]:
                obs_lane_x = LANE_POSITIONS[obs['lane']]
                obs_left = obs_lane_x - 1  # Obstacles are 3 chars wide centered on lane
                obs_right = obs_lane_x + 1
                obs_y = obs['y_pos']
                
                # Check horizontal overlap
                horizontal_overlap = not (bat_right < obs_left or bat_left > obs_right)
                # Check vertical overlap (obstacle is 1 line tall)
                vertical_overlap = abs(bat_top - obs_y) <= 1 or abs(bat_bottom - obs_y) <= 1
                
                if horizontal_overlap and vertical_overlap:
                    obstacles.remove(obs)
        
        # Despawn old bats and loot (older than 60 seconds)
        try:
            now_ts = time.time()
            # Remove bats older than 60s
            for bat in bats[:]:
                try:
                    if now_ts - float(bat.get('spawn_ts', now_ts)) > 60:
                        bats.remove(bat)
                except Exception:
                    # If malformed spawn_ts, skip removal for safety
                    continue
            # Remove loot items older than 60s
            for loot in loot_items[:]:
                try:
                    if now_ts - float(loot.get('spawn_ts', now_ts)) > 60:
                        if loot.get('type') == 'orange_egg' and loot.get('y_pos') == STARTING_LINE:
                                # find lane index from x_pos
                                lane_x = loot.get('x_pos')
                                lane = LANE_POSITIONS.index(lane_x)
                                # find the bird that occupies that lane
                                for bi in range(NUM_BALLS):
                                    if random_lanes[bi] == lane:
                                            # check for egg-state markers
                                            if (ball_colors[bi] == ORANGE and ball_y[bi] == 999 and ball_speeds[bi] == 0 and not ball_lost[bi]):
                                                # mark bird as lost and decrement lives
                                                ball_lost[bi] = True
                                                ball_y[bi] = HEIGHT - 1
                                                lives -= 1
                                                if lives <= 0:
                                                    game_over = True
                                            break
                        # Finally, remove the loot item (best-effort)
                        loot_items.remove(loot)
                except Exception:
                    continue
        except Exception:
            pass

        # Update speed boosts (decrease frame counter)
        for bird_idx in list(speed_boosts.keys()):
            if speed_boosts[bird_idx] > 0:
                # Positive = speed boost
                speed_boosts[bird_idx] -= 1
                if speed_boosts[bird_idx] <= 0:
                    try:
                        del speed_boosts[bird_idx]
                    except KeyError:
                        pass
                    # If a positive speed boost expired naturally, ensure the
                    # bird's power-used flag is cleared so UI/colour returns to normal
                    try:
                        if 0 <= bird_idx < len(ball_colors) and ball_colors[bird_idx] == BLUE:
                            bird_power_used[bird_idx] = False
                    except Exception:
                        pass
            else:
                # Negative = slow effect (count up towards 0)
                speed_boosts[bird_idx] += 1
                if speed_boosts[bird_idx] >= 0:
                    del speed_boosts[bird_idx]
        
        # Update scared birds (decrease frame counter)
        for bird_idx in list(scared_birds.keys()):
            scared_birds[bird_idx] -= 1
            if scared_birds[bird_idx] <= 0:
                del scared_birds[bird_idx]

        # Update stealth timers (decrease frame counter) - when expired, return to stealth
        for bird_idx in list(stealth_timers.keys()):
            stealth_timers[bird_idx] -= 1
            if stealth_timers[bird_idx] <= 0:
                try:
                    del stealth_timers[bird_idx]
                except Exception:
                    pass
                # IMPORTANT: do NOT reset bird_power_used here.
                # bird_power_used should remain True until the bird finishes the ascent
                # (e.g. bounces or starts descending). Resetting here would allow the
                # player to re-activate the power again during the same rise.
                # Restore previous speed if we saved one
                try:
                    if bird_idx in stealth_prev_speeds:
                        prev = stealth_prev_speeds.pop(bird_idx)
                        # Only restore if bird still exists
                        try:
                            ball_speeds[bird_idx] = prev
                        except Exception:
                            pass
                except Exception:
                    pass
        
        # Blue birds lose fear when crossing yellow birds
        # (blue going down, yellow going up, in adjacent lanes, blue passes yellow)
        birds_to_unfear = []
        for i in range(NUM_BALLS):
            if ball_colors[i] == BLUE and i in scared_birds and not ball_lost[i]:
                if ball_vy[i] == 1:  # Blue bird moving down
                    blue_lane = random_lanes[i]
                    blue_y = ball_y[i]
                    
                    # Check adjacent lanes for yellow birds moving up
                    for adj_offset in [-1, 1]:
                        adj_lane = blue_lane + adj_offset
                        if 0 <= adj_lane < 9:
                            # Find bird in adjacent lane
                            for j in range(NUM_BALLS):
                                if j != i and not ball_lost[j] and random_lanes[j] == adj_lane:
                                    if ball_colors[j] == YELLOW and ball_vy[j] == -1:  # Yellow moving up
                                        yellow_y = ball_y[j]
                                        # Check if they're crossing (blue coming from above, yellow from below)
                                        # Crossing happens when blue is just above or at same height as yellow
                                        if abs(blue_y - yellow_y) <= 2:
                                            # Pride restored - remove fear
                                            birds_to_unfear.append(i)
                                            break
                        if i in birds_to_unfear:
                            break
        
        # Remove fear from birds that crossed yellows
        for bird_idx in birds_to_unfear:
            if bird_idx in scared_birds:
                del scared_birds[bird_idx]
        
        # Update red projectiles
        for proj in red_projectiles[:]:
            # Move projectile up at speed 5
            if frame_count % 1 == 0:  # Speed 5 = move every frame
                proj['y_pos'] -= 1
                
                # Remove if off screen
                if proj['y_pos'] < 0:
                    red_projectiles.remove(proj)
                    continue
                
                # Check collision with bats
                hit_bat = False
                for bat in bats[:]:
                    bat_left = bat['x_pos']
                    bat_right = bat['x_pos'] + 8
                    bat_top = bat['y_pos']
                    bat_bottom = bat['y_pos'] + 1
                    
                    if (bat_left <= proj['x_pos'] <= bat_right and 
                        bat_top <= proj['y_pos'] <= bat_bottom):
                        # Hit bat - deal damage based on projectile power
                        bat['hp'] -= proj.get('damage', 1)
                        hit_bat = True
                        
                        if bat['hp'] <= 0:
                            # Bat defeated
                            add_score(bat['max_hp'])
                            
                            # Find closest lane to bat center
                            bat_center_x = bat['x_pos'] + 4
                            closest_lane = min(range(9), key=lambda lane_idx: abs(LANE_POSITIONS[lane_idx] - bat_center_x))
                            
                            # Loot drop logic (4 tiers with new percentages)
                            tier = bat['tier']
                            if tier == 1:
                                rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[60, 25, 10, 5])[0]
                            elif tier == 2:
                                rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[50, 30, 15, 5])[0]
                            elif tier == 3:
                                rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[40, 33, 17, 10])[0]
                            else:  # tier 4
                                rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[35, 25, 20, 15])[0]
                            
                            loot_type = choose_loot_type(rarity)
                            
                            loot_items.append({
                                'x_pos': LANE_POSITIONS[closest_lane],
                                'y_pos': bat['y_pos'],
                                'type': loot_type,
                                'rarity': rarity,
                                'spawn_ts': time.time()
                            })
                            
                            tier = bat.get('tier', None)
                            # notify achievements about bat destroy (with tier)
                            check_achievements_event('destroy_bat', tier=tier)
                            bats.remove(bat)
                        break
                
                if hit_bat:
                    red_projectiles.remove(proj)
                    continue
                
                # Check collision with obstacles
                for obs in obstacles[:]:
                    if obs['lane'] == proj['lane'] and abs(proj['y_pos'] - obs['y_pos']) <= 1:
                        # Hit obstacle - deal damage based on projectile power
                        obs['hp'] -= proj.get('damage', 1)
                        
                        if obs['hp'] <= 0:
                            add_score(obs['tier'] * 2)
                            obstacles.remove(obs)
                        
                        red_projectiles.remove(proj)
                        break
        
        # Update power-ups (decrease frame counters)
        # Active STEALTH tangible damage: while a stealth bird is tangible, apply 24 damage
        # to any bat/obstacle/loot in proximity so the power reliably has an effect.
        for i in range(NUM_BALLS):
            if ball_colors[i] == STEALTH and i in stealth_timers and stealth_timers.get(i, 0) > 0 and not ball_lost[i]:
                bird_lane = random_lanes[i]
                bird_x = LANE_POSITIONS[bird_lane]
                bird_y = ball_y[i]

                # Damage bats in proximity
                for bat in bats[:]:
                    if abs(bat.get('x_pos', 0) - bird_x) <= 6 and abs(bat.get('y_pos', 0) - bird_y) <= 2:
                        bat['hp'] -= 24
                        if bat.get('hp', 0) <= 0:
                            add_score(bat.get('max_hp', 0))
                            bat_center_x = bat.get('x_pos', 0) + 4
                            closest_lane = min(range(9), key=lambda lane_idx: abs(LANE_POSITIONS[lane_idx] - bat_center_x))
                            tier = bat.get('tier', None)
                            if tier == 1:
                                rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[60, 25, 10, 5])[0]
                            elif tier == 2:
                                rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[50, 30, 15, 5])[0]
                            elif tier == 3:
                                rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[40, 33, 17, 10])[0]
                            else:
                                rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[35, 25, 20, 15])[0]
                            loot_type = choose_loot_type(rarity)
                            loot_items.append({
                                'x_pos': LANE_POSITIONS[closest_lane],
                                'y_pos': bat.get('y_pos', 0),
                                'type': loot_type,
                                'rarity': rarity,
                                'spawn_ts': time.time()
                            })
                            try:
                                check_achievements_event('destroy_bat', tier=tier)
                            except Exception:
                                pass
                            try:
                                bats.remove(bat)
                            except ValueError:
                                pass

                # Damage obstacles in same lane
                for obs in obstacles[:]:
                    if obs.get('lane') == bird_lane and abs(obs.get('y_pos', 0) - bird_y) <= 1:
                        obs['hp'] -= 24
                        if obs.get('hp', 0) <= 0:
                            add_score(obs.get('tier', 0) * 2)
                            try:
                                obstacles.remove(obs)
                            except ValueError:
                                pass

                # Destroy loot items in proximity (tangible destroys loot)
                for loot in loot_items[:]:
                    if abs(bird_x - loot.get('x_pos', 0)) <= 2 and abs(bird_y - loot.get('y_pos', 0)) <= 2:
                        try:
                            loot_items.remove(loot)
                        except ValueError:
                            pass
        if powerups['wide_cursor_active']:
            powerups['wide_cursor_frames'] -= 1
            if powerups['wide_cursor_frames'] <= 0:
                powerups['wide_cursor_active'] = False
                powerups['wide_cursor_lanes'] = 1
        
        if powerups['bounce_boost_active']:
            powerups['bounce_boost_frames'] -= 1
            if powerups['bounce_boost_frames'] <= 0:
                powerups['bounce_boost_active'] = False
                powerups['bounce_boost_duration'] = 0
        
        if powerups['suction_active']:
            powerups['suction_frames'] -= 1
            if powerups['suction_frames'] <= 0:
                powerups['suction_active'] = False
                powerups['suction_boost_duration'] = 0

        # Tailwind expiry handling
        if powerups.get('tailwind_active'):
            try:
                powerups['tailwind_frames'] -= 1
                if powerups['tailwind_frames'] <= 0:
                    powerups['tailwind_active'] = False
                    powerups['tailwind_up_bonus'] = 0
                    powerups['tailwind_down_penalty'] = 0
            except Exception:
                powerups['tailwind_active'] = False
                powerups['tailwind_up_bonus'] = 0
                powerups['tailwind_down_penalty'] = 0

        # (slow-motion powerup removed; no expiry handling required)
        
        for i in range(NUM_BALLS):
            current_speed = ball_speeds[i]
            
            # Apply speed boost if active (only when going up)
            if i in speed_boosts:
                if speed_boosts[i] > 0 and ball_vy[i] == -1:
                    # Positive = speed boost
                    current_speed += 1
                elif speed_boosts[i] < 0 and ball_vy[i] == 1:
                    # Negative = slow effect (yellow power)
                    current_speed = max(1, current_speed - 1)
            
            # Apply scared speed boost when going down
            if i in scared_birds and ball_vy[i] == 1:
                current_speed += 1

            # Apply tailwind powerup effects (tiered):
            # - when rising (ball_vy == -1) apply up bonus (increase speed)
            # - when falling (ball_vy == 1) apply down penalty (decrease speed)
            # Clamp overall speed to [1, 6]
            if powerups.get('tailwind_active'):
                try:
                    up_bonus = int(powerups.get('tailwind_up_bonus', 0))
                    down_pen = int(powerups.get('tailwind_down_penalty', 0))
                    if ball_vy[i] == -1 and up_bonus != 0:
                        current_speed = min(6, current_speed + up_bonus)
                    elif ball_vy[i] == 1 and down_pen != 0:
                        current_speed = max(1, current_speed - down_pen)
                except Exception:
                    # On any unexpected issue, don't alter speed
                    pass
            
            # Convert speed: higher number = faster, so invert for modulo
            move_interval = max(1, 6 - current_speed)
            if not ball_lost[i] and frame_count % move_interval == 0:
                # Calculate score for active bird based on speed and position
                position_multiplier = 0.5 + (HEIGHT - ball_y[i]) / HEIGHT
                # Gold bird scores a fixed 100 points instead of its speed
                try:
                    score_value = 100 if ball_colors[i] == GOLD else ball_speeds[i]
                except Exception:
                    score_value = ball_speeds[i]
                add_score(score_value * position_multiplier)
                
                # Check collision with obstacles BEFORE moving (when moving up)
                if ball_vy[i] == -1:  # Only check collision when bird is moving up
                    bird_lane = random_lanes[i]
                    bird_lane_x = LANE_POSITIONS[bird_lane]
                    next_y = ball_y[i] + ball_vy[i]  # Calculate next position
                    collided = False
                    broken_through = False
                    
                    # Check collision with bats first - if bat enters bird's lane AT ALL, collision!
                    # Stealth birds (when not tangible) pass through bats
                    if not (ball_colors[i] == STEALTH and not (i in stealth_timers and stealth_timers.get(i, 0) > 0)):
                        for bat in bats[:]:
                            bat_left = bat['x_pos']
                            bat_right = bat['x_pos'] + 8
                            bat_top = bat['y_pos']
                            bat_bottom = bat['y_pos'] + 1

                            lane_left = bird_lane_x - 2
                            lane_right = bird_lane_x + 2
                            horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)
                            vertical_overlap = not (next_y + 2 < bat_top or next_y > bat_bottom)

                            if horizontal_overlap and vertical_overlap:
                                # Se arancione: distruggi subito il pipistrello
                                if ball_colors[i] == ORANGE:
                                    bat['hp'] = 0
                                else:
                                    # STEALTH tangible: fixed high damage
                                    if ball_colors[i] == STEALTH and (i in stealth_timers and stealth_timers.get(i, 0) > 0):
                                        damage = 24
                                    # GOLD bird deals fixed damage = 1
                                    elif ball_colors[i] == GOLD:
                                        damage = 1
                                    else:
                                        damage = current_speed
                                        if ball_colors[i] == BLUE and bird_power_used[i]:
                                            damage += 1
                                    bat['hp'] -= damage

                                # Effects on the bird (only when NOT stealth-tangible)
                                if not (ball_colors[i] == STEALTH and (i in stealth_timers and stealth_timers.get(i, 0) > 0)):
                                    bat_tier = bat['tier']
                                    if bat_tier == 1:
                                        scared_birds[i] = max(1, int(2.0 / base_sleep))
                                    elif bat_tier == 2:
                                        scared_birds[i] = max(1, int(2.0 / base_sleep))
                                    elif bat_tier == 3:
                                        scared_birds[i] = max(1, int(2.0 / base_sleep))
                                        speed_boosts[i] = int(2.0 / base_sleep)
                                    else:
                                        scared_birds[i] = max(1, int(2.0 / base_sleep))
                                        speed_boosts[i] = int(2.0 / base_sleep)

                                if bat['hp'] <= 0:
                                    add_score(bat['max_hp'])
                                    bat_center_x = bat['x_pos'] + 4
                                    closest_lane = min(range(9), key=lambda lane_idx: abs(LANE_POSITIONS[lane_idx] - bat_center_x))
                                    tier = bat['tier']
                                    if tier == 1:
                                        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[60, 25, 10, 5])[0]
                                    elif tier == 2:
                                        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[50, 30, 15, 5])[0]
                                    elif tier == 3:
                                        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[40, 33, 17, 10])[0]
                                    else:
                                        rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=[35, 25, 20, 15])[0]
                                    loot_type = choose_loot_type(rarity)
                                    loot_items.append({
                                        'x_pos': LANE_POSITIONS[closest_lane],
                                        'y_pos': bat['y_pos'],
                                        'type': loot_type,
                                        'rarity': rarity,
                                        'spawn_ts': time.time()
                                    })
                                    tier = bat.get('tier', None)
                                    # If this kill was caused by an orange bird, emit special event
                                    if ball_colors[i] == ORANGE:
                                        check_achievements_event('destroy_bat_with_orange')
                                    check_achievements_event('destroy_bat', tier=tier)
                                    bats.remove(bat)
                                    broken_through = True
                                else:
                                    ball_vy[i] = 1
                                    ball_y[i] = bat_bottom + 1
                                    # If a blue bird was sprinting, stop its sprint when it bounces
                                    try:
                                        if ball_colors[i] == BLUE:
                                            bird_power_used[i] = False
                                    except Exception:
                                        pass
                                    collided = True
                                break
                    
                    # Check collision with obstacles if not hit bat
                    if not collided and not broken_through:
                        # Stealth birds (when not tangible) pass through obstacles
                        if not (ball_colors[i] == STEALTH and not (i in stealth_timers and stealth_timers.get(i, 0) > 0)):
                            for obs in obstacles[:]:
                                if obs['lane'] == bird_lane and abs(next_y - obs['y_pos']) <= 1:
                                    # Se arancione: distruggi subito il blocco
                                    if ball_colors[i] == ORANGE:
                                        obs['hp'] = 0
                                    else:
                                        # STEALTH tangible: fixed high damage
                                        if ball_colors[i] == STEALTH and (i in stealth_timers and stealth_timers.get(i, 0) > 0):
                                            damage = 24
                                        # GOLD bird deals fixed damage = 1
                                        elif ball_colors[i] == GOLD:
                                            damage = 1
                                        else:
                                            damage = current_speed
                                            if ball_colors[i] == BLUE and bird_power_used[i]:
                                                damage += 1
                                        obs['hp'] -= damage

                                    if obs['hp'] <= 0:
                                        add_score(obs['tier'] * 2)
                                        obstacles.remove(obs)
                                        broken_through = True
                                    else:
                                        ball_vy[i] = 1
                                        # If a blue bird was sprinting, stop its sprint when it bounces
                                        try:
                                            if ball_colors[i] == BLUE:
                                                bird_power_used[i] = False
                                        except Exception:
                                            pass
                                        collided = True
                                    break
                    
                    # Only move if no collision OR broke through
                    if not collided:
                        ball_y[i] += ball_vy[i]
                else:
                    # Moving down, just move
                    # Bounce immediato per il bird clockwork (solo se ha carica)
                    if ball_colors[i] == CLOCKWORK and ball_vy[i] == 1 and ball_y[i] + ball_vy[i] >= STARTING_LINE:
                        try:
                            c = clockwork_charge.get(i, None)
                            if c is None:
                                c = 2
                                clockwork_charge[i] = 2
                            if c > 0:
                                ball_y[i] = STARTING_LINE
                                ball_vy[i] = -1
                                bird_power_used[i] = False
                            else:
                                # carica == 0: non rimbalzare qui, lasciare che cada
                                ball_y[i] += ball_vy[i]
                        except Exception:
                            # fallback: comportamento precedente
                            ball_y[i] = STARTING_LINE
                            ball_vy[i] = -1
                            bird_power_used[i] = False
                    else:
                        ball_y[i] += ball_vy[i]
                
                # Check for loot collection
                bird_lane = random_lanes[i]
                bird_lane_x = LANE_POSITIONS[bird_lane]
                for loot in loot_items[:]:
                    # Stealth birds pass through loot unless their power is active (tangible)
                    if ball_colors[i] == STEALTH and not (i in stealth_timers and stealth_timers.get(i, 0) > 0):
                        continue
                    # Check if bird is near loot (within lane and vertically close)
                    if abs(bird_lane_x - loot['x_pos']) <= 2 and abs(ball_y[i] - loot['y_pos']) <= 2:
                        # Collect loot
                        loot_type = loot['type']
                        # Notify achievements about collected loot
                        check_achievements_event('collect', loot=loot_type)

                        loot_items.remove(loot)

                        # Apply loot effects
                        if loot_type == 'yellow_egg':
                            # Spawn yellow bird in first empty lane
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_colors[idx] = YELLOW
                                    ball_lost[idx] = False
                                    # Ensure speed matches color
                                    ball_speeds[idx] = 2
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1  # Restore life
                                    break
                        elif loot_type == 'red_egg':
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_colors[idx] = RED
                                    ball_lost[idx] = False
                                    # Ensure speed matches color
                                    ball_speeds[idx] = 3
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1  # Restore life
                                    break
                        elif loot_type == 'blue_egg':
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_colors[idx] = BLUE
                                    ball_lost[idx] = False
                                    # Ensure speed matches color
                                    ball_speeds[idx] = 4
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1  # Restore life
                                    break
                        elif loot_type == 'white_egg':
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_lost[idx] = False
                                    ball_colors[idx] = WHITE
                                    ball_speeds[idx] = 5  # Fastest bird
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1  # Restore life
                                    break
                        elif loot_type == 'clockwork_egg':
                            for idx in range(NUM_BALLS):
                                    if ball_lost[idx]:
                                        ball_lost[idx] = False
                                        ball_colors[idx] = CLOCKWORK
                                        # Initialize clockwork charge and speed
                                        try:
                                            clockwork_charge[idx] = 2
                                            ball_speeds[idx] = 2
                                        except Exception:
                                            ball_speeds[idx] = 2
                                        ball_y[idx] = STARTING_LINE
                                        ball_vy[idx] = -1
                                        lives += 1  # Restore life
                                        break
                        elif loot_type == 'purple_egg':
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_lost[idx] = False
                                    ball_colors[idx] = PURPLE
                                    ball_speeds[idx] = 3
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1
                                    break
                        elif loot_type == 'gold_egg':
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_lost[idx] = False
                                    ball_colors[idx] = GOLD
                                    # Gold special bird = speed 6
                                    ball_speeds[idx] = 6
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1  # Restore life
                                    break
                        elif loot_type == 'patchwork_egg':
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_lost[idx] = False
                                    ball_colors[idx] = PATCHWORK
                                    # Patchwork bird = speed 3 (per design)
                                    ball_speeds[idx] = 3
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1  # Restore life
                                    break
                        elif loot_type == 'stealth_egg':
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_lost[idx] = False
                                    ball_colors[idx] = STEALTH
                                    # Stealth bird = speed 3 by default
                                    ball_speeds[idx] = 3
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1  # Restore life
                                    break
                        elif loot_type == 'orange_egg':
                            for idx in range(NUM_BALLS):
                                if ball_lost[idx]:
                                    ball_lost[idx] = False
                                    ball_colors[idx] = ORANGE
                                    ball_speeds[idx] = 5  # Fastest bird
                                    ball_y[idx] = STARTING_LINE
                                    ball_vy[idx] = -1
                                    lives += 1  # Restore life
                                    break
                        elif loot_type == 'wide_cursor':
                            powerups['wide_cursor_active'] = True
                            powerups['wide_cursor_frames'] = int(10.0 / base_sleep)
                            powerups['wide_cursor_lanes'] = 3
                            check_achievements_event('power_used', power='wide_cursor')
                        elif loot_type == 'wide_cursor+':
                            powerups['wide_cursor_active'] = True
                            powerups['wide_cursor_frames'] = int(20.0 / base_sleep)
                            powerups['wide_cursor_lanes'] = 3
                            check_achievements_event('power_used', power='wide_cursor')
                        elif loot_type == 'wide_cursor++':
                            powerups['wide_cursor_active'] = True
                            powerups['wide_cursor_frames'] = int(25.0 / base_sleep)
                            powerups['wide_cursor_lanes'] = 5
                            check_achievements_event('power_used', power='wide_cursor')
                        elif loot_type == 'wide_cursor_max':
                            powerups['wide_cursor_active'] = True
                            powerups['wide_cursor_frames'] = int(50.0 / base_sleep)
                            powerups['wide_cursor_lanes'] = 5
                            check_achievements_event('power_used', power='wide_cursor')
                        elif loot_type == 'bounce_boost':
                            powerups['bounce_boost_active'] = True
                            powerups['bounce_boost_frames'] = int(10.0 / base_sleep)
                            powerups['bounce_boost_duration'] = 4
                            check_achievements_event('power_used', power='bounce_boost')
                        elif loot_type == 'bounce_boost+':
                            powerups['bounce_boost_active'] = True
                            powerups['bounce_boost_frames'] = int(20.0 / base_sleep)
                            powerups['bounce_boost_duration'] = 4
                            check_achievements_event('power_used', power='bounce_boost')
                        elif loot_type == 'bounce_boost++':
                            powerups['bounce_boost_active'] = True
                            powerups['bounce_boost_frames'] = int(25.0 / base_sleep)
                            powerups['bounce_boost_duration'] = 8
                            check_achievements_event('power_used', power='bounce_boost')
                        elif loot_type == 'bounce_boost_max':
                            powerups['bounce_boost_active'] = True
                            powerups['bounce_boost_frames'] = int(50.0 / base_sleep)
                            powerups['bounce_boost_duration'] = 12
                            check_achievements_event('power_used', power='bounce_boost')
                        elif loot_type == 'suction':
                            powerups['suction_active'] = True
                            powerups['suction_frames'] = int(10.0 / base_sleep)
                            powerups['suction_boost_duration'] = 0
                            check_achievements_event('power_used', power='suction')
                        elif loot_type == 'suction+':
                            powerups['suction_active'] = True
                            powerups['suction_frames'] = int(20.0 / base_sleep)
                            powerups['suction_boost_duration'] = 0
                            check_achievements_event('power_used', power='suction')
                        elif loot_type == 'suction++':
                            powerups['suction_active'] = True
                            powerups['suction_frames'] = int(25.0 / base_sleep)
                            powerups['suction_boost_duration'] = 4
                            check_achievements_event('power_used', power='suction')
                        elif loot_type == 'suction_max':
                            powerups['suction_active'] = True
                            powerups['suction_frames'] = int(50.0 / base_sleep)
                            powerups['suction_boost_duration'] = 8
                            check_achievements_event('power_used', power='suction')
                        elif loot_type == 'tailwind':
                            # Basic tailwind: small up boost, small down penalty
                            powerups['tailwind_active'] = True
                            powerups['tailwind_frames'] = int(10.0 / base_sleep)
                            powerups['tailwind_up_bonus'] = 1
                            powerups['tailwind_down_penalty'] = 1
                            check_achievements_event('power_used', power='tailwind')
                        elif loot_type == 'tailwind+':
                            powerups['tailwind_active'] = True
                            powerups['tailwind_frames'] = int(15.0 / base_sleep)
                            powerups['tailwind_up_bonus'] = 2
                            powerups['tailwind_down_penalty'] = 1
                            check_achievements_event('power_used', power='tailwind')
                        elif loot_type == 'tailwind++':
                            powerups['tailwind_active'] = True
                            powerups['tailwind_frames'] = int(20.0 / base_sleep)
                            powerups['tailwind_up_bonus'] = 3
                            powerups['tailwind_down_penalty'] = 2
                            check_achievements_event('power_used', power='tailwind')
                        elif loot_type == 'tailwind_max':
                            powerups['tailwind_active'] = True
                            powerups['tailwind_frames'] = int(30.0 / base_sleep)
                            powerups['tailwind_up_bonus'] = 3
                            powerups['tailwind_down_penalty'] = 3
                            check_achievements_event('power_used', power='tailwind')
                        elif loot_type == 'shuffle':
                            # Shuffle 2 birds (basic)
                            try:
                                perform_shuffle(1)
                                check_achievements_event('power_used', power='shuffle')
                            except Exception:
                                pass
                        elif loot_type == 'shuffle+':
                            # Shuffle 4 birds
                            try:
                                perform_shuffle(2)
                                check_achievements_event('power_used', power='shuffle')
                            except Exception:
                                pass
                        elif loot_type == 'shuffle++':
                            # Shuffle 6 birds
                            try:
                                perform_shuffle(3)
                                check_achievements_event('power_used', power='shuffle')
                            except Exception:
                                pass
                        elif loot_type == 'shuffle_max':
                            # Shuffle many (attempt to compact all outer birds)
                            try:
                                perform_shuffle(4)
                                check_achievements_event('power_used', power='shuffle')
                            except Exception:
                                pass
                
                # Bounce off ceiling
                if ball_y[i] <= 1:
                    if ball_colors[i] == ORANGE:
                        lane = random_lanes[i]
                        ball_lost[i] = False
                        ball_y[i] = 999
                        ball_vy[i] = 0
                        bird_power_used[i] = False
                        ball_speeds[i] = 0
                        loot_items.append({'x_pos': LANE_POSITIONS[lane], 'y_pos': STARTING_LINE, 'type': 'orange_egg', 'rarity': 'epic', 'spawn_ts': time.time()})
                        continue
                    ball_y[i] = 1
                    ball_vy[i] = 1
                    bird_power_used[i] = False  # Reset power when starting to descend
                
                # Check if ball hits floor
                if ball_y[i] >= HEIGHT - 1:
                    if ball_colors[i] == CLOCKWORK:
                        # CLOCKWORK behaviour: only auto-bounce if charge > 0
                        try:
                            c = clockwork_charge.get(i, None)
                            if c is None:
                                c = 2
                                clockwork_charge[i] = 2
                            if c > 0:
                                ball_y[i] = STARTING_LINE
                                ball_vy[i] = -1
                                bird_power_used[i] = False
                            else:
                                # charge == 0: behave like other birds hitting the floor -> die
                                if not ball_lost[i]:
                                    ball_lost[i] = True
                                    ball_y[i] = HEIGHT - 1
                                    lives -= 1
                                    # Check for game over
                                    if lives <= 0:
                                        game_over = True
                        except Exception:
                            # Fallback: normal behaviour
                            ball_y[i] = STARTING_LINE
                            ball_vy[i] = -1
                            bird_power_used[i] = False
                    elif ball_colors[i] == ORANGE:
                        continue
                    elif not ball_lost[i]:  # Solo gli altri muoiono
                        ball_lost[i] = True
                        ball_y[i] = HEIGHT - 1
                        lives -= 1
                        # Check for game over
                        if lives <= 0:
                            game_over = True
        
        # Check if game over
        if game_over:
            # Clean up terminal first
            if os.name != 'nt':
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
                fcntl.fcntl(sys.stdin, fcntl.F_SETFL, old_flags)
            
            # Clear screen and show cursor
            print("\033[2J\033[H\033[?25h")
            
            # Simple game over screen with proper line endings
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print(f"{RED}{'=' * 50}{RESET}\r")
            print(f"{RED}                   GAME OVER                     {RESET}\r")
            print(f"{RED}{'=' * 50}{RESET}\r")
            print("\r")
            print(f"  Final Score:      {int(score)}\r")
            print(f"  Level Reached:    {level}\r")
            print("\r")
            # Calculate and display elapsed play time
            try:
                if game_start_time:
                    elapsed = int(time.time() - game_start_time)
                else:
                    elapsed = 0
            except Exception:
                elapsed = 0

            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            if hours > 0:
                elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                elapsed_str = f"{minutes:02d}:{seconds:02d}"

            print(f"  Time Played:      {elapsed_str} ({elapsed} s)\r")
            print(f"{RED}{'=' * 50}{RESET}\r")
            print("\r")
            # Prompt for optional leaderboard name and submit score
            try:
                name = input("Enter name for leaderboard (leave blank to skip): ").strip()[:20]
            except Exception:
                name = ""

            # Best-effort remote reporting
            try:
                if firebase_client:
                    try:
                        if name:
                            # Include time played and version when submitting leaderboard entry
                            try:
                                # Compute average points per minute (avg_ppm).
                                try:
                                    minutes = float(elapsed) / 60.0 if elapsed > 0 else 0.0
                                    if minutes > 0:
                                        avg_ppm = float(score) / minutes
                                    else:
                                        avg_ppm = float(score)
                                except Exception:
                                    avg_ppm = float(score)

                                background_call(firebase_client.send_score, name, int(score), elapsed, elapsed_str, GAME_VERSION, avg_ppm)
                            except Exception:
                                # Fallback to original call if something goes wrong
                                try:
                                    background_call(firebase_client.send_score, name, int(score))
                                except Exception:
                                    pass
                        # Include time played in the game_over analytics event
                        try:
                            # Include version and avg_ppm in the game_over analytics event as well
                            try:
                                minutes = float(elapsed) / 60.0 if elapsed > 0 else 0.0
                                if minutes > 0:
                                    avg_ppm = float(score) / minutes
                                else:
                                    avg_ppm = float(score)
                            except Exception:
                                avg_ppm = float(score)

                            background_call(firebase_client.log_event, 'game_over', {'score': int(score), 'level': level, 'time_played_seconds': elapsed, 'time_played': elapsed_str, 'version': GAME_VERSION, 'avg_ppm': avg_ppm})
                        except Exception:
                            # Fallback: log without time info
                            background_call(firebase_client.log_event, 'game_over', {'score': int(score), 'level': level, 'version': GAME_VERSION})
                        background_call(firebase_client.sync_achievements, achievements)
                    except Exception:
                        pass
            except Exception:
                pass

            print("Thanks for playing. Press Enter to exit.")
            try:
                input()
            except Exception:
                pass
            break
        
        # Gestione auto-bounce CLOCKWORK
        handle_clockwork_auto_bounce()

        time.sleep(current_sleep)

except KeyboardInterrupt:
    pass
except Exception:
    # Report unexpected crashes to Firebase (best-effort) and re-raise for visibility
    try:
        import traceback as _tb
        trace = _tb.format_exc()
        try:
            if firebase_client:
                firebase_client.report_crash(trace)
        except Exception:
            pass
    except Exception:
        pass
    raise
finally:
    cleanup()

