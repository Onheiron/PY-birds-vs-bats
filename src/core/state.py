#!/usr/bin/env python3
"""
Game state module - contains all mutable game state organized in namespaces.
This module centralizes all variables that change during gameplay.
Import as: from src.core import state
Access as: state.birds.colors, state.game.score, etc.
"""

import time
from src.core import constants
from src.entities.bird_types import BirdType, get_default_speed, get_color_for_bird_type
from types import SimpleNamespace

# Default yellow color (avoid circular import from sprites)
_YELLOW_DEFAULT = get_color_for_bird_type(BirdType.YELLOW)

# Game seed for deterministic RNG (set on new game, saved/restored on load)
game_seed = None

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
    random_lanes=[],      # Current physical lane
    home_lanes=[],        # "Home" lane - where bird would end up following portals down
    per_bird_xp=[],
    transformed=[],
    pending_transform=[],  # Bird wants to transform but can't (limit reached) - stores target color
    original_indices=[],
    portal_cooldown={},  # {bird_idx: frame_until_can_teleport_again}
)

# ============================================================================
# SPECIAL BIRDS STATE (organized as namespace)
# ============================================================================
special = SimpleNamespace(
    # Red bird projectiles
    red_projectiles=[],
    
    # Speed boosts
    speed_boosts={},

    # Dive fall boosts (from diver bats in diving state)
    dive_fall_boosts={},

    # Dinosaur
    dinosaur_up_presses={},

    # Scared birds
    scared_birds={},

    # Stunned birds (from obstacle collision - short duration, no speed boost)
    stunned_birds={},

    # Frozen birds (from Tree Boss blue flower)
    # {bird_idx: {'thaw_attempts_needed': int, 'thaw_attempts_done': int}}
    frozen_birds={},

    # Poisoned birds (from Tree Boss green flower)
    # {bird_idx: {'death_time': float, 'cure_attempts_needed': int, 'cure_attempts_done': int}}
    poisoned_birds={},

    # Bleeding birds (from Tree Boss red flower)
    # {bird_idx: {'end_time': float}} - press UP = instant death
    bleeding_birds={},

    # Stealth
    stealth_timers={},
    stealth_prev_speeds={},
    
    # Clockwork
    clockwork_charge={},       # bird_idx -> current charge (0-3)
    clockwork_last_decay={},   # bird_idx -> timestamp of last decay
    
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
    up_miss_counter=0,

    # Track last UP press time (for Purple hold-to-charge)
    last_up_time=0.0,

    # Rainbow bird state
    rainbow_charge={},          # bird_idx -> charge level (0-100)
    rainbow_last_decay={},      # bird_idx -> timestamp of last decay

    # Twister bird state
    twister_tailwind={},        # bird_idx -> {'end_time': float, 'lanes': [int]}

    # Status effect birds (power boost mode)
    frosty_boosted={},          # bird_idx -> end_time (60% freeze mode)
    poison_boosted={},          # bird_idx -> end_time (60% poison mode)
    berserk_boosted={},         # bird_idx -> end_time (60% bleed mode)
    rock_boosted={},            # bird_idx -> end_time (boosted push mode)
    rock_prev_speeds={},        # bird_idx -> original speed before ROCK boost

    # Enemy debuffs (NEW - applied by birds to enemies)
    frozen_enemies={},          # enemy_id -> {'end_time': float, 'type': 'bat'|'obstacle'}
    poisoned_enemies={},        # enemy_id -> {'end_time': float, 'last_tick': float}
    bleeding_enemies={},        # enemy_id -> {'end_time': float, 'last_tick': float}
)

# ============================================================================
# ENEMIES STATE (organized as namespace)
# ============================================================================
enemies = SimpleNamespace(
    obstacles=[],
    obstacle_spawn_timer=0,
    obstacle_id_counter=0,  # Unique ID counter for obstacles
    bats=[],
    bat_spawn_timer=0,
    spawn_queue=[],
    # Mini bats that hide in tier 3+ obstacles
    mini_bats=[],  # Active mini bats on screen
    hidden_mini_bats={},  # Mini bats hidden in obstacles: {obstacle_id: [mini_bat, ...]}
    # Decorative barriers in right panel (no collision)
    right_panel_barriers=[],
    right_panel_barrier_timer=0,
    # Mountain Range cloud banks (foreground fog)
    cloud_banks=[],
    cloud_spawn_timer=0,
    # Boss state (end of biome bosses)
    boss=None,  # None or dict with boss data
    boss_spawned=False,  # True if boss has been spawned this level
    boss_defeated=False,  # True if boss was defeated
    # Cave portals (biome 5) - always spawn in pairs
    # Each portal: {'x_pos': int, 'y_pos': int, 'pair_id': int, 'portal_idx': 0 or 1}
    portals=[],
    portal_spawn_timer=0,
    portal_pair_counter=0,  # Unique ID for portal pairs
)

# ============================================================================
# ITEMS STATE (organized as namespace)
# ============================================================================
items = SimpleNamespace(
    loot_items=[]
)

# ============================================================================
# SPELL EFFECTS STATE (from spellcaster bats)
# ============================================================================
spells = SimpleNamespace(
    # Silence spell - lanes where bird powers are disabled
    # {lane_index: {'end_time': float, 'caster_tier': int}}
    silenced_lanes={},

    # Repugnant wind spell - reverse tailwind effect on lanes
    # {lane_index: {'end_time': float, 'speed_boost': int, 'speed_nerf': int}}
    repugnant_wind_lanes={},

    # Exile spell - pending swaps
    # [{'swap_time': float, 'bird_a_idx': int, 'bird_b_idx': int or None}]
    pending_exiles=[],
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
    tailwind_down_penalty=0,
    # Timelapse effect (slows game tick)
    timelapse_active=False,
    timelapse_end_time=0.0,  # Unix timestamp when timelapse ends (real time)
    timelapse_slowdown=1.0,  # Multiplier: 2.0 = game runs at half speed
    # Wind Boss effects
    wind_boss_up_bonus=0,
    wind_boss_down_penalty=0,
)

# ============================================================================
# GAME STATE (organized as namespace)
# ============================================================================
game = SimpleNamespace(
    score=0,              # Total score (never decreases)
    momentum=getattr(constants.speed, 'starting_momentum', 100),  # Momentum (from config)
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
    # Parallax background layers (3 layers with different speeds)
    bg_offset=0,         # Slowest layer (original tree pattern)
    bg_mid_offset=0,     # Middle layer (∧ symbols, intermediate speed)
    # Cave shimmer effect - particles that fade in/out from darkness
    # Dict of {(x, y): brightness} where brightness is 0.0 (dark) to 1.0 (bright)
    cave_shimmer={},
    # Notifications: list of dicts with {title, text, expire_frame}
    # New notifications insert at index 0 (top), old ones at end (bottom)
    notifications=[],
    # Level sign animation in right panel (legacy, not used)
    level_sign_scroll_y=0,
    level_sign_scrolling=False,
    # Pause menu state
    pause_menu_index=0,  # 0=RESUME, 1=RESTART, 2=SAVE & EXIT, etc.
    # Settings menu state
    settings_menu=None,  # None=not in settings, 'main'/'sound'/'graphics'/'controls'/'save'/'load'
    settings_index=0,    # Current selection index in settings submenu
    # Key rebinding state
    rebinding_control=None,  # None or control name being rebound (e.g., 'MOVE_LEFT')
    # Title screen state
    title_menu_index=0,  # 0=CONTINUE, 1=NEW GAME, 2=LOAD, 3=QUIT
    show_title=True,     # True when on title screen
)

# ============================================================================
# SETTINGS STATE (runtime settings that can be toggled)
# ============================================================================
settings = SimpleNamespace(
    # Sound settings
    sfx_enabled=True,
    music_enabled=True,
    # Graphics settings
    background_enabled=True,
    parallax_enabled=True,
    accessibility_enabled=False,
    # Difficulty: 0=EASY, 1=NORMAL, 2=HARD, 3=HELL
    difficulty=1,
    # Key bindings (can be remapped)
    key_bindings={
        'MOVE_LEFT': 'LEFT',
        'MOVE_RIGHT': 'RIGHT',
        'BOUNCE': 'UP',
        'SUCTION': 'DOWN',
        'SWAP': 'SPACE',
    },
    # Flag to track if settings have been initialized from config
    _initialized=False,
)

# ============================================================================
# DISCOVERY STATE (tracks what the player has discovered)
# ============================================================================
discovery = SimpleNamespace(
    # Bird types discovered (set of bird type names)
    birds=set(),
    # Bat types discovered (set of bat type names)
    bats=set(),
    # Obstacle types discovered (set of obstacle type names)
    obstacles=set(),
    # Biomes visited (set of biome names)
    biomes=set(),
)


def init(seed=None):
    """Initialize all game state using namespaces.

    Args:
        seed: Optional seed for RNG. If None, generates a new one based on current time.
    """
    global game_seed
    import random

    # Generate or use provided seed for deterministic gameplay
    if seed is None:
        game_seed = int(time.time() * 1000) % (2**32)
    else:
        game_seed = seed
    random.seed(game_seed)

    # Initialize bird colors from default formation (configurable via constants.birds.default_formation)
    birds.colors = []
    for bird_type in constants.birds.default_formation[:constants.layout.num_balls]:
        color = get_color_for_bird_type(bird_type)
        birds.colors.append(color)

    # Pad with YELLOW if formation is shorter than NUM_BALLS
    while len(birds.colors) < constants.layout.num_balls:
        birds.colors.append(_YELLOW_DEFAULT)

    # Randomize which bird goes to which lane
    birds.random_lanes = list(range(constants.layout.num_lanes))
    if constants.birds.randomize_lanes:
        random.shuffle(birds.random_lanes)
    # Home lanes start same as random_lanes (where bird would go following portals down)
    birds.home_lanes = birds.random_lanes.copy()

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
    birds.pending_transform = [None] * constants.layout.num_balls  # None or target color

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
    special.dive_fall_boosts = {}
    special.dinosaur_up_presses = {}
    special.scared_birds = {}
    special.stunned_birds = {}
    special.frozen_birds = {}
    special.poisoned_birds = {}
    special.bleeding_birds = {}
    special.stealth_timers = {}
    special.stealth_prev_speeds = {}
    special.clockwork_charge = {}
    special.clockwork_last_decay = {}
    special.cookie_crumbs_made = {}
    special.up_hold_counter = 0
    special.up_miss_counter = 0
    special.last_up_time = 0.0

    # New bird states
    special.rainbow_charge = {}
    special.rainbow_last_decay = {}
    special.twister_tailwind = {}
    special.frosty_boosted = {}
    special.poison_boosted = {}
    special.berserk_boosted = {}
    special.rock_boosted = {}
    special.rock_prev_speeds = {}

    # Enemy debuffs
    special.frozen_enemies = {}
    special.poisoned_enemies = {}
    special.bleeding_enemies = {}

    # Spell effects
    spells.silenced_lanes = {}
    spells.repugnant_wind_lanes = {}
    spells.pending_exiles = []

    # UI state
    ui.show_xp_overlay = False
    ui.bg_offset = 0
    ui.bg_mid_offset = 0
    ui.cave_shimmer = {}
    ui.notifications = []
    ui.level_sign_scroll_y = 0
    ui.level_sign_scrolling = False
    ui.pause_menu_index = 0
    ui.settings_menu = None
    ui.settings_index = 0

    # Note: settings state is NOT reset on init() - persists across restarts
    
    # Enemies
    enemies.obstacles = []
    enemies.obstacle_spawn_timer = 0
    enemies.obstacle_id_counter = 0
    enemies.bats = []
    enemies.bat_spawn_timer = 0
    enemies.spawn_queue = []
    enemies.mini_bats = []
    enemies.hidden_mini_bats = {}
    enemies.right_panel_barriers = []
    enemies.right_panel_barrier_timer = 0
    enemies.boss = None
    enemies.boss_spawned = False
    enemies.boss_defeated = False
    enemies.portals = []
    enemies.portal_spawn_timer = 0
    enemies.portal_pair_counter = 0

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
    powerups.timelapse_active = False
    powerups.timelapse_end_time = 0.0
    powerups.timelapse_slowdown = 1.0
    powerups.wind_boss_up_bonus = 0
    powerups.wind_boss_down_penalty = 0
    
    # Game state
    game.score = 0
    game.miles = 0.0
    game.level_group = 1
    game.level = 1
    game.level_sub = 1
    game.speed = 1
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
    birds.portal_cooldown = {}
    
    # Assign speeds based on bird formation
    birds.speeds = []
    for i in range(constants.layout.num_balls):
        try:
            bird_type = constants.birds.default_formation[i] if i < len(constants.birds.default_formation) else BirdType.YELLOW
            spd = get_default_speed(bird_type)
            birds.speeds.append(int(spd))
        except Exception:
            birds.speeds.append(2)

    # Initialize runtime settings from config (only once, on first init)
    if not settings._initialized:
        settings.background_enabled = getattr(constants.background, 'enabled', True)
        settings.parallax_enabled = getattr(constants.background, 'parallax', True)
        settings._initialized = True
