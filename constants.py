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

# Layout
WIDTH = 45
HEIGHT = 30
NUM_BALLS = 9
NUM_LANES = 9
MIN_LANE_INDEX = 0
MAX_LANE_INDEX = 8
LANE_POSITIONS = [5, 9, 13, 17, 21, 25, 29, 33, 37]
STARTING_LINE = HEIGHT - 4

# Bird configuration
from bird_types import DEFAULT_FORMATION

DEFAULT_BIRD_FORMATION = DEFAULT_FORMATION  # Use BirdType enums from bird_types
RANDOMIZE_LANES = True

# Timing
BASE_SLEEP = 0.2
MIN_SLEEP = 0.02
NOTIFICATION_DURATION_SECONDS = 3.0
FRAME_SLEEP_LEVEL_MULTIPLIER = 0.88

# Limits
MAX_ENTITIES = 50

# Physics
SPEED_MIN = 1
SPEED_MAX = 6
# Note: Ball speeds are now in BIRD_TYPES[bird_type]['speed']

# Eggs
EGG_PROBS = {0: 0.0, 1: 0.25, 2: 0.35, 3: 0.45, 4: 0.55}
RARITY_WEIGHTS = {
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

# Bats
BAT_SPAWN_INTERVAL_RANGE = [120, 220]
BAT_MAX_ON_SCREEN = 3
BAT_HP_BY_TIER = {1: 16, 2: 32, 3: 64, 4: 128}
SCARED_BASE_SECONDS = 2.0
SCARED_SPEED_BOOST_SECONDS = 2.0
BAT_LOOT_BASE_WEIGHTS = {
    1: [60, 25, 10, 5],
    2: [50, 30, 15, 5],
    3: [40, 33, 17, 10],
    4: [35, 25, 20, 15],
}

# Bat spawning
BAT_WAVE_OFFSET_MIN = 0
BAT_WAVE_OFFSET_MAX = 10
BAT_TARGET_Y_MIN_LOW_LEVEL = 10
BAT_TARGET_Y_MAX_LOW_LEVEL = 12
BAT_TARGET_Y_MIN_HIGH_LEVEL = 18
BAT_TARGET_Y_MAX_HIGH_LEVEL = 22
BAT_TARGET_Y_LEVEL_THRESHOLD = 5
BAT_SPAWN_MAX_ATTEMPTS = 20
BAT_SPAWN_X_MIN = 1
BAT_SPAWN_X_MARGIN = 9
BAT_MIN_SEPARATION = 15
BAT_SPAWN_FAIL_RETRY_TIMER = 50
BAT_CONSECUTIVE_SPAWN_LIMIT = 2
BAT_CONSECUTIVE_RETRY_TIMER = 20
BAT_SPAWN_Y_START = 1

# Bat tiers
BAT_TIER_WEIGHTS_LEVEL_0_2 = [70, 20, 8, 2]
BAT_TIER_WEIGHTS_LEVEL_3_4 = [50, 30, 15, 5]
BAT_TIER_WEIGHTS_LEVEL_5_7 = [30, 35, 25, 10]
BAT_TIER_WEIGHTS_LEVEL_8_PLUS = [15, 30, 35, 20]
BAT_TIER_LEVEL_THRESHOLD_1 = 2
BAT_TIER_LEVEL_THRESHOLD_2 = 4
BAT_TIER_LEVEL_THRESHOLD_3 = 7
BAT_HP_TIER_1 = 16
BAT_HP_TIER_2 = 32
BAT_HP_TIER_3 = 64
BAT_HP_TIER_4 = 128

# Obstacles
OBSTACLE_MAX_HP_BY_TIER = {1: 4, 2: 6, 3: 10, 4: 16}

# Obstacle spawning
OBSTACLE_BASE_SPAWN_RATE_BASE = 60
OBSTACLE_BASE_SPAWN_RATE_MIN = 15
OBSTACLE_SPAWN_RATE_LEVEL_MULTIPLIER = 4
OBSTACLE_SPAWN_VARIANCE_BASE = 30
OBSTACLE_SPAWN_VARIANCE_MIN = 10
OBSTACLE_SPAWN_VARIANCE_LEVEL_MULTIPLIER = 2
OBSTACLE_RETRY_TIMER_DIVISOR = 2
OBSTACLE_RETRY_TIMER_MIN = 5
OBSTACLE_CONSECUTIVE_SPAWN_LIMIT = 2

# Obstacle tiers
OBSTACLE_TIER_WEIGHTS_LEVEL_0_2 = [70, 20, 8, 2]
OBSTACLE_TIER_WEIGHTS_LEVEL_3_4 = [55, 28, 13, 4]
OBSTACLE_TIER_WEIGHTS_LEVEL_5_7 = [35, 35, 20, 10]
OBSTACLE_TIER_WEIGHTS_LEVEL_8_PLUS = [20, 30, 30, 20]
OBSTACLE_TIER_LEVEL_THRESHOLD_1 = 2
OBSTACLE_TIER_LEVEL_THRESHOLD_2 = 4
OBSTACLE_TIER_LEVEL_THRESHOLD_3 = 7
OBSTACLE_HP_TIER_1 = 4
OBSTACLE_HP_TIER_2 = 6
OBSTACLE_HP_TIER_3 = 10
OBSTACLE_HP_TIER_4 = 16

# Powers
POWERS_DEFAULT = {}

# ============================================================================
# POWER-UPS (organized as namespaces)
# ============================================================================

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

# Backward compatibility - keep old constants for now
WIDE_CURSOR_BASE_SECONDS = wide_cursor.seconds.base
WIDE_CURSOR_PLUS_SECONDS = wide_cursor.seconds.plus
WIDE_CURSOR_PLUSPLUS_SECONDS = wide_cursor.seconds.plusplus
WIDE_CURSOR_MAX_SECONDS = wide_cursor.seconds.max
WIDE_CURSOR_LANES_BASE = wide_cursor.lanes.base
WIDE_CURSOR_LANES_MAX = wide_cursor.lanes.max

BOUNCE_BOOST_BASE_SECONDS = bounce_boost.seconds.base
BOUNCE_BOOST_PLUS_SECONDS = bounce_boost.seconds.plus
BOUNCE_BOOST_PLUSPLUS_SECONDS = bounce_boost.seconds.plusplus
BOUNCE_BOOST_MAX_SECONDS = bounce_boost.seconds.max
BOUNCE_BOOST_DURATION_BASE = bounce_boost.duration.base
BOUNCE_BOOST_DURATION_PLUS = bounce_boost.duration.plus
BOUNCE_BOOST_DURATION_PLUSPLUS = bounce_boost.duration.plusplus
BOUNCE_BOOST_DURATION_MAX = bounce_boost.duration.max

SUCTION_BASE_SECONDS = suction.seconds.base
SUCTION_PLUS_SECONDS = suction.seconds.plus
SUCTION_PLUSPLUS_SECONDS = suction.seconds.plusplus
SUCTION_MAX_SECONDS = suction.seconds.max
SUCTION_BOOST_DURATION_BASE = suction.boost_duration.base
SUCTION_BOOST_DURATION_PLUS = suction.boost_duration.plus
SUCTION_BOOST_DURATION_PLUSPLUS = suction.boost_duration.plusplus
SUCTION_BOOST_DURATION_MAX = suction.boost_duration.max

TAILWIND_BASE_SECONDS = tailwind.seconds.base
TAILWIND_PLUS_SECONDS = tailwind.seconds.plus
TAILWIND_PLUSPLUS_SECONDS = tailwind.seconds.plusplus
TAILWIND_MAX_SECONDS = tailwind.seconds.max
TAILWIND_UP_BONUS_BASE = tailwind.up_bonus.base
TAILWIND_UP_BONUS_PLUS = tailwind.up_bonus.plus
TAILWIND_UP_BONUS_PLUSPLUS = tailwind.up_bonus.plusplus
TAILWIND_DOWN_PENALTY_BASE = tailwind.down_penalty.base
TAILWIND_DOWN_PENALTY_PLUS = tailwind.down_penalty.plus
TAILWIND_DOWN_PENALTY_PLUSPLUS = tailwind.down_penalty.plusplus
TAILWIND_DOWN_PENALTY_MAX = tailwind.down_penalty.max

# Special
BLUE_ADJACENT_BOOST_SECONDS = 5.0

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

# Backward compatibility
DINOSAUR_PRESSES_TO_BOUNCE = dinosaur.presses_to_bounce
DINOSAUR_PRESS_CHUNK = dinosaur.press_chunk
DINOSAUR_RECOVERY_ON_EGG = dinosaur.recovery_on_egg
DINOSAUR_DAMAGE = dinosaur.damage

STEALTH_DAMAGE = stealth.damage
STEALTH_TANGIBLE_SECONDS = stealth.tangible_seconds
STEALTH_SPEED_BOOST = stealth.speed_boost

GOLD_DAMAGE = gold.damage
GOLD_SCORE_VALUE = gold.score_value

CLOCKWORK_DECAY_SECONDS = clockwork.decay_seconds
CLOCKWORK_INITIAL_CHARGE = clockwork.initial_charge
CLOCKWORK_MIN_CHARGE = clockwork.min_charge
CLOCKWORK_MAX_CHARGE = clockwork.max_charge
CLOCKWORK_LANES_BASE = clockwork.lanes.base
CLOCKWORK_LANES_MAX = clockwork.lanes.max

GLITCH_BOUNCE_IGNORE_CHANCE = glitch.bounce_ignore_chance
GLITCH_LOOT_IGNORE_CHANCE = glitch.loot_ignore_chance
GLITCH_LOOT_PROMOTE_CHANCE = glitch.loot_promote_chance
GLITCH_DAMAGE_MIN = glitch.damage.min
GLITCH_DAMAGE_MAX = glitch.damage.max
GLITCH_SURVIVE_ON_FLOOR_CHANCE = glitch.survive_on_floor_chance
GLITCH_SPEED_MIN = glitch.speed.min
GLITCH_SPEED_MAX = glitch.speed.max
GLITCH_FLIP_CHANCE = glitch.flip_chance
GLITCH_SWAP_CHANCE = glitch.swap_chance
GLITCH_NUDGE_CHANCE = glitch.nudge_chance
GLITCH_DUPLICATE_CHANCE = glitch.duplicate_chance

ORANGE_RECOVER_CHANCE = orange.recover_chance
ORANGE_OUT_OF_PLAY_Y = orange.out_of_play_y

# Progression
XP_BASE = 500.0
GRADE_EXP_FACTOR = 1.07
LEVEL_SCORE_BASE = 500.0
LEVEL_SCORE_FACTOR = 1.07

# Combo
COMBO_WINDOW_FRAMES = 200
YELLOW_BLUE_CHAIN_WINDOW = 60

# Combat
BAT_CENTER_OFFSET = 4
XP_BONUS_PER_TIER = 10
OBSTACLE_SCORE_MULTIPLIER = 2

# Collision
LANE_COLLISION_HALF_WIDTH = 2
LOOT_COLLECTION_DISTANCE = 2
BAT_SPRITE_WIDTH = 8

# Rendering
DINOSAUR_SPRITE_HEIGHT = 3
NORMAL_BIRD_SPRITE_HEIGHT = 2

# Shuffle
SHUFFLE_LEVEL_BASE = 1
SHUFFLE_LEVEL_PLUS = 2
SHUFFLE_LEVEL_PLUSPLUS = 3
SHUFFLE_LEVEL_MAX = 4

# Despawn
BAT_DESPAWN_TIME = 60
LOOT_DESPAWN_TIME = 60

# Game over
GAME_OVER_SEPARATOR_WIDTH = 50
GAME_OVER_TIME_DIVIDER = 3600
GAME_OVER_TIME_REMAINDER = 3600
GAME_OVER_MINUTES_DIVIDER = 60
LEADERBOARD_NAME_MAX_LENGTH = 20

# Keyboard controls
KEY_MOVE_LEFT = 'LEFT'
KEY_MOVE_RIGHT = 'RIGHT'
KEY_MOVE_UP = 'UP'
KEY_MOVE_DOWN = 'DOWN'
KEY_ACTION = 'SPACE'
KEY_PAUSE = 'p'
KEY_PAUSE_ALT = 'P'
KEY_TOGGLE_XP = 'x'
KEY_TOGGLE_XP_ALT = 'X'
KEY_QUIT = 'QUIT'


# Apply configuration overrides
if config:
    # Layout
    if 'layout' in config and isinstance(config['layout'], dict):
        layout_cfg = config['layout']
        WIDTH = layout_cfg.get('width', WIDTH)
        HEIGHT = layout_cfg.get('height', HEIGHT)
        NUM_BALLS = layout_cfg.get('num_balls', NUM_BALLS)
        if 'lane_positions' in layout_cfg:
            LANE_POSITIONS = layout_cfg['lane_positions']
        
        if 'constraints' in layout_cfg and isinstance(layout_cfg['constraints'], dict):
            const = layout_cfg['constraints']
            NUM_LANES = const.get('num_lanes', NUM_LANES)
            MIN_LANE_INDEX = const.get('min_lane_index', MIN_LANE_INDEX)
            MAX_LANE_INDEX = const.get('max_lane_index', MAX_LANE_INDEX)
    
    # Recalculate derived values
    STARTING_LINE = HEIGHT - 4
    
    # Birds
    if 'birds' in config and isinstance(config['birds'], dict):
        birds_cfg = config['birds']
        if 'formation' in birds_cfg:
            DEFAULT_BIRD_FORMATION = [str(b).upper() for b in birds_cfg['formation']]
        RANDOMIZE_LANES = birds_cfg.get('randomize_lanes', RANDOMIZE_LANES)
    
    # Timing
    if 'timing' in config and isinstance(config['timing'], dict):
        timing_cfg = config['timing']
        NOTIFICATION_DURATION_SECONDS = timing_cfg.get('notification_duration_seconds', NOTIFICATION_DURATION_SECONDS)
        BASE_SLEEP = timing_cfg.get('base_sleep', BASE_SLEEP)
        MIN_SLEEP = timing_cfg.get('min_sleep', MIN_SLEEP)
        FRAME_SLEEP_LEVEL_MULTIPLIER = timing_cfg.get('frame_sleep_level_multiplier', FRAME_SLEEP_LEVEL_MULTIPLIER)
    
    # Limits
    if 'limits' in config and isinstance(config['limits'], dict):
        MAX_ENTITIES = config['limits'].get('max_entities', MAX_ENTITIES)
    
    # Eggs
    if 'egg_probs' in config:
        ev = config['egg_probs']
        if isinstance(ev, dict):
            EGG_PROBS = {int(k): float(v) for k, v in ev.items()}
        elif isinstance(ev, (list, tuple)):
            EGG_PROBS = {i: float(ev[i]) for i in range(len(ev))}
    
    if 'rarity_weights' in config and isinstance(config['rarity_weights'], dict):
        for rarity, weights in config['rarity_weights'].items():
            if rarity in RARITY_WEIGHTS and isinstance(weights, dict):
                RARITY_WEIGHTS[rarity].update(weights)
    
    # Physics
    if 'physics' in config and isinstance(config['physics'], dict):
        physics_cfg = config['physics']
        SPEED_MIN = physics_cfg.get('speed_min', SPEED_MIN)
        SPEED_MAX = physics_cfg.get('speed_max', SPEED_MAX)
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

# Version
GAME_VERSION = "0.8.0"

# Note: Egg mappings, color limits, and display names are now in bird_types.py
# Use: get_bird_type_from_egg(), get_spawn_limit(), get_display_name()

# Rarity eggs candidates (unified: candidates + weights from config)
RARITY_EGGS_CANDIDATES = {
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

# Note: Display names now in bird_types.get_display_name()

# Synergy transfer ratio
SYNERGY_TRANSFER_RATIO = 0.10

# Prestige modifiers per grade
PRESTIGE_MODIFIERS = {
    'D': 0.0,
    'C1': 0.03125,
    'C2': 0.0625,
    'B1': 0.125,
    'B2': 0.25,
    'A1': 0.5,
    'A2': 1.0,
    'S': 5.0,
}

# Prestige rarity factor
PRESTIGE_RARITY_FACTOR = 0.1

# Transform limits for patchwork birds
TRANSFORM_LIMITS = {
    YELLOW: 5,
    RED: 3,
    BLUE: 2,
}

# Bat constants
bat = SimpleNamespace(
    scared_seconds=2.0,
    scared_speed_boost_seconds=2.0
)
BAT_SCARED_SECONDS = bat.scared_seconds
BAT_SCARED_SPEED_BOOST_SECONDS = bat.scared_speed_boost_seconds

# Shuffle constants
shuffle = SimpleNamespace(
    level=SimpleNamespace(
        base=10,
        plus=15,
        plusplus=20,
        max=25
    )
)
SHUFFLE_LEVEL_BASE = shuffle.level.base
SHUFFLE_LEVEL_PLUS = shuffle.level.plus
SHUFFLE_LEVEL_PLUSPLUS = shuffle.level.plusplus
SHUFFLE_LEVEL_MAX = shuffle.level.max

# HP color scaling base RGB values
BATS_BASE_COLOR_RGB = (255, 0, 255)   # magenta FF00FF
OBSTACLES_BASE_COLOR_RGB = (0, 255, 0)     # green 00FF00
