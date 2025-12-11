#!/usr/bin/env python3
"""
Global game variables and configuration state.
Initialized from config file via init.py.
"""
import init
from types import SimpleNamespace

# Load configuration
_config, _args = init.init_config()

# Export config for other modules
config = _config
args = _args

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

# Backward compatibility
WIDTH = layout.width
HEIGHT = layout.height
NUM_BALLS = layout.num_balls
NUM_LANES = layout.num_lanes
MIN_LANE_INDEX = layout.min_lane_index
MAX_LANE_INDEX = layout.max_lane_index
LANE_POSITIONS = layout.lane_positions
STARTING_LINE = layout.starting_line

# Bird configuration
from bird_types import DEFAULT_FORMATION

birds = SimpleNamespace(
    default_formation=DEFAULT_FORMATION,
    randomize_lanes=True
)

# Backward compatibility
DEFAULT_BIRD_FORMATION = birds.default_formation
RANDOMIZE_LANES = birds.randomize_lanes

# Timing
timing = SimpleNamespace(
    base_sleep=0.2,
    min_sleep=0.02,
    notification_duration_seconds=3.0,
    frame_sleep_level_multiplier=0.88
)

# Backward compatibility
BASE_SLEEP = timing.base_sleep
MIN_SLEEP = timing.min_sleep
NOTIFICATION_DURATION_SECONDS = timing.notification_duration_seconds
FRAME_SLEEP_LEVEL_MULTIPLIER = timing.frame_sleep_level_multiplier

# Limits
limits = SimpleNamespace(
    max_entities=50
)

# Backward compatibility
MAX_ENTITIES = limits.max_entities

# Physics
physics = SimpleNamespace(
    speed_min=1,
    speed_max=6
)
# Note: Ball speeds are now in BIRD_TYPES[bird_type]['speed']

# Backward compatibility
SPEED_MIN = physics.speed_min
SPEED_MAX = physics.speed_max

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

# Backward compatibility
EGG_PROBS = eggs.drop_probs
RARITY_WEIGHTS = eggs.rarity_weights
RARITY_EGGS_CANDIDATES = eggs.rarity_candidates

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

# Backward compatibility
BAT_SPAWN_INTERVAL_RANGE = bat_enemy.spawn_interval_range
BAT_MAX_ON_SCREEN = bat_enemy.max_on_screen
BAT_HP_BY_TIER = bat_enemy.hp_by_tier
SCARED_BASE_SECONDS = bat_enemy.scared.base_seconds
SCARED_SPEED_BOOST_SECONDS = bat_enemy.scared.speed_boost_seconds
BAT_LOOT_BASE_WEIGHTS = bat_enemy.loot_base_weights
BAT_WAVE_OFFSET_MIN = bat_enemy.spawning.wave_offset.min
BAT_WAVE_OFFSET_MAX = bat_enemy.spawning.wave_offset.max
BAT_TARGET_Y_MIN_LOW_LEVEL = bat_enemy.spawning.target_y_low_level.min
BAT_TARGET_Y_MAX_LOW_LEVEL = bat_enemy.spawning.target_y_low_level.max
BAT_TARGET_Y_MIN_HIGH_LEVEL = bat_enemy.spawning.target_y_high_level.min
BAT_TARGET_Y_MAX_HIGH_LEVEL = bat_enemy.spawning.target_y_high_level.max
BAT_TARGET_Y_LEVEL_THRESHOLD = bat_enemy.spawning.level_threshold
BAT_SPAWN_MAX_ATTEMPTS = bat_enemy.spawning.max_attempts
BAT_SPAWN_X_MIN = bat_enemy.spawning.x_min
BAT_SPAWN_X_MARGIN = bat_enemy.spawning.x_margin
BAT_MIN_SEPARATION = bat_enemy.spawning.min_separation
BAT_SPAWN_FAIL_RETRY_TIMER = bat_enemy.spawning.fail_retry_timer
BAT_CONSECUTIVE_SPAWN_LIMIT = bat_enemy.spawning.consecutive_spawn_limit
BAT_CONSECUTIVE_RETRY_TIMER = bat_enemy.spawning.consecutive_retry_timer
BAT_SPAWN_Y_START = bat_enemy.spawning.y_start
BAT_TIER_WEIGHTS_LEVEL_0_2 = bat_enemy.tiers.weights_level_0_2
BAT_TIER_WEIGHTS_LEVEL_3_4 = bat_enemy.tiers.weights_level_3_4
BAT_TIER_WEIGHTS_LEVEL_5_7 = bat_enemy.tiers.weights_level_5_7
BAT_TIER_WEIGHTS_LEVEL_8_PLUS = bat_enemy.tiers.weights_level_8_plus
BAT_TIER_LEVEL_THRESHOLD_1 = bat_enemy.tiers.level_threshold_1
BAT_TIER_LEVEL_THRESHOLD_2 = bat_enemy.tiers.level_threshold_2
BAT_TIER_LEVEL_THRESHOLD_3 = bat_enemy.tiers.level_threshold_3
BAT_HP_TIER_1 = bat_enemy.tiers.hp_tier_1
BAT_HP_TIER_2 = bat_enemy.tiers.hp_tier_2
BAT_HP_TIER_3 = bat_enemy.tiers.hp_tier_3
BAT_HP_TIER_4 = bat_enemy.tiers.hp_tier_4

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

# Backward compatibility
OBSTACLE_MAX_HP_BY_TIER = obstacle.max_hp_by_tier
OBSTACLE_BASE_SPAWN_RATE_BASE = obstacle.spawning.base_spawn_rate.base
OBSTACLE_BASE_SPAWN_RATE_MIN = obstacle.spawning.base_spawn_rate.min
OBSTACLE_SPAWN_RATE_LEVEL_MULTIPLIER = obstacle.spawning.spawn_rate_level_multiplier
OBSTACLE_SPAWN_VARIANCE_BASE = obstacle.spawning.spawn_variance.base
OBSTACLE_SPAWN_VARIANCE_MIN = obstacle.spawning.spawn_variance.min
OBSTACLE_SPAWN_VARIANCE_LEVEL_MULTIPLIER = obstacle.spawning.spawn_variance_level_multiplier
OBSTACLE_RETRY_TIMER_DIVISOR = obstacle.spawning.retry_timer_divisor
OBSTACLE_RETRY_TIMER_MIN = obstacle.spawning.retry_timer_min
OBSTACLE_CONSECUTIVE_SPAWN_LIMIT = obstacle.spawning.consecutive_spawn_limit
OBSTACLE_TIER_WEIGHTS_LEVEL_0_2 = obstacle.tiers.weights_level_0_2
OBSTACLE_TIER_WEIGHTS_LEVEL_3_4 = obstacle.tiers.weights_level_3_4
OBSTACLE_TIER_WEIGHTS_LEVEL_5_7 = obstacle.tiers.weights_level_5_7
OBSTACLE_TIER_WEIGHTS_LEVEL_8_PLUS = obstacle.tiers.weights_level_8_plus
OBSTACLE_TIER_LEVEL_THRESHOLD_1 = obstacle.tiers.level_threshold_1
OBSTACLE_TIER_LEVEL_THRESHOLD_2 = obstacle.tiers.level_threshold_2
OBSTACLE_TIER_LEVEL_THRESHOLD_3 = obstacle.tiers.level_threshold_3
OBSTACLE_HP_TIER_1 = obstacle.tiers.hp_tier_1
OBSTACLE_HP_TIER_2 = obstacle.tiers.hp_tier_2
OBSTACLE_HP_TIER_3 = obstacle.tiers.hp_tier_3
OBSTACLE_HP_TIER_4 = obstacle.tiers.hp_tier_4

# ============================================================================
# POWER-UPS (organized as namespaces)
# ============================================================================

# Powers state
powers = SimpleNamespace(
    default={},
    blue_adjacent_boost_seconds=5.0
)

# Backward compatibility
POWERS_DEFAULT = powers.default
BLUE_ADJACENT_BOOST_SECONDS = powers.blue_adjacent_boost_seconds

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

# Backward compatibility
XP_BASE = progression.xp_base
GRADE_EXP_FACTOR = progression.grade_exp_factor
LEVEL_SCORE_BASE = progression.level_score_base
LEVEL_SCORE_FACTOR = progression.level_score_factor

COMBO_WINDOW_FRAMES = combo.window_frames
YELLOW_BLUE_CHAIN_WINDOW = combo.yellow_blue_chain_window

BAT_CENTER_OFFSET = combat.bat_center_offset
XP_BONUS_PER_TIER = combat.xp_bonus_per_tier
OBSTACLE_SCORE_MULTIPLIER = combat.obstacle_score_multiplier

LANE_COLLISION_HALF_WIDTH = collision.lane_half_width
LOOT_COLLECTION_DISTANCE = collision.loot_collection_distance
BAT_SPRITE_WIDTH = collision.bat_sprite_width

DINOSAUR_SPRITE_HEIGHT = rendering.dinosaur_sprite_height
NORMAL_BIRD_SPRITE_HEIGHT = rendering.normal_bird_sprite_height

BAT_DESPAWN_TIME = despawn.bat_time
LOOT_DESPAWN_TIME = despawn.loot_time

GAME_OVER_SEPARATOR_WIDTH = game_over.separator_width
GAME_OVER_TIME_DIVIDER = game_over.time_divider
GAME_OVER_TIME_REMAINDER = game_over.time_remainder
GAME_OVER_MINUTES_DIVIDER = game_over.minutes_divider
LEADERBOARD_NAME_MAX_LENGTH = game_over.leaderboard_name_max_length

KEY_MOVE_LEFT = controls.move_left
KEY_MOVE_RIGHT = controls.move_right
KEY_MOVE_UP = controls.move_up
KEY_MOVE_DOWN = controls.move_down
KEY_ACTION = controls.action
KEY_PAUSE = controls.pause
KEY_PAUSE_ALT = controls.pause_alt
KEY_TOGGLE_XP = controls.toggle_xp
KEY_TOGGLE_XP_ALT = controls.toggle_xp_alt
KEY_QUIT = controls.quit

SHUFFLE_LEVEL_BASE = shuffle.level.base
SHUFFLE_LEVEL_PLUS = shuffle.level.plus
SHUFFLE_LEVEL_PLUSPLUS = shuffle.level.plusplus
SHUFFLE_LEVEL_MAX = shuffle.level.max


# Apply configuration overrides
if config:
    # Layout
    if 'layout' in config and isinstance(config['layout'], dict):
        layout_cfg = config['layout']
        WIDTH = layout_cfg.get('width', layout.width)
        HEIGHT = layout_cfg.get('height', layout.height)
        NUM_BALLS = layout_cfg.get('num_balls', layout.num_balls)
        if 'lane_positions' in layout_cfg:
            LANE_POSITIONS = layout_cfg['lane_positions']
        
        if 'constraints' in layout_cfg and isinstance(layout_cfg['constraints'], dict):
            const = layout_cfg['constraints']
            NUM_LANES = const.get('num_lanes', layout.num_lanes)
            MIN_LANE_INDEX = const.get('min_lane_index', layout.min_lane_index)
            MAX_LANE_INDEX = const.get('max_lane_index', layout.max_lane_index)
    
    # Recalculate derived values
    STARTING_LINE = HEIGHT - 4
    
    # Birds
    if 'birds' in config and isinstance(config['birds'], dict):
        birds_cfg = config['birds']
        if 'formation' in birds_cfg:
            DEFAULT_BIRD_FORMATION = [str(b).upper() for b in birds_cfg['formation']]
        RANDOMIZE_LANES = birds_cfg.get('randomize_lanes', birds.randomize_lanes)
    
    # Timing
    if 'timing' in config and isinstance(config['timing'], dict):
        timing_cfg = config['timing']
        NOTIFICATION_DURATION_SECONDS = timing_cfg.get('notification_duration_seconds', timing.notification_duration_seconds)
        BASE_SLEEP = timing_cfg.get('base_sleep', timing.base_sleep)
        MIN_SLEEP = timing_cfg.get('min_sleep', timing.min_sleep)
        FRAME_SLEEP_LEVEL_MULTIPLIER = timing_cfg.get('frame_sleep_level_multiplier', timing.frame_sleep_level_multiplier)
    
    # Limits
    if 'limits' in config and isinstance(config['limits'], dict):
        MAX_ENTITIES = config['limits'].get('max_entities', limits.max_entities)
    
    # Eggs
    if 'egg_probs' in config:
        ev = config['egg_probs']
        if isinstance(ev, dict):
            EGG_PROBS = {int(k): float(v) for k, v in ev.items()}
        elif isinstance(ev, (list, tuple)):
            EGG_PROBS = {i: float(ev[i]) for i in range(len(ev))}
    
    if 'rarity_weights' in config and isinstance(config['rarity_weights'], dict):
        for rarity, weights in config['rarity_weights'].items():
            if rarity in eggs.rarity_weights and isinstance(weights, dict):
                eggs.rarity_weights[rarity].update(weights)
                RARITY_WEIGHTS[rarity].update(weights)
    
    # Physics
    if 'physics' in config and isinstance(config['physics'], dict):
        physics_cfg = config['physics']
        SPEED_MIN = physics_cfg.get('speed_min', physics.speed_min)
        SPEED_MAX = physics_cfg.get('speed_max', physics.speed_max)
        # Note: Bird-specific speeds are now managed in bird_types.BIRD_TYPES
    
    # Progression
    if 'progression' in config and isinstance(config['progression'], dict):
        prog = config['progression']
        XP_BASE = float(prog.get('xp_base', XP_BASE))
        GRADE_EXP_FACTOR = float(prog.get('grade_exp_factor', GRADE_EXP_FACTOR))
        LEVEL_SCORE_BASE = float(prog.get('level_score_base', LEVEL_SCORE_BASE))
        LEVEL_SCORE_FACTOR = float(prog.get('level_score_factor', LEVEL_SCORE_FACTOR))
    
    # Combo
    if 'combo' in config and isinstance(config['combo'], dict):
        combo = config['combo']
        COMBO_WINDOW_FRAMES = combo.get('combo_window_frames', COMBO_WINDOW_FRAMES)
        YELLOW_BLUE_CHAIN_WINDOW = combo.get('yellow_blue_chain_window', YELLOW_BLUE_CHAIN_WINDOW)
    
    # Combat
    if 'combat' in config and isinstance(config['combat'], dict):
        combat = config['combat']
        BAT_CENTER_OFFSET = combat.get('bat_center_offset', BAT_CENTER_OFFSET)
        XP_BONUS_PER_TIER = combat.get('xp_bonus_per_tier', XP_BONUS_PER_TIER)
        OBSTACLE_SCORE_MULTIPLIER = combat.get('obstacle_score_multiplier', OBSTACLE_SCORE_MULTIPLIER)
    
    # Collision
    if 'collision' in config and isinstance(config['collision'], dict):
        coll = config['collision']
        LANE_COLLISION_HALF_WIDTH = coll.get('lane_collision_half_width', LANE_COLLISION_HALF_WIDTH)
        LOOT_COLLECTION_DISTANCE = coll.get('loot_collection_distance', LOOT_COLLECTION_DISTANCE)
        BAT_SPRITE_WIDTH = coll.get('bat_sprite_width', BAT_SPRITE_WIDTH)
    
    # Rendering
    if 'rendering' in config and isinstance(config['rendering'], dict):
        rend = config['rendering']
        DINOSAUR_SPRITE_HEIGHT = rend.get('dinosaur_sprite_height', DINOSAUR_SPRITE_HEIGHT)
        NORMAL_BIRD_SPRITE_HEIGHT = rend.get('normal_bird_sprite_height', NORMAL_BIRD_SPRITE_HEIGHT)
    
    # Shuffle
    if 'shuffle' in config and isinstance(config['shuffle'], dict):
        shuf = config['shuffle']
        SHUFFLE_LEVEL_BASE = shuf.get('level_base', SHUFFLE_LEVEL_BASE)
        SHUFFLE_LEVEL_PLUS = shuf.get('level_plus', SHUFFLE_LEVEL_PLUS)
        SHUFFLE_LEVEL_PLUSPLUS = shuf.get('level_plusplus', SHUFFLE_LEVEL_PLUSPLUS)
        SHUFFLE_LEVEL_MAX = shuf.get('level_max', SHUFFLE_LEVEL_MAX)
    
    # Despawn
    if 'despawn' in config and isinstance(config['despawn'], dict):
        desp = config['despawn']
        BAT_DESPAWN_TIME = desp.get('bat_despawn_time', BAT_DESPAWN_TIME)
        LOOT_DESPAWN_TIME = desp.get('loot_despawn_time', LOOT_DESPAWN_TIME)
    
    # Game over
    if 'game_over' in config and isinstance(config['game_over'], dict):
        go = config['game_over']
        GAME_OVER_SEPARATOR_WIDTH = go.get('separator_width', GAME_OVER_SEPARATOR_WIDTH)
        GAME_OVER_TIME_DIVIDER = go.get('time_divider', GAME_OVER_TIME_DIVIDER)
        GAME_OVER_TIME_REMAINDER = go.get('time_remainder', GAME_OVER_TIME_REMAINDER)
        GAME_OVER_MINUTES_DIVIDER = go.get('minutes_divider', GAME_OVER_MINUTES_DIVIDER)
        LEADERBOARD_NAME_MAX_LENGTH = go.get('leaderboard_name_max_length', LEADERBOARD_NAME_MAX_LENGTH)
    
    # Controls
    if 'controls' in config and isinstance(config['controls'], dict):
        ctrl = config['controls']
        KEY_MOVE_LEFT = str(ctrl.get('key_move_left', KEY_MOVE_LEFT))
        KEY_MOVE_RIGHT = str(ctrl.get('key_move_right', KEY_MOVE_RIGHT))
        KEY_MOVE_UP = str(ctrl.get('key_move_up', KEY_MOVE_UP))
        KEY_MOVE_DOWN = str(ctrl.get('key_move_down', KEY_MOVE_DOWN))
        KEY_ACTION = str(ctrl.get('key_action', KEY_ACTION))
        KEY_PAUSE = str(ctrl.get('key_pause', KEY_PAUSE))
        KEY_PAUSE_ALT = str(ctrl.get('key_pause_alt', KEY_PAUSE_ALT))
        KEY_TOGGLE_XP = str(ctrl.get('key_toggle_xp', KEY_TOGGLE_XP))
        KEY_TOGGLE_XP_ALT = str(ctrl.get('key_toggle_xp_alt', KEY_TOGGLE_XP_ALT))
        KEY_QUIT = str(ctrl.get('key_quit', KEY_QUIT))
    
    # Note: Bats, Obstacles, Powers, and Special configs are too complex
    # to apply here. They should be handled by the main game file that needs them.

# ============================================================================
# ADDITIONAL CONSTANTS (from modularization cleanup)
# ============================================================================

# Import color constants from sprites
from sprites import (
    YELLOW, RED, BLUE, PATCHWORK, PURPLE, CLOCKWORK, GOLD, STEALTH,
    WHITE, ORANGE, COOKIE, DINOSAUR, GLITCH
)

# Game metadata
game = SimpleNamespace(
    version="0.8.0"
)

# Backward compatibility
GAME_VERSION = game.version

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
        YELLOW: 5,
        RED: 3,
        BLUE: 2,
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

# Backward compatibility
SYNERGY_TRANSFER_RATIO = synergy.transfer_ratio
PRESTIGE_MODIFIERS = prestige.modifiers
PRESTIGE_RARITY_FACTOR = prestige.rarity_factor
TRANSFORM_LIMITS = transform.limits
BATS_BASE_COLOR_RGB = colors.bats_base_rgb
OBSTACLES_BASE_COLOR_RGB = colors.obstacles_base_rgb
