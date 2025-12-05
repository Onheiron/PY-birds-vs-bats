#!/usr/bin/env python3
import sys
import time
import os
import random
    
if os.name == 'nt':
    import msvcrt
else:
    import termios
    import fcntl

from sprites import *

import variables
from functions import *
import render
import achievements
import state

try:
    import firebase_client
except Exception:
    firebase_client = None

try:
    setup()
    achievements.init_achievements()
    # Track start time for the play session (used for reporting total play time)
    game_start_time = time.time()
    # Initialize Firebase client (best-effort)
    if firebase_client:
        try:
            # init synchronously (fast local file read); defer network calls
            firebase_client.init_from_env()
            # perform network calls in background to avoid blocking startup
            background_call(firebase_client.sign_in_anonymous)
            background_call(firebase_client.log_event, 'session_start', {'client': 'terminal'})
            # Inform player (best-effort)
            achievements.add_notification('Firebase: enabled', state.frame_count, state.notifications)
        except Exception:
            # don't fail startup on network/auth issues
            achievements.add_notification('Firebase: disabled', state.frame_count, state.notifications)
    # Music engine support removed from this file.
    # No music engine will be started from the game process.

    # Pre-build static parts
    ceiling = "=" * variables.WIDTH
    floor = ceiling
    
    while True:
        # Handle input
        key = render.get_key()

        # Detect space key press (edge detection)
        space_pressed_this_frame = (key == variables.KEY_ACTION)
        space_just_pressed = space_pressed_this_frame and not state.last_space_state
        state.last_space_state = space_pressed_this_frame

        # When state.paused, ignore all input except P (toggle pause) and QUIT.
        # Also prevent SPACE edge from triggering while state.paused.
        if state.paused:
            if key and key not in ('P', 'p', 'QUIT'):
                key = None
                space_pressed_this_frame = False
                space_just_pressed = False

        if key:
            if key == variables.KEY_ACTION and space_just_pressed:
                # Space pressed - toggle swap mode or execute swap
                if state.selected_lane is None:
                    # Enter swap mode - select current lane
                    state.selected_lane = state.player_lane
                elif state.selected_lane == state.player_lane:
                    # Pressed on same lane - cancel swap mode
                    state.selected_lane = None

                else:
                    # Different lane - execute swap (costs 200 * state.level points)
                    swap_cost = 200 * state.level
                    if state.score >= swap_cost:
                        current_lane = state.player_lane

                        # Find bird indices for both lanes
                        bird_in_selected = find_bird_in_lane(state.selected_lane)
                        bird_in_current = find_bird_in_lane(current_lane)

                        # Swap if both birds exist (even if one or both are dead)
                        if bird_in_selected >= 0 and bird_in_current >= 0:
                            # Deduct cost (use helper so state.level recompute/achievements can react)
                            deduct_score(swap_cost)
                            # track swap usage for achievements
                            state.swaps_used += 1
                            achievements.check_achievements_event('swap', swaps=state.swaps_used, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)

                            # Swap lanes (handles orange egg updates)
                            swap_bird_lanes(bird_in_selected, bird_in_current)

                        # Always reset swap mode after attempting swap (whether successful or not)
                        state.selected_lane = None

            elif key == variables.KEY_PAUSE or key == variables.KEY_PAUSE_ALT:
                # Toggle pause (top-state.level handler)
                state.paused = not state.paused
                if state.paused:
                    achievements.add_notification('PAUSED', state.frame_count, state.notifications)
                else:
                    achievements.add_notification('RESUMED', state.frame_count, state.notifications)
            elif key == variables.KEY_MOVE_LEFT:
                state.player_lane = max(0, state.player_lane - 1)
            elif key == variables.KEY_MOVE_RIGHT:
                state.player_lane = min(8, state.player_lane + 1)  # 9 lanes: 0-8
            elif key == variables.KEY_TOGGLE_XP or key == variables.KEY_TOGGLE_XP_ALT:
                # Toggle XP overlay for debugging / verification
                state.show_xp_overlay = not state.show_xp_overlay
                if state.show_xp_overlay:
                    achievements.add_notification('XP overlay: ON', state.frame_count, state.notifications)
                else:
                    achievements.add_notification('XP overlay: OFF', state.frame_count, state.notifications)
            elif key == variables.KEY_MOVE_UP:
                # Determine which lanes to affect based on wide cursor
                lanes_to_affect = get_affected_lanes()

                # Process each affected lane
                for lane in lanes_to_affect:
                    bird_in_lane = find_bird_in_lane(lane)
                    if bird_in_lane >= 0 and not state.ball_lost[bird_in_lane]:
                        if state.ball_colors[bird_in_lane] == ORANGE and state.ball_speeds[bird_in_lane] == 0:
                            # Use configurable recover chance for orange eggs
                            if random.random() >= float(variables.ORANGE_RECOVER_CHANCE):
                                continue
                            lane = state.random_lanes[bird_in_lane]
                            state.ball_y[bird_in_lane] = variables.STARTING_LINE
                            set_ball_vy(bird_in_lane, -1)
                            reset_bird_power(bird_in_lane)
                            state.ball_speeds[bird_in_lane] = 5
                            item = next((li for li in state.loot_items
                                         if li.get('type') == 'orange_egg' and li.get('x_pos') == variables.LANE_POSITIONS[lane]
                                         and li.get('y_pos') == variables.STARTING_LINE and li.get('rarity') == 'epic'), None)
                            if item is not None:
                                state.loot_items.remove(item)   # rimuove la prima occorrenza dell'oggetto trovato
                        # Can't bounce scared birds
                        elif not can_bird_bounce(bird_in_lane):
                            continue  # Scared bird ignores bounce command (tranne purple)
                        elif state.ball_vy[bird_in_lane] == 1:  # Moving down - bounce it up
                            # Special DINOSAUR behaviour: requires 10 UP presses to bounce.
                            if state.ball_colors[bird_in_lane] == DINOSAUR:
                                cnt = state.dinosaur_up_presses.get(bird_in_lane, 0) + 1
                                state.dinosaur_up_presses[bird_in_lane] = cnt
                                # Every DINOSAUR_PRESS_CHUNK UP presses reduce current fall speed by 1
                                chunk = int(variables.DINOSAUR_PRESS_CHUNK)
                                if chunk > 0 and cnt % chunk == 0:
                                    # If this is the final (DINOSAUR_PRESSES_TO_BOUNCE) press, bounce up
                                    target = int(variables.DINOSAUR_PRESSES_TO_BOUNCE)
                                    if cnt >= target:
                                        set_ball_vy(bird_in_lane, -1)
                                        state.ball_speeds[bird_in_lane] = int(variables.BALL_SPEEDS_DEFAULT.get('DINOSAUR', 4))
                                        state.dinosaur_up_presses[bird_in_lane] = 0
                                        reset_bird_power(bird_in_lane)
                                    else:
                                        # Reduce the fall speed by 1 (but keep >=1)
                                        state.ball_speeds[bird_in_lane] = max(1, state.ball_speeds[bird_in_lane] - 1)
                                # Don't perform the normal immediate bounce
                                continue
                            # Normal behavior for non-DINOSAUR birds
                            # Try bounce (GLITCH has a chance to ignore)
                            if not try_glitch_bounce(bird_in_lane):
                                continue  # GLITCH ignored the bounce

                            # Bounce bird up with boost if active
                            bounce_bird(bird_in_lane, apply_boost=True)
                        elif state.ball_vy[bird_in_lane] == -1:  # Already moving up - activate special power
                            # Only use power once per ascent
                            # Allow extra power use for A-grade birds (2 uses per ascent)
                            grade_label, _ = compute_grade_from_xp(state.per_bird_xp[bird_in_lane])
                            allowed_uses = 2 if (grade_label and grade_label.startswith('A')) else 1
                            if not allow_consume_power(bird_in_lane, allowed_uses=allowed_uses):
                                # already consumed allowed uses - do nothing
                                pass
                            else:
                                bird_color = state.ball_colors[bird_in_lane]
                                # Notify achievements about power use
                                p_name = get_color_name(bird_color)
                                bird_lane = state.random_lanes[bird_in_lane]
                                achievements.check_achievements_event('power_used', power=p_name, lane=bird_lane, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)

                                if bird_color == YELLOW:
                                    # Yellow power: Slow down adjacent falling birds by -1
                                    # EXCEPT for other yellow birds - bounce them instead
                                    affected_count = 0
                                    for adj_lane, adj_bird in find_adjacent_birds(bird_lane):
                                        if not state.ball_lost[adj_bird]:
                                            # Check if bird is falling (moving down)
                                            if state.ball_vy[adj_bird] == 1:
                                                # If the adjacent bird is a yellow/patchwork, bounce it
                                                if state.ball_colors[adj_bird] == YELLOW or state.ball_colors[adj_bird] == PATCHWORK:
                                                    # Try bounce (GLITCH may ignore)
                                                    if try_glitch_bounce(adj_bird):
                                                        reset_bird_power(adj_bird)  # Reset power for bounced yellow
                                                        affected_count += 1
                                                        achievements.append_recent_action('bounce', lane=adj_lane, color=state.ball_colors[adj_bird], frame_count=state.frame_count)

                                                        # When a yellow is bounced, nearby SCARED blue birds that are falling
                                                        # and occupying adjacent lanes should lose their scared state.
                                                        for cross_lane, bi in find_adjacent_birds(adj_lane):
                                                            if (not state.ball_lost[bi] and state.ball_colors[bi] == BLUE and 
                                                                bi in state.scared_birds and state.ball_vy[bi] == 1):
                                                                del state.scared_birds[bi]
                                                else:
                                                    # Non-yellow bird - apply slow effect
                                                    state.speed_boosts[adj_bird] = -int(3.0 / variables.base_sleep)  # 3 seconds of slow
                                                    affected_count += 1
                                                

                                elif bird_color == RED:
                                    # Red power: Launch projectile immediately
                                    # Count adjacent red/purple/PATCHWORK birds moving up for damage bonus
                                    damage_bonus = 0
                                    for adj_lane, idx in find_adjacent_birds(bird_lane):
                                        if not state.ball_lost[idx]:
                                            if (state.ball_colors[idx] == RED or state.ball_colors[idx] == PURPLE or 
                                                state.ball_colors[idx] == PATCHWORK) and state.ball_vy[idx] == -1:
                                                damage_bonus += 1
                                    state.red_projectiles.append({
                                        'x_pos': variables.LANE_POSITIONS[bird_lane],
                                        'y_pos': state.ball_y[bird_in_lane],
                                        'lane': bird_lane,
                                        'damage': 1 + damage_bonus,
                                        'powered': damage_bonus > 0,
                                        'owner': bird_in_lane,
                                        'speed': 1
                                    })

                                elif bird_color == PURPLE:
                                    # PURPLE: begin priming the charge when UP is held; actual charging starts next frame
                                    if state.purple_state[bird_in_lane] == 0:
                                        state.purple_state[bird_in_lane] = 1
                                        state.purple_primed_frame[bird_in_lane] = state.frame_count
                                        state.purple_hold_counter[bird_in_lane] = 0
                                elif bird_color == COOKIE:
                                    # COOKIE power: drop a cookie crumb at current lane containing 3/4 of cookie's XP
                                    crumb_xp = int(max(0, int(state.per_bird_xp[bird_in_lane] * 0.75)))
                                    state.loot_items.append({
                                        'x_pos': variables.LANE_POSITIONS[bird_lane],
                                        'y_pos': state.ball_y[bird_in_lane],
                                        'type': 'cookie_crumb',
                                        'rarity': 'rare',
                                        'xp': crumb_xp,
                                        'spawn_ts': time.time()
                                    })

                                    # Track crumbs created by this cookie bird
                                    state.cookie_crumbs_made[bird_in_lane] = state.cookie_crumbs_made.get(bird_in_lane, 0) + 1
                                    # After leaving 5 crumbs, the cookie bird disappears and should count as a loss
                                    if state.cookie_crumbs_made.get(bird_in_lane, 0) >= 5:
                                        # Only count the loss once (guard against double-decrement)
                                        if not state.ball_lost[bird_in_lane]:
                                            state.ball_lost[bird_in_lane] = True
                                            # place bird off-screen to indicate loss
                                            state.ball_y[bird_in_lane] = variables.HEIGHT - 1
                                            state.per_bird_xp[bird_in_lane] = 0
                                            state.lives -= 1
                                            if state.lives <= 0:
                                                state.game_over = True

                                elif bird_color == BLUE:
                                    # Blue power: Speed boost + extra damage flag
                                    boost_frames = int(3.0 / variables.base_sleep)
                                    state.speed_boosts[bird_in_lane] = boost_frames
                                    # Mark this bird as having blue power active (for extra damage)
                                    if bird_in_lane not in state.speed_boosts:
                                        state.speed_boosts[bird_in_lane] = boost_frames

                                elif bird_color == WHITE:
                                    # White power: Affect 4 adjacent lanes (2 left + 2 right)
                                    for adj_lane, adj_bird in find_adjacent_birds(bird_lane, offsets=[-2, -1, 1, 2]):
                                        if not state.ball_lost[adj_bird]:
                                            if state.ball_vy[adj_bird] == 1:
                                                # Bird is falling - bounce it up (if not scared)
                                                if can_bird_bounce(adj_bird):
                                                    # Try bounce (GLITCH may ignore)
                                                    if try_glitch_bounce(adj_bird):
                                                        reset_bird_power(adj_bird)  # Reset their power
                                                        achievements.append_recent_action('bounce', lane=adj_lane, color=state.ball_colors[adj_bird], frame_count=state.frame_count)

                                            elif state.ball_vy[adj_bird] == -1:
                                                    # Bird is rising - activate its power (if not already used)
                                                    # Allow extra power use for A-grade adjacent birds
                                                    adj_grade, _ = compute_grade_from_xp(state.per_bird_xp[adj_bird])
                                                    adj_allowed = 2 if (adj_grade and adj_grade.startswith('A')) else 1

                                                    if not allow_consume_power(adj_bird, allowed_uses=adj_allowed):
                                                        pass
                                                    else:
                                                        adj_bird_color = state.ball_colors[adj_bird]
                                                        # Notify achievements about adjacent bird power use
                                                        p_name = get_color_name(adj_bird_color)
                                                        achievements.check_achievements_event('power_used', power=p_name, lane=adj_lane, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                                                        adj_bird_lane = state.random_lanes[adj_bird]

                                                        # Execute the bird's power based on its color
                                                        if adj_bird_color == YELLOW:
                                                            # Yellow power on adjacent bird - bounces yellows, slows others
                                                            for y_lane, y_bird in find_adjacent_birds(adj_bird_lane):
                                                                if not state.ball_lost[y_bird] and state.ball_vy[y_bird] == 1:
                                                                    # Respect scared state
                                                                    if can_bird_bounce(y_bird):
                                                                        if state.ball_colors[y_bird] == YELLOW:
                                                                            # Bounce yellow bird
                                                                            set_ball_vy(y_bird, -1)
                                                                            reset_bird_power(y_bird)
                                                                        else:
                                                                            # Slow non-yellow bird
                                                                            state.speed_boosts[y_bird] = -int(3.0 / variables.base_sleep)

                                                        elif adj_bird_color == RED:
                                                            # Red power on adjacent bird
                                                            # Count adjacent red birds moving up for damage bonus
                                                            damage_bonus = 0
                                                            for adj_lane2, idx2 in find_adjacent_birds(adj_bird_lane):
                                                                if not state.ball_lost[idx2]:
                                                                    if state.ball_colors[idx2] == RED and state.ball_vy[idx2] == -1:
                                                                        damage_bonus += 1

                                                            state.red_projectiles.append({
                                                                'x_pos': variables.LANE_POSITIONS[adj_bird_lane],
                                                                'y_pos': state.ball_y[adj_bird],
                                                                'lane': adj_bird_lane,
                                                                'damage': 1 + damage_bonus,
                                                                'powered': damage_bonus > 0,
                                                                'owner': adj_bird
                                                            })

                                                        elif adj_bird_color == BLUE:
                                                            # Blue power on adjacent bird
                                                            boost_frames = int(variables.BLUE_ADJACENT_BOOST_SECONDS / variables.base_sleep)
                                                            state.speed_boosts[adj_bird] = boost_frames
                                elif bird_color == CLOCKWORK:
                                    # CLOCKWORK power: increase charge up to max 3.
                                    cur = state.clockwork_charge.get(bird_in_lane, variables.CLOCKWORK_INITIAL_CHARGE)
                                    if cur is None:
                                        cur = variables.CLOCKWORK_INITIAL_CHARGE
                                    newc = min(int(variables.CLOCKWORK_MAX_CHARGE), cur + 1)
                                    state.clockwork_charge[bird_in_lane] = newc
                                    # When charge > 0, speed mirrors charge
                                    if newc > 0:
                                        state.ball_speeds[bird_in_lane] = newc
                                elif bird_color == STEALTH:
                                    # Stealth power: become tangible for a short duration and deal heavy damage
                                    # state.bird_power_used[bird_in_lane] is already True
                                    state.stealth_timers[bird_in_lane] = max(1, int(variables.STEALTH_TANGIBLE_SECONDS / variables.base_sleep))
                                    # Save previous speed and apply temporary speed boost
                                    state.stealth_prev_speeds[bird_in_lane] = state.ball_speeds[bird_in_lane]
                                    state.ball_speeds[bird_in_lane] = int(variables.STEALTH_SPEED_BOOST)
                                    achievements.append_recent_action('stealth', lane=bird_lane, color=STEALTH, frame_count=state.frame_count)

            elif key == variables.KEY_MOVE_DOWN:
                # Suction: pull bird down if moving up
                if state.powerups['suction_active']:
                    # Determine affected lanes (support wide cursor)
                    lanes_to_affect = get_affected_lanes()

                    for lane in lanes_to_affect:
                        bird_in_lane = find_bird_in_lane(lane)
                        if bird_in_lane >= 0 and not state.ball_lost[bird_in_lane]:
                            if state.ball_vy[bird_in_lane] == -1:  # Moving up - pull it down
                                set_ball_vy(bird_in_lane, 1)
                                # Apply suction boost if configured
                                if state.powerups['suction_boost_duration'] > 0 and bird_in_lane not in state.speed_boosts:
                                    boost_frames = int(state.powerups['suction_boost_duration'] / variables.base_sleep)
                                    state.speed_boosts[bird_in_lane] = boost_frames
                                # record suction action for combo detection
                                achievements.append_recent_action('suction', lane=state.random_lanes[bird_in_lane], color=state.ball_colors[bird_in_lane], frame_count=state.frame_count)
            elif key == variables.KEY_QUIT:
                break

        # Build output buffer (don't clear screen, just reposition)
        output = "\033[2J\033[H"  # Clear screen and move to home
        
        # Recompute state.level from current state.score so spending points can LOWER the state.level
        state.level = compute_level_from_score(state.score)

        # Draw simple header with state.score, state.level, state.lives, and compact per-lane XP (trimmed to fit WIDTH)
        next_level_score = calculate_level_threshold(state.level + 1)
        lives_display = "●" * state.lives + "◌" * (5 - state.lives)

        # Compute prestige for display (safe fallback to 1.0)
        prestige_val = compute_prestige()
        if prestige_val is None:
            prestige_val = 1.0
        prestige_display = f"{prestige_val:.2f}x"

        base_score_line = f"SCORE: {int(state.score)}  |  LEVEL: {state.level}  |  NEXT: {next_level_score}  |  LIVES: {lives_display}  |  PRESTIGE: {prestige_display}"

        # XP and grade display removed from header per user request.
        # Keep internal XP bookkeeping (state.per_bird_xp) intact, but do not render it.
        output += f"\033[1;1H{base_score_line}\n"
        output += f"\033[2;1H{ceiling}\n"
        # Render single queued notification at the bottom (replace help/commands area)
        active_notifications = [n for n in state.notifications if n[1] > state.frame_count]
        if active_notifications:
            text, exp = active_notifications[0]
            footer_y = variables.HEIGHT + 3  # bottom area after game box
            # Truncate to width to avoid wrapping
            display_text = text[:variables.WIDTH]
            output += f"\033[{footer_y};1H{YELLOW}{display_text}{RESET}\n"
        # Prune expired state.notifications (keep order)
        state.notifications[:] = active_notifications
        
        # Draw starting line (dashed line near bottom)
        starting_line_y = variables.STARTING_LINE + 2  # +2 for header offset
        if 3 <= starting_line_y < variables.HEIGHT + 2:
            # When tailwind is active, render the starting line as blue carets '^'
            if state.powerups.get('tailwind_active'):
                dashed_line = "^ " * (variables.WIDTH // 2)
                output += f"\033[{starting_line_y};1H{BLUE}{dashed_line[:variables.WIDTH]}{RESET}"
            else:
                dashed_line = "- " * (variables.WIDTH // 2)  # Create dashed pattern
                output += f"\033[{starting_line_y};1H{DARK_GRAY}{dashed_line[:variables.WIDTH]}{RESET}"
            
            # Show power-up indicators on affected lanes
            # Calculate which lanes are affected by cursor
            lanes_to_check = get_affected_lanes()
            
            # Draw indicators on the starting line for each affected lane
            for lane in lanes_to_check:
                lane_x = variables.LANE_POSITIONS[lane]
                bird_in_lane = find_bird_in_lane(lane)
                
                if bird_in_lane >= 0 and not state.ball_lost[bird_in_lane]:
                    # Bounce boost: show blue ^ if bird is falling
                    if state.powerups['bounce_boost_active'] and state.ball_vy[bird_in_lane] == 1:
                        output += f"\033[{starting_line_y};{lane_x}H{BLUE}\033[1m^{RESET}"
                    # Suction: show red v if bird is rising
                    elif state.powerups['suction_active'] and state.ball_vy[bird_in_lane] == -1:
                        output += f"\033[{starting_line_y};{lane_x}H{RED}\033[1mv{RESET}"
            
        
        # Draw state.obstacles
        for obs in state.obstacles:
            # Color based on remaining HP (scale from base green to black)
            max_hp = variables._OBST_MAX_HP_BY_TIER.get(obs.get('tier', 1), obs.get('hp', 1))
            obs_color = render.color_from_hp(variables._OBST_BASE_RGB, obs.get('hp', 0), max_hp)

            # Draw sprite - single line, no HP display
            for line_idx, line in enumerate(OBSTACLE_SPRITE):
                y_pos = obs['y_pos'] + line_idx + 2  # +2 for header offset
                if 3 <= y_pos < variables.HEIGHT + 2:
                    x_pos = variables.LANE_POSITIONS[obs['lane']] - 1  # Center 3-char sprite
                    output += f"\033[{y_pos};{x_pos}H{obs_color}{line}{RESET}"
        
        # Draw state.bats
        for bat in state.bats:
            # Color based on remaining HP (scale from magenta to black)
            bat_hp = bat.get('hp', 0)
            bat_max = bat.get('max_hp', bat_hp if bat_hp > 0 else 1)
            bat_color = render.color_from_hp(variables._BATS_BASE_RGB, bat_hp, bat_max)

            # Choose sprite frame based on animation
            bat_sprite = BAT_FRAME_1 if (state.frame_count // 3) % 2 == 0 else BAT_FRAME_2
            
            # Draw bat - no HP display
            for line_idx, line in enumerate(bat_sprite):
                y_pos = bat['y_pos'] + line_idx + 2  # +2 for header offset
                if 3 <= y_pos < variables.HEIGHT + 2:
                    output += f"\033[{y_pos};{bat['x_pos']}H{bat_color}{line}{RESET}"
        
        # Draw loot items
        for loot in state.loot_items:
            y_pos = loot['y_pos'] + 2  # +2 for header offset
            if 3 <= y_pos < variables.HEIGHT + 2:
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
                elif loot_type == 'cookie_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{COOKIE}⬯{RESET}"
                elif loot_type == 'cookie_crumb':
                    # Small dot for crumb
                    output += f"\033[{y_pos};{loot['x_pos']}H{COOKIE}•{RESET}"
                elif loot_type == 'dinosaur_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{DINOSAUR}⬯{RESET}"
                elif loot_type == 'glitch_egg':
                    output += f"\033[{y_pos};{loot['x_pos']}H{GLITCH}⬯{RESET}"
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
        
        # Draw projectiles (red and others)
        for proj in state.red_projectiles:
            y_pos = proj['y_pos'] + 2  # +2 for header offset
            if 3 <= y_pos < variables.HEIGHT + 2:
                # Use • for powered (bonus damage), ⋅ for base
                symbol = "•" if proj.get('powered', False) else "⋅"
                proj_color = proj.get('color', RED)
                output += f"\033[{y_pos};{proj['x_pos']}H{proj_color}{symbol}{RESET}"
        
        # Draw active birds
        for b in range(variables.NUM_BALLS):
            if not state.ball_lost[b]:
                # Check if bird is slowed by yellow power (negative state.speed_boosts AND moving down)
                is_slowed = b in state.speed_boosts and state.speed_boosts[b] < 0 and state.ball_vy[b] == 1
                
                # Choose sprite based on direction and animate with frame counter
                # Special: CLOCKWORK animation depends on charge:
                #  - charge > 1: normal period
                #  - charge == 1: slower period
                #  - charge == 0: frozen (single frame)
                # Freeze animation if bird is slowed (external slow effect)
                if state.ball_vy[b] == -1:  # Moving up
                    if state.ball_colors[b] == CLOCKWORK:
                        try:
                            c = state.clockwork_charge.get(b, variables.CLOCKWORK_INITIAL_CHARGE)
                        except Exception:
                            c = variables.CLOCKWORK_INITIAL_CHARGE
                        if c == 0:
                            sprite = BIRD_UP_2  # frozen
                        elif c == 1:
                            sprite = BIRD_UP_1 if (state.frame_count // 6) % 2 == 0 else BIRD_UP_2
                        else:
                            sprite = BIRD_UP_1 if (state.frame_count // 3) % 2 == 0 else BIRD_UP_2
                    else:
                        # DINOSAUR has its own larger sprites
                        if state.ball_colors[b] == DINOSAUR:
                            sprite = DINOSAUR_UP_1 if (state.frame_count // 3) % 2 == 0 else DINOSAUR_UP_2
                        # If a blue bird is sprinting (power active), lock the up-frame to BIRD_UP_1
                        # This prevents the animation from toggling while sprint is active.
                        elif state.ball_colors[b] == BLUE and state.bird_power_used[b]:
                            sprite = BIRD_UP_1
                        else:
                            sprite = BIRD_UP_1 if (state.frame_count // 3) % 2 == 0 else BIRD_UP_2
                else:  # Moving down
                    if is_slowed:
                        sprite = BIRD_DOWN_2 # Frozen frame when slowed
                    else:
                        if state.ball_colors[b] == CLOCKWORK:
                            c = state.clockwork_charge.get(b, variables.CLOCKWORK_INITIAL_CHARGE)
                            if c == 0:
                                sprite = BIRD_DOWN_2  # frozen
                            elif c == 1:
                                sprite = BIRD_DOWN_1 if (state.frame_count // 6) % 2 == 0 else BIRD_DOWN_2
                            else:
                                sprite = BIRD_DOWN_1 if (state.frame_count // 3) % 2 == 0 else BIRD_DOWN_2
                        else:
                            # DINOSAUR falling sprites
                            if state.ball_colors[b] == DINOSAUR:
                                sprite = DINOSAUR_DOWN_1 if (state.frame_count // 3) % 2 == 0 else DINOSAUR_DOWN_2
                            else:
                                sprite = BIRD_DOWN_1 if (state.frame_count // 3) % 2 == 0 else BIRD_DOWN_2
                
                            # GLITCH: mix sprite pieces each frame to create a glitched appearance
                            if state.ball_colors[b] == GLITCH:
                                # Choose base frames depending on direction
                                if state.ball_vy[b] == -1:
                                    f1 = BIRD_UP_1
                                    f2 = BIRD_UP_2
                                else:
                                    f1 = BIRD_DOWN_1
                                    f2 = BIRD_DOWN_2

                                mixed = []
                                for li in range(min(len(f1), len(f2))):
                                    line1 = f1[li]
                                    line2 = f2[li]
                                    # Pad to same length
                                    maxlen = max(len(line1), len(line2))
                                    line1 = line1.ljust(maxlen)
                                    line2 = line2.ljust(maxlen)
                                    chars = []
                                    for c1, c2 in zip(line1, line2):
                                        # randomly pick char from either frame
                                        chars.append(random.choice([c1, c2]))
                                    mixed.append(''.join(chars))
                                sprite = mixed

                # Choose color - handle STEALTH specially, blue birds turn cyan when power is active
                if state.ball_colors[b] == STEALTH:
                    # Tangible when a stealth timer is active for this bird
                    tangible = b in state.stealth_timers and state.stealth_timers.get(b, 0) > 0
                    # Pulse between DARK_GRAY (visible) and ANSI "conceal" (invisible) over a period
                    # This makes the bird actually invisible on terminals that support SGR 8.
                    # Use a faster visible pulse (~0.5s cycle) so the change is noticeable
                    period = max(4, int(2 / variables.base_sleep))

                    phase = (state.frame_count % period) / period
                    # Use DARK_GRAY for first half, ANSI conceal for second half (hidden/invisible)
                    # If the terminal doesn't support conceal, it'll appear as no-op; we can add
                    # a fallback later if needed.
                    color = DARK_GRAY if phase < 0.5 else "\033[8m"
                    # When tangible, show as a brighter color so the player clearly sees the effect
                    if tangible:
                        color = WHITE
                elif state.ball_colors[b] == BLUE and state.bird_power_used[b]:
                    color = CYAN  # Light blue when power active
                else:
                    color = state.ball_colors[b]
                
                # Draw each line of the bird (centered)
                for line_idx, line in enumerate(sprite):
                    y_pos = state.ball_y[b] + line_idx + 2  # +2 for header offset
                    if 3 <= y_pos < variables.HEIGHT + 2:
                        # Center sprites: compute offset from sprite width (works for 3- and 5-char sprites)
                        x_offset = len(line) // 2
                        # CLOCKWORK: special per-char coloring and blinking for '.' and '\''
                        if state.ball_colors[b] == CLOCKWORK:
                            c = state.clockwork_charge.get(b, variables.CLOCKWORK_INITIAL_CHARGE)
                            blink_period = max(1, int(0.6 / variables.base_sleep))
                            blink_on = ((state.frame_count // blink_period) % 2) == 0
                            colored = render_clockwork_line(line, c, blink_on)
                            output += f"\033[{y_pos};{state.ball_cols[b]-x_offset}H{colored}"
                        elif state.ball_colors[b] == PATCHWORK:
                            # Render each character with a different color pattern
                            colored = render_patchwork_line(line)
                            output += f"\033[{y_pos};{state.ball_cols[b]-x_offset}H{colored}"
                        else:
                            output += f"\033[{y_pos};{state.ball_cols[b]-x_offset}H{color}{line}{RESET}"
                    # After drawing the sprite lines, render a PURPLE charging orb in front of the bird if applicable
                    if state.ball_colors[b] == PURPLE and state.purple_state[b] == 2:
                        start_frame = state.purple_charge_started_frame[b]
                        # Only render after charging actually started
                        if state.frame_count >= start_frame:
                            elapsed_seconds = int((state.frame_count - start_frame) * variables.base_sleep)
                            s = max(0, min(3, elapsed_seconds))
                            if s <= 0:
                                sym = '⋅'
                            elif s == 1:
                                sym = '•'
                            else:
                                sym = '●'
                            # place orb in front of the bird (one line above the sprite)
                            orb_y = state.ball_y[b] + 1 + 2 - 1
                            if 3 <= orb_y < variables.HEIGHT + 2:
                                output += f"\033[{orb_y};{state.ball_cols[b]}H{PURPLE}{sym}{RESET}"

        # Check for state.level up
        if state.score >= calculate_level_threshold(state.level):
            state.level += 1
        
        # Calculate current speed based on state.level - more aggressive speed increase
        base_frame_sleep = variables.base_sleep * (variables.FRAME_SLEEP_LEVEL_MULTIPLIER ** state.level)
        # slow-motion removed: main loop sleep is not modified by state.powerups
        current_sleep = max(variables.min_sleep, base_frame_sleep)
        # Music engine integration removed from main loop
        
        # Draw floor and player
        output += f"\033[{variables.HEIGHT+2};1H{floor}\n"
        
        # Draw lost balls on floor as gray X
        for b in range(variables.NUM_BALLS):
            if state.ball_lost[b]:
                output += f"\033[{variables.HEIGHT+2};{state.ball_cols[b]}H\033[90mX{RESET}"
        
        
        # Draw player cursor - large and bright for visibility
        cursor_x = variables.LANE_POSITIONS[state.player_lane] - 1  # Center on lane
        # Change fallback cursor color when in swap mode (lane selected)
        fallback_cursor_color = YELLOW if state.selected_lane is not None else GREEN

        # Helper: map grade letter to requested cursor color
        def _grade_letter_color(letter):
            # User-specified mapping:
            # D: verde
            # C: bronzo (use ORANGE)
            # B: argento (use WHITE)
            # A: oro (use GOLD)
            # S: rosso (use RED)
            # compute_grade_from_xp returns labels like 'C1','B2' etc.
            # Use the first character as the prefix to determine color.
            if letter and isinstance(letter, str) and len(letter) > 0:
                prefix = letter[0]
            else:
                prefix = None
            if prefix == 'D':
                return GREEN
            if prefix == 'C':
                return ORANGE
            if prefix == 'B':
                return CLOCKWORK
            if prefix == 'A':
                return GOLD
            if prefix == 'S':
                return RED
            return fallback_cursor_color

        # Draw wide cursor if active
        if state.powerups['wide_cursor_active']:
            half_width = state.powerups['wide_cursor_lanes'] // 2
            cursor_str = ""
            for offset in range(-half_width, half_width + 1):
                lane = state.player_lane + offset
                if 0 <= lane < 9:
                    lane_x = variables.LANE_POSITIONS[lane] - 1
                    # Determine grade color for this lane if a bird exists
                    bird_idx = state.random_lanes.index(lane) if lane in state.random_lanes else -1

                    if bird_idx >= 0 and not state.ball_lost[bird_idx]:
                        letter, _ = compute_grade_from_xp(state.per_bird_xp[bird_idx])
                        color = _grade_letter_color(letter)
                    else:
                        color = fallback_cursor_color

                    if lane == state.player_lane:
                        # Main cursor: use glyph X1
                        glyph = '^'
                        cursor_str += f"\033[{variables.HEIGHT+3};{lane_x}H{color}\033[1m[{glyph}]{RESET}"
                    else:
                        # Extended cursor wings: use glyph X2
                        glyph = '^'
                        cursor_str += f"\033[{variables.HEIGHT+3};{lane_x}H{color}\033[1m[{glyph}]{RESET}"
            output += cursor_str + "\n"
        else:
            # Normal cursor: color by grade of bird in state.player_lane if present
            bird_idx = state.random_lanes.index(state.player_lane) if state.player_lane in state.random_lanes else -1
            if bird_idx >= 0 and not state.ball_lost[bird_idx]:
                letter, _ = compute_grade_from_xp(state.per_bird_xp[bird_idx])
                color = _grade_letter_color(letter)
            else:
                color = fallback_cursor_color

            glyph = '^'
            output += f"\033[{variables.HEIGHT+3};{cursor_x}H{color}\033[1m[{glyph}]{RESET}\n"
        
        # Highlight selected lane if in swap mode
        if state.selected_lane is not None:
            selected_x = variables.LANE_POSITIONS[state.selected_lane] - 1
            output += f"\033[{variables.HEIGHT+3};{selected_x}H{YELLOW}\033[1m[*]{RESET}"  # Mark selected lane
        
        # Count active balls
        active_balls = sum(1 for lost in state.ball_lost if not lost)
        swap_hint = " | Press SPACE again to swap or cancel" if state.selected_lane is not None else ""
        output += f"\033[{variables.HEIGHT+4};1HUse ← → to move, ↑ to bounce, Ctrl+C to quit | Birds: {active_balls}/{variables.NUM_BALLS}{swap_hint}"
        # Optional debug overlay: show per-bird XP and grade summary near footer
        if state.show_xp_overlay:
            parts = []
            for i in range(variables.NUM_BALLS):
                label, _ = compute_grade_from_xp(state.per_bird_xp[i])
                parts.append(f"{label}({int(state.per_bird_xp[i])})")
            xp_summary = ' '.join(parts)
            output += f"\033[{variables.HEIGHT+5};1HXP: {xp_summary[:WIDTH]}{RESET}"
        
        # If state.paused, render a PAUSED overlay (keep input responsive)
        if state.paused:
            pause_y = 2 + (variables.HEIGHT // 2)
            pause_x = max(1, (variables.WIDTH // 2) - 3)
            output += f"\033[{pause_y};{pause_x}H{YELLOW}\033[1mPAUSED{RESET}"

        # Write all at once - handle blocking errors gracefully
        try:
            sys.stdout.write(output)
            sys.stdout.flush()
        except BlockingIOError:
            # Buffer full, skip this frame
            pass

        # If state.paused, skip per-frame updates but sleep to avoid tight-loop
        if state.paused:
            time.sleep(current_sleep)
            continue
        
        # Update ball positions
        state.frame_count += 1
        state.obstacle_spawn_timer += 1
        state.bat_spawn_timer += 1
        # CLOCKWORK decay: every 30s reduce charge by 1 (per bird)
        # Use configurable CLOCKWORK_DECAY_SECONDS (seconds) converted to frames
        decay_frames = max(1, int(float(variables.CLOCKWORK_DECAY_SECONDS) / variables.base_sleep))
        if decay_frames > 0 and state.frame_count % decay_frames == 0:
            for i in range(variables.NUM_BALLS):
                if state.ball_colors[i] == CLOCKWORK and not state.ball_lost[i]:
                    c = state.clockwork_charge.get(i, None)
                    if c is None:
                        c = variables.CLOCKWORK_INITIAL_CHARGE
                        state.clockwork_charge[i] = variables.CLOCKWORK_INITIAL_CHARGE
                    if c > 0:
                        state.clockwork_charge[i] = c - 1
                        newc = state.clockwork_charge[i]
                        if newc > 0:
                            state.ball_speeds[i] = newc
                        else:
                            # Enter freefall: set very fast falling speed and ensure bird is falling
                            state.ball_speeds[i] = 6
                            set_ball_vy(i, 1)
                            achievements.add_notification('Clockwork freefall!', state.frame_count, state.notifications)

        # --- Per-frame achievement-related checks ---
        # Area hold: check if all active birds are in top X% areas
        # top50: y <= HEIGHT * 0.5, top30: y <= HEIGHT * 0.3
        active_idxs = [i for i in range(variables.NUM_BALLS) if not state.ball_lost[i]]
        if active_idxs:
            top50_y = int(variables.HEIGHT * 0.5)
            top30_y = int(variables.HEIGHT * 0.3)
            all_top50 = all(state.ball_y[i] <= top50_y for i in active_idxs)
            all_top30 = all(state.ball_y[i] <= top30_y for i in active_idxs)

            if all_top50:
                achievements.top50_hold_frames += 1
            else:
                achievements.top50_hold_frames = 0

            if all_top30:
                achievements.top30_hold_frames += 1
            else:
                achievements.top30_hold_frames = 0

            # Fire area_hold events
            achievements.check_achievements_event('area_hold', area='top50', frames=achievements.top50_hold_frames, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
            achievements.check_achievements_event('area_hold', area='top30', frames=achievements.top30_hold_frames, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)

        # Original birds alive tracking
        originals_alive = all(not state.ball_lost[idx] for idx in state.original_indices)
        if originals_alive:
            achievements.original_alive_frames += 1
        else:
            achievements.original_alive_frames = 0
        achievements.check_achievements_event('original_survive', frames=achievements.original_alive_frames, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)

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
            count = sum(1 for i in range(variables.NUM_BALLS) if not state.ball_lost[i] and state.ball_colors[i] == cval)
            achievements.check_achievements_event('color_count', color=cname, count=count, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
        
        # Count current entities on screen (excluding birds)
        active_birds = sum(1 for lost in state.ball_lost if not lost)
        current_entities = len(state.obstacles) + len(state.bats) + active_birds
        
        # Try to spawn from queue if we're under the entity limit
        if current_entities < variables.MAX_ENTITIES and state.spawn_queue:
            entity = state.spawn_queue.pop(0)
            if entity['type'] == 'bat':
                # stamp a spawn timestamp for despawn logic
                entity['data']['spawn_ts'] = time.time()
                state.bats.append(entity['data'])
            elif entity['type'] == 'obstacle':
                state.obstacles.append(entity['data'])
        
        # Queue bat spawns - spawn rate reduced to make state.bats rarer
        # Spawn less often and allow up to 3 state.bats on screen
        if len(state.bats) < 2 and state.bat_spawn_timer > random.randint(120, 220):
            state.bat_spawn_timer = 0
            
            # Calculate target Y position based on state.level
            # Lower levels: state.bats stop higher (around 5-8)
            # Higher levels: state.bats stop lower (max half screen = 12)
            if state.level <= 3:
                target_y = random.randint(5, 8)
            elif state.level <= 6:
                target_y = random.randint(8, 10)
            else:
                target_y = random.randint(variables.BAT_TARGET_Y_MIN_LOW_LEVEL, variables.BAT_TARGET_Y_MAX_LOW_LEVEL)  # Max at half screen
            
            # Tier selection increases with state.level (4 tiers now)
            if state.level <= variables.BAT_TIER_LEVEL_THRESHOLD_1:
                tier = random.choices([1, 2, 3, 4], weights=variables.BAT_TIER_WEIGHTS_LEVEL_0_2)[0]
            elif state.level <= variables.BAT_TIER_LEVEL_THRESHOLD_2:
                tier = random.choices([1, 2, 3, 4], weights=variables.BAT_TIER_WEIGHTS_LEVEL_3_4)[0]
            elif state.level <= variables.BAT_TIER_LEVEL_THRESHOLD_3:
                tier = random.choices([1, 2, 3, 4], weights=variables.BAT_TIER_WEIGHTS_LEVEL_5_7)[0]
            else:
                tier = random.choices([1, 2, 3, 4], weights=variables.BAT_TIER_WEIGHTS_LEVEL_8_PLUS)[0]
            
            # HP progression: 16, 32, 64, 128
            if tier == 1:
                hp = variables.BAT_HP_TIER_1
            elif tier == 2:
                hp = variables.BAT_HP_TIER_2
            elif tier == 3:
                hp = variables.BAT_HP_TIER_3
            else:  # tier 4
                hp = variables.BAT_HP_TIER_4
            
            # Try to find a spawn position that doesn't overlap with existing state.bats
            max_attempts = variables.BAT_SPAWN_MAX_ATTEMPTS
            spawn_x = None
            for attempt in range(max_attempts):
                # Spawn within game box: state.bats are 8 chars wide, need margin
                candidate_x = random.randint(variables.BAT_SPAWN_X_MIN, variables.WIDTH - variables.BAT_SPAWN_X_MARGIN)  # Keep bat fully inside box
                # Check if this position overlaps with any existing bat
                overlaps = False
                for existing_bat in state.bats:
                    # Bats are 8 chars wide - need at least variables.BAT_MIN_SEPARATION chars separation
                    if abs(candidate_x - existing_bat['x_pos']) < variables.BAT_MIN_SEPARATION:
                        overlaps = True
                        break
                
                # Also check overlap with spawn queue
                for queued in state.spawn_queue:
                    if queued['type'] == 'bat':
                        if abs(candidate_x - queued['data']['x_pos']) < variables.BAT_MIN_SEPARATION:
                            overlaps = True
                            break
                
                if not overlaps:
                    spawn_x = candidate_x
                    break
            
            # If we couldn't find a good position, DON'T SPAWN
            if spawn_x is None:
                state.bat_spawn_timer = variables.BAT_SPAWN_FAIL_RETRY_TIMER  # Wait a bit before trying again
            else:
                # Check if last 2 items in queue are state.bats - if so, skip this spawn
                can_add = True
                if len(state.spawn_queue) >= variables.BAT_CONSECUTIVE_SPAWN_LIMIT:
                    if state.spawn_queue[-1]['type'] == 'bat' and state.spawn_queue[-2]['type'] == 'bat':
                        can_add = False
                        state.bat_spawn_timer = variables.BAT_CONSECUTIVE_RETRY_TIMER  # Retry soon
                
                if can_add:
                    # Found a good position - queue the bat
                    direction = random.choice([-1, 1])  # -1 = left, 1 = right
                    
                    state.spawn_queue.append({
                        'type': 'bat',
                        'data': {
                            'x_pos': spawn_x,
                            'y_pos': variables.BAT_SPAWN_Y_START,  # Start from top like state.obstacles
                            'target_y': target_y,  # Stop at this Y position
                            'tier': tier,
                            'hp': hp,
                            'max_hp': hp,
                            'direction': direction,
                            'wave_offset': random.randint(variables.BAT_WAVE_OFFSET_MIN, variables.BAT_WAVE_OFFSET_MAX)
                        }
                    })
        
        # Queue obstacle spawns - much more aggressive spawn rate
        base_spawn_rate = max(variables.OBSTACLE_BASE_SPAWN_RATE_MIN, variables.OBSTACLE_BASE_SPAWN_RATE_BASE - (state.level * variables.OBSTACLE_SPAWN_RATE_LEVEL_MULTIPLIER))  # Much faster spawning
        spawn_variance = max(variables.OBSTACLE_SPAWN_VARIANCE_MIN, variables.OBSTACLE_SPAWN_VARIANCE_BASE - (state.level * variables.OBSTACLE_SPAWN_VARIANCE_LEVEL_MULTIPLIER))
        
        if state.obstacle_spawn_timer > random.randint(base_spawn_rate - spawn_variance, base_spawn_rate + spawn_variance):
            state.obstacle_spawn_timer = 0
            
            # Get list of active lanes (where birds are still alive)
            active_lanes = [state.random_lanes[i] for i in range(variables.NUM_BALLS) if not state.ball_lost[i]]
            
            # Only spawn obstacle if there are active lanes
            if active_lanes:
                # Filter out lanes occupied by state.bats
                available_lanes = []
                for lane_idx in active_lanes:
                    lane_x = variables.LANE_POSITIONS[lane_idx]
                    lane_left = lane_x - variables.LANE_COLLISION_HALF_WIDTH
                    lane_right = lane_x + variables.LANE_COLLISION_HALF_WIDTH
                    
                    # Check if any bat overlaps with this lane
                    bat_in_lane = False
                    for bat in state.bats:
                        bat_left = bat['x_pos']
                        bat_right = bat['x_pos'] + variables.BAT_SPRITE_WIDTH
                        if not (bat_right < lane_left or bat_left > lane_right):
                            bat_in_lane = True
                            break
                    
                    if not bat_in_lane:
                        available_lanes.append(lane_idx)
                
                # If no lanes available (all have state.bats), skip this spawn
                if not available_lanes:
                    state.obstacle_spawn_timer = max(5, base_spawn_rate // 2)
                else:
                    # Only spawn in lanes without state.obstacles
                    lanes_without_obstacles = []
                    for lane_idx in available_lanes:
                        has_obstacle = any(obs['lane'] == lane_idx for obs in state.obstacles)
                        if not has_obstacle:
                            lanes_without_obstacles.append(lane_idx)
                    
                    # Only spawn if there's at least one free lane
                    if not lanes_without_obstacles:
                        # All available lanes have state.obstacles - skip spawn
                        state.obstacle_spawn_timer = max(variables.OBSTACLE_RETRY_TIMER_MIN, base_spawn_rate // variables.OBSTACLE_RETRY_TIMER_DIVISOR)
                    else:
                        # Choose a free lane
                        lane = random.choice(lanes_without_obstacles)
                    
                        # Tier distribution changes with state.level - higher tiers become MORE common (4 tiers)
                        if state.level <= variables.OBSTACLE_TIER_LEVEL_THRESHOLD_1:
                            tier = random.choices([1, 2, 3, 4], weights=variables.OBSTACLE_TIER_WEIGHTS_LEVEL_0_2)[0]
                        elif state.level <= variables.OBSTACLE_TIER_LEVEL_THRESHOLD_2:
                            tier = random.choices([1, 2, 3, 4], weights=variables.OBSTACLE_TIER_WEIGHTS_LEVEL_3_4)[0]
                        elif state.level <= variables.OBSTACLE_TIER_LEVEL_THRESHOLD_3:
                            tier = random.choices([1, 2, 3, 4], weights=variables.OBSTACLE_TIER_WEIGHTS_LEVEL_5_7)[0]
                        else:
                            tier = random.choices([1, 2, 3, 4], weights=variables.OBSTACLE_TIER_WEIGHTS_LEVEL_8_PLUS)[0]
                        
                        # HP based on tier: 4, 6, 10, 16
                        if tier == 1:
                            hp = variables.OBSTACLE_HP_TIER_1
                        elif tier == 2:
                            hp = variables.OBSTACLE_HP_TIER_2
                        elif tier == 3:
                            hp = variables.OBSTACLE_HP_TIER_3
                        else:  # tier 4
                            hp = variables.OBSTACLE_HP_TIER_4
                        
                        # Check if last 2 items in queue are state.obstacles - if so, skip this spawn
                        can_add = True
                        if len(state.spawn_queue) >= variables.OBSTACLE_CONSECUTIVE_SPAWN_LIMIT:
                            if state.spawn_queue[-1]['type'] == 'obstacle' and state.spawn_queue[-2]['type'] == 'obstacle':
                                can_add = False
                                state.obstacle_spawn_timer = max(variables.OBSTACLE_RETRY_TIMER_MIN, base_spawn_rate // variables.OBSTACLE_RETRY_TIMER_DIVISOR)  # Retry sooner
                        
                        if can_add:
                            state.spawn_queue.append({
                                'type': 'obstacle',
                                'data': {'lane': lane, 'y_pos': 1, 'tier': tier, 'hp': hp}
                            })
        
        # Move state.obstacles down - always speed 1 (slowest)
        for obs in state.obstacles[:]:
            if state.frame_count % (6 - 1) == 0:  # Speed 1: move every 5 frames
                obs['y_pos'] += 1
            
            # Auto-remove state.obstacles when they reach the line above the starting line
            if obs['y_pos'] >= variables.STARTING_LINE - 1:
                state.obstacles.remove(obs)
            elif obs['y_pos'] >= variables.HEIGHT:
                state.obstacles.remove(obs)
        
        # Move state.bats horizontally and vertically (wave motion)
        for bat in state.bats[:]:
            if state.frame_count % 3 == 0:  # Bats move every 3 frames
                # Calculate next horizontal position
                next_x = bat['x_pos'] + bat['direction'] * 2
                
                # Check if bat would overlap with another bat at next position
                can_move = True
                
                # Check collision with other state.bats
                for other_bat in state.bats:
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
                    for i in range(variables.NUM_BALLS):
                        if not state.ball_lost[i]:
                            # Get bird's LANE position - birds are in lanes!
                            bird_lane_x = variables.LANE_POSITIONS[state.random_lanes[i]]
                            # Each lane is effectively a column - if bat enters lane, block it
                            bird_y = state.ball_y[i]
                            
                            # Predict bird's next movement
                            current_speed = state.ball_speeds[i]
                            if i in state.speed_boosts:
                                current_speed += 1
                            move_interval = max(1, int(variables.SPEED_MAX - current_speed))
                            
                            # Check if bird will move this frame
                            if state.frame_count % move_interval == 0:
                                next_bird_y = bird_y + state.ball_vy[i]
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
                    # Bounce off walls (state.bats are 8 chars wide)
                    if bat['x_pos'] <= 0:
                        bat['x_pos'] = 0
                        bat['direction'] = 1
                    elif bat['x_pos'] >= variables.WIDTH - 8:
                        bat['x_pos'] = variables.WIDTH - 8
                        bat['direction'] = -1
                else:
                    # Can't move, reverse direction
                    bat['direction'] *= -1
            
            # Move bat downward at speed 1 until it reaches target_y
            if state.frame_count % (6 - 1) == 0:  # Speed 1: move every 5 frames (same as state.obstacles)
                if bat['y_pos'] < bat['target_y']:
                    bat['y_pos'] += 1
        
        # Check bat-obstacle collisions and remove state.obstacles
        for bat in state.bats:
            bat_left = bat['x_pos']
            bat_right = bat['x_pos'] + 8  # Bats are 8 chars wide
            bat_top = bat['y_pos']
            bat_bottom = bat['y_pos'] + 1  # Bats are 2 lines tall
            
            for obs in state.obstacles[:]:
                obs_lane_x = variables.LANE_POSITIONS[obs['lane']]
                obs_left = obs_lane_x - 1  # Obstacles are 3 chars wide centered on lane
                obs_right = obs_lane_x + 1
                obs_y = obs['y_pos']
                
                # Check horizontal overlap
                horizontal_overlap = not (bat_right < obs_left or bat_left > obs_right)
                # Check vertical overlap (obstacle is 1 line tall)
                vertical_overlap = abs(bat_top - obs_y) <= 1 or abs(bat_bottom - obs_y) <= 1
                
                if horizontal_overlap and vertical_overlap:
                    state.obstacles.remove(obs)
        
        # Despawn old state.bats and loot (older than 60 seconds)
        now_ts = time.time()
        # Remove state.bats older than BAT_DESPAWN_TIME seconds
        for bat in state.bats[:]:
            try:
                if now_ts - float(bat.get('spawn_ts', now_ts)) > variables.BAT_DESPAWN_TIME:
                    state.bats.remove(bat)
            except Exception:
                # If malformed spawn_ts, skip removal for safety
                continue

        # Remove loot items older than LOOT_DESPAWN_TIME seconds
        for loot in state.loot_items[:]:
            if now_ts - float(loot.get('spawn_ts', now_ts)) > variables.LOOT_DESPAWN_TIME:
                if loot.get('type') == 'orange_egg' and loot.get('y_pos') == variables.STARTING_LINE:
                        # find lane index from x_pos
                        lane_x = loot.get('x_pos')
                        lane = variables.LANE_POSITIONS.index(lane_x)
                        # find the bird that occupies that lane
                        for bi in range(variables.NUM_BALLS):
                            if state.random_lanes[bi] == lane:
                                    # check for egg-state markers
                                    if (state.ball_colors[bi] == variables.ORANGE and state.ball_y[bi] == variables.ORANGE_OUT_OF_PLAY_Y and state.ball_speeds[bi] == 0 and not state.ball_lost[bi]):
                                        # mark bird as lost and decrement state.lives
                                        state.ball_lost[bi] = True
                                        state.ball_y[bi] = variables.HEIGHT - 1
                                        state.lives -= 1
                                        if state.lives <= 0:
                                            state.game_over = True
                                    break
                # Finally, remove the loot item (best-effort)
                state.loot_items.remove(loot)

        # Update speed boosts (decrease frame counter)
        for bird_idx in list(state.speed_boosts.keys()):
            if state.speed_boosts[bird_idx] > 0:
                # Positive = speed boost
                state.speed_boosts[bird_idx] -= 1
                if state.speed_boosts[bird_idx] <= 0:
                    del state.speed_boosts[bird_idx]
                    # If a positive speed boost expired naturally, ensure the
                    # bird's power-used flag is cleared so UI/colour returns to normal
                    if 0 <= bird_idx < len(state.ball_colors) and state.ball_colors[bird_idx] == BLUE:
                        reset_bird_power(bird_idx)
            else:
                # Negative = slow effect (count up towards 0)
                state.speed_boosts[bird_idx] += 1
                if state.speed_boosts[bird_idx] >= 0:
                    del state.speed_boosts[bird_idx]
        
        # Update scared birds (decrease frame counter)
        for bird_idx in list(state.scared_birds.keys()):
            state.scared_birds[bird_idx] -= 1
            if state.scared_birds[bird_idx] <= 0:
                del state.scared_birds[bird_idx]

        # Update stealth timers (decrease frame counter) - when expired, return to stealth
        for bird_idx in list(state.stealth_timers.keys()):
            state.stealth_timers[bird_idx] -= 1
            if state.stealth_timers[bird_idx] <= 0:
                del state.stealth_timers[bird_idx]
                # IMPORTANT: do NOT reset state.bird_power_used here.
                # state.bird_power_used should remain True until the bird finishes the ascent
                # (e.g. bounces or starts descending). Resetting here would allow the
                # player to re-activate the power again during the same rise.
                # Restore previous speed if we saved one
                if bird_idx in state.stealth_prev_speeds:
                    prev = state.stealth_prev_speeds.pop(bird_idx)
                    # Only restore if bird still exists
                    state.ball_speeds[bird_idx] = prev
        
        # Blue birds lose fear when crossing yellow birds
        # (blue going down, yellow going up, in adjacent lanes, blue passes yellow)
        birds_to_unfear = []
        for i in range(variables.NUM_BALLS):
            if state.ball_colors[i] == BLUE and i in state.scared_birds and not state.ball_lost[i]:
                if state.ball_vy[i] == 1:  # Blue bird moving down
                    blue_lane = state.random_lanes[i]
                    blue_y = state.ball_y[i]
                    
                    # Check adjacent lanes for yellow birds moving up
                    for adj_offset in [-1, 1]:
                        adj_lane = blue_lane + adj_offset
                        if 0 <= adj_lane < 9:
                            # Find bird in adjacent lane
                            for j in range(variables.NUM_BALLS):
                                if j != i and not state.ball_lost[j] and state.random_lanes[j] == adj_lane:
                                    if state.ball_colors[j] == YELLOW and state.ball_vy[j] == -1:  # Yellow moving up
                                        yellow_y = state.ball_y[j]
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
            if bird_idx in state.scared_birds:
                del state.scared_birds[bird_idx]
        
        # Track UP hold/release state (edge detection) to support charging behavior
        # Use prev_up_state to remember the previous-frame state so intermittent
        # terminal key-repeat (missing frames) doesn't cancel primed charging.
        # Debounced UP hold/release detection to avoid single-frame glitches
        up_pressed_this_frame = (key == variables.KEY_MOVE_UP)

        if up_pressed_this_frame:
            state.up_hold_counter = state.up_hold_counter + 1
            state.up_miss_counter = 0
        else:
            state.up_miss_counter = state.up_miss_counter + 1

        # Consider a release only when UP has been missing for >=2 consecutive frames
        up_released = (state.up_hold_counter > 0 and state.up_miss_counter >= 2)
        if up_released:
            state.up_hold_counter = 0
            state.up_miss_counter = 0

        # Handle PURPLE charging state machine per bird
        for b in range(variables.NUM_BALLS):
            purple_bird_state = state.purple_state[b]
            # Transition primed -> charging on next frame if UP still held
            if purple_bird_state == 1:
                # Transition primed -> charging if UP is still considered held.
                # Use prev_up_state OR current up_pressed_this_frame to tolerate
                # intermittent key-repeat frames where the terminal doesn't
                # emit the arrow every single game frame.
                # Consider UP held only if currently pressed (debounced via miss count).
                held = up_pressed_this_frame

                # Enter charging if we've not seen too many misses since priming
                if state.frame_count > state.purple_primed_frame[b] and state.purple_miss_count[b] < 2 and not state.ball_lost[b] and state.ball_vy[b] == -1:
                    # Enter charging: save current vy (do NOT change state.ball_vy so sprite/direction remains)
                    state.purple_saved_vy[b] = state.ball_vy[b]
                    state.purple_state[b] = 2
                    state.purple_charge_started_frame[b] = state.frame_count
                else:
                    # Debounced cancel: allow up to 1 missed frame before cancelling primed
                    if not held:
                        state.purple_miss_count[b] += 1
                    else:
                        state.purple_miss_count[b] = 0

                    if state.purple_miss_count[b] >= 3:
                        if state.bird_power_uses[b] > 0:
                            state.bird_power_uses[b] = max(0, state.bird_power_uses[b] - 1)
                        state.bird_power_used[b] = False
                        # ensure any saved vy is cleared
                        state.purple_saved_vy[b] = None
                        state.purple_state[b] = 0
                        state.purple_primed_frame[b] = 0
                        state.purple_miss_count[b] = 0

            elif purple_bird_state == 2:
                # Charging: compute elapsed seconds
                start_frame = state.purple_charge_started_frame[b]
                elapsed_seconds = 0
                elapsed_seconds = int((state.frame_count - start_frame) * variables.base_sleep)
                s = max(0, min(3, elapsed_seconds))

                # Auto-fire at max charge
                if s >= 3:
                    fire_now = True
                else:
                    # Only fire when player releases UP or the bird is lost.
                    # Do NOT treat changes to state.ball_vy as a trigger because we
                    # intentionally set state.ball_vy=0 to freeze the bird while
                    # charging; treating that as 'not -1' caused immediate
                    # accidental firing.
                    fire_now = bool(up_released or state.ball_lost[b])

                if fire_now:
                    if s >= 1:
                        dmg = int(pow(4, s))
                        state.red_projectiles.append({
                            'x_pos': variables.LANE_POSITIONS[state.random_lanes[b]],
                            'y_pos': state.ball_y[b],
                            'lane': state.random_lanes[b],
                            'damage': dmg,
                            'powered': dmg > 1,
                            'owner': b,
                            'speed': 4,
                            'color': PURPLE
                        })
                        # Briefly protect the bird from immediate collision changes
                        # Provide a slightly larger protection window (frames)
                        # so the per-bird decrement at loop start doesn't
                        # immediately clear the protection. Use a small
                        # safety margin (at least 3 frames).
                        state.purple_just_fired_frames[b] = max(3, int(0.2 / variables.base_sleep) + 2)
                    else:
                        # Cancelled before 1s: refund power
                        if state.bird_power_uses[b] > 0:
                            state.bird_power_uses[b] = max(0, state.bird_power_uses[b] - 1)
                        state.bird_power_used[b] = False

                    # Restore bird vertical movement from saved vy
                    if state.purple_saved_vy[b] is not None:
                        state.ball_vy[b] = state.purple_saved_vy[b]

                    state.purple_saved_vy[b] = None

                    # Reset charging state
                    state.purple_state[b] = 0
                    state.purple_charge_started_frame[b] = 0
                    state.purple_primed_frame[b] = 0

        # Update red projectiles
        for proj in state.red_projectiles[:]:
            # Move projectile upward by its speed (allow fast purple shots). We move step-by-step
            # so collisions are checked for each unit traveled.
            move_steps = int(max(1, proj.get('speed', 1)))
            removed_proj = False
            for _step in range(move_steps):
                proj['y_pos'] -= 1

                # Remove if off screen
                if proj['y_pos'] < 0:
                    try:
                        state.red_projectiles.remove(proj)
                    except ValueError:
                        pass
                    removed_proj = True
                    break

                # Check collision with state.bats
                hit_bat = False
                for bat in state.bats[:]:
                    bat_left = bat['x_pos']
                    bat_right = bat['x_pos'] + 8
                    bat_top = bat['y_pos']
                    bat_bottom = bat['y_pos'] + 1

                    if (bat_left <= proj['x_pos'] <= bat_right and 
                        bat_top <= proj['y_pos'] <= bat_bottom):
                        # Hit bat - deal damage based on projectile power
                        dmg = int(proj.get('damage', 1))
                        bat['hp'] -= dmg
                        hit_bat = True

                        # Award XP equal to damage to projectile owner if present
                        owner = proj.get('owner', None)
                        if owner is not None:
                            award_xp(owner, dmg)

                        if bat['hp'] <= 0:
                            # Bat defeated: award bonus XP based on tier to owner
                            owner = proj.get('owner', None)
                            tier = int(bat.get('tier', 1) or 1)
                            bonus = variables.XP_BONUS_PER_TIER * tier
                            if owner is not None:
                                award_xp(owner, bonus)

                            # Bat defeated - award state.score and drop loot
                            add_score(bat.get('max_hp', 0))

                            # Find closest lane to bat center
                            bat_center_x = bat['x_pos'] + variables.BAT_CENTER_OFFSET
                            closest_lane = min(range(variables.NUM_LANES), key=lambda lane_idx: abs(variables.LANE_POSITIONS[lane_idx] - bat_center_x))

                            # Loot drop logic (4 tiers with new percentages)
                            tier = bat['tier']
                            prestige = compute_prestige()
                            base = variables.BAT_LOOT_BASE_WEIGHTS.get(tier, variables.BAT_LOOT_BASE_WEIGHTS.get(4))
                            adj_weights = adjust_rarity_weights(base, prestige)
                            rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]

                            loot_type = choose_loot_type(rarity)

                            state.loot_items.append({
                                'x_pos': variables.LANE_POSITIONS[closest_lane],
                                'y_pos': bat['y_pos'],
                                'type': loot_type,
                                'rarity': rarity,
                                'spawn_ts': time.time()
                            })

                            tier = bat.get('tier', None)
                            # notify achievements about bat destroy (with tier)
                            achievements.check_achievements_event('destroy_bat', tier=tier, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                            state.bats.remove(bat)
                        break
                if hit_bat:
                    state.red_projectiles.remove(proj)
                    removed_proj = True
                    break

                # Check collision with state.obstacles
                for obs in state.obstacles[:]:
                    if obs['lane'] == proj['lane'] and abs(proj['y_pos'] - obs['y_pos']) <= variables.NORMAL_BIRD_SPRITE_HEIGHT:
                        # Hit obstacle - deal damage based on projectile power
                        dmg = int(proj.get('damage', 1))
                        obs['hp'] -= dmg

                        # Award XP equal to damage to projectile owner if present
                        owner = proj.get('owner', None)
                        if owner is not None:
                            award_xp(owner, dmg)
                        if obs['hp'] <= 0:
                            state.obstacles.remove(obs)
                        # Projectile is consumed by hitting obstacle
                        state.red_projectiles.remove(proj)
                        removed_proj = True
                        break
                if removed_proj:
                    break
        
        # Update power-ups (decrease frame counters)
        # Active STEALTH tangible damage: while a stealth bird is tangible, apply 24 damage
        # to any bat/obstacle/loot in proximity so the power reliably has an effect.
        for i in range(variables.NUM_BALLS):
            if state.ball_colors[i] == STEALTH and i in state.stealth_timers and state.stealth_timers.get(i, 0) > 0 and not state.ball_lost[i]:
                bird_lane = state.random_lanes[i]
                bird_x = variables.LANE_POSITIONS[bird_lane]
                bird_y = state.ball_y[i]

                # Damage state.bats in proximity
                for bat in state.bats[:]:
                    if abs(bat.get('x_pos', 0) - bird_x) <= 6 and abs(bat.get('y_pos', 0) - bird_y) <= 2:
                        dmg = 24
                        bat['hp'] -= dmg
                        # award XP for damage from this bird
                        award_xp(i, dmg)
                        if bat.get('hp', 0) <= 0:
                            # bonus XP for kill
                            tier = int(bat.get('tier', 1) or 1)
                            award_xp(i, variables.XP_BONUS_PER_TIER * tier)
                            add_score(bat.get('max_hp', 0))
                            bat_center_x = bat.get('x_pos', 0) + variables.BAT_CENTER_OFFSET
                            closest_lane = min(range(variables.NUM_LANES), key=lambda lane_idx: abs(variables.LANE_POSITIONS[lane_idx] - bat_center_x))
                            tier = bat.get('tier', None)
                            prestige = compute_prestige()
                            # Use configurable base weights for bat loot by tier
                            base = variables.BAT_LOOT_BASE_WEIGHTS.get(int(tier) or 4, variables.BAT_LOOT_BASE_WEIGHTS.get(4))
                            adj_weights = adjust_rarity_weights(base, prestige)
                            rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
                            loot_type = choose_loot_type(rarity)
                            state.loot_items.append({
                                'x_pos': variables.LANE_POSITIONS[closest_lane],
                                'y_pos': bat.get('y_pos', 0),
                                'type': loot_type,
                                'rarity': rarity,
                                'spawn_ts': time.time()
                            })
                            achievements.check_achievements_event('destroy_bat', tier=tier, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                            state.bats.remove(bat)

                # Damage state.obstacles in same lane
                for obs in state.obstacles[:]:
                    if obs.get('lane') == bird_lane and abs(obs.get('y_pos', 0) - bird_y) <= 1:
                        dmg = 24
                        obs['hp'] -= dmg
                        award_xp(i, dmg)
                        if obs.get('hp', 0) <= 0:
                            tier = int(obs.get('tier', 1) or 1)
                            award_xp(i, variables.XP_BONUS_PER_TIER * tier)
                            add_score(obs.get('tier', 0) * variables.OBSTACLE_SCORE_MULTIPLIER)
                            state.obstacles.remove(obs)

                # Destroy loot items in proximity (tangible destroys loot)
                for loot in state.loot_items[:]:
                    if abs(bird_x - loot.get('x_pos', 0)) <= 2 and abs(bird_y - loot.get('y_pos', 0)) <= 2:
                        state.loot_items.remove(loot)
                        
        if state.powerups['wide_cursor_active']:
            state.powerups['wide_cursor_frames'] -= 1
            if state.powerups['wide_cursor_frames'] <= 0:
                state.powerups['wide_cursor_active'] = False
                state.powerups['wide_cursor_lanes'] = 1
        
        if state.powerups['bounce_boost_active']:
            state.powerups['bounce_boost_frames'] -= 1
            if state.powerups['bounce_boost_frames'] <= 0:
                state.powerups['bounce_boost_active'] = False
                state.powerups['bounce_boost_duration'] = 0
        
        if state.powerups['suction_active']:
            state.powerups['suction_frames'] -= 1
            if state.powerups['suction_frames'] <= 0:
                state.powerups['suction_active'] = False
                state.powerups['suction_boost_duration'] = 0

        # Tailwind expiry handling
        if state.powerups.get('tailwind_active'):
            state.powerups['tailwind_frames'] -= 1
            if state.powerups['tailwind_frames'] <= 0:
                state.powerups['tailwind_active'] = False
                state.powerups['tailwind_up_bonus'] = 0
                state.powerups['tailwind_down_penalty'] = 0

        # (slow-motion powerup removed; no expiry handling required)
        
        for i in range(variables.NUM_BALLS):
            # Decrement any just-fired protection timers
            if state.purple_just_fired_frames[i] > 0:
                state.purple_just_fired_frames[i] -= 1

            # If this bird is charging or under just-fired protection, keep it frozen
            # and skip any behaviors that could change its vy (GLITCH flips, duplicates, etc.)
            if state.purple_state[i] == 2 or (state.purple_just_fired_frames[i] > 0):
                # Skip any behavior that could flip direction while charging
                # or during immediate post-fire protection. Do NOT modify
                # state.ball_vy here so rendering keeps the original direction.
                continue
            # GLITCH birds pick a random speed each step
            if state.ball_colors[i] == GLITCH and not state.ball_lost[i]:
                # Random speed each step (configurable range)
                state.ball_speeds[i] = random.randint(int(variables.GLITCH_SPEED_MIN), int(variables.GLITCH_SPEED_MAX))
            current_speed = state.ball_speeds[i]

            # Apply speed boost if active (only when going up)
            if i in state.speed_boosts:
                if state.speed_boosts[i] > 0 and state.ball_vy[i] == -1:
                    # Positive = speed boost
                    current_speed += 1
                elif state.speed_boosts[i] < 0 and state.ball_vy[i] == 1:
                    # Negative = slow effect (yellow power)
                    current_speed = max(int(variables.SPEED_MIN), current_speed - 1)
            
            # Apply scared speed boost when going down
            if i in state.scared_birds and state.ball_vy[i] == 1:
                current_speed += 1

            # GLITCH: 1% chance to flip direction spontaneously each step
            if state.ball_colors[i] == GLITCH and not state.ball_lost[i]:
                if random.random() < float(variables.GLITCH_FLIP_CHANCE):
                    state.ball_vy[i] = -state.ball_vy[i]

            # GLITCH additional chaotic behaviors requested by user:
            # 1) 1% chance to swap lanes with another active bird
            # 2) 1% chance to nudge the player cursor +/-1 lane
            # 3) 1% chance to duplicate into another lane (resurrect or replace)
            if state.ball_colors[i] == GLITCH and not state.ball_lost[i]:
                # 1) swap lanes with another random active bird (1%)
                if random.random() < float(variables.GLITCH_SWAP_CHANCE):
                    others = [j for j in range(variables.NUM_BALLS) if j != i and not state.ball_lost[j]]
                    if others:
                        j = random.choice(others)
                        state.random_lanes[i], state.random_lanes[j] = state.random_lanes[j], state.random_lanes[i]
                        # update rendered columns
                        state.ball_cols[i] = variables.LANE_POSITIONS[state.random_lanes[i]]
                        state.ball_cols[j] = variables.LANE_POSITIONS[state.random_lanes[j]]

                # 2) nudge player cursor by -1 or +1 with 1% chance
                if random.random() < float(variables.GLITCH_NUDGE_CHANCE):
                    delta = random.choice([-1, 1])
                    # clamp between min and max lane index
                    state.player_lane = max(int(variables.MIN_LANE_INDEX), min(int(variables.MAX_LANE_INDEX), state.player_lane + delta))

                # 3) duplicate: 1% chance to spawn/replace a GLITCH in a random lane
                if random.random() < float(variables.GLITCH_DUPLICATE_CHANCE):
                    target_lane = random.randint(int(variables.MIN_LANE_INDEX), int(variables.MAX_LANE_INDEX))
                    target_idx = next((idx for idx in range(variables.NUM_BALLS) if state.random_lanes[idx] == target_lane), None)
                    if target_idx is not None:
                        # If the slot is empty (lost), resurrect it as GLITCH
                        if state.ball_lost[target_idx]:
                            state.ball_lost[target_idx] = False
                            state.ball_colors[target_idx] = GLITCH
                            state.ball_speeds[target_idx] = random.randint(int(variables.GLITCH_SPEED_MIN), int(variables.GLITCH_SPEED_MAX))
                            state.ball_y[target_idx] = variables.STARTING_LINE
                            state.ball_vy[target_idx] = -1
                            state.per_bird_xp[target_idx] = 0
                            state.transformed_s[target_idx] = False
                            state.ball_cols[target_idx] = variables.LANE_POSITIONS[target_lane]
                        else:
                            # Replace existing bird in that lane with GLITCH
                            state.ball_colors[target_idx] = GLITCH
                            state.ball_speeds[target_idx] = random.randint(int(variables.GLITCH_SPEED_MIN), int(variables.GLITCH_SPEED_MAX))
                            state.per_bird_xp[target_idx] = 0
                            state.ball_y[target_idx] = variables.STARTING_LINE
                            state.ball_vy[target_idx] = -1
                            state.transformed_s[target_idx] = False
                            state.ball_cols[target_idx] = variables.LANE_POSITIONS[target_lane]

            # Apply tailwind powerup effects (tiered):
            # - when rising (ball_vy== -1) apply up bonus (increase speed)
            # - when falling (ball_vy== 1) apply down penalty (decrease speed)
            # Clamp overall speed to [1, 6]
            if state.powerups.get('tailwind_active'):
                up_bonus = int(state.powerups.get('tailwind_up_bonus', 0))
                down_pen = int(state.powerups.get('tailwind_down_penalty', 0))
                if state.ball_vy[i] == -1 and up_bonus != 0:
                    current_speed = min(int(variables.SPEED_MAX), current_speed + up_bonus)
                elif state.ball_vy[i] == 1 and down_pen != 0:
                    current_speed = max(int(variables.SPEED_MIN), current_speed - down_pen)
            
            # Convert speed: higher number = faster, so invert for modulo
            move_interval = max(1, int(variables.SPEED_MAX - current_speed))

            # If this bird is actively charging (PURPLE state == 2) or was
            # just fired, keep it frozen: skip physics, collisions and loot
            # collection until charging finishes or protection expires.
            if state.purple_state[i] == 2 or (state.purple_just_fired_frames[i] > 0):
                continue

            if not state.ball_lost[i] and state.frame_count % move_interval == 0:
                # Calculate state.score for active bird based on speed and position
                position_multiplier = 0.5 + (variables.HEIGHT - state.ball_y[i]) / variables.HEIGHT
                # Gold bird scores a fixed 100 points instead of its speed
                try:
                    score_value = variables.GOLD_SCORE_VALUE if state.ball_colors[i] == variables.GOLD else state.ball_speeds[i]
                except Exception:
                    score_value = state.ball_speeds[i]
                # Credit the bird that generated this state.score with XP as well
                add_score(score_value * position_multiplier, by_bird=i)
                
                # Check collision with state.obstacles BEFORE moving (when moving up)
                if state.ball_vy[i] == -1:  # Only check collision when bird is moving up
                    bird_lane = state.random_lanes[i]
                    bird_lane_x = variables.LANE_POSITIONS[bird_lane]
                    next_y = state.ball_y[i] + state.ball_vy[i]  # Calculate next position
                    collided = False
                    broken_through = False

                    # Bird sprite height (default or DINOSAUR)
                    bird_height = int(variables.DINOSAUR_SPRITE_HEIGHT) if state.ball_colors[i] == variables.DINOSAUR else int(variables.NORMAL_BIRD_SPRITE_HEIGHT)

                    # Check collision with state.bats first - if bat enters bird's lane AT ALL, collision!
                    # Stealth birds (when not tangible) pass through state.bats
                    if not (state.ball_colors[i] == STEALTH and not (i in state.stealth_timers and state.stealth_timers.get(i, 0) > 0)):
                        for bat in state.bats[:]:
                            bat_left = bat['x_pos']
                            bat_right = bat['x_pos'] + variables.BAT_SPRITE_WIDTH
                            bat_top = bat['y_pos']
                            bat_bottom = bat['y_pos'] + 1

                            lane_left = bird_lane_x - variables.LANE_COLLISION_HALF_WIDTH
                            lane_right = bird_lane_x + variables.LANE_COLLISION_HALF_WIDTH
                            horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)
                            vertical_overlap = not (next_y + bird_height < bat_top or next_y > bat_bottom)

                            if horizontal_overlap and vertical_overlap:
                                # Orange bird: destroy bat instantly
                                if state.ball_colors[i] == ORANGE:
                                    bat['hp'] = 0
                                else:
                                    # DINOSAUR deals fixed damage
                                    if state.ball_colors[i] == DINOSAUR:
                                        damage = variables.DINOSAUR_DAMAGE
                                    # STEALTH tangible: fixed high damage
                                    elif state.ball_colors[i] == STEALTH and (i in state.stealth_timers and state.stealth_timers.get(i, 0) > 0):
                                        damage = variables.STEALTH_DAMAGE
                                    # GOLD bird deals fixed damage
                                    elif state.ball_colors[i] == GOLD:
                                        damage = variables.GOLD_DAMAGE
                                    # GLITCH deals random damage in configured range
                                    elif state.ball_colors[i] == GLITCH:
                                        damage = int(random.randint(int(variables.GLITCH_DAMAGE_MIN), int(variables.GLITCH_DAMAGE_MAX)))
                                    else:
                                        damage = current_speed
                                        if state.ball_colors[i] == BLUE and state.bird_power_used[i]:
                                            damage += 1
                                    bat['hp'] -= damage
                                    # Award XP equal to damage inflicted
                                    award_xp(i, damage)

                                # Effects on the bird (only when NOT stealth-tangible)
                                if not (state.ball_colors[i] == STEALTH and (i in state.stealth_timers and state.stealth_timers.get(i, 0) > 0)):
                                    bat_tier = bat['tier']
                                    if bat_tier == 1:
                                        state.scared_birds[i] = get_scared_frames(i, variables.SCARED_BASE_SECONDS)
                                    elif bat_tier == 2:
                                        state.scared_birds[i] = get_scared_frames(i, variables.SCARED_BASE_SECONDS)
                                    elif bat_tier == 3:
                                        state.scared_birds[i] = get_scared_frames(i, variables.SCARED_BASE_SECONDS)
                                        state.speed_boosts[i] = int(variables.SCARED_SPEED_BOOST_SECONDS / variables.base_sleep)
                                    else:
                                        state.scared_birds[i] = get_scared_frames(i, variables.SCARED_BASE_SECONDS)
                                        state.speed_boosts[i] = int(variables.SCARED_SPEED_BOOST_SECONDS / variables.base_sleep)

                                if bat['hp'] <= 0:
                                    # Bonus XP for destroying the bat
                                    tier = int(bat.get('tier', 1) or 1)
                                    award_xp(i, variables.XP_BONUS_PER_TIER * tier)
                                    add_score(bat['max_hp'])
                                    bat_center_x = bat['x_pos'] + variables.BAT_CENTER_OFFSET
                                    closest_lane = min(range(variables.NUM_LANES), key=lambda lane_idx: abs(variables.LANE_POSITIONS[lane_idx] - bat_center_x))
                                    tier = bat['tier']
                                    prestige = compute_prestige()
                                    # Use configured bat loot base weights when available
                                    base = variables.BAT_LOOT_BASE_WEIGHTS.get(int(tier) or 4, variables.BAT_LOOT_BASE_WEIGHTS.get(4))
                                    adj_weights = adjust_rarity_weights(base, prestige)
                                    rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
                                    loot_type = choose_loot_type(rarity)
                                    state.loot_items.append({
                                        'x_pos': variables.LANE_POSITIONS[closest_lane],
                                        'y_pos': bat['y_pos'],
                                        'type': loot_type,
                                        'rarity': rarity,
                                        'spawn_ts': time.time()
                                    })
                                    tier = bat.get('tier', None)
                                    if state.ball_colors[i] == ORANGE:
                                        achievements.check_achievements_event('destroy_bat_with_orange', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                                    achievements.check_achievements_event('destroy_bat', tier=tier, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                                    state.bats.remove(bat)
                                    broken_through = True
                                else:
                                    set_ball_vy(i, 1)
                                    state.ball_y[i] = bat_bottom + 1
                                    if state.ball_colors[i] == BLUE:
                                        reset_bird_power(i)
                                    collided = True
                                break

                    # Check collision with state.obstacles if not hit bat
                    if not collided and not broken_through:
                        if not (state.ball_colors[i] == STEALTH and not (i in state.stealth_timers and state.stealth_timers.get(i, 0) > 0)):
                            for obs in state.obstacles[:]:
                                if obs['lane'] == bird_lane and abs(next_y - obs['y_pos']) <= 1:
                                    if state.ball_colors[i] == ORANGE:
                                        obs['hp'] = 0
                                    else:
                                        if state.ball_colors[i] == DINOSAUR:
                                            damage = variables.DINOSAUR_DAMAGE
                                        elif state.ball_colors[i] == STEALTH and (i in state.stealth_timers and state.stealth_timers.get(i, 0) > 0):
                                            damage = variables.STEALTH_DAMAGE
                                        elif state.ball_colors[i] == GOLD:
                                            damage = variables.GOLD_DAMAGE
                                        elif state.ball_colors[i] == GLITCH:
                                            damage = int(random.randint(int(variables.GLITCH_DAMAGE_MIN), int(variables.GLITCH_DAMAGE_MAX)))
                                        else:
                                            damage = current_speed
                                            if state.ball_colors[i] == BLUE and state.bird_power_used[i]:
                                                damage += 1
                                        obs['hp'] -= damage
                                        # Award XP equal to damage to this bird
                                        award_xp(i, damage)

                                    if obs['hp'] <= 0:
                                        tier = int(obs.get('tier', 1) or 1)
                                        award_xp(i, variables.XP_BONUS_PER_TIER * tier)
                                        add_score(obs['tier'] * variables.OBSTACLE_SCORE_MULTIPLIER)
                                        state.obstacles.remove(obs)
                                        broken_through = True
                                    else:
                                        set_ball_vy(i, 1)
                                        if state.ball_colors[i] == BLUE:
                                            reset_bird_power(i)
                                        collided = True
                                    break

                    # Only move if no collision OR broke through
                    if not collided:
                        state.ball_y[i] += state.ball_vy[i]
                else:
                    # Moving down, just move
                    if state.ball_colors[i] == CLOCKWORK and state.ball_vy[i] == 1 and state.ball_y[i] + state.ball_vy[i] >= variables.STARTING_LINE:
                        c = state.clockwork_charge.get(i, None)
                        if c is None:
                            c = variables.CLOCKWORK_INITIAL_CHARGE
                            state.clockwork_charge[i] = variables.CLOCKWORK_INITIAL_CHARGE
                        if c > 0:
                            state.ball_y[i] = variables.STARTING_LINE
                            state.ball_vy[i] = -1
                            reset_bird_power(i)
                        else:
                            state.ball_y[i] += state.ball_vy[i]
                    else:
                        state.ball_y[i] += state.ball_vy[i]
                
                # Check for loot collection
                bird_lane = state.random_lanes[i]
                bird_lane_x = variables.LANE_POSITIONS[bird_lane]
                for loot in state.loot_items[:]:
                    # Stealth birds pass through loot unless their power is active (tangible)
                    if state.ball_colors[i] == STEALTH and not (i in state.stealth_timers and state.stealth_timers.get(i, 0) > 0):
                        continue
                    # Check if bird is near loot (within lane and vertically close)
                    if abs(bird_lane_x - loot['x_pos']) <= variables.LOOT_COLLECTION_DISTANCE and abs(state.ball_y[i] - loot['y_pos']) <= variables.LOOT_COLLECTION_DISTANCE:
                        # Collect loot
                        loot_type = loot['type']
                        # Notify achievements about collected loot
                        achievements.check_achievements_event('collect', loot=loot_type, frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)

                        # GLITCH interaction with loot: configurable ignore/promote chances
                        if state.ball_colors[i] == GLITCH:
                            r = random.random()
                            if r < float(variables.GLITCH_LOOT_IGNORE_CHANCE):
                                # ignore the loot entirely
                                continue
                            elif r < float(variables.GLITCH_LOOT_IGNORE_CHANCE) + float(variables.GLITCH_LOOT_PROMOTE_CHANCE):
                                # promote rarity one tier
                                rar = loot.get('rarity', 'common')
                                if rar == 'common':
                                    loot['rarity'] = 'uncommon'
                                elif rar == 'uncommon':
                                    loot['rarity'] = 'rare'
                                elif rar == 'rare':
                                    loot['rarity'] = 'epic'
                                # otherwise epic stays epic

                        # Cookie crumbs should NOT be collected by COOKIE birds themselves;
                        # if the nearest collector is the COOKIE that dropped it, skip collection.
                        if loot_type == 'cookie_crumb' and state.ball_colors[i] == COOKIE:
                            continue

                        state.loot_items.remove(loot)

                        # Apply loot effects
                        if loot_type == 'yellow_egg':
                            spawn_bird_from_egg(YELLOW, loot_type)
                        elif loot_type == 'cookie_egg':
                            spawn_bird_from_egg(COOKIE, loot_type)
                        elif loot_type == 'red_egg':
                            spawn_bird_from_egg(RED, loot_type)
                        elif loot_type == 'blue_egg':
                            spawn_bird_from_egg(BLUE, loot_type)
                        elif loot_type == 'white_egg':
                            spawn_bird_from_egg(WHITE, loot_type)
                        elif loot_type == 'clockwork_egg':
                            spawn_bird_from_egg(CLOCKWORK, loot_type)
                        elif loot_type == 'purple_egg':
                            spawn_bird_from_egg(PURPLE, loot_type)
                        elif loot_type == 'dinosaur_egg':
                            spawn_bird_from_egg(DINOSAUR, loot_type)
                        elif loot_type == 'glitch_egg':
                            spawn_bird_from_egg(GLITCH, loot_type)
                        elif loot_type == 'gold_egg':
                            spawn_bird_from_egg(GOLD, loot_type)
                        elif loot_type == 'patchwork_egg':
                            spawn_bird_from_egg(PATCHWORK, loot_type)
                        elif loot_type == 'stealth_egg':
                            spawn_bird_from_egg(STEALTH, loot_type)
                        elif loot_type == 'orange_egg':
                            for idx in range(variables.NUM_BALLS):
                                if state.ball_lost[idx]:
                                    state.ball_lost[idx] = False
                                    state.ball_colors[idx] = ORANGE
                                    cname = variables.COLOR_NAME_MAP.get(ORANGE, 'ORANGE')
                                    state.ball_speeds[idx] = int(variables.BALL_SPEEDS_DEFAULT.get(cname, variables.BALL_SPEEDS_DEFAULT.get('ORANGE', 5)))
                                    state.ball_y[idx] = variables.STARTING_LINE
                                    state.ball_vy[idx] = -1
                                    state.lives += 1  # Restore life
                                    state.transformed_s[idx] = False
                                    transform_bird_to_s(idx)
                                    break
                        # Cookie crumb pickup: grant contained XP to non-COOKIE birds only
                        elif loot_type == 'cookie_crumb':
                            # Only non-COOKIE birds can collect crumbs
                            if state.ball_colors[i] == COOKIE:
                                # Cookie birds ignore crumbs
                                pass
                            else:
                                xp_val = int(loot.get('xp', 0) or 0)
                                if xp_val > 0:
                                    award_xp(i, xp_val)
                        elif loot_type.startswith('wide_cursor'):
                            cfg = variables.POWERS_DEFAULT.get('wide_cursor', {})
                            state.powerups['wide_cursor_active'] = True
                            # determine which seconds to use based on suffix
                            if loot_type == 'wide_cursor':
                                sec = cfg.get('base_seconds', variables.WIDE_CURSOR_BASE_SECONDS)
                                lanes = cfg.get('lanes_base', variables.WIDE_CURSOR_LANES_BASE)
                            elif loot_type == 'wide_cursor+':
                                sec = cfg.get('plus_seconds', variables.WIDE_CURSOR_PLUS_SECONDS)
                                lanes = cfg.get('lanes_base', variables.WIDE_CURSOR_LANES_BASE)
                            elif loot_type == 'wide_cursor++':
                                sec = cfg.get('plusplus_seconds', variables.WIDE_CURSOR_PLUSPLUS_SECONDS)
                                lanes = cfg.get('lanes_max', variables.WIDE_CURSOR_LANES_MAX)
                            else:
                                sec = cfg.get('max_seconds', variables.WIDE_CURSOR_MAX_SECONDS)
                                lanes = cfg.get('lanes_max', variables.WIDE_CURSOR_LANES_MAX)
                            state.powerups['wide_cursor_frames'] = max(1, int(float(sec) / variables.base_sleep))
                            state.powerups['wide_cursor_lanes'] = int(lanes)
                            achievements.check_achievements_event('power_used', power='wide_cursor', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type.startswith('bounce_boost'):
                            cfg = variables.POWERS_DEFAULT.get('bounce_boost', {})
                            state.powerups['bounce_boost_active'] = True
                            if loot_type == 'bounce_boost':
                                sec = cfg.get('base_seconds', variables.BOUNCE_BOOST_BASE_SECONDS)
                                duration = cfg.get('duration_base', variables.BOUNCE_BOOST_DURATION_BASE)
                            elif loot_type == 'bounce_boost+':
                                sec = cfg.get('plus_seconds', variables.BOUNCE_BOOST_PLUS_SECONDS)
                                duration = cfg.get('duration_plus', variables.BOUNCE_BOOST_DURATION_PLUS)
                            elif loot_type == 'bounce_boost++':
                                sec = cfg.get('plusplus_seconds', variables.BOUNCE_BOOST_PLUSPLUS_SECONDS)
                                duration = cfg.get('duration_plusplus', variables.BOUNCE_BOOST_DURATION_PLUSPLUS)
                            else:
                                sec = cfg.get('max_seconds', variables.BOUNCE_BOOST_MAX_SECONDS)
                                duration = cfg.get('duration_max', variables.BOUNCE_BOOST_DURATION_MAX)
                            state.powerups['bounce_boost_frames'] = max(1, int(float(sec) / variables.base_sleep))
                            state.powerups['bounce_boost_duration'] = int(duration)
                            achievements.check_achievements_event('power_used', power='bounce_boost', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type.startswith('suction'):
                            cfg = variables.POWERS_DEFAULT.get('suction', {})
                            state.powerups['suction_active'] = True
                            if loot_type == 'suction':
                                sec = cfg.get('base_seconds', variables.SUCTION_BASE_SECONDS)
                                boost = cfg.get('boost_duration_base', variables.SUCTION_BOOST_DURATION_BASE)
                            elif loot_type == 'suction+':
                                sec = cfg.get('plus_seconds', variables.SUCTION_PLUS_SECONDS)
                                boost = cfg.get('boost_duration_plus', variables.SUCTION_BOOST_DURATION_PLUS)
                            elif loot_type == 'suction++':
                                sec = cfg.get('plusplus_seconds', variables.SUCTION_PLUSPLUS_SECONDS)
                                boost = cfg.get('boost_duration_plusplus', variables.SUCTION_BOOST_DURATION_PLUSPLUS)
                            else:
                                sec = cfg.get('max_seconds', variables.SUCTION_MAX_SECONDS)
                                boost = cfg.get('boost_duration_max', variables.SUCTION_BOOST_DURATION_MAX)
                            state.powerups['suction_frames'] = max(1, int(float(sec) / variables.base_sleep))
                            state.powerups['suction_boost_duration'] = int(boost)
                            achievements.check_achievements_event('power_used', power='suction', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type.startswith('tailwind'):
                            cfg = variables.POWERS_DEFAULT.get('tailwind', {})
                            state.powerups['tailwind_active'] = True
                            if loot_type == 'tailwind':
                                sec = cfg.get('base_seconds', variables.TAILWIND_BASE_SECONDS)
                                up = cfg.get('up_bonus_base', variables.TAILWIND_UP_BONUS_BASE)
                                down = cfg.get('down_penalty_base', variables.TAILWIND_DOWN_PENALTY_BASE)
                            elif loot_type == 'tailwind+':
                                sec = cfg.get('plus_seconds', variables.TAILWIND_PLUS_SECONDS)
                                up = cfg.get('up_bonus_plus', variables.TAILWIND_UP_BONUS_PLUS)
                                down = cfg.get('down_penalty_plus', variables.TAILWIND_DOWN_PENALTY_PLUS)
                            elif loot_type == 'tailwind++':
                                sec = cfg.get('plusplus_seconds', variables.TAILWIND_PLUSPLUS_SECONDS)
                                up = cfg.get('up_bonus_plusplus', variables.TAILWIND_UP_BONUS_PLUSPLUS)
                                down = cfg.get('down_penalty_plusplus', variables.TAILWIND_DOWN_PENALTY_PLUSPLUS)
                            else:
                                sec = cfg.get('max_seconds', variables.TAILWIND_MAX_SECONDS)
                                up = cfg.get('up_bonus_plusplus', variables.TAILWIND_UP_BONUS_PLUSPLUS)
                                down = cfg.get('down_penalty_max', variables.TAILWIND_DOWN_PENALTY_MAX)
                            state.powerups['tailwind_frames'] = max(1, int(float(sec) / variables.base_sleep))
                            state.powerups['tailwind_up_bonus'] = int(up)
                            state.powerups['tailwind_down_penalty'] = int(down)
                            achievements.check_achievements_event('power_used', power='tailwind', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type == 'shuffle':
                            # Shuffle 2 birds (basic)
                            perform_shuffle(variables.SHUFFLE_LEVEL_BASE)
                            achievements.check_achievements_event('power_used', power='shuffle', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type == 'shuffle+':
                            # Shuffle 4 birds
                            perform_shuffle(variables.SHUFFLE_LEVEL_PLUS)
                            achievements.check_achievements_event('power_used', power='shuffle', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type == 'shuffle++':
                            # Shuffle 6 birds
                            perform_shuffle(variables.SHUFFLE_LEVEL_PLUSPLUS)
                            achievements.check_achievements_event('power_used', power='shuffle', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type == 'shuffle_max':
                            # Shuffle many (attempt to compact all outer birds)
                            perform_shuffle(variables.SHUFFLE_LEVEL_MAX)
                            achievements.check_achievements_event('power_used', power='shuffle', frame_count=state.frame_count, notifications_list=state.notifications, firebase_client=firebase_client, background_call=background_call)
                
                # Bounce off ceiling
                if state.ball_y[i] <= 1:
                    if state.ball_colors[i] == ORANGE:
                        lane = state.random_lanes[i]
                        state.ball_lost[i] = False
                        state.ball_y[i] = variables.ORANGE_OUT_OF_PLAY_Y
                        set_ball_vy(i, 0)
                        reset_bird_power(i)
                        state.ball_speeds[i] = 0
                        # Transformed S-birds do not produce egg loot
                        if not state.transformed_s[i]:
                            state.loot_items.append({'x_pos': variables.LANE_POSITIONS[lane], 'y_pos': variables.STARTING_LINE, 'type': 'orange_egg', 'rarity': 'epic', 'spawn_ts': time.time()})
                        continue
                    state.ball_y[i] = 1
                    set_ball_vy(i, 1)
                    reset_bird_power(i)  # Reset power when starting to descend
                
                # Check if ball hits floor
                if state.ball_y[i] >= variables.HEIGHT - 1:
                    if state.ball_colors[i] == CLOCKWORK:
                        # CLOCKWORK behaviour: only auto-bounce if charge > 0
                        c = state.clockwork_charge.get(i, None)
                        if c is None:
                            c = variables.CLOCKWORK_INITIAL_CHARGE
                            state.clockwork_charge[i] = variables.CLOCKWORK_INITIAL_CHARGE
                        if c > 0:
                            state.ball_y[i] = variables.STARTING_LINE
                            set_ball_vy(i, -1)
                            reset_bird_power(i)
                        else:
                            # charge == 0: behave like other birds hitting the floor -> die
                            if not state.ball_lost[i]:
                                state.ball_lost[i] = True
                                state.ball_y[i] = variables.HEIGHT - 1
                                # Reset XP for this bird on death so a new spawn starts at 0
                                state.per_bird_xp[i] = 0
                                state.lives -= 1
                                # Check for game over
                                if state.lives <= 0:
                                    state.game_over = True
                    elif state.ball_colors[i] == ORANGE:
                        continue
                    elif not state.ball_lost[i]:  # Solo gli altri muoiono (incl. GLITCH special-case)
                        # GLITCH: 20% chance to survive and bounce instead of dying
                        if state.ball_colors[i] == GLITCH and random.random() < float(variables.GLITCH_SURVIVE_ON_FLOOR_CHANCE):
                            # Bounce instead of dying
                            state.ball_y[i] = variables.STARTING_LINE
                            set_ball_vy(i, -1)
                            reset_bird_power(i)
                            continue

                        state.ball_lost[i] = True
                        state.ball_y[i] = variables.HEIGHT - 1
                        # Reset XP for this bird on death so a new spawn starts at 0
                        state.per_bird_xp[i] = 0
                        state.lives -= 1
                        # Check for game over
                        if state.lives <= 0:
                            state.game_over = True
        
        # Check if game over
        if state.game_over:
            # Clean up terminal using cleanup function
            cleanup()
            
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
            print(f"{RED}{'=' * variables.GAME_OVER_SEPARATOR_WIDTH}{RESET}\r")
            print(f"{RED}                   GAME OVER                     {RESET}\r")
            print(f"{RED}{'=' * variables.GAME_OVER_SEPARATOR_WIDTH}{RESET}\r")
            print("\r")
            print(f"  Final Score:      {int(state.score)}\r")
            print(f"  Level Reached:    {state.level}\r")
            print("\r")
            # Calculate and display elapsed play time
            if game_start_time:
                elapsed = int(time.time() - game_start_time)
            else:
                elapsed = 0

            hours = elapsed // variables.GAME_OVER_TIME_DIVIDER
            minutes = (elapsed % variables.GAME_OVER_TIME_REMAINDER) // variables.GAME_OVER_MINUTES_DIVIDER
            seconds = elapsed % variables.GAME_OVER_MINUTES_DIVIDER
            if hours > 0:
                elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                elapsed_str = f"{minutes:02d}:{seconds:02d}"

            print(f"  Time Played:      {elapsed_str} ({elapsed} s)\r")
            print(f"{RED}{'=' * variables.GAME_OVER_SEPARATOR_WIDTH}{RESET}\r")
            print("\r")
            # Prompt for optional leaderboard name and submit state.score
            name = input("Enter name for leaderboard (leave blank to skip): ").strip()[:variables.LEADERBOARD_NAME_MAX_LENGTH]

            # Best-effort remote reporting
            if firebase_client:
                try:
                    if name:
                        # Include time played and version when submitting leaderboard entry
                        try:
                            # Compute average points per minute (avg_ppm).
                            try:
                                minutes = float(elapsed) / float(variables.GAME_OVER_MINUTES_DIVIDER) if elapsed > 0 else 0.0
                                if minutes > 0:
                                    avg_ppm = float(state.score) / minutes
                                else:
                                    avg_ppm = float(state.score)
                            except Exception:
                                avg_ppm = float(state.score)

                            background_call(firebase_client.send_score, name, int(state.score), elapsed, elapsed_str, variables.GAME_VERSION, avg_ppm)
                        except Exception:
                            # Fallback to original call if something goes wrong
                            try:
                                background_call(firebase_client.send_score, name, int(state.score))
                            except Exception:
                                pass
                    # Include time played in the state.game_over analytics event
                    try:
                        # Include version and avg_ppm in the state.game_over analytics event as well
                        try:
                            minutes = float(elapsed) / float(variables.GAME_OVER_MINUTES_DIVIDER) if elapsed > 0 else 0.0
                            if minutes > 0:
                                avg_ppm = float(state.score) / minutes
                            else:
                                avg_ppm = float(state.score)
                        except Exception:
                            avg_ppm = float(state.score)

                        background_call(firebase_client.log_event, 'game_over', {'score': int(state.score), 'level': state.level, 'time_played_seconds': elapsed, 'time_played': elapsed_str, 'version': variables.GAME_VERSION, 'avg_ppm': avg_ppm})
                    except Exception:
                        # Fallback: log without time info
                        background_call(firebase_client.log_event, 'game_over', {'score': int(state.score), 'level': state.level, 'version': variables.GAME_VERSION})
                    background_call(firebase_client.sync_achievements, achievements.achievements)
                except Exception:
                    pass

            print("Thanks for playing. Press Enter to exit.")
            input()
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

