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


def initialize_arrays():
    """Initialize all state arrays based on current NUM_BALLS configuration."""
    global ball_colors, ball_cols, ball_y, ball_vy, ball_speeds, ball_lost
    global bird_power_used, bird_power_uses, per_bird_xp, transformed_s
    global purple_state, purple_primed_frame, purple_charge_started_frame
    global purple_saved_vy, purple_miss_count, purple_just_fired_frames, purple_hold_counter
    global random_lanes
    
    # Initialize arrays with correct size
    ball_colors = []
    ball_cols = []
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
    
    random_lanes = list(range(v.NUM_LANES))
