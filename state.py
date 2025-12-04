#!/usr/bin/env python3
"""
Game state module - contains all mutable game state variables.
This module centralizes all variables that change during gameplay.
Import as: import state
Access as: state.score, state.ball_y, etc.
"""

import variables as v

# Ball/bird state arrays
ball_colors = []
ball_cols = []
ball_y = []
ball_vy = []
ball_speeds = []
ball_lost = []
bird_power_used = []
bird_power_uses = []

# Lane randomization
random_lanes = []

# Projectiles (red bird)
red_projectiles = []

# Bird experience and progression
per_bird_xp = []
transformed_s = []
show_xp_overlay = False

# Background
bg_offset = 0

# Obstacles
obstacles = []
obstacle_spawn_timer = 0

# Bats
bats = []
bat_spawn_timer = 0

# Loot
loot_items = []

# Spawn queue
spawn_queue = []

# Speed boosts
speed_boosts = {}

# Dinosaur special counters
dinosaur_up_presses = {}

# Scared birds
scared_birds = {}

# Stealth timers
stealth_timers = {}
stealth_prev_speeds = {}

# Clockwork bird charge
clockwork_charge = {}

# Cookie bird crumbs
cookie_crumbs_made = {}

# Purple bird charging state machine
purple_state = []
purple_primed_frame = []
purple_charge_started_frame = []
purple_saved_vy = []
purple_miss_count = []
purple_just_fired_frames = []
purple_hold_counter = []

# Global UP hold/miss counters
up_hold_counter = 0
up_miss_counter = 0

# Power-ups state
powerups = {
    'wide_cursor_active': False,
    'wide_cursor_frames': 0,
    'wide_cursor_lanes': 1,
    'bounce_boost_active': False,
    'bounce_boost_frames': 0,
    'bounce_boost_duration': 0,
    'suction_active': False,
    'suction_frames': 0,
    'suction_boost_duration': 0,
    'tailwind_active': False,
    'tailwind_frames': 0,
    'tailwind_up_bonus': 0,
    'tailwind_down_penalty': 0
}

# Score system
score = 0
level = 1
lives = 5
game_over = False
swaps_used = 0
paused = False

# Notifications
notifications = []

# Player cursor
player_lane = 2
selected_lane = None
last_space_state = False
last_up_state = False

# Frame counter
frame_count = 0


def init():
    """Initialize all game state variables."""
    global ball_colors, ball_cols, ball_y, ball_vy, ball_speeds, ball_lost
    global bird_power_used, bird_power_uses, per_bird_xp, transformed_s
    global purple_state, purple_primed_frame, purple_charge_started_frame
    global purple_saved_vy, purple_miss_count, purple_just_fired_frames, purple_hold_counter
    global random_lanes, red_projectiles, show_xp_overlay, bg_offset
    global obstacles, obstacle_spawn_timer, bats, bat_spawn_timer, loot_items, spawn_queue
    global speed_boosts, dinosaur_up_presses, scared_birds, stealth_timers
    global stealth_prev_speeds, clockwork_charge, cookie_crumbs_made
    global up_hold_counter, up_miss_counter, powerups
    global score, level, lives, game_over, swaps_used, paused
    global player_lane, selected_lane, last_space_state, last_up_state, frame_count
    global notifications
    
    import random
    from sprites import YELLOW, RED, BLUE, WHITE, ORANGE, GOLD, PATCHWORK, PURPLE, CLOCKWORK, STEALTH, COOKIE, DINOSAUR, GLITCH
    
    # Initialize bird colors from DEFAULT_BIRD_FORMATION
    ball_colors = []
    for bird_name in v.DEFAULT_BIRD_FORMATION[:v.NUM_BALLS]:
        bird_name_upper = bird_name.upper()
        if bird_name_upper == 'YELLOW':
            ball_colors.append(YELLOW)
        elif bird_name_upper == 'RED':
            ball_colors.append(RED)
        elif bird_name_upper == 'BLUE':
            ball_colors.append(BLUE)
        elif bird_name_upper == 'WHITE':
            ball_colors.append(WHITE)
        elif bird_name_upper == 'ORANGE':
            ball_colors.append(ORANGE)
        elif bird_name_upper == 'GOLD':
            ball_colors.append(GOLD)
        elif bird_name_upper == 'PATCHWORK':
            ball_colors.append(PATCHWORK)
        elif bird_name_upper == 'PURPLE':
            ball_colors.append(PURPLE)
        elif bird_name_upper == 'CLOCKWORK':
            ball_colors.append(CLOCKWORK)
        elif bird_name_upper == 'STEALTH':
            ball_colors.append(STEALTH)
        elif bird_name_upper == 'COOKIE':
            ball_colors.append(COOKIE)
        elif bird_name_upper == 'DINOSAUR':
            ball_colors.append(DINOSAUR)
        elif bird_name_upper == 'GLITCH':
            ball_colors.append(GLITCH)
        else:
            ball_colors.append(YELLOW)  # Default fallback
    
    # Pad with YELLOW if formation is shorter than NUM_BALLS
    while len(ball_colors) < v.NUM_BALLS:
        ball_colors.append(YELLOW)
    
    # Randomize which bird goes to which lane
    random.seed()
    random_lanes = list(range(v.NUM_LANES))
    if v.RANDOMIZE_LANES:
        random.shuffle(random_lanes)
    
    # Initialize position and velocity arrays
    ball_cols = [v.LANE_POSITIONS[random_lanes[i]] for i in range(v.NUM_BALLS)]
    v.STARTING_LINE = v.HEIGHT - 4
    ball_y = [v.STARTING_LINE] * v.NUM_BALLS
    ball_vy = [-1] * v.NUM_BALLS
    ball_speeds = []
    ball_lost = [False] * v.NUM_BALLS
    bird_power_used = [False] * v.NUM_BALLS
    bird_power_uses = [0] * v.NUM_BALLS
    
    per_bird_xp = [0] * v.NUM_BALLS
    transformed_s = [False] * v.NUM_BALLS
    
    purple_state = [0] * v.NUM_BALLS
    purple_primed_frame = [0] * v.NUM_BALLS
    purple_charge_started_frame = [0] * v.NUM_BALLS
    purple_saved_vy = [None] * v.NUM_BALLS
    purple_miss_count = [0] * v.NUM_BALLS
    purple_just_fired_frames = [0] * v.NUM_BALLS
    purple_hold_counter = [0] * v.NUM_BALLS
    
    # Projectiles
    red_projectiles = []
    
    # XP and transformation tracking
    per_bird_xp = [0] * v.NUM_BALLS
    transformed_s = [False] * v.NUM_BALLS
    show_xp_overlay = False
    
    # Background scroll
    bg_offset = 0
    
    # Obstacles
    obstacles = []
    obstacle_spawn_timer = 0
    
    # Bats
    bats = []
    bat_spawn_timer = 0
    
    # Loot items
    loot_items = []
    
    # Spawn queue
    spawn_queue = []
    
    # Speed boosts
    speed_boosts = {}
    
    # Dinosaur counters
    dinosaur_up_presses = {}
    
    # Scared birds
    scared_birds = {}
    
    # Stealth timers
    stealth_timers = {}
    stealth_prev_speeds = {}
    
    # Clockwork charge
    clockwork_charge = {}
    
    # Cookie crumbs
    cookie_crumbs_made = {}
    
    # Global UP counters
    up_hold_counter = 0
    up_miss_counter = 0
    
    # Power-ups
    powerups = {
        'wide_cursor_active': False,
        'wide_cursor_frames': 0,
        'wide_cursor_lanes': 1,
        'bounce_boost_active': False,
        'bounce_boost_frames': 0,
        'bounce_boost_duration': 0,
        'suction_active': False,
        'suction_frames': 0,
        'suction_boost_duration': 0,
        'tailwind_active': False,
        'tailwind_frames': 0,
        'tailwind_up_bonus': 0,
        'tailwind_down_penalty': 0
    }
    
    # Score system
    score = 0
    level = 1
    lives = 5
    game_over = False
    swaps_used = 0
    paused = False
    
    # Player
    player_lane = 2
    selected_lane = None
    last_space_state = False
    last_up_state = False
    
    # Frame counter
    frame_count = 0
    
    # Assign speeds based on bird formation
    ball_speeds = []
    for i in range(v.NUM_BALLS):
        try:
            bird_name = v.DEFAULT_BIRD_FORMATION[i].upper() if i < len(v.DEFAULT_BIRD_FORMATION) else 'YELLOW'
            spd = v.BALL_SPEEDS_DEFAULT.get(bird_name, 2)
            ball_speeds.append(int(spd))
        except Exception:
            ball_speeds.append(2)
    
    # Notifications
    notifications = []
