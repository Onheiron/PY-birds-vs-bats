#!/usr/bin/env python3
"""
Script to refactor start_new.py to use state module for all global variables.
"""

import re

# List of variables to refactor (add state. prefix)
VARIABLES = [
    'ball_colors', 'ball_cols', 'ball_y', 'ball_vy', 'ball_speeds', 'ball_lost',
    'bird_power_used', 'bird_power_uses', 'random_lanes', 'red_projectiles',
    'per_bird_xp', 'transformed_s', 'show_xp_overlay', 'bg_offset',
    'obstacles', 'obstacle_spawn_timer', 'bats', 'bat_spawn_timer',
    'loot_items', 'spawn_queue', 'speed_boosts', 'dinosaur_up_presses',
    'scared_birds', 'stealth_timers', 'stealth_prev_speeds', 'clockwork_charge',
    'cookie_crumbs_made', 'purple_state', 'purple_primed_frame',
    'purple_charge_started_frame', 'purple_saved_vy', 'purple_miss_count',
    'purple_just_fired_frames', 'purple_hold_counter', 'up_hold_counter',
    'up_miss_counter', 'powerups', 'score', 'level', 'lives', 'game_over',
    'swaps_used', 'paused', 'notifications', 'player_lane', 'selected_lane',
    'last_space_state', 'last_up_state', 'frame_count'
]

def refactor_file(filepath):
    """Refactor the file to use state. prefix for all variables."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # For each variable, replace all occurrences with state.variable
    # Use word boundaries to avoid partial matches
    for var in VARIABLES:
        # Match the variable as a whole word (not part of another identifier)
        # Negative lookbehind to avoid matching state.variable or already prefixed
        pattern = r'(?<!state\.)(?<!\.)\b' + var + r'\b'
        replacement = 'state.' + var
        content = re.sub(pattern, replacement, content)
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Refactored {filepath}")
    print(f"Variables updated: {len(VARIABLES)}")

if __name__ == '__main__':
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else '/Users/carlomoretti/Developer/Projects/BVB/start_new.py'
    refactor_file(filepath)
