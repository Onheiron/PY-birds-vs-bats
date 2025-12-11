#!/usr/bin/env python3
"""
Global game variables and configuration state.
Initialized from config file via init.py.
"""
import init

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

# Bird formation
DEFAULT_BIRD_FORMATION = ['YELLOW', 'YELLOW', 'YELLOW', 'YELLOW', 'RED', 'RED', 'RED', 'BLUE', 'BLUE']
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
BALL_SPEEDS_DEFAULT = {
    'YELLOW': 2,
    'RED': 3,
    'BLUE': 4,
    'ORANGE': 5,
    'GOLD': 6,
    'PATCHWORK': 3,
    'CLOCKWORK': 2,
    'COOKIE': 3,
    'STEALTH': 3,
    'DINOSAUR': 4,
    'WHITE': 4,
    'PURPLE': 3,
    'GLITCH': 3,
}

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

# Wide cursor
WIDE_CURSOR_BASE_SECONDS = 10.0
WIDE_CURSOR_PLUS_SECONDS = 20.0
WIDE_CURSOR_PLUSPLUS_SECONDS = 25.0
WIDE_CURSOR_MAX_SECONDS = 50.0
WIDE_CURSOR_LANES_BASE = 3
WIDE_CURSOR_LANES_MAX = 5

# Bounce boost
BOUNCE_BOOST_BASE_SECONDS = 10.0
BOUNCE_BOOST_PLUS_SECONDS = 20.0
BOUNCE_BOOST_PLUSPLUS_SECONDS = 25.0
BOUNCE_BOOST_MAX_SECONDS = 50.0
BOUNCE_BOOST_DURATION_BASE = 4
BOUNCE_BOOST_DURATION_PLUS = 4
BOUNCE_BOOST_DURATION_PLUSPLUS = 8
BOUNCE_BOOST_DURATION_MAX = 12

# Suction
SUCTION_BASE_SECONDS = 10.0
SUCTION_PLUS_SECONDS = 20.0
SUCTION_PLUSPLUS_SECONDS = 25.0
SUCTION_MAX_SECONDS = 50.0
SUCTION_BOOST_DURATION_BASE = 0
SUCTION_BOOST_DURATION_PLUS = 0
SUCTION_BOOST_DURATION_PLUSPLUS = 4
SUCTION_BOOST_DURATION_MAX = 8

# Tailwind
TAILWIND_BASE_SECONDS = 10.0
TAILWIND_PLUS_SECONDS = 15.0
TAILWIND_PLUSPLUS_SECONDS = 20.0
TAILWIND_MAX_SECONDS = 30.0
TAILWIND_UP_BONUS_BASE = 1
TAILWIND_UP_BONUS_PLUS = 2
TAILWIND_UP_BONUS_PLUSPLUS = 3
TAILWIND_DOWN_PENALTY_BASE = 1
TAILWIND_DOWN_PENALTY_PLUS = 1
TAILWIND_DOWN_PENALTY_PLUSPLUS = 2
TAILWIND_DOWN_PENALTY_MAX = 3

# Special
BLUE_ADJACENT_BOOST_SECONDS = 5.0

# Dinosaur
DINOSAUR_PRESSES_TO_BOUNCE = 15
DINOSAUR_PRESS_CHUNK = 3
DINOSAUR_RECOVERY_ON_EGG = 0.10
DINOSAUR_DAMAGE = 16

# Stealth
STEALTH_DAMAGE = 24
STEALTH_TANGIBLE_SECONDS = 2.0

# Gold
GOLD_DAMAGE = 1
GOLD_SCORE_VALUE = 100

# Clockwork
CLOCKWORK_DECAY_SECONDS = 30.0
CLOCKWORK_INITIAL_CHARGE = 2
CLOCKWORK_MIN_CHARGE = 0
CLOCKWORK_MAX_CHARGE = 3

# Glitch
GLITCH_BOUNCE_IGNORE_CHANCE = 0.05
GLITCH_LOOT_IGNORE_CHANCE = 0.05
GLITCH_LOOT_PROMOTE_CHANCE = 0.05
GLITCH_DAMAGE_MIN = 1
GLITCH_DAMAGE_MAX = 32
GLITCH_SURVIVE_ON_FLOOR_CHANCE = 0.20
GLITCH_SPEED_MIN = 1
GLITCH_SPEED_MAX = 6
GLITCH_FLIP_CHANCE = 0.01
GLITCH_SWAP_CHANCE = 0.01
GLITCH_NUDGE_CHANCE = 0.01
GLITCH_DUPLICATE_CHANCE = 0.01

# Orange
ORANGE_RECOVER_CHANCE = 0.10
ORANGE_OUT_OF_PLAY_Y = 999

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
        if 'ball_speeds' in physics_cfg and isinstance(physics_cfg['ball_speeds'], dict):
            BALL_SPEEDS_DEFAULT.update({str(k): int(v) for k, v in physics_cfg['ball_speeds'].items()})
    
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

# Egg to color mapping
EGG_TO_COLOR = {
    'yellow_egg': YELLOW,
    'red_egg': RED,
    'blue_egg': BLUE,
    'patchwork_egg': PATCHWORK,
    'purple_egg': PURPLE,
    'clockwork_egg': CLOCKWORK,
    'gold_egg': GOLD,
    'stealth_egg': STEALTH,
    'white_egg': WHITE,
    'orange_egg': ORANGE,
    'cookie_egg': COOKIE,
    'dinosaur_egg': DINOSAUR,
    'glitch_egg': GLITCH,
}

# Color spawn limits (None = unlimited)
COLOR_LIMITS = {
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
    COOKIE: 1,
    DINOSAUR: 1,
    GLITCH: 1,
}

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

# Color name mapping for display
COLOR_NAME_MAP = {
    YELLOW: 'Yellow',
    RED: 'Red',
    BLUE: 'Blue',
    ORANGE: 'Orange',
    GOLD: 'Gold',
    PATCHWORK: 'Patchwork',
    CLOCKWORK: 'Clockwork',
    COOKIE: 'Cookie',
    STEALTH: 'Stealth',
    DINOSAUR: 'Dinosaur',
    WHITE: 'White',
    PURPLE: 'Purple',
    GLITCH: 'Glitch',
}

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

# Power-specific constants
STEALTH_SPEED_BOOST = 2
BOUNCE_BOOST_DURATION_BASE = 4
BOUNCE_BOOST_DURATION_PLUS = 4
BOUNCE_BOOST_DURATION_PLUSPLUS = 8
BOUNCE_BOOST_DURATION_MAX = 12
SUCTION_BOOST_DURATION_BASE = 0
SUCTION_BOOST_DURATION_PLUS = 0
SUCTION_BOOST_DURATION_PLUSPLUS = 4
SUCTION_BOOST_DURATION_MAX = 8
TAILWIND_UP_BONUS_BASE = 1
TAILWIND_UP_BONUS_PLUS = 2
TAILWIND_UP_BONUS_PLUSPLUS = 3
TAILWIND_DOWN_PENALTY_BASE = 1
TAILWIND_DOWN_PENALTY_PLUS = 1
TAILWIND_DOWN_PENALTY_PLUSPLUS = 2
TAILWIND_DOWN_PENALTY_MAX = 3

# Special bird constants
DINOSAUR_PRESSES_TO_BOUNCE = 15
DINOSAUR_PRESS_CHUNK = 3
DINOSAUR_RECOVERY_CHANCE_ON_EGG = 0.10
DINOSAUR_DAMAGE = 16
STEALTH_DAMAGE = 24
STEALTH_TANGIBLE_SECONDS = 2.0
GOLD_DAMAGE = 1
GOLD_SCORE_VALUE = 100
CLOCKWORK_LANES_BASE = 3
CLOCKWORK_LANES_MAX = 5
BLUE_ADJACENT_BOOST_SECONDS = 5.0

# Bat constants
BAT_SCARED_SECONDS = 2.0
BAT_SCARED_SPEED_BOOST_SECONDS = 2.0

# Shuffle constants
SHUFFLE_LEVEL_BASE = 10
SHUFFLE_LEVEL_PLUS = 15
SHUFFLE_LEVEL_PLUSPLUS = 20
SHUFFLE_LEVEL_MAX = 25

# HP color scaling base RGB values
_BATS_BASE_RGB = (255, 0, 255)   # magenta FF00FF
_OBST_BASE_RGB = (0, 255, 0)     # green 00FF00
_OBST_MAX_HP_BY_TIER = {1: 4, 2: 6, 3: 10, 4: 16}

# Power defaults - Wide Cursor
WIDE_CURSOR_BASE_SECONDS = 10.0
WIDE_CURSOR_PLUS_SECONDS = 20.0
WIDE_CURSOR_PLUSPLUS_SECONDS = 25.0
WIDE_CURSOR_MAX_SECONDS = 50.0
WIDE_CURSOR_LANES_BASE = 3
WIDE_CURSOR_LANES_MAX = 5

# Power defaults - Bounce Boost
BOUNCE_BOOST_BASE_SECONDS = 10.0
BOUNCE_BOOST_PLUS_SECONDS = 20.0
BOUNCE_BOOST_PLUSPLUS_SECONDS = 25.0
BOUNCE_BOOST_MAX_SECONDS = 50.0

# Power defaults - Suction
SUCTION_BASE_SECONDS = 10.0
SUCTION_PLUS_SECONDS = 20.0
SUCTION_PLUSPLUS_SECONDS = 25.0
SUCTION_MAX_SECONDS = 50.0

# Power defaults - Tailwind
TAILWIND_BASE_SECONDS = 10.0
TAILWIND_PLUS_SECONDS = 15.0
TAILWIND_PLUSPLUS_SECONDS = 20.0
TAILWIND_MAX_SECONDS = 30.0
    # This file only contains the most commonly used constants.
