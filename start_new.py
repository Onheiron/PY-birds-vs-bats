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

import constants
from bird_types import BirdType, get_default_speed
from functions import *
from render import *
import achievements
import state

try:
    import firebase_client
except Exception:
    firebase_client = None

try:
    setup()
    achievements.init_achievements()
    game_start_time = time.time()
    if firebase_client:
        try:
            firebase_client.init_from_env()
            background_call(firebase_client.sign_in_anonymous)
            background_call(firebase_client.log_event, 'session_start', {'client': 'terminal'})
            achievements.add_notification('Firebase: enabled', state.game.frame_count, state.ui.notifications)
        except Exception:
            achievements.add_notification('Firebase: disabled', state.game.frame_count, state.ui.notifications)

    while True:
        key = get_key()
        space_pressed_this_frame = (key == constants.controls.action)
        space_just_pressed = space_pressed_this_frame and not state.player.last_space_state
        state.player.last_space_state = space_pressed_this_frame
        if state.game.paused:
            if key and key not in ('P', 'p', 'QUIT'):
                key = None
                space_pressed_this_frame = False
                space_just_pressed = False

        if key:
            if key == constants.controls.action and space_just_pressed:
                if state.player.selected_lane is None:
                    state.player.selected_lane = state.player.lane
                elif state.player.selected_lane == state.player.lane:
                    state.player.selected_lane = None
                else:
                    swap_cost = 200 * state.game.level
                    if state.game.score >= swap_cost:
                        current_lane = state.player.lane
                        bird_in_selected = find_bird_in_lane(state.player.selected_lane)
                        bird_in_current = find_bird_in_lane(current_lane)
                        if bird_in_selected >= 0 and bird_in_current >= 0:
                            deduct_score(swap_cost)
                            state.game.swaps_used += 1
                            achievements.check_achievements_event('swap', swaps=state.game.swaps_used, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                            swap_bird_lanes(bird_in_selected, bird_in_current)
                        state.player.selected_lane = None
            elif key == constants.controls.pause or key == constants.controls.pause_alt:
                state.game.paused = not state.game.paused
                if state.game.paused:
                    achievements.add_notification('PAUSED', state.game.frame_count, state.ui.notifications)
                else:
                    achievements.add_notification('RESUMED', state.game.frame_count, state.ui.notifications)
            elif key == constants.controls.move_left:
                state.player.lane = max(0, state.player.lane - 1)
            elif key == constants.controls.move_right:
                state.player.lane = min(8, state.player.lane + 1)  # 9 lanes: 0-8
            elif key == constants.controls.toggle_xp or key == constants.controls.toggle_xp_alt:
                state.ui.show_xp_overlay = not state.ui.show_xp_overlay
                if state.ui.show_xp_overlay:
                    achievements.add_notification('XP overlay: ON', state.game.frame_count, state.ui.notifications)
                else:
                    achievements.add_notification('XP overlay: OFF', state.game.frame_count, state.ui.notifications)
            elif key == constants.controls.move_up:
                lanes_to_affect = get_affected_lanes()
                for lane in lanes_to_affect:
                    bird_in_lane = find_bird_in_lane(lane)
                    if bird_in_lane >= 0 and not state.birds.lost[bird_in_lane]:
                        if state.birds.colors[bird_in_lane] == ORANGE and state.birds.speeds[bird_in_lane] == 0:
                            if random.random() >= float(constants.orange.recover_chance):
                                continue
                            lane = state.birds.random_lanes[bird_in_lane]
                            state.birds.y[bird_in_lane] = constants.layout.starting_line
                            set_ball_vy(bird_in_lane, -1)
                            reset_bird_power(bird_in_lane)
                            state.birds.speeds[bird_in_lane] = 5
                            item = next((li for li in state.items.loot_items
                                         if li.get('type') == 'orange_egg' and li.get('x_pos') == constants.layout.lane_positions[lane]
                                         and li.get('y_pos') == constants.layout.starting_line and li.get('rarity') == 'epic'), None)
                            if item is not None:
                                state.items.loot_items.remove(item)   # rimuove la prima occorrenza dell'oggetto trovato
                        elif not can_bird_bounce(bird_in_lane):
                            continue  # Scared bird ignores bounce command (tranne purple)
                        elif state.birds.vy[bird_in_lane] == 1:  # Moving down - bounce it up
                            if state.birds.colors[bird_in_lane] == DINOSAUR:
                                cnt = state.special.dinosaur_up_presses.get(bird_in_lane, 0) + 1
                                state.special.dinosaur_up_presses[bird_in_lane] = cnt
                                chunk = int(constants.dinosaur.press_chunk)
                                if chunk > 0 and cnt % chunk == 0:
                                    target = int(constants.dinosaur.presses_to_bounce)
                                    if cnt >= target:
                                        set_ball_vy(bird_in_lane, -1)
                                        state.birds.speeds[bird_in_lane] = int(get_default_speed(BirdType.DINOSAUR))
                                        state.special.dinosaur_up_presses[bird_in_lane] = 0
                                        reset_bird_power(bird_in_lane)
                                    else:
                                        state.birds.speeds[bird_in_lane] = max(1, state.birds.speeds[bird_in_lane] - 1)
                                continue
                            if not try_glitch_bounce(bird_in_lane):
                                continue  # GLITCH ignored the bounce
                            bounce_bird(bird_in_lane, apply_boost=True)
                        elif state.birds.vy[bird_in_lane] == -1:  # Already moving up - activate special power
                            grade_label, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_in_lane])
                            allowed_uses = 2 if (grade_label and grade_label.startswith('A')) else 1
                            if not allow_consume_power(bird_in_lane, allowed_uses=allowed_uses):
                                pass
                            else:
                                bird_color = state.birds.colors[bird_in_lane]
                                p_name = get_color_name(bird_color)
                                bird_lane = state.birds.random_lanes[bird_in_lane]
                                achievements.check_achievements_event('power_used', power=p_name, lane=bird_lane, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)

                                if bird_color == YELLOW:
                                    affected_count = 0
                                    for adj_lane, adj_bird in find_adjacent_birds(bird_lane):
                                        if not state.birds.lost[adj_bird]:
                                            if state.birds.vy[adj_bird] == 1:
                                                if state.birds.colors[adj_bird] == YELLOW or state.birds.colors[adj_bird] == PATCHWORK:
                                                    if try_glitch_bounce(adj_bird):
                                                        reset_bird_power(adj_bird)  # Reset power for bounced yellow
                                                        affected_count += 1
                                                        achievements.append_recent_action('bounce', lane=adj_lane, color=state.birds.colors[adj_bird], frame_count=state.game.frame_count)
                                                        for cross_lane, bi in find_adjacent_birds(adj_lane):
                                                            if (not state.birds.lost[bi] and state.birds.colors[bi] == BLUE and 
                                                                bi in state.special.scared_birds and state.birds.vy[bi] == 1):
                                                                del state.special.scared_birds[bi]
                                                else:
                                                    state.special.speed_boosts[adj_bird] = -int(3.0 / constants.timing.base_sleep)  # 3 seconds of slow
                                                    affected_count += 1
                                                

                                elif bird_color == RED:
                                    damage_bonus = 0
                                    for adj_lane, idx in find_adjacent_birds(bird_lane):
                                        if not state.birds.lost[idx]:
                                            if (state.birds.colors[idx] == RED or state.birds.colors[idx] == PURPLE or 
                                                state.birds.colors[idx] == PATCHWORK) and state.birds.vy[idx] == -1:
                                                damage_bonus += 1
                                    state.special.red_projectiles.append({
                                        'x_pos': constants.layout.lane_positions[bird_lane],
                                        'y_pos': state.birds.y[bird_in_lane],
                                        'lane': bird_lane,
                                        'damage': 1 + damage_bonus,
                                        'powered': damage_bonus > 0,
                                        'owner': bird_in_lane,
                                        'speed': 1
                                    })

                                elif bird_color == PURPLE:
                                    if state.special.purple_state[bird_in_lane] == 0:
                                        state.special.purple_state[bird_in_lane] = 1
                                        state.special.purple_primed_frame[bird_in_lane] = state.game.frame_count
                                        state.special.purple_hold_counter[bird_in_lane] = 0
                                elif bird_color == COOKIE:
                                    crumb_xp = int(max(0, int(state.birds.per_bird_xp[bird_in_lane] * 0.75)))
                                    state.items.loot_items.append({
                                        'x_pos': constants.layout.lane_positions[bird_lane],
                                        'y_pos': state.birds.y[bird_in_lane],
                                        'type': 'cookie_crumb',
                                        'rarity': 'rare',
                                        'xp': crumb_xp,
                                        'spawn_ts': time.time()
                                    })
                                    state.special.cookie_crumbs_made[bird_in_lane] = state.special.cookie_crumbs_made.get(bird_in_lane, 0) + 1
                                    if state.special.cookie_crumbs_made.get(bird_in_lane, 0) >= 5:
                                        if not state.birds.lost[bird_in_lane]:
                                            state.birds.lost[bird_in_lane] = True
                                            state.birds.y[bird_in_lane] = constants.layout.height - 1
                                            state.birds.per_bird_xp[bird_in_lane] = 0
                                            state.game.lives -= 1
                                            if state.game.lives <= 0:
                                                state.game.game_over = True

                                elif bird_color == BLUE:
                                    boost_frames = int(3.0 / constants.timing.base_sleep)
                                    state.special.speed_boosts[bird_in_lane] = boost_frames
                                    if bird_in_lane not in state.special.speed_boosts:
                                        state.special.speed_boosts[bird_in_lane] = boost_frames

                                elif bird_color == WHITE:
                                    for adj_lane, adj_bird in find_adjacent_birds(bird_lane, offsets=[-2, -1, 1, 2]):
                                        if not state.birds.lost[adj_bird]:
                                            if state.birds.vy[adj_bird] == 1:
                                                if can_bird_bounce(adj_bird):
                                                    if try_glitch_bounce(adj_bird):
                                                        reset_bird_power(adj_bird)  # Reset their power
                                                        achievements.append_recent_action('bounce', lane=adj_lane, color=state.birds.colors[adj_bird], frame_count=state.game.frame_count)

                                            elif state.birds.vy[adj_bird] == -1:
                                                    adj_grade, _ = compute_grade_from_xp(state.birds.per_bird_xp[adj_bird])
                                                    adj_allowed = 2 if (adj_grade and adj_grade.startswith('A')) else 1

                                                    if not allow_consume_power(adj_bird, allowed_uses=adj_allowed):
                                                        pass
                                                    else:
                                                        adj_bird_color = state.birds.colors[adj_bird]
                                                        p_name = get_color_name(adj_bird_color)
                                                        achievements.check_achievements_event('power_used', power=p_name, lane=adj_lane, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                                                        adj_bird_lane = state.birds.random_lanes[adj_bird]
                                                        if adj_bird_color == YELLOW:
                                                            for y_lane, y_bird in find_adjacent_birds(adj_bird_lane):
                                                                if not state.birds.lost[y_bird] and state.birds.vy[y_bird] == 1:
                                                                    if can_bird_bounce(y_bird):
                                                                        if state.birds.colors[y_bird] == YELLOW:
                                                                            set_ball_vy(y_bird, -1)
                                                                            reset_bird_power(y_bird)
                                                                        else:
                                                                            state.special.speed_boosts[y_bird] = -int(3.0 / constants.timing.base_sleep)

                                                        elif adj_bird_color == RED:
                                                            damage_bonus = 0
                                                            for adj_lane2, idx2 in find_adjacent_birds(adj_bird_lane):
                                                                if not state.birds.lost[idx2]:
                                                                    if state.birds.colors[idx2] == RED and state.birds.vy[idx2] == -1:
                                                                        damage_bonus += 1

                                                            state.special.red_projectiles.append({
                                                                'x_pos': constants.layout.lane_positions[adj_bird_lane],
                                                                'y_pos': state.birds.y[adj_bird],
                                                                'lane': adj_bird_lane,
                                                                'damage': 1 + damage_bonus,
                                                                'powered': damage_bonus > 0,
                                                                'owner': adj_bird
                                                            })

                                                        elif adj_bird_color == BLUE:
                                                            boost_frames = int(constants.powers.blue_adjacent_boost_seconds / constants.timing.base_sleep)
                                                            state.special.speed_boosts[adj_bird] = boost_frames
                                elif bird_color == CLOCKWORK:
                                    cur = state.special.clockwork_charge.get(bird_in_lane, constants.clockwork.initial_charge)
                                    if cur is None:
                                        cur = constants.clockwork.initial_charge
                                    newc = min(int(constants.clockwork.max_charge), cur + 1)
                                    state.special.clockwork_charge[bird_in_lane] = newc
                                    if newc > 0:
                                        state.birds.speeds[bird_in_lane] = newc
                                elif bird_color == STEALTH:
                                    state.special.stealth_timers[bird_in_lane] = max(1, int(constants.stealth.tangible_seconds / constants.timing.base_sleep))
                                    state.special.stealth_prev_speeds[bird_in_lane] = state.birds.speeds[bird_in_lane]
                                    state.birds.speeds[bird_in_lane] = int(constants.stealth.speed_boost)
                                    achievements.append_recent_action('stealth', lane=bird_lane, color=STEALTH, frame_count=state.game.frame_count)
            elif key == constants.controls.move_down:
                if state.powerups.suction_active:
                    lanes_to_affect = get_affected_lanes()

                    for lane in lanes_to_affect:
                        bird_in_lane = find_bird_in_lane(lane)
                        if bird_in_lane >= 0 and not state.birds.lost[bird_in_lane]:
                            if state.birds.vy[bird_in_lane] == -1:  # Moving up - pull it down
                                set_ball_vy(bird_in_lane, 1)
                                if state.powerups.suction_boost_duration > 0 and bird_in_lane not in state.special.speed_boosts:
                                    boost_frames = int(state.powerups.suction_boost_duration / constants.timing.base_sleep)
                                    state.special.speed_boosts[bird_in_lane] = boost_frames
                                achievements.append_recent_action('suction', lane=state.birds.random_lanes[bird_in_lane], color=state.birds.colors[bird_in_lane], frame_count=state.game.frame_count)
            elif key == constants.controls.quit:
                break

        render_game()
        if state.game.paused:
            time.sleep(current_sleep)
            continue
        base_frame_sleep = constants.timing.base_sleep * (constants.timing.frame_sleep_level_multiplier ** state.game.level)
        current_sleep = max(constants.timing.min_sleep, base_frame_sleep)
        state.game.frame_count += 1
        state.enemies.obstacle_spawn_timer += 1
        state.enemies.bat_spawn_timer += 1
        decay_frames = max(1, int(float(constants.clockwork.decay_seconds) / constants.timing.base_sleep))
        if decay_frames > 0 and state.game.frame_count % decay_frames == 0:
            for i in range(constants.layout.num_balls):
                if state.birds.colors[i] == CLOCKWORK and not state.birds.lost[i]:
                    c = state.special.clockwork_charge.get(i, None)
                    if c is None:
                        c = constants.clockwork.initial_charge
                        state.special.clockwork_charge[i] = constants.clockwork.initial_charge
                    if c > 0:
                        state.special.clockwork_charge[i] = c - 1
                        newc = state.special.clockwork_charge[i]
                        if newc > 0:
                            state.birds.speeds[i] = newc
                        else:
                            state.birds.speeds[i] = 6
                            set_ball_vy(i, 1)
                            achievements.add_notification('Clockwork freefall!', state.game.frame_count, state.ui.notifications)
        active_idxs = [i for i in range(constants.layout.num_balls) if not state.birds.lost[i]]
        if active_idxs:
            top50_y = int(constants.layout.height * 0.5)
            top30_y = int(constants.layout.height * 0.3)
            all_top50 = all(state.birds.y[i] <= top50_y for i in active_idxs)
            all_top30 = all(state.birds.y[i] <= top30_y for i in active_idxs)

            if all_top50:
                achievements.top50_hold_frames += 1
            else:
                achievements.top50_hold_frames = 0

            if all_top30:
                achievements.top30_hold_frames += 1
            else:
                achievements.top30_hold_frames = 0
            achievements.check_achievements_event('area_hold', area='top50', frames=achievements.top50_hold_frames, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
            achievements.check_achievements_event('area_hold', area='top30', frames=achievements.top30_hold_frames, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
        originals_alive = all(not state.birds.lost[idx] for idx in state.birds.original_indices)
        if originals_alive:
            achievements.original_alive_frames += 1
        else:
            achievements.original_alive_frames = 0
        achievements.check_achievements_event('original_survive', frames=achievements.original_alive_frames, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
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
            count = sum(1 for i in range(constants.layout.num_balls) if not state.birds.lost[i] and state.birds.colors[i] == cval)
            achievements.check_achievements_event('color_count', color=cname, count=count, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
        active_birds = sum(1 for lost in state.birds.lost if not lost)
        current_entities = len(state.enemies.obstacles) + len(state.enemies.bats) + active_birds
        if current_entities < constants.limits.max_entities and state.enemies.spawn_queue:
            entity = state.enemies.spawn_queue.pop(0)
            if entity['type'] == 'bat':
                entity['data']['spawn_ts'] = time.time()
                state.enemies.bats.append(entity['data'])
            elif entity['type'] == 'obstacle':
                state.enemies.obstacles.append(entity['data'])
        if len(state.enemies.bats) < 2 and state.enemies.bat_spawn_timer > random.randint(120, 220):
            state.enemies.bat_spawn_timer = 0
            if state.game.level <= 3:
                target_y = random.randint(5, 8)
            elif state.game.level <= 6:
                target_y = random.randint(8, 10)
            else:
                target_y = random.randint(constants.bat_enemy.spawning.target_y_low_level.min, constants.bat_enemy.spawning.target_y_low_level.max)  # Max at half screen
            if state.game.level <= constants.bat_enemy.tiers.level_threshold_1:
                tier = random.choices([1, 2, 3, 4], weights=constants.bat_enemy.tiers.weights_level_0_2)[0]
            elif state.game.level <= constants.bat_enemy.tiers.level_threshold_2:
                tier = random.choices([1, 2, 3, 4], weights=constants.bat_enemy.tiers.weights_level_3_4)[0]
            elif state.game.level <= constants.bat_enemy.tiers.level_threshold_3:
                tier = random.choices([1, 2, 3, 4], weights=constants.bat_enemy.tiers.weights_level_5_7)[0]
            else:
                tier = random.choices([1, 2, 3, 4], weights=constants.bat_enemy.tiers.weights_level_8_plus)[0]
            if tier == 1:
                hp = constants.bat_enemy.tiers.hp_tier_1
            elif tier == 2:
                hp = constants.bat_enemy.tiers.hp_tier_2
            elif tier == 3:
                hp = constants.bat_enemy.tiers.hp_tier_3
            else:  # tier 4
                hp = constants.bat_enemy.tiers.hp_tier_4
            max_attempts = constants.bat_enemy.spawning.max_attempts
            spawn_x = None
            for attempt in range(max_attempts):
                candidate_x = random.randint(constants.bat_enemy.spawning.x_min, constants.layout.width - constants.bat_enemy.spawning.x_margin)  # Keep bat fully inside box
                overlaps = False
                for existing_bat in state.enemies.bats:
                    if abs(candidate_x - existing_bat['x_pos']) < constants.bat_enemy.spawning.min_separation:
                        overlaps = True
                        break
                for queued in state.enemies.spawn_queue:
                    if queued['type'] == 'bat':
                        if abs(candidate_x - queued['data']['x_pos']) < constants.bat_enemy.spawning.min_separation:
                            overlaps = True
                            break
                
                if not overlaps:
                    spawn_x = candidate_x
                    break
            if spawn_x is None:
                state.enemies.bat_spawn_timer = constants.bat_enemy.spawning.fail_retry_timer  # Wait a bit before trying again
            else:
                can_add = True
                if len(state.enemies.spawn_queue) >= constants.bat_enemy.spawning.consecutive_spawn_limit:
                    if state.enemies.spawn_queue[-1]['type'] == 'bat' and state.enemies.spawn_queue[-2]['type'] == 'bat':
                        can_add = False
                        state.enemies.bat_spawn_timer = constants.bat_enemy.spawning.consecutive_retry_timer  # Retry soon
                
                if can_add:
                    direction = random.choice([-1, 1])  # -1 = left, 1 = right
                    
                    state.enemies.spawn_queue.append({
                        'type': 'bat',
                        'data': {
                            'x_pos': spawn_x,
                            'y_pos': constants.bat_enemy.spawning.y_start,  # Start from top like state.enemies.obstacles
                            'target_y': target_y,  # Stop at this Y position
                            'tier': tier,
                            'hp': hp,
                            'max_hp': hp,
                            'direction': direction,
                            'wave_offset': random.randint(constants.bat_enemy.spawning.wave_offset.min, constants.bat_enemy.spawning.wave_offset.max)
                        }
                    })
        base_spawn_rate = max(constants.obstacle.spawning.base_spawn_rate.min, constants.obstacle.spawning.base_spawn_rate.base - (state.game.level * constants.obstacle.spawning.spawn_rate_level_multiplier))  # Much faster spawning
        spawn_variance = max(constants.obstacle.spawning.spawn_variance.min, constants.obstacle.spawning.spawn_variance.base - (state.game.level * constants.obstacle.spawning.spawn_variance_level_multiplier))
        
        if state.enemies.obstacle_spawn_timer > random.randint(base_spawn_rate - spawn_variance, base_spawn_rate + spawn_variance):
            state.enemies.obstacle_spawn_timer = 0
            active_lanes = [state.birds.random_lanes[i] for i in range(constants.layout.num_balls) if not state.birds.lost[i]]
            if active_lanes:
                available_lanes = []
                for lane_idx in active_lanes:
                    lane_x = constants.layout.lane_positions[lane_idx]
                    lane_left = lane_x - constants.collision.lane_half_width
                    lane_right = lane_x + constants.collision.lane_half_width
                    bat_in_lane = False
                    for bat in state.enemies.bats:
                        bat_left = bat['x_pos']
                        bat_right = bat['x_pos'] + constants.collision.bat_sprite_width
                        if not (bat_right < lane_left or bat_left > lane_right):
                            bat_in_lane = True
                            break
                    
                    if not bat_in_lane:
                        available_lanes.append(lane_idx)
                if not available_lanes:
                    state.enemies.obstacle_spawn_timer = max(5, base_spawn_rate // 2)
                else:
                    lanes_without_obstacles = []
                    for lane_idx in available_lanes:
                        has_obstacle = any(obs['lane'] == lane_idx for obs in state.enemies.obstacles)
                        if not has_obstacle:
                            lanes_without_obstacles.append(lane_idx)
                    if not lanes_without_obstacles:
                        state.enemies.obstacle_spawn_timer = max(constants.obstacle.spawning.retry_timer_min, base_spawn_rate // constants.obstacle.spawning.retry_timer_divisor)
                    else:
                        lane = random.choice(lanes_without_obstacles)
                        if state.game.level <= constants.obstacle.tiers.level_threshold_1:
                            tier = random.choices([1, 2, 3, 4], weights=constants.obstacle.tiers.weights_level_0_2)[0]
                        elif state.game.level <= constants.obstacle.tiers.level_threshold_2:
                            tier = random.choices([1, 2, 3, 4], weights=constants.obstacle.tiers.weights_level_3_4)[0]
                        elif state.game.level <= constants.obstacle.tiers.level_threshold_3:
                            tier = random.choices([1, 2, 3, 4], weights=constants.obstacle.tiers.weights_level_5_7)[0]
                        else:
                            tier = random.choices([1, 2, 3, 4], weights=constants.obstacle.tiers.weights_level_8_plus)[0]
                        if tier == 1:
                            hp = constants.obstacle.tiers.hp_tier_1
                        elif tier == 2:
                            hp = constants.obstacle.tiers.hp_tier_2
                        elif tier == 3:
                            hp = constants.obstacle.tiers.hp_tier_3
                        else:  # tier 4
                            hp = constants.obstacle.tiers.hp_tier_4
                        can_add = True
                        if len(state.enemies.spawn_queue) >= constants.obstacle.spawning.consecutive_spawn_limit:
                            if state.enemies.spawn_queue[-1]['type'] == 'obstacle' and state.enemies.spawn_queue[-2]['type'] == 'obstacle':
                                can_add = False
                                state.enemies.obstacle_spawn_timer = max(constants.obstacle.spawning.retry_timer_min, base_spawn_rate // constants.obstacle.spawning.retry_timer_divisor)  # Retry sooner
                        
                        if can_add:
                            state.enemies.spawn_queue.append({
                                'type': 'obstacle',
                                'data': {'lane': lane, 'y_pos': 1, 'tier': tier, 'hp': hp}
                            })
        for obs in state.enemies.obstacles[:]:
            if state.game.frame_count % (6 - 1) == 0:  # Speed 1: move every 5 frames
                obs['y_pos'] += 1
            if obs['y_pos'] >= constants.layout.starting_line - 1:
                state.enemies.obstacles.remove(obs)
            elif obs['y_pos'] >= constants.layout.height:
                state.enemies.obstacles.remove(obs)
        for bat in state.enemies.bats[:]:
            if state.game.frame_count % 3 == 0:  # Bats move every 3 frames
                next_x = bat['x_pos'] + bat['direction'] * 2
                can_move = True
                for other_bat in state.enemies.bats:
                    if other_bat is bat:
                        continue
                    other_left = other_bat['x_pos']
                    other_right = other_bat['x_pos'] + 8
                    next_left = next_x
                    next_right = next_x + 8
                    if not (next_right < other_left or next_left > other_right):
                        can_move = False
                        break
                if can_move:
                    for i in range(constants.layout.num_balls):
                        if not state.birds.lost[i]:
                            bird_lane_x = constants.layout.lane_positions[state.birds.random_lanes[i]]
                            bird_y = state.birds.y[i]
                            current_speed = state.birds.speeds[i]
                            if i in state.special.speed_boosts:
                                current_speed += 1
                            move_interval = max(1, int(constants.physics.speed_max - current_speed))
                            if state.game.frame_count % move_interval == 0:
                                next_bird_y = bird_y + state.birds.vy[i]
                            else:
                                next_bird_y = bird_y
                            bat_left = next_x
                            bat_right = next_x + 8
                            bat_top = bat['y_pos']
                            bat_bottom = bat['y_pos'] + 2
                            lane_left = bird_lane_x - 2
                            lane_right = bird_lane_x + 2
                            horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)
                            
                            if horizontal_overlap:
                                if abs(bird_y - bat['y_pos']) < 8 or abs(next_bird_y - bat['y_pos']) < 8:
                                    can_move = False
                                    break
                
                if can_move:
                    bat['x_pos'] = next_x
                    if bat['x_pos'] <= 0:
                        bat['x_pos'] = 0
                        bat['direction'] = 1
                    elif bat['x_pos'] >= constants.layout.width - 8:
                        bat['x_pos'] = constants.layout.width - 8
                        bat['direction'] = -1
                else:
                    bat['direction'] *= -1
            if state.game.frame_count % (6 - 1) == 0:  # Speed 1: move every 5 frames (same as state.enemies.obstacles)
                if bat['y_pos'] < bat['target_y']:
                    bat['y_pos'] += 1
        for bat in state.enemies.bats:
            bat_left = bat['x_pos']
            bat_right = bat['x_pos'] + 8  # Bats are 8 chars wide
            bat_top = bat['y_pos']
            bat_bottom = bat['y_pos'] + 1  # Bats are 2 lines tall
            
            for obs in state.enemies.obstacles[:]:
                obs_lane_x = constants.layout.lane_positions[obs['lane']]
                obs_left = obs_lane_x - 1  # Obstacles are 3 chars wide centered on lane
                obs_right = obs_lane_x + 1
                obs_y = obs['y_pos']
                horizontal_overlap = not (bat_right < obs_left or bat_left > obs_right)
                vertical_overlap = abs(bat_top - obs_y) <= 1 or abs(bat_bottom - obs_y) <= 1
                
                if horizontal_overlap and vertical_overlap:
                    state.enemies.obstacles.remove(obs)
        now_ts = time.time()
        for bat in state.enemies.bats[:]:
            if now_ts - float(bat.get('spawn_ts', now_ts)) > constants.despawn.bat_time:
                state.enemies.bats.remove(bat)
        for loot in state.items.loot_items[:]:
            if now_ts - float(loot.get('spawn_ts', now_ts)) > constants.despawn.loot_time:
                if loot.get('type') == 'orange_egg' and loot.get('y_pos') == constants.layout.starting_line:
                        lane_x = loot.get('x_pos')
                        lane = constants.layout.lane_positions.index(lane_x)
                        for bi in range(constants.layout.num_balls):
                            if state.birds.random_lanes[bi] == lane:
                                    if (state.birds.colors[bi] == constants.ORANGE and state.birds.y[bi] == constants.orange.out_of_play_y and state.birds.speeds[bi] == 0 and not state.birds.lost[bi]):
                                        state.birds.lost[bi] = True
                                        state.birds.y[bi] = constants.layout.height - 1
                                        state.game.lives -= 1
                                        if state.game.lives <= 0:
                                            state.game.game_over = True
                                    break
                state.items.loot_items.remove(loot)
        for bird_idx in list(state.special.speed_boosts.keys()):
            if state.special.speed_boosts[bird_idx] > 0:
                state.special.speed_boosts[bird_idx] -= 1
                if state.special.speed_boosts[bird_idx] <= 0:
                    del state.special.speed_boosts[bird_idx]
                    if 0 <= bird_idx < len(state.birds.colors) and state.birds.colors[bird_idx] == BLUE:
                        reset_bird_power(bird_idx)
            else:
                state.special.speed_boosts[bird_idx] += 1
                if state.special.speed_boosts[bird_idx] >= 0:
                    del state.special.speed_boosts[bird_idx]
        for bird_idx in list(state.special.scared_birds.keys()):
            state.special.scared_birds[bird_idx] -= 1
            if state.special.scared_birds[bird_idx] <= 0:
                del state.special.scared_birds[bird_idx]
        for bird_idx in list(state.special.stealth_timers.keys()):
            state.special.stealth_timers[bird_idx] -= 1
            if state.special.stealth_timers[bird_idx] <= 0:
                del state.special.stealth_timers[bird_idx]
                if bird_idx in state.special.stealth_prev_speeds:
                    prev = state.special.stealth_prev_speeds.pop(bird_idx)
                    state.birds.speeds[bird_idx] = prev
        birds_to_unfear = []
        for i in range(constants.layout.num_balls):
            if state.birds.colors[i] == BLUE and i in state.special.scared_birds and not state.birds.lost[i]:
                if state.birds.vy[i] == 1:  # Blue bird moving down
                    blue_lane = state.birds.random_lanes[i]
                    blue_y = state.birds.y[i]
                    for adj_offset in [-1, 1]:
                        adj_lane = blue_lane + adj_offset
                        if 0 <= adj_lane < 9:
                            for j in range(constants.layout.num_balls):
                                if j != i and not state.birds.lost[j] and state.birds.random_lanes[j] == adj_lane:
                                    if state.birds.colors[j] == YELLOW and state.birds.vy[j] == -1:  # Yellow moving up
                                        yellow_y = state.birds.y[j]
                                        if abs(blue_y - yellow_y) <= 2:
                                            birds_to_unfear.append(i)
                                            break
                        if i in birds_to_unfear:
                            break
        for bird_idx in birds_to_unfear:
            if bird_idx in state.special.scared_birds:
                del state.special.scared_birds[bird_idx]
        up_pressed_this_frame = (key == constants.controls.move_up)

        if up_pressed_this_frame:
            state.special.up_hold_counter = state.special.up_hold_counter + 1
            state.special.up_miss_counter = 0
        else:
            state.special.up_miss_counter = state.special.up_miss_counter + 1
        up_released = (state.special.up_hold_counter > 0 and state.special.up_miss_counter >= 2)
        if up_released:
            state.special.up_hold_counter = 0
            state.special.up_miss_counter = 0
        for b in range(constants.layout.num_balls):
            purple_bird_state = state.special.purple_state[b]
            if purple_bird_state == 1:
                held = up_pressed_this_frame
                if state.game.frame_count > state.special.purple_primed_frame[b] and state.special.purple_miss_count[b] < 2 and not state.birds.lost[b] and state.birds.vy[b] == -1:
                    state.special.purple_saved_vy[b] = state.birds.vy[b]
                    state.special.purple_state[b] = 2
                    state.special.purple_charge_started_frame[b] = state.game.frame_count
                else:
                    if not held:
                        state.special.purple_miss_count[b] += 1
                    else:
                        state.special.purple_miss_count[b] = 0

                    if state.special.purple_miss_count[b] >= 3:
                        if state.birds.power_uses[b] > 0:
                            state.birds.power_uses[b] = max(0, state.birds.power_uses[b] - 1)
                        state.birds.power_used[b] = False
                        state.special.purple_saved_vy[b] = None
                        state.special.purple_state[b] = 0
                        state.special.purple_primed_frame[b] = 0
                        state.special.purple_miss_count[b] = 0

            elif purple_bird_state == 2:
                start_frame = state.special.purple_charge_started_frame[b]
                elapsed_seconds = 0
                elapsed_seconds = int((state.game.frame_count - start_frame) * constants.timing.base_sleep)
                s = max(0, min(3, elapsed_seconds))
                if s >= 3:
                    fire_now = True
                else:
                    fire_now = bool(up_released or state.birds.lost[b])

                if fire_now:
                    if s >= 1:
                        dmg = int(pow(4, s))
                        state.special.red_projectiles.append({
                            'x_pos': constants.layout.lane_positions[state.birds.random_lanes[b]],
                            'y_pos': state.birds.y[b],
                            'lane': state.birds.random_lanes[b],
                            'damage': dmg,
                            'powered': dmg > 1,
                            'owner': b,
                            'speed': 4,
                            'color': PURPLE
                        })
                        state.special.purple_just_fired_frames[b] = max(3, int(0.2 / constants.timing.base_sleep) + 2)
                    else:
                        if state.birds.power_uses[b] > 0:
                            state.birds.power_uses[b] = max(0, state.birds.power_uses[b] - 1)
                        state.birds.power_used[b] = False
                    if state.special.purple_saved_vy[b] is not None:
                        state.birds.vy[b] = state.special.purple_saved_vy[b]

                    state.special.purple_saved_vy[b] = None
                    state.special.purple_state[b] = 0
                    state.special.purple_charge_started_frame[b] = 0
                    state.special.purple_primed_frame[b] = 0
        for proj in state.special.red_projectiles[:]:
            move_steps = int(max(1, proj.get('speed', 1)))
            removed_proj = False
            for _step in range(move_steps):
                proj['y_pos'] -= 1
                if proj['y_pos'] < 0:
                    try:
                        state.special.red_projectiles.remove(proj)
                    except ValueError:
                        pass
                    removed_proj = True
                    break
                hit_bat = False
                for bat in state.enemies.bats[:]:
                    bat_left = bat['x_pos']
                    bat_right = bat['x_pos'] + 8
                    bat_top = bat['y_pos']
                    bat_bottom = bat['y_pos'] + 1

                    if (bat_left <= proj['x_pos'] <= bat_right and 
                        bat_top <= proj['y_pos'] <= bat_bottom):
                        dmg = int(proj.get('damage', 1))
                        bat['hp'] -= dmg
                        hit_bat = True
                        owner = proj.get('owner', None)
                        if owner is not None:
                            award_xp(owner, dmg)

                        if bat['hp'] <= 0:
                            owner = proj.get('owner', None)
                            tier = int(bat.get('tier', 1) or 1)
                            bonus = constants.combat.xp_bonus_per_tier * tier
                            if owner is not None:
                                award_xp(owner, bonus)
                            add_score(bat.get('max_hp', 0))
                            bat_center_x = bat['x_pos'] + constants.combat.bat_center_offset
                            closest_lane = min(range(constants.layout.num_lanes), key=lambda lane_idx: abs(constants.layout.lane_positions[lane_idx] - bat_center_x))
                            tier = bat['tier']
                            prestige = compute_prestige()
                            base = constants.bat_enemy.loot_base_weights.get(tier, constants.bat_enemy.loot_base_weights.get(4))
                            adj_weights = adjust_rarity_weights(base, prestige)
                            rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]

                            loot_type = choose_loot_type(rarity)

                            state.items.loot_items.append({
                                'x_pos': constants.layout.lane_positions[closest_lane],
                                'y_pos': bat['y_pos'],
                                'type': loot_type,
                                'rarity': rarity,
                                'spawn_ts': time.time()
                            })

                            tier = bat.get('tier', None)
                            achievements.check_achievements_event('destroy_bat', tier=tier, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                            state.enemies.bats.remove(bat)
                        break
                if hit_bat:
                    state.special.red_projectiles.remove(proj)
                    removed_proj = True
                    break
                for obs in state.enemies.obstacles[:]:
                    if obs['lane'] == proj['lane'] and abs(proj['y_pos'] - obs['y_pos']) <= constants.rendering.normal_bird_sprite_height:
                        dmg = int(proj.get('damage', 1))
                        obs['hp'] -= dmg
                        owner = proj.get('owner', None)
                        if owner is not None:
                            award_xp(owner, dmg)
                        if obs['hp'] <= 0:
                            state.enemies.obstacles.remove(obs)
                        state.special.red_projectiles.remove(proj)
                        removed_proj = True
                        break
                if removed_proj:
                    break
        for i in range(constants.layout.num_balls):
            if state.birds.colors[i] == STEALTH and i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0 and not state.birds.lost[i]:
                bird_lane = state.birds.random_lanes[i]
                bird_x = constants.layout.lane_positions[bird_lane]
                bird_y = state.birds.y[i]
                for bat in state.enemies.bats[:]:
                    if abs(bat.get('x_pos', 0) - bird_x) <= 6 and abs(bat.get('y_pos', 0) - bird_y) <= 2:
                        dmg = 24
                        bat['hp'] -= dmg
                        award_xp(i, dmg)
                        if bat.get('hp', 0) <= 0:
                            tier = int(bat.get('tier', 1) or 1)
                            award_xp(i, constants.combat.xp_bonus_per_tier * tier)
                            add_score(bat.get('max_hp', 0))
                            bat_center_x = bat.get('x_pos', 0) + constants.combat.bat_center_offset
                            closest_lane = min(range(constants.layout.num_lanes), key=lambda lane_idx: abs(constants.layout.lane_positions[lane_idx] - bat_center_x))
                            tier = bat.get('tier', None)
                            prestige = compute_prestige()
                            base = constants.bat_enemy.loot_base_weights.get(int(tier) or 4, constants.bat_enemy.loot_base_weights.get(4))
                            adj_weights = adjust_rarity_weights(base, prestige)
                            rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
                            loot_type = choose_loot_type(rarity)
                            state.items.loot_items.append({
                                'x_pos': constants.layout.lane_positions[closest_lane],
                                'y_pos': bat.get('y_pos', 0),
                                'type': loot_type,
                                'rarity': rarity,
                                'spawn_ts': time.time()
                            })
                            achievements.check_achievements_event('destroy_bat', tier=tier, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                            state.enemies.bats.remove(bat)
                for obs in state.enemies.obstacles[:]:
                    if obs.get('lane') == bird_lane and abs(obs.get('y_pos', 0) - bird_y) <= 1:
                        dmg = 24
                        obs['hp'] -= dmg
                        award_xp(i, dmg)
                        if obs.get('hp', 0) <= 0:
                            tier = int(obs.get('tier', 1) or 1)
                            award_xp(i, constants.combat.xp_bonus_per_tier * tier)
                            add_score(obs.get('tier', 0) * constants.combat.obstacle_score_multiplier)
                            state.enemies.obstacles.remove(obs)
                for loot in state.items.loot_items[:]:
                    if abs(bird_x - loot.get('x_pos', 0)) <= 2 and abs(bird_y - loot.get('y_pos', 0)) <= 2:
                        state.items.loot_items.remove(loot)
                        
        if state.powerups.wide_cursor_active:
            state.powerups.wide_cursor_frames -= 1
            if state.powerups.wide_cursor_frames <= 0:
                state.powerups.wide_cursor_active = False
                state.powerups.wide_cursor_lanes = 1
        
        if state.powerups.bounce_boost_active:
            state.powerups.bounce_boost_frames -= 1
            if state.powerups.bounce_boost_frames <= 0:
                state.powerups.bounce_boost_active = False
                state.powerups.bounce_boost_duration = 0
        
        if state.powerups.suction_active:
            state.powerups.suction_frames -= 1
            if state.powerups.suction_frames <= 0:
                state.powerups.suction_active = False
                state.powerups.suction_boost_duration = 0
        if state.powerups.tailwind_active:
            state.powerups.tailwind_frames -= 1
            if state.powerups.tailwind_frames <= 0:
                state.powerups.tailwind_active = False
                state.powerups.tailwind_up_bonus = 0
                state.powerups.tailwind_down_penalty = 0

        for i in range(constants.layout.num_balls):
            if state.special.purple_just_fired_frames[i] > 0:
                state.special.purple_just_fired_frames[i] -= 1
            if state.special.purple_state[i] == 2 or (state.special.purple_just_fired_frames[i] > 0):
                continue
            if state.birds.colors[i] == GLITCH and not state.birds.lost[i]:
                state.birds.speeds[i] = random.randint(int(constants.glitch.speed.min), int(constants.glitch.speed.max))
            current_speed = state.birds.speeds[i]
            if i in state.special.speed_boosts:
                if state.special.speed_boosts[i] > 0 and state.birds.vy[i] == -1:
                    current_speed += 1
                elif state.special.speed_boosts[i] < 0 and state.birds.vy[i] == 1:
                    current_speed = max(int(constants.physics.speed_min), current_speed - 1)
            if i in state.special.scared_birds and state.birds.vy[i] == 1:
                current_speed += 1
            if state.birds.colors[i] == GLITCH and not state.birds.lost[i]:
                if random.random() < float(constants.glitch.flip_chance):
                    state.birds.vy[i] = -state.birds.vy[i]
            if state.birds.colors[i] == GLITCH and not state.birds.lost[i]:
                if random.random() < float(constants.glitch.swap_chance):
                    others = [j for j in range(constants.layout.num_balls) if j != i and not state.birds.lost[j]]
                    if others:
                        j = random.choice(others)
                        state.birds.random_lanes[i], state.birds.random_lanes[j] = state.birds.random_lanes[j], state.birds.random_lanes[i]
                        state.birds.cols[i] = constants.layout.lane_positions[state.birds.random_lanes[i]]
                        state.birds.cols[j] = constants.layout.lane_positions[state.birds.random_lanes[j]]
                if random.random() < float(constants.glitch.nudge_chance):
                    delta = random.choice([-1, 1])
                    state.player.lane = max(int(constants.layout.min_lane_index), min(int(constants.layout.max_lane_index), state.player.lane + delta))
                if random.random() < float(constants.glitch.duplicate_chance):
                    target_lane = random.randint(int(constants.layout.min_lane_index), int(constants.layout.max_lane_index))
                    target_idx = next((idx for idx in range(constants.layout.num_balls) if state.birds.random_lanes[idx] == target_lane), None)
                    if target_idx is not None:
                        if state.birds.lost[target_idx]:
                            state.birds.lost[target_idx] = False
                            state.birds.colors[target_idx] = GLITCH
                            state.birds.speeds[target_idx] = random.randint(int(constants.glitch.speed.min), int(constants.glitch.speed.max))
                            state.birds.y[target_idx] = constants.layout.starting_line
                            state.birds.vy[target_idx] = -1
                            state.birds.per_bird_xp[target_idx] = 0
                            state.birds.transformed[target_idx] = False
                            state.birds.cols[target_idx] = constants.layout.lane_positions[target_lane]
                        else:
                            state.birds.colors[target_idx] = GLITCH
                            state.birds.speeds[target_idx] = random.randint(int(constants.glitch.speed.min), int(constants.glitch.speed.max))
                            state.birds.per_bird_xp[target_idx] = 0
                            state.birds.y[target_idx] = constants.layout.starting_line
                            state.birds.vy[target_idx] = -1
                            state.birds.transformed[target_idx] = False
                            state.birds.cols[target_idx] = constants.layout.lane_positions[target_lane]
            if state.powerups.tailwind_active:
                up_bonus = int(getattr(state.powerups, 'tailwind_up_bonus', 0))
                down_pen = int(getattr(state.powerups, 'tailwind_down_penalty', 0))
                if state.birds.vy[i] == -1 and up_bonus != 0:
                    current_speed = min(int(constants.physics.speed_max), current_speed + up_bonus)
                elif state.birds.vy[i] == 1 and down_pen != 0:
                    current_speed = max(int(constants.physics.speed_min), current_speed - down_pen)
            move_interval = max(1, int(constants.physics.speed_max - current_speed))
            if state.special.purple_state[i] == 2 or (state.special.purple_just_fired_frames[i] > 0):
                continue

            if not state.birds.lost[i] and state.game.frame_count % move_interval == 0:
                position_multiplier = 0.5 + (constants.layout.height - state.birds.y[i]) / constants.layout.height
                try:
                    score_value = constants.gold.score_value if state.birds.colors[i] == constants.GOLD else state.birds.speeds[i]
                except Exception:
                    score_value = state.birds.speeds[i]
                add_score(score_value * position_multiplier, by_bird=i)
                if state.birds.vy[i] == -1:  # Only check collision when bird is moving up
                    bird_lane = state.birds.random_lanes[i]
                    bird_lane_x = constants.layout.lane_positions[bird_lane]
                    next_y = state.birds.y[i] + state.birds.vy[i]  # Calculate next position
                    collided = False
                    broken_through = False
                    bird_height = int(constants.rendering.dinosaur_sprite_height) if state.birds.colors[i] == constants.DINOSAUR else int(constants.rendering.normal_bird_sprite_height)
                    if not (state.birds.colors[i] == STEALTH and not (i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0)):
                        for bat in state.enemies.bats[:]:
                            bat_left = bat['x_pos']
                            bat_right = bat['x_pos'] + constants.collision.bat_sprite_width
                            bat_top = bat['y_pos']
                            bat_bottom = bat['y_pos'] + 1

                            lane_left = bird_lane_x - constants.collision.lane_half_width
                            lane_right = bird_lane_x + constants.collision.lane_half_width
                            horizontal_overlap = not (bat_right < lane_left or bat_left > lane_right)
                            vertical_overlap = not (next_y + bird_height < bat_top or next_y > bat_bottom)

                            if horizontal_overlap and vertical_overlap:
                                if state.birds.colors[i] == ORANGE:
                                    bat['hp'] = 0
                                else:
                                    if state.birds.colors[i] == DINOSAUR:
                                        damage = constants.dinosaur.damage
                                    elif state.birds.colors[i] == STEALTH and (i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0):
                                        damage = constants.stealth.damage
                                    elif state.birds.colors[i] == GOLD:
                                        damage = constants.gold.damage
                                    elif state.birds.colors[i] == GLITCH:
                                        damage = int(random.randint(int(constants.glitch.damage.min), int(constants.glitch.damage.max)))
                                    else:
                                        damage = current_speed
                                        if state.birds.colors[i] == BLUE and state.birds.power_used[i]:
                                            damage += 1
                                    bat['hp'] -= damage
                                    award_xp(i, damage)
                                if not (state.birds.colors[i] == STEALTH and (i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0)):
                                    bat_tier = bat['tier']
                                    if bat_tier == 1:
                                        state.special.scared_birds[i] = get_scared_frames(i, constants.bat_enemy.scared.base_seconds)
                                    elif bat_tier == 2:
                                        state.special.scared_birds[i] = get_scared_frames(i, constants.bat_enemy.scared.base_seconds)
                                    elif bat_tier == 3:
                                        state.special.scared_birds[i] = get_scared_frames(i, constants.bat_enemy.scared.base_seconds)
                                        state.special.speed_boosts[i] = int(constants.bat_enemy.scared.speed_boost_seconds / constants.timing.base_sleep)
                                    else:
                                        state.special.scared_birds[i] = get_scared_frames(i, constants.bat_enemy.scared.base_seconds)
                                        state.special.speed_boosts[i] = int(constants.bat_enemy.scared.speed_boost_seconds / constants.timing.base_sleep)

                                if bat['hp'] <= 0:
                                    tier = int(bat.get('tier', 1) or 1)
                                    award_xp(i, constants.combat.xp_bonus_per_tier * tier)
                                    add_score(bat['max_hp'])
                                    bat_center_x = bat['x_pos'] + constants.combat.bat_center_offset
                                    closest_lane = min(range(constants.layout.num_lanes), key=lambda lane_idx: abs(constants.layout.lane_positions[lane_idx] - bat_center_x))
                                    tier = bat['tier']
                                    prestige = compute_prestige()
                                    base = constants.bat_enemy.loot_base_weights.get(int(tier) or 4, constants.bat_enemy.loot_base_weights.get(4))
                                    adj_weights = adjust_rarity_weights(base, prestige)
                                    rarity = random.choices(['common', 'uncommon', 'rare', 'epic'], weights=adj_weights)[0]
                                    loot_type = choose_loot_type(rarity)
                                    state.items.loot_items.append({
                                        'x_pos': constants.layout.lane_positions[closest_lane],
                                        'y_pos': bat['y_pos'],
                                        'type': loot_type,
                                        'rarity': rarity,
                                        'spawn_ts': time.time()
                                    })
                                    tier = bat.get('tier', None)
                                    if state.birds.colors[i] == ORANGE:
                                        achievements.check_achievements_event('destroy_bat_with_orange', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                                    achievements.check_achievements_event('destroy_bat', tier=tier, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                                    state.enemies.bats.remove(bat)
                                    broken_through = True
                                else:
                                    set_ball_vy(i, 1)
                                    state.birds.y[i] = bat_bottom + 1
                                    if state.birds.colors[i] == BLUE:
                                        reset_bird_power(i)
                                    collided = True
                                break
                    if not collided and not broken_through:
                        if not (state.birds.colors[i] == STEALTH and not (i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0)):
                            for obs in state.enemies.obstacles[:]:
                                if obs['lane'] == bird_lane and abs(next_y - obs['y_pos']) <= 1:
                                    if state.birds.colors[i] == ORANGE:
                                        obs['hp'] = 0
                                    else:
                                        if state.birds.colors[i] == DINOSAUR:
                                            damage = constants.dinosaur.damage
                                        elif state.birds.colors[i] == STEALTH and (i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0):
                                            damage = constants.stealth.damage
                                        elif state.birds.colors[i] == GOLD:
                                            damage = constants.gold.damage
                                        elif state.birds.colors[i] == GLITCH:
                                            damage = int(random.randint(int(constants.glitch.damage.min), int(constants.glitch.damage.max)))
                                        else:
                                            damage = current_speed
                                            if state.birds.colors[i] == BLUE and state.birds.power_used[i]:
                                                damage += 1
                                        obs['hp'] -= damage
                                        award_xp(i, damage)

                                    if obs['hp'] <= 0:
                                        tier = int(obs.get('tier', 1) or 1)
                                        award_xp(i, constants.combat.xp_bonus_per_tier * tier)
                                        add_score(obs['tier'] * constants.combat.obstacle_score_multiplier)
                                        state.enemies.obstacles.remove(obs)
                                        broken_through = True
                                    else:
                                        set_ball_vy(i, 1)
                                        if state.birds.colors[i] == BLUE:
                                            reset_bird_power(i)
                                        collided = True
                                    break
                    if not collided:
                        state.birds.y[i] += state.birds.vy[i]
                else:
                    if state.birds.colors[i] == CLOCKWORK and state.birds.vy[i] == 1 and state.birds.y[i] + state.birds.vy[i] >= constants.layout.starting_line:
                        c = state.special.clockwork_charge.get(i, None)
                        if c is None:
                            c = constants.clockwork.initial_charge
                            state.special.clockwork_charge[i] = constants.clockwork.initial_charge
                        if c > 0:
                            state.birds.y[i] = constants.layout.starting_line
                            state.birds.vy[i] = -1
                            reset_bird_power(i)
                        else:
                            state.birds.y[i] += state.birds.vy[i]
                    else:
                        state.birds.y[i] += state.birds.vy[i]
                bird_lane = state.birds.random_lanes[i]
                bird_lane_x = constants.layout.lane_positions[bird_lane]
                for loot in state.items.loot_items[:]:
                    if state.birds.colors[i] == STEALTH and not (i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0):
                        continue
                    if abs(bird_lane_x - loot['x_pos']) <= constants.collision.loot_collection_distance and abs(state.birds.y[i] - loot['y_pos']) <= constants.collision.loot_collection_distance:
                        loot_type = loot['type']
                        achievements.check_achievements_event('collect', loot=loot_type, frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                        if state.birds.colors[i] == GLITCH:
                            r = random.random()
                            if r < float(constants.glitch.loot_ignore_chance):
                                continue
                            elif r < float(constants.glitch.loot_ignore_chance) + float(constants.glitch.loot_promote_chance):
                                rar = loot.get('rarity', 'common')
                                if rar == 'common':
                                    loot['rarity'] = 'uncommon'
                                elif rar == 'uncommon':
                                    loot['rarity'] = 'rare'
                                elif rar == 'rare':
                                    loot['rarity'] = 'epic'
                        if loot_type == 'cookie_crumb' and state.birds.colors[i] == COOKIE:
                            continue

                        state.items.loot_items.remove(loot)
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
                            for idx in range(constants.layout.num_balls):
                                if state.birds.lost[idx]:
                                    state.birds.lost[idx] = False
                                    state.birds.colors[idx] = ORANGE
                                    state.birds.speeds[idx] = int(get_default_speed(BirdType.ORANGE))
                                    state.birds.y[idx] = constants.layout.starting_line
                                    state.birds.vy[idx] = -1
                                    state.game.lives += 1  # Restore life
                                    state.birds.transformed[idx] = False
                                    transform_bird_to_s(idx)
                                    break
                        elif loot_type == 'cookie_crumb':
                            if state.birds.colors[i] == COOKIE:
                                pass
                            else:
                                xp_val = int(loot.get('xp', 0) or 0)
                                if xp_val > 0:
                                    award_xp(i, xp_val)
                        elif loot_type.startswith('wide_cursor'):
                            cfg = constants.powers.default.get('wide_cursor', {})
                            state.powerups.wide_cursor_active = True
                            if loot_type == 'wide_cursor':
                                sec = cfg.get('base_seconds', constants.wide_cursor.seconds.base)
                                lanes = cfg.get('lanes_base', constants.wide_cursor.lanes.base)
                            elif loot_type == 'wide_cursor+':
                                sec = cfg.get('plus_seconds', constants.wide_cursor.seconds.plus)
                                lanes = cfg.get('lanes_base', constants.wide_cursor.lanes.base)
                            elif loot_type == 'wide_cursor++':
                                sec = cfg.get('plusplus_seconds', constants.wide_cursor.seconds.plusplus)
                                lanes = cfg.get('lanes_max', constants.wide_cursor.lanes.max)
                            else:
                                sec = cfg.get('max_seconds', constants.wide_cursor.seconds.max)
                                lanes = cfg.get('lanes_max', constants.wide_cursor.lanes.max)
                            state.powerups.wide_cursor_frames = max(1, int(float(sec) / constants.timing.base_sleep))
                            state.powerups.wide_cursor_lanes = int(lanes)
                            achievements.check_achievements_event('power_used', power='wide_cursor', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type.startswith('bounce_boost'):
                            cfg = constants.powers.default.get('bounce_boost', {})
                            state.powerups.bounce_boost_active = True
                            if loot_type == 'bounce_boost':
                                sec = cfg.get('base_seconds', constants.bounce_boost.seconds.base)
                                duration = cfg.get('duration_base', constants.bounce_boost.duration.base)
                            elif loot_type == 'bounce_boost+':
                                sec = cfg.get('plus_seconds', constants.bounce_boost.seconds.plus)
                                duration = cfg.get('duration_plus', constants.bounce_boost.duration.plus)
                            elif loot_type == 'bounce_boost++':
                                sec = cfg.get('plusplus_seconds', constants.bounce_boost.seconds.plusplus)
                                duration = cfg.get('duration_plusplus', constants.bounce_boost.duration.plusPLUS)
                            else:
                                sec = cfg.get('max_seconds', constants.bounce_boost.seconds.max)
                                duration = cfg.get('duration_max', constants.bounce_boost.duration.max)
                            state.powerups.bounce_boost_frames = max(1, int(float(sec) / constants.timing.base_sleep))
                            state.powerups.bounce_boost_duration = int(duration)
                            achievements.check_achievements_event('power_used', power='bounce_boost', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type.startswith('suction'):
                            cfg = constants.powers.default.get('suction', {})
                            state.powerups.suction_active = True
                            if loot_type == 'suction':
                                sec = cfg.get('base_seconds', constants.suction.seconds.base)
                                boost = cfg.get('boost_duration_base', constants.suction.boost_duration.base)
                            elif loot_type == 'suction+':
                                sec = cfg.get('plus_seconds', constants.suction.seconds.plus)
                                boost = cfg.get('boost_duration_plus', constants.suction.boost_duration.plus)
                            elif loot_type == 'suction++':
                                sec = cfg.get('plusplus_seconds', constants.suction.seconds.plusplus)
                                boost = cfg.get('boost_duration_plusplus', constants.suction.boost_duration.plusPLUS)
                            else:
                                sec = cfg.get('max_seconds', constants.suction.seconds.max)
                                boost = cfg.get('boost_duration_max', constants.suction.boost_duration.max)
                            state.powerups.suction_frames = max(1, int(float(sec) / constants.timing.base_sleep))
                            state.powerups.suction_boost_duration = int(boost)
                            achievements.check_achievements_event('power_used', power='suction', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type.startswith('tailwind'):
                            cfg = constants.powers.default.get('tailwind', {})
                            state.powerups.tailwind_active = True
                            if loot_type == 'tailwind':
                                sec = cfg.get('base_seconds', constants.tailwind.seconds.base)
                                up = cfg.get('up_bonus_base', constants.tailwind.up_bonus.base)
                                down = cfg.get('down_penalty_base', constants.tailwind.down_penalty.base)
                            elif loot_type == 'tailwind+':
                                sec = cfg.get('plus_seconds', constants.tailwind.seconds.plus)
                                up = cfg.get('up_bonus_plus', constants.tailwind.up_bonus.plus)
                                down = cfg.get('down_penalty_plus', constants.tailwind.down_penalty.plus)
                            elif loot_type == 'tailwind++':
                                sec = cfg.get('plusplus_seconds', constants.tailwind.seconds.plusplus)
                                up = cfg.get('up_bonus_plusplus', constants.tailwind.up_bonus.plusPLUS)
                                down = cfg.get('down_penalty_plusplus', constants.tailwind.down_penalty.plusPLUS)
                            else:
                                sec = cfg.get('max_seconds', constants.tailwind.seconds.max)
                                up = cfg.get('up_bonus_plusplus', constants.tailwind.up_bonus.plusPLUS)
                                down = cfg.get('down_penalty_max', constants.tailwind.down_penalty.max)
                            state.powerups.tailwind_frames = max(1, int(float(sec) / constants.timing.base_sleep))
                            state.powerups.tailwind_up_bonus = int(up)
                            state.powerups.tailwind_down_penalty = int(down)
                            achievements.check_achievements_event('power_used', power='tailwind', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type == 'shuffle':
                            perform_shuffle(constants.shuffle.level.base)
                            achievements.check_achievements_event('power_used', power='shuffle', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type == 'shuffle+':
                            perform_shuffle(constants.shuffle.level.plus)
                            achievements.check_achievements_event('power_used', power='shuffle', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type == 'shuffle++':
                            perform_shuffle(constants.shuffle.level.plusPLUS)
                            achievements.check_achievements_event('power_used', power='shuffle', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                        elif loot_type == 'shuffle_max':
                            perform_shuffle(constants.shuffle.level.max)
                            achievements.check_achievements_event('power_used', power='shuffle', frame_count=state.game.frame_count, notifications_list=state.ui.notifications, firebase_client=firebase_client, background_call=background_call)
                if state.birds.y[i] <= 1:
                    if state.birds.colors[i] == ORANGE:
                        lane = state.birds.random_lanes[i]
                        state.birds.lost[i] = False
                        state.birds.y[i] = constants.orange.out_of_play_y
                        set_ball_vy(i, 0)
                        reset_bird_power(i)
                        state.birds.speeds[i] = 0
                        if not state.birds.transformed[i]:
                            state.items.loot_items.append({'x_pos': constants.layout.lane_positions[lane], 'y_pos': constants.layout.starting_line, 'type': 'orange_egg', 'rarity': 'epic', 'spawn_ts': time.time()})
                        continue
                    state.birds.y[i] = 1
                    set_ball_vy(i, 1)
                    reset_bird_power(i)  # Reset power when starting to descend
                if state.birds.y[i] >= constants.layout.height - 1:
                    if state.birds.colors[i] == CLOCKWORK:
                        c = state.special.clockwork_charge.get(i, None)
                        if c is None:
                            c = constants.clockwork.initial_charge
                            state.special.clockwork_charge[i] = constants.clockwork.initial_charge
                        if c > 0:
                            state.birds.y[i] = constants.layout.starting_line
                            set_ball_vy(i, -1)
                            reset_bird_power(i)
                        else:
                            if not state.birds.lost[i]:
                                state.birds.lost[i] = True
                                state.birds.y[i] = constants.layout.height - 1
                                state.birds.per_bird_xp[i] = 0
                                state.game.lives -= 1
                                if state.game.lives <= 0:
                                    state.game.game_over = True
                    elif state.birds.colors[i] == ORANGE:
                        continue
                    elif not state.birds.lost[i]:  # Solo gli altri muoiono (incl. GLITCH special-case)
                        if state.birds.colors[i] == GLITCH and random.random() < float(constants.glitch.survive_on_floor_chance):
                            state.birds.y[i] = constants.layout.starting_line
                            set_ball_vy(i, -1)
                            reset_bird_power(i)
                            continue

                        state.birds.lost[i] = True
                        state.birds.y[i] = constants.layout.height - 1
                        state.birds.per_bird_xp[i] = 0
                        state.game.lives -= 1
                        if state.game.lives <= 0:
                            state.game.game_over = True
        if state.game.game_over:
            cleanup()
            print("\033[2J\033[H\033[?25h")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print("\r")
            print(f"{RED}{'=' * constants.game_over.separator_width}{RESET}\r")
            print(f"{RED}                   GAME OVER                     {RESET}\r")
            print(f"{RED}{'=' * constants.game_over.separator_width}{RESET}\r")
            print("\r")
            print(f"  Final Score:      {int(state.game.score)}\r")
            print(f"  Level Reached:    {state.game.level}\r")
            print("\r")
            if game_start_time:
                elapsed = int(time.time() - game_start_time)
            else:
                elapsed = 0

            hours = elapsed // constants.game_over.time_divider
            minutes = (elapsed % constants.game_over.time_remainder) // constants.game_over.minutes_divider
            seconds = elapsed % constants.game_over.minutes_divider
            if hours > 0:
                elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                elapsed_str = f"{minutes:02d}:{seconds:02d}"

            print(f"  Time Played:      {elapsed_str} ({elapsed} s)\r")
            print(f"{RED}{'=' * constants.game_over.separator_width}{RESET}\r")
            print("\r")
            name = input("Enter name for leaderboard (leave blank to skip): ").strip()[:constants.game_over.leaderboard_name_max_length]
            if firebase_client:
                try:
                    if name:
                        try:
                            try:
                                minutes = float(elapsed) / float(constants.game_over.minutes_divider) if elapsed > 0 else 0.0
                                if minutes > 0:
                                    avg_ppm = float(state.game.score) / minutes
                                else:
                                    avg_ppm = float(state.game.score)
                            except Exception:
                                avg_ppm = float(state.game.score)

                            background_call(firebase_client.send_score, name, int(state.game.score), elapsed, elapsed_str, constants.game.version, avg_ppm)
                        except Exception:
                            try:
                                background_call(firebase_client.send_score, name, int(state.game.score))
                            except Exception:
                                pass
                    try:
                        try:
                            minutes = float(elapsed) / float(constants.game_over.minutes_divider) if elapsed > 0 else 0.0
                            if minutes > 0:
                                avg_ppm = float(state.game.score) / minutes
                            else:
                                avg_ppm = float(state.game.score)
                        except Exception:
                            avg_ppm = float(state.game.score)

                        background_call(firebase_client.log_event, 'game_over', {'score': int(state.game.score), 'level': state.game.level, 'time_played_seconds': elapsed, 'time_played': elapsed_str, 'version': constants.game.version, 'avg_ppm': avg_ppm})
                    except Exception:
                        background_call(firebase_client.log_event, 'game_over', {'score': int(state.game.score), 'level': state.game.level, 'version': constants.game.version})
                    background_call(firebase_client.sync_achievements, achievements.achievements)
                except Exception:
                    pass

            print("Thanks for playing. Press Enter to exit.")
            input()
            break
        handle_clockwork_auto_bounce()
        time.sleep(current_sleep)

except KeyboardInterrupt:
    pass
except Exception:
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

