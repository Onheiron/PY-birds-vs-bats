#!/usr/bin/env python3
"""
Game state module - contains all mutable game state organized in namespaces.
This module centralizes all variables that change during gameplay.
Import as: from src.core import state
Access as: state.birds.colors, state.game.score, etc.
"""

from src.core import constants
from src.entities.bird_types import BirdType, get_default_speed, get_color_for_bird_type
from src.entities.sprites import YELLOW
from types import SimpleNamespace

# ============================================================================
# BIRDS STATE (organized as namespace)
# ============================================================================
birds = SimpleNamespace(
    colors=[],
    cols=[],
    y=[],
    vy=[],
    speeds=[],
    lost=[],
    power_used=[],
    power_uses=[],
    random_lanes=[],
    per_bird_xp=[],
    transformed=[],
    original_indices=[]
)

# ============================================================================
# SPECIAL BIRDS STATE (organized as namespace)
# ============================================================================
special = SimpleNamespace(
    # Red bird projectiles
    red_projectiles=[],
    
    # Speed boosts
    speed_boosts={},
    
    # Dinosaur
    dinosaur_up_presses={},
    
    # Scared birds
    scared_birds={},

    # Stunned birds (from obstacle collision - short duration, no speed boost)
    stunned_birds={},
    
    # Stealth
    stealth_timers={},
    stealth_prev_speeds={},
    
    # Clockwork
    clockwork_charge={},
    
    # Cookie
    cookie_crumbs_made={},
    
    # Purple bird charging state
    purple_state=[],
    purple_primed_frame=[],
    purple_charge_started_frame=[],
    purple_saved_vy=[],
    purple_miss_count=[],
    purple_just_fired_frames=[],
    purple_hold_counter=[],
    
    # Global UP counters
    up_hold_counter=0,
    up_miss_counter=0
)

# ============================================================================
# ENEMIES STATE (organized as namespace)
# ============================================================================
enemies = SimpleNamespace(
    obstacles=[],
    obstacle_spawn_timer=0,
    bats=[],
    bat_spawn_timer=0,
    spawn_queue=[]
)

# ============================================================================
# ITEMS STATE (organized as namespace)
# ============================================================================
items = SimpleNamespace(
    loot_items=[]
)

# ============================================================================
# POWER-UPS STATE (organized as namespace)
# ============================================================================
powerups = SimpleNamespace(
    wide_cursor_active=False,
    wide_cursor_frames=0,
    wide_cursor_lanes=1,
    bounce_boost_active=False,
    bounce_boost_frames=0,
    bounce_boost_duration=0,
    suction_active=False,
    suction_frames=0,
    suction_boost_duration=0,
    tailwind_active=False,
    tailwind_frames=0,
    tailwind_up_bonus=0,
    tailwind_down_penalty=0
)

# ============================================================================
# GAME STATE (organized as namespace)
# ============================================================================
game = SimpleNamespace(
    score=0,
    level=1,              # Level as milestone (1-18, displayed as 1-1 to 6-3)
    level_group=1,        # Group number (1-6)
    level_sub=1,          # Sub-level within group (1-3)
    speed=1,              # Speed level (1-10) - controls game pace
    miles=0.0,            # Miles traveled (accumulated over time based on speed)
    lives=5,
    game_over=False,
    quit_requested=False,  # True quando l'utente esce con Q/CTRL+C
    swaps_used=0,
    paused=False,
    frame_count=0,
    start_time=None,
    last_mile_update=None  # Timestamp for mile calculation
)

# ============================================================================
# PLAYER STATE (organized as namespace)
# ============================================================================
player = SimpleNamespace(
    lane=2,
    selected_lane=None,
    last_space_state=False,
    last_up_state=False
)

# ============================================================================
# UI STATE (organized as namespace)
# ============================================================================
ui = SimpleNamespace(
    show_xp_overlay=False,
    bg_offset=0,
    notifications=[]
)


def init():
    """Initialize all game state using namespaces."""
    import random
    
    # Initialize bird colors from default formation (configurable via constants.birds.default_formation)
    birds.colors = []
    for bird_type in constants.birds.default_formation[:constants.layout.num_balls]:
        color = get_color_for_bird_type(bird_type)
        birds.colors.append(color)
    
    # Pad with YELLOW if formation is shorter than NUM_BALLS
    while len(birds.colors) < constants.layout.num_balls:
        birds.colors.append(YELLOW)
    
    # Randomize which bird goes to which lane
    random.seed()
    birds.random_lanes = list(range(constants.layout.num_lanes))
    if constants.birds.randomize_lanes:
        random.shuffle(birds.random_lanes)
    
    # Initialize position and velocity arrays
    birds.cols = [constants.layout.lane_positions[birds.random_lanes[i]] for i in range(constants.layout.num_balls)]
    constants.layout.starting_line = constants.layout.height - 4
    birds.y = [constants.layout.starting_line] * constants.layout.num_balls
    birds.vy = [-1] * constants.layout.num_balls
    birds.lost = [False] * constants.layout.num_balls
    birds.power_used = [False] * constants.layout.num_balls
    birds.power_uses = [0] * constants.layout.num_balls
    
    birds.per_bird_xp = [0] * constants.layout.num_balls
    birds.transformed = [False] * constants.layout.num_balls
    
    # Purple bird state
    special.purple_state = [0] * constants.layout.num_balls
    special.purple_primed_frame = [0] * constants.layout.num_balls
    special.purple_charge_started_frame = [0] * constants.layout.num_balls
    special.purple_saved_vy = [None] * constants.layout.num_balls
    special.purple_miss_count = [0] * constants.layout.num_balls
    special.purple_just_fired_frames = [0] * constants.layout.num_balls
    special.purple_hold_counter = [0] * constants.layout.num_balls
    
    # Red bird projectiles
    special.red_projectiles = []
    
    # Special bird state
    special.speed_boosts = {}
    special.dinosaur_up_presses = {}
    special.scared_birds = {}
    special.stunned_birds = {}
    special.stealth_timers = {}
    special.stealth_prev_speeds = {}
    special.clockwork_charge = {}
    special.cookie_crumbs_made = {}
    special.up_hold_counter = 0
    special.up_miss_counter = 0
    
    # UI state
    ui.show_xp_overlay = False
    ui.bg_offset = 0
    ui.notifications = []
    
    # Enemies
    enemies.obstacles = []
    enemies.obstacle_spawn_timer = 0
    enemies.bats = []
    enemies.bat_spawn_timer = 0
    enemies.spawn_queue = []
    
    # Items
    items.loot_items = []
    
    # Power-ups (reset to default values)
    powerups.wide_cursor_active = False
    powerups.wide_cursor_frames = 0
    powerups.wide_cursor_lanes = 1
    powerups.bounce_boost_active = False
    powerups.bounce_boost_frames = 0
    powerups.bounce_boost_duration = 0
    powerups.suction_active = False
    powerups.suction_frames = 0
    powerups.suction_boost_duration = 0
    powerups.tailwind_active = False
    powerups.tailwind_frames = 0
    powerups.tailwind_up_bonus = 0
    powerups.tailwind_down_penalty = 0
    
    # Game state
    game.score = 0
    game.level = 1
    game.level_group = 1
    game.level_sub = 1
    game.speed = 1
    game.miles = 0.0
    game.lives = 5
    game.game_over = False
    game.quit_requested = False
    game.swaps_used = 0
    game.paused = False
    game.frame_count = 0
    game.last_mile_update = None
    
    # Player state
    player.lane = 2
    player.selected_lane = None
    player.last_space_state = False
    player.last_up_state = False

    # Track original bird indices
    birds.original_indices = list(range(constants.layout.num_balls))
    
    # Assign speeds based on bird formation
    birds.speeds = []
    for i in range(constants.layout.num_balls):
        try:
            bird_type = constants.birds.default_formation[i] if i < len(constants.birds.default_formation) else BirdType.YELLOW
            spd = get_default_speed(bird_type)
            birds.speeds.append(int(spd))
        except Exception:
            birds.speeds.append(2)
