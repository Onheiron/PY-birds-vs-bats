#!/usr/bin/env python3
"""
Global game variables and configuration state.
Initialized from config file via init.py.
"""
import init
from types import SimpleNamespace

# Load configuration
config, args = init.init_config()

# Game state globals (will be set by configuration)
# These can be imported by other modules with: from variables import WIDTH, HEIGHT, etc.

# ============================================================================
# LAYOUT (organized as namespace)
# ============================================================================

layout = SimpleNamespace(
    width=45,
    height=30,
    num_balls=9,
    num_lanes=9,
    min_lane_index=0,
    max_lane_index=8,
    lane_positions=[5, 9, 13, 17, 21, 25, 29, 33, 37],
    starting_line=26  # height - 4
)

# Bird configuration
from bird_types import DEFAULT_FORMATION, BirdType, get_color_for_bird_type

birds = SimpleNamespace(
    default_formation=DEFAULT_FORMATION,
    randomize_lanes=True
)

# Timing
timing = SimpleNamespace(
    base_sleep=0.2,
    min_sleep=0.02,
    notification_duration_seconds=3.0,
    frame_sleep_level_multiplier=0.88
)

# Limits
limits = SimpleNamespace(
    max_entities=50
)

# Physics
physics = SimpleNamespace(
    speed_min=1,
    speed_max=6
)
# Note: Ball speeds are now in BIRD_TYPES[bird_type]['speed']

# Eggs
eggs = SimpleNamespace(
    drop_probs={0: 0.0, 1: 0.25, 2: 0.35, 3: 0.45, 4: 0.55},
    rarity_weights={
        'common': {
            'yellow_egg': 30,
            'red_egg': 25,
            'blue_egg': 20,
            'patchwork_egg': 15,
            'purple_egg': 10,
        },
        'uncommon': {
            'blue_egg': 33,
            'patchwork_egg': 25,
            'purple_egg': 20,
            'clockwork_egg': 12,
            'stealth_egg': 7,
            'cookie_egg': 3,
        },
        'rare': {
            'white_egg': 34,
            'orange_egg': 33,
            'gold_egg': 33,
        },
        'epic': {
            'dinosaur_egg': 50,
            'glitch_egg': 50,
        }
    },
    rarity_candidates={
        'common': {
            'yellow_egg': 30,
            'red_egg': 25,
            'blue_egg': 20,
            'patchwork_egg': 15,
            'purple_egg': 10,
        },
        'uncommon': {
            'blue_egg': 33,
            'patchwork_egg': 25,
            'purple_egg': 20,
            'clockwork_egg': 12,
            'stealth_egg': 7,
            'cookie_egg': 3,
        },
        'rare': {
            'white_egg': 34,
            'orange_egg': 33,
            'gold_egg': 33,
        },
        'epic': {
            'dinosaur_egg': 50,
            'glitch_egg': 50,
        }
    }
)

# ============================================================================
# ENEMIES (organized as namespaces)
# ============================================================================

# Bat enemies
bat_enemy = SimpleNamespace(
    spawn_interval_range=[120, 220],
    max_on_screen=3,
    hp_by_tier={1: 16, 2: 32, 3: 64, 4: 128},
    scared=SimpleNamespace(
        base_seconds=2.0,
        speed_boost_seconds=2.0
    ),
    loot_base_weights={
        1: [60, 25, 10, 5],
        2: [50, 30, 15, 5],
        3: [40, 33, 17, 10],
        4: [35, 25, 20, 15],
    },
    spawning=SimpleNamespace(
        wave_offset=SimpleNamespace(min=0, max=10),
        target_y_low_level=SimpleNamespace(min=10, max=12),
        target_y_high_level=SimpleNamespace(min=18, max=22),
        level_threshold=5,
        max_attempts=20,
        x_min=1,
        x_margin=9,
        min_separation=15,
        fail_retry_timer=50,
        consecutive_spawn_limit=2,
        consecutive_retry_timer=20,
        y_start=1
    ),
    tiers=SimpleNamespace(
        weights_level_0_2=[70, 20, 8, 2],
        weights_level_3_4=[50, 30, 15, 5],
        weights_level_5_7=[30, 35, 25, 10],
        weights_level_8_plus=[15, 30, 35, 20],
        level_threshold_1=2,
        level_threshold_2=4,
        level_threshold_3=7,
        hp_tier_1=16,
        hp_tier_2=32,
        hp_tier_3=64,
        hp_tier_4=128
    )
)

# Obstacle enemies
obstacle = SimpleNamespace(
    max_hp_by_tier={1: 4, 2: 6, 3: 10, 4: 16},
    spawning=SimpleNamespace(
        base_spawn_rate=SimpleNamespace(base=60, min=15),
        spawn_rate_level_multiplier=4,
        spawn_variance=SimpleNamespace(base=30, min=10),
        spawn_variance_level_multiplier=2,
        retry_timer_divisor=2,
        retry_timer_min=5,
        consecutive_spawn_limit=2
    ),
    tiers=SimpleNamespace(
        weights_level_0_2=[70, 20, 8, 2],
        weights_level_3_4=[55, 28, 13, 4],
        weights_level_5_7=[35, 35, 20, 10],
        weights_level_8_plus=[20, 30, 30, 20],
        level_threshold_1=2,
        level_threshold_2=4,
        level_threshold_3=7,
        hp_tier_1=4,
        hp_tier_2=6,
        hp_tier_3=10,
        hp_tier_4=16
    )
)

# ============================================================================
# POWER-UPS (organized as namespaces)
# ============================================================================

# Powers state
powers = SimpleNamespace(
    default={},
    blue_adjacent_boost_seconds=5.0
)

# Wide Cursor power-up
wide_cursor = SimpleNamespace(
    seconds=SimpleNamespace(
        base=10.0,
        plus=20.0,
        plusplus=25.0,
        max=50.0
    ),
    lanes=SimpleNamespace(
        base=3,
        max=5
    )
)

# Bounce Boost power-up
bounce_boost = SimpleNamespace(
    seconds=SimpleNamespace(
        base=10.0,
        plus=20.0,
        plusplus=25.0,
        max=50.0
    ),
    duration=SimpleNamespace(
        base=4,
        plus=4,
        plusplus=8,
        max=12
    )
)

# Suction power-up
suction = SimpleNamespace(
    seconds=SimpleNamespace(
        base=10.0,
        plus=20.0,
        plusplus=25.0,
        max=50.0
    ),
    boost_duration=SimpleNamespace(
        base=0,
        plus=0,
        plusplus=4,
        max=8
    )
)

# Tailwind power-up
tailwind = SimpleNamespace(
    seconds=SimpleNamespace(
        base=10.0,
        plus=15.0,
        plusplus=20.0,
        max=30.0
    ),
    up_bonus=SimpleNamespace(
        base=1,
        plus=2,
        plusplus=3
    ),
    down_penalty=SimpleNamespace(
        base=1,
        plus=1,
        plusplus=2,
        max=3
    )
)

# ============================================================================
# SPECIAL BIRDS (organized as namespaces)
# ============================================================================

# Dinosaur bird
dinosaur = SimpleNamespace(
    presses_to_bounce=15,
    press_chunk=3,
    recovery_on_egg=0.10,
    damage=16
)

# Stealth bird
stealth = SimpleNamespace(
    damage=24,
    tangible_seconds=2.0,
    speed_boost=2
)

# Gold bird
gold = SimpleNamespace(
    damage=1,
    score_value=100
)

# Clockwork bird
clockwork = SimpleNamespace(
    decay_seconds=30.0,
    initial_charge=2,
    min_charge=0,
    max_charge=3,
    lanes=SimpleNamespace(
        base=3,
        max=5
    )
)

# Glitch bird
glitch = SimpleNamespace(
    bounce_ignore_chance=0.05,
    loot_ignore_chance=0.05,
    loot_promote_chance=0.05,
    damage=SimpleNamespace(
        min=1,
        max=32
    ),
    survive_on_floor_chance=0.20,
    speed=SimpleNamespace(
        min=1,
        max=6
    ),
    flip_chance=0.01,
    swap_chance=0.01,
    nudge_chance=0.01,
    duplicate_chance=0.01
)

# Orange bird
orange = SimpleNamespace(
    recover_chance=0.10,
    out_of_play_y=999
)

# Shuffle system
shuffle = SimpleNamespace(
    level=SimpleNamespace(
        base=10,
        plus=15,
        plusplus=20,
        max=25
    )
)

# ============================================================================
# GAME SYSTEMS (organized as namespaces)
# ============================================================================

# Progression system
progression = SimpleNamespace(
    xp_base=500.0,
    grade_exp_factor=1.07,
    level_score_base=500.0,
    level_score_factor=1.07
)

# Combo system
combo = SimpleNamespace(
    window_frames=200,
    yellow_blue_chain_window=60
)

# Combat system
combat = SimpleNamespace(
    bat_center_offset=4,
    xp_bonus_per_tier=10,
    obstacle_score_multiplier=2
)

# Collision detection
collision = SimpleNamespace(
    lane_half_width=2,
    loot_collection_distance=2,
    bat_sprite_width=8
)

# Rendering
rendering = SimpleNamespace(
    dinosaur_sprite_height=3,
    normal_bird_sprite_height=2
)

# Despawn timers
despawn = SimpleNamespace(
    bat_time=60,
    loot_time=60
)

# Game over screen
game_over = SimpleNamespace(
    separator_width=50,
    time_divider=3600,
    time_remainder=3600,
    minutes_divider=60,
    leaderboard_name_max_length=20
)

# Keyboard controls
controls = SimpleNamespace(
    move_left='LEFT',
    move_right='RIGHT',
    move_up='UP',
    move_down='DOWN',
    action='SPACE',
    pause='p',
    pause_alt='P',
    toggle_xp='x',
    toggle_xp_alt='X',
    quit='QUIT'
)


# ============================================================================
# ADDITIONAL CONSTANTS (from modularization cleanup)
# ============================================================================

# Game metadata
game = SimpleNamespace(
    version="0.8.0"
)

# Note: Egg mappings, color limits, and display names are now in bird_types.py
# Use: get_bird_type_from_egg(), get_spawn_limit(), get_display_name()
# Note: Display names now in bird_types.get_display_name()

# ============================================================================
# GAME MECHANICS (organized as namespaces)
# ============================================================================

# Synergy system
synergy = SimpleNamespace(
    transfer_ratio=0.10
)

# Prestige system
prestige = SimpleNamespace(
    modifiers={
        'D': 0.0,
        'C1': 0.03125,
        'C2': 0.0625,
        'B1': 0.125,
        'B2': 0.25,
        'A1': 0.5,
        'A2': 1.0,
        'S': 5.0,
    },
    rarity_factor=0.1
)

# Transform limits (patchwork birds)
transform = SimpleNamespace(
    limits={
        get_color_for_bird_type(BirdType.YELLOW): 5,
        get_color_for_bird_type(BirdType.RED): 3,
        get_color_for_bird_type(BirdType.BLUE): 2,
    }
)

# Bat special behavior
bat = SimpleNamespace(
    scared_seconds=2.0,
    scared_speed_boost_seconds=2.0
)

# HP color scaling
colors = SimpleNamespace(
    bats_base_rgb=(255, 0, 255),   # magenta FF00FF
    obstacles_base_rgb=(0, 255, 0)  # green 00FF00
)

# ============================================================================
# APPLY CONFIGURATION OVERRIDES
# ============================================================================
# Apply configuration from YAML file to all namespaces
if config:
    from init import apply_config_to_namespace
    
    # Apply config to all namespace objects
    namespace_map = {
        'layout': layout,
        'birds': birds,
        'timing': timing,
        'limits': limits,
        'physics': physics,
        'eggs': eggs,
        'bat_enemy': bat_enemy,
        'obstacle': obstacle,
        'powers': powers,
        'wide_cursor': wide_cursor,
        'bounce_boost': bounce_boost,
        'suction': suction,
        'tailwind': tailwind,
        'dinosaur': dinosaur,
        'stealth': stealth,
        'gold': gold,
        'clockwork': clockwork,
        'glitch': glitch,
        'orange': orange,
        'shuffle': shuffle,
        'progression': progression,
        'combo': combo,
        'combat': combat,
        'collision': collision,
        'rendering': rendering,
        'despawn': despawn,
        'game_over': game_over,
        'controls': controls,
        'game': game,
        'synergy': synergy,
        'prestige': prestige,
        'transform': transform,
        'bat': bat,
        'colors': colors,
    }
    
    for key, namespace_obj in namespace_map.items():
        if key in config:
            apply_config_to_namespace(namespace_obj, config[key], key)
