#!/usr/bin/env python3
"""
Input handling for BVB game.
Processes keyboard input and modifies game state accordingly.
"""

import random
import time

from src.core import state
from src.core import constants
from src.services import achievements
from src.entities.sprites import *
from src.entities import bird_types

# Audio module (optional)
try:
    from src.services import audio
    AUDIO_AVAILABLE = audio.is_audio_available()
except ImportError:
    audio = None
    AUDIO_AVAILABLE = False


def play_sfx(name):
    """Play sound effect if audio is available and SFX is enabled."""
    if AUDIO_AVAILABLE and audio and state.settings.sfx_enabled:
        audio.play_sfx(name)


def _find_bird_in_lane(lane):
    """Return bird index for given lane, or -1 if not found."""
    if lane in state.birds.random_lanes:
        return state.birds.random_lanes.index(lane)
    return -1


def _find_all_birds_in_lane(lane):
    """Return list of all bird indices in given lane."""
    birds = []
    for i, bird_lane in enumerate(state.birds.random_lanes):
        if bird_lane == lane:
            birds.append(i)
    return birds


def _get_affected_lanes():
    """Return list of lanes affected by current cursor (considers wide cursor)."""
    if state.powerups.wide_cursor_active:
        lanes = []
        half_width = state.powerups.wide_cursor_lanes // 2
        for offset in range(-half_width, half_width + 1):
            lane = state.player.lane + offset
            if 0 <= lane < constants.layout.num_lanes:
                lanes.append(lane)
        return lanes
    return [state.player.lane]


def _set_ball_vy(idx, val):
    """Safely set vertical velocity for bird idx."""
    if 0 <= idx < constants.layout.num_balls:
        # Don't change vy for charging or just-fired purple birds
        if state.special.purple_state[idx] == 2:
            return
        if state.special.purple_just_fired_frames[idx] > 0:
            return
        state.birds.vy[idx] = val


def _reset_bird_power(idx):
    """Reset bird power state."""
    state.birds.power_used[idx] = False
    state.birds.power_uses[idx] = 0


def _allow_consume_power(idx, allowed_uses=1):
    """Return True and consume one use if bird may use its power."""
    if state.birds.power_uses[idx] < allowed_uses:
        state.birds.power_uses[idx] += 1
        state.birds.power_used[idx] = True
        return True
    return False


def _get_scared_frames(bird_idx, base_seconds=2.0):
    """Return number of frames for scared state."""
    from src.functions import compute_grade_from_xp
    label, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
    if not label.startswith('D') and not label.startswith('C'):
        base_seconds = max(1, base_seconds - 1.0)
    return max(1, int(float(base_seconds) / constants.timing.base_sleep))


def handle_pause():
    """Toggle pause state."""
    state.game.paused = not state.game.paused
    msg = 'PAUSED' if state.game.paused else 'RESUMED'
    _add_notification(msg)


def _add_notification(text, duration_frames=None, title=None):
    """Add a notification to display in right panel.

    Args:
        text: Main notification text
        duration_frames: How long to display (defaults to config value)
        title: Optional title for the card (e.g., "Achievement:", "Power-Up:")
    """
    if duration_frames is None:
        try:
            duration_seconds = constants.notifications.duration_seconds
        except AttributeError:
            duration_seconds = 3.0
        duration_frames = int(duration_seconds / constants.timing.base_sleep)

    expire_frame = state.game.frame_count + duration_frames

    # New notification format: dict with title, text, expire_frame
    notification = {
        'title': title or '',
        'text': text,
        'expire_frame': expire_frame
    }

    # Insert at beginning (top of stack)
    state.ui.notifications.insert(0, notification)

    # Limit stack size (remove from bottom)
    try:
        max_stack = constants.notifications.max_stack
    except AttributeError:
        max_stack = 3

    while len(state.ui.notifications) > max_stack:
        state.ui.notifications.pop()  # Remove oldest (bottom)


def handle_movement(direction):
    """Handle LEFT/RIGHT cursor movement."""
    if direction == 'LEFT':
        state.player.lane = max(0, state.player.lane - 1)
    elif direction == 'RIGHT':
        state.player.lane = min(constants.layout.num_lanes - 1, state.player.lane + 1)


def handle_swap():
    """Handle SPACE key for swap mode."""
    if state.player.selected_lane is None:
        # Enter swap mode
        state.player.selected_lane = state.player.lane
    elif state.player.selected_lane == state.player.lane:
        # Cancel swap mode
        state.player.selected_lane = None
    else:
        # Execute swap
        _execute_swap()


def _find_bird_by_home_lane(lane):
    """Find bird whose home_lane is the given lane."""
    for i, home_lane in enumerate(state.birds.home_lanes):
        if home_lane == lane:
            return i
    return -1


def _execute_swap():
    """Execute a bird swap between selected lane and current lane.

    Uses home_lanes to determine which birds to swap - this ensures correct
    behavior when birds are temporarily in different lanes due to portals.
    """
    from src.functions import compute_gear_from_momentum, calculate_gear_threshold, deduct_momentum

    gear = compute_gear_from_momentum(state.game.momentum)
    gear_momentum_delta = calculate_gear_threshold(gear + 1) - calculate_gear_threshold(gear)
    swap_cost = gear_momentum_delta * 0.2  # Swap costs 20% of gear momentum delta

    # Check if we have enough MOMENTUM for the swap
    if state.game.momentum < swap_cost:
        state.player.selected_lane = None
        return

    current_lane = state.player.lane
    selected_lane = state.player.selected_lane

    # Find birds by their HOME lane, not current physical lane
    bird_in_selected = _find_bird_by_home_lane(selected_lane)
    bird_in_current = _find_bird_by_home_lane(current_lane)

    if bird_in_selected < 0 or bird_in_current < 0:
        state.player.selected_lane = None
        return

    # Deduct momentum (not score - score never decreases)
    deduct_momentum(swap_cost)
    state.game.swaps_used += 1
    achievements.check_achievements_event('swap', state.game.frame_count, state.ui.notifications, swaps=state.game.swaps_used)

    # Handle orange eggs before swap
    for idx, other_idx in [(bird_in_selected, bird_in_current), (bird_in_current, bird_in_selected)]:
        if _is_orange_egg_state(idx):
            old_lane = state.birds.home_lanes[idx]
            new_lane = state.birds.home_lanes[other_idx]
            for loot in state.items.loot_items:
                if loot['type'] == 'orange_egg' and loot['x_pos'] == constants.layout.lane_positions[old_lane]:
                    loot['x_pos'] = constants.layout.lane_positions[new_lane]
                    break

    # Swap home_lanes
    state.birds.home_lanes[bird_in_selected], state.birds.home_lanes[bird_in_current] = \
        state.birds.home_lanes[bird_in_current], state.birds.home_lanes[bird_in_selected]

    # Swap physical lanes too
    state.birds.random_lanes[bird_in_selected], state.birds.random_lanes[bird_in_current] = \
        state.birds.random_lanes[bird_in_current], state.birds.random_lanes[bird_in_selected]

    # Update columns
    state.birds.cols[bird_in_selected] = constants.layout.lane_positions[state.birds.random_lanes[bird_in_selected]]
    state.birds.cols[bird_in_current] = constants.layout.lane_positions[state.birds.random_lanes[bird_in_current]]

    # Reset non-orange-egg birds to starting line (in their new home lane)
    for idx in [bird_in_selected, bird_in_current]:
        if not state.birds.lost[idx] and not _is_orange_egg_state(idx):
            # Reset to home lane and starting position
            state.birds.random_lanes[idx] = state.birds.home_lanes[idx]
            state.birds.cols[idx] = constants.layout.lane_positions[state.birds.home_lanes[idx]]
            state.birds.y[idx] = constants.layout.starting_line
            _set_ball_vy(idx, -1)

    state.player.selected_lane = None


def _is_orange_egg_state(bird_idx):
    """Check if bird is in orange egg dormant state."""
    return (state.birds.colors[bird_idx] == ORANGE and
            state.birds.speeds[bird_idx] == 0 and
            state.birds.y[bird_idx] == 999)


def handle_bounce():
    """Handle UP key for bouncing birds.

    Processes ALL birds in the affected lanes (multiple birds can be in same lane due to portals).
    """
    lanes = _get_affected_lanes()

    for lane in lanes:
        # Find ALL birds in this lane (not just one)
        birds_in_lane = _find_all_birds_in_lane(lane)

        for bird_idx in birds_in_lane:
            if state.birds.lost[bird_idx]:
                continue

            bird_color = state.birds.colors[bird_idx]

            # Handle orange egg recovery
            if bird_color == ORANGE and state.birds.speeds[bird_idx] == 0:
                if random.random() >= constants.orange.recover_chance:
                    continue
                _recover_orange_bird(bird_idx, lane)
                continue

            # Can't bounce scared birds (except purple)
            if bird_idx in state.special.scared_birds and bird_color != PURPLE:
                continue

            # Can't bounce stunned birds (from obstacle collision)
            if bird_idx in state.special.stunned_birds:
                continue

            # BLEEDING BIRDS: each UP press costs a life, when lives reach 0 bird dies
            if bird_idx in state.special.bleeding_birds:
                bleed_info = state.special.bleeding_birds[bird_idx]
                bleed_info['lives_lost'] = bleed_info.get('lives_lost', 0) + 1
                if bleed_info['lives_lost'] >= bleed_info.get('lives_needed', 3):
                    # Lives depleted - bird dies!
                    if not state.birds.lost[bird_idx]:
                        state.birds.lost[bird_idx] = True
                        state.birds.y[bird_idx] = constants.layout.height - 1
                        state.game.lives -= 1
                        del state.special.bleeding_birds[bird_idx]
                        if state.game.lives <= 0:
                            state.game.game_over = True
                continue  # Don't process normal bounce while bleeding

            # FROZEN BIRDS: button press attempts to thaw
            if bird_idx in state.special.frozen_birds:
                frozen_info = state.special.frozen_birds[bird_idx]
                frozen_info['thaw_attempts_done'] = frozen_info.get('thaw_attempts_done', 0) + 1
                if frozen_info['thaw_attempts_done'] >= frozen_info.get('thaw_attempts_needed', 3):
                    # Bird thawed!
                    del state.special.frozen_birds[bird_idx]
                    # Reset to normal state - bounce up
                    state.birds.vy[bird_idx] = -1
                    _reset_bird_power(bird_idx)
                continue  # Don't process normal bounce while frozen

            # POISONED BIRDS: button press decrements heal counter, bird is cured when counter reaches 0
            if bird_idx in state.special.poisoned_birds:
                poison_info = state.special.poisoned_birds[bird_idx]
                poison_info['cure_attempts_done'] = poison_info.get('cure_attempts_done', 0) + 1
                if poison_info['cure_attempts_done'] >= poison_info.get('cure_attempts_needed', 3):
                    # Heal counter reached 0 - bird is cured!
                    del state.special.poisoned_birds[bird_idx]
                # Continue to normal bounce processing (poisoned birds can still bounce)

            # Bird moving down - bounce it up
            if state.birds.vy[bird_idx] == 1:
                _bounce_bird_up(bird_idx)
            # Bird moving up - activate power
            elif state.birds.vy[bird_idx] == -1:
                _activate_bird_power(bird_idx)


def _recover_orange_bird(bird_idx, lane):
    """Recover an orange bird from egg state."""
    state.birds.y[bird_idx] = constants.layout.starting_line
    _set_ball_vy(bird_idx, -1)
    _reset_bird_power(bird_idx)
    state.birds.speeds[bird_idx] = 5

    # Remove the orange egg loot item
    for loot in state.items.loot_items[:]:
        if (loot.get('type') == 'orange_egg' and
            loot.get('x_pos') == constants.layout.lane_positions[lane] and
            loot.get('y_pos') == constants.layout.starting_line):
            state.items.loot_items.remove(loot)
            break


def _bounce_bird_up(bird_idx):
    """Bounce a bird upward."""
    bird_color = state.birds.colors[bird_idx]

    # DINOSAUR special handling
    if bird_color == DINOSAUR:
        _handle_dinosaur_bounce(bird_idx)
        return

    # GLITCH has chance to ignore bounce
    if bird_color == GLITCH:
        if random.random() < constants.glitch.bounce_ignore_chance:
            return

    _set_ball_vy(bird_idx, -1)
    _reset_bird_power(bird_idx)
    # play_sfx('bounce')  # Disabled - too frequent, clashes with music

    # CLOCKWORK charge restoration
    if bird_color == CLOCKWORK:
        charge = state.special.clockwork_charge.get(bird_idx)
        if charge is None:
            state.special.clockwork_charge[bird_idx] = constants.clockwork.initial_charge
        elif charge == 0:
            state.special.clockwork_charge[bird_idx] = 1
            state.birds.speeds[bird_idx] = 1

    # Apply bounce boost if active
    if state.powerups.bounce_boost_active and bird_idx not in state.special.speed_boosts:
        boost_frames = int(state.powerups.bounce_boost_duration / constants.timing.base_sleep)
        state.special.speed_boosts[bird_idx] = boost_frames

    # Record for combos
    achievements.append_recent_action('bounce', lane=state.birds.random_lanes[bird_idx],
                                     color=bird_color, frame_count=state.game.frame_count)


def _handle_dinosaur_bounce(bird_idx):
    """Handle dinosaur multi-press bounce."""
    cnt = state.special.dinosaur_up_presses.get(bird_idx, 0) + 1
    state.special.dinosaur_up_presses[bird_idx] = cnt

    chunk = constants.dinosaur.press_chunk
    if chunk > 0 and cnt % chunk == 0:
        if cnt >= constants.dinosaur.presses_to_bounce:
            _set_ball_vy(bird_idx, -1)
            state.birds.speeds[bird_idx] = bird_types.BIRD_TYPES.get('DINOSAUR', {}).get('speed', 4)
            state.special.dinosaur_up_presses[bird_idx] = 0
            _reset_bird_power(bird_idx)
        else:
            state.birds.speeds[bird_idx] = max(1, state.birds.speeds[bird_idx] - 1)


def _activate_bird_power(bird_idx):
    """Activate a bird's special power."""
    from src.functions import compute_grade_from_xp

    # POISONED BIRDS: power is blocked while poisoned (cure handled in main input handler)
    if bird_idx in state.special.poisoned_birds:
        return

    # Check if lane is silenced by spellcaster bat
    bird_lane = state.birds.random_lanes[bird_idx]
    if bird_lane in state.spells.silenced_lanes:
        # Power blocked by silence spell
        return

    # Check allowed uses
    label, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
    allowed_uses = 2 if (label and label.startswith('A')) else 1

    if not _allow_consume_power(bird_idx, allowed_uses):
        return

    bird_color = state.birds.colors[bird_idx]

    # Notify achievements
    color_name = _get_color_name(bird_color)
    achievements.check_achievements_event('power_used', state.game.frame_count, state.ui.notifications, power=color_name, lane=bird_lane)

    # Execute power based on color
    if bird_color == YELLOW:
        _power_yellow(bird_idx, bird_lane)
    elif bird_color == RED:
        _power_red(bird_idx, bird_lane)
    elif bird_color == PURPLE:
        _power_purple(bird_idx)
    elif bird_color == COOKIE:
        _power_cookie(bird_idx, bird_lane)
    elif bird_color == BLUE:
        _power_blue(bird_idx)
    elif bird_color == WHITE:
        _power_white(bird_idx, bird_lane)
    elif bird_color == CLOCKWORK:
        _power_clockwork(bird_idx)
    elif bird_color == STEALTH:
        _power_stealth(bird_idx, bird_lane)


def _get_color_name(bird_color):
    """Map bird color to simple name string."""
    color_map = {
        YELLOW: 'yellow', RED: 'red', BLUE: 'blue', WHITE: 'white',
        PURPLE: 'purple', ORANGE: 'orange', STEALTH: 'stealth',
        CLOCKWORK: 'clockwork', GOLD: 'gold', PATCHWORK: 'patchwork',
        COOKIE: 'cookie', DINOSAUR: 'dinosaur', GLITCH: 'glitch'
    }
    return color_map.get(bird_color, 'unknown')


def _power_yellow(bird_idx, bird_lane):
    """Yellow power: bounce adjacent yellows, slow others."""
    for adj_offset in [-1, 1]:
        adj_lane = bird_lane + adj_offset
        if not (0 <= adj_lane < constants.layout.num_lanes):
            continue

        adj_bird = _find_bird_in_lane(adj_lane)
        if adj_bird < 0 or state.birds.lost[adj_bird]:
            continue
        if state.birds.vy[adj_bird] != 1:  # Must be falling
            continue

        adj_color = state.birds.colors[adj_bird]
        if adj_color == YELLOW or adj_color == PATCHWORK:
            # Bounce adjacent yellow/patchwork
            if adj_color == GLITCH and random.random() < constants.glitch.bounce_ignore_chance:
                continue
            _set_ball_vy(adj_bird, -1)
            _reset_bird_power(adj_bird)
            achievements.append_recent_action('bounce', lane=adj_lane,
                                             color=adj_color, frame_count=state.game.frame_count)
            # Cure scared blue birds nearby
            _cure_nearby_scared_blues(adj_lane)
        else:
            # Slow non-yellow bird
            state.special.speed_boosts[adj_bird] = -int(3.0 / constants.timing.base_sleep)


def _cure_nearby_scared_blues(lane):
    """Cure scared blue birds in adjacent lanes."""
    for cross_offset in [-1, 1]:
        cross_lane = lane + cross_offset
        if not (0 <= cross_lane < constants.layout.num_lanes):
            continue
        for bi in range(constants.layout.num_balls):
            if (state.birds.random_lanes[bi] == cross_lane and
                not state.birds.lost[bi] and
                state.birds.colors[bi] == BLUE and
                bi in state.special.scared_birds and
                state.birds.vy[bi] == 1):
                del state.special.scared_birds[bi]


def _power_red(bird_idx, bird_lane):
    """Red power: launch projectile with damage bonus from adjacent reds."""
    damage_bonus = 0
    for adj_offset in [-1, 1]:
        adj_lane = bird_lane + adj_offset
        if not (0 <= adj_lane < constants.layout.num_lanes):
            continue
        for idx in range(constants.layout.num_balls):
            if state.birds.random_lanes[idx] == adj_lane and not state.birds.lost[idx]:
                adj_color = state.birds.colors[idx]
                if adj_color in (RED, PURPLE, PATCHWORK) and state.birds.vy[idx] == -1:
                    damage_bonus += 1
                break

    state.special.red_projectiles.append({
        'x_pos': constants.layout.lane_positions[bird_lane],
        'y_pos': state.birds.y[bird_idx],
        'lane': bird_lane,
        'damage': 1 + damage_bonus,
        'powered': damage_bonus > 0,
        'owner': bird_idx,
        'speed': 1,
        'color': RED
    })


def _power_purple(bird_idx):
    """Purple power: begin charging."""
    if state.special.purple_state[bird_idx] == 0:
        state.special.purple_state[bird_idx] = 1
        state.special.purple_primed_frame[bird_idx] = state.game.frame_count
        state.special.purple_hold_counter[bird_idx] = 0


def _power_cookie(bird_idx, bird_lane):
    """Cookie power: drop a cookie crumb with XP."""
    crumb_xp = int(max(0, int(state.birds.per_bird_xp[bird_idx] * 0.75)))

    state.items.loot_items.append({
        'x_pos': constants.layout.lane_positions[bird_lane],
        'y_pos': state.birds.y[bird_idx],
        'type': 'cookie_crumb',
        'rarity': 'rare',
        'xp': crumb_xp,
        'spawn_ts': time.time()
    })

    # Track crumbs made
    state.special.cookie_crumbs_made[bird_idx] = state.special.cookie_crumbs_made.get(bird_idx, 0) + 1

    # After 5 crumbs, cookie bird dies
    if state.special.cookie_crumbs_made.get(bird_idx, 0) >= 5:
        if not state.birds.lost[bird_idx]:
            state.birds.lost[bird_idx] = True
            state.birds.y[bird_idx] = constants.layout.height - 1
            state.birds.per_bird_xp[bird_idx] = 0
            state.game.lives -= 1
            if state.game.lives <= 0:
                state.game.game_over = True


def _power_blue(bird_idx):
    """Blue power: speed boost."""
    boost_frames = int(3.0 / constants.timing.base_sleep)
    state.special.speed_boosts[bird_idx] = boost_frames


def _power_white(bird_idx, bird_lane):
    """White power: affect 4 adjacent lanes."""
    from src.functions import compute_grade_from_xp

    for adj_offset in [-2, -1, 1, 2]:
        adj_lane = bird_lane + adj_offset
        if not (0 <= adj_lane < constants.layout.num_lanes):
            continue

        adj_bird = _find_bird_in_lane(adj_lane)
        if adj_bird < 0 or state.birds.lost[adj_bird]:
            continue

        adj_color = state.birds.colors[adj_bird]

        if state.birds.vy[adj_bird] == 1:  # Falling - bounce it
            if adj_bird in state.special.scared_birds and adj_color != PURPLE:
                continue
            if adj_bird in state.special.stunned_birds:
                continue
            if adj_color == GLITCH and random.random() < constants.glitch.bounce_ignore_chance:
                continue
            _set_ball_vy(adj_bird, -1)
            _reset_bird_power(adj_bird)
            achievements.append_recent_action('bounce', lane=adj_lane,
                                             color=adj_color, frame_count=state.game.frame_count)
        elif state.birds.vy[adj_bird] == -1:  # Rising - activate power
            label, _ = compute_grade_from_xp(state.birds.per_bird_xp[adj_bird])
            adj_allowed = 2 if (label and label.startswith('A')) else 1
            if _allow_consume_power(adj_bird, adj_allowed):
                _activate_adjacent_power(adj_bird, adj_lane)


def _activate_adjacent_power(adj_bird, adj_lane):
    """Activate an adjacent bird's power (triggered by white bird)."""
    adj_color = state.birds.colors[adj_bird]

    if adj_color == YELLOW:
        _power_yellow(adj_bird, adj_lane)
    elif adj_color == RED:
        _power_red(adj_bird, adj_lane)
    elif adj_color == BLUE:
        _power_blue(adj_bird)


def _power_clockwork(bird_idx):
    """Clockwork power: increase charge."""
    cur = state.special.clockwork_charge.get(bird_idx, constants.clockwork.initial_charge)
    if cur is None:
        cur = constants.clockwork.initial_charge
    newc = min(constants.clockwork.max_charge, cur + 1)
    state.special.clockwork_charge[bird_idx] = newc
    if newc > 0:
        state.birds.speeds[bird_idx] = newc


def _power_stealth(bird_idx, bird_lane):
    """Stealth power: become tangible with speed boost."""
    state.special.stealth_timers[bird_idx] = max(1, int(constants.stealth.tangible_seconds / constants.timing.base_sleep))
    state.special.stealth_prev_speeds[bird_idx] = state.birds.speeds[bird_idx]
    state.birds.speeds[bird_idx] = constants.stealth.speed_boost
    achievements.append_recent_action('stealth', lane=bird_lane, color=STEALTH, frame_count=state.game.frame_count)


def handle_suction():
    """Handle DOWN key for suction power."""
    if not state.powerups.suction_active:
        return

    lanes = _get_affected_lanes()

    for lane in lanes:
        bird_idx = _find_bird_in_lane(lane)
        if bird_idx < 0 or state.birds.lost[bird_idx]:
            continue

        if state.birds.vy[bird_idx] == -1:  # Moving up - pull it down
            _set_ball_vy(bird_idx, 1)

            if state.powerups.suction_boost_duration > 0 and bird_idx not in state.special.speed_boosts:
                boost_frames = int(state.powerups.suction_boost_duration / constants.timing.base_sleep)
                state.special.speed_boosts[bird_idx] = boost_frames

            achievements.append_recent_action('suction', lane=lane,
                                             color=state.birds.colors[bird_idx],
                                             frame_count=state.game.frame_count)


def handle_xp_toggle():
    """Toggle XP overlay display."""
    state.ui.show_xp_overlay = not state.ui.show_xp_overlay
    msg = 'XP overlay: ON' if state.ui.show_xp_overlay else 'XP overlay: OFF'
    _add_notification(msg)


def handle_audio_toggle():
    """Toggle audio on/off (mute/unmute)."""
    if not AUDIO_AVAILABLE or not audio:
        _add_notification('Audio not available')
        return

    # Toggle audio state
    current = getattr(audio, '_audio_enabled', True)
    new_state = not current
    audio.set_audio_enabled(new_state)

    if new_state:
        # Re-enable audio and restart music
        audio.start_music()
        _add_notification('Audio: ON')
    else:
        _add_notification('Audio: OFF')


def _execute_pause_menu_action():
    """Execute the currently selected pause menu action."""
    from src.core import state as game_state

    selected = state.ui.pause_menu_index

    if selected == 0:
        # RESUME - unpause the game
        handle_pause()
    elif selected == 1:
        # RESTART - restart game
        _handle_restart()
    elif selected == 2:
        # SAVE - open save menu
        state.ui.settings_menu = 'save'
        state.ui.settings_index = 0
    elif selected == 3:
        # LOAD - open load menu
        state.ui.settings_menu = 'load'
        state.ui.settings_index = 0
    elif selected == 4:
        # BIRDPEDIA - open birdpedia menu
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 0
    elif selected == 5:
        # SETTINGS - enter settings menu
        state.ui.settings_menu = 'main'
        state.ui.settings_index = 0
    elif selected == 6:
        # MAIN MENU - return to title screen
        state.game.paused = False
        state.ui.pause_menu_index = 0
        state.ui.settings_menu = None
        state.ui.show_title = True
        state.ui.title_menu_index = 0
        state.game.game_over = True  # End current game loop to return to title


def _handle_restart():
    """Restart the game from the beginning."""
    from src.core import state as game_state

    # Re-initialize game state
    game_state.init()

    # Unpause
    state.game.paused = False
    state.ui.pause_menu_index = 0

    _add_notification("New game!", title="Restart:")


def _get_settings_options_count():
    """Return the number of options in the current settings submenu."""
    menu = state.ui.settings_menu
    if menu == 'main':
        return 5  # SOUND, GRAPHICS, CONTROLS, DIFFICULTY, < BACK
    elif menu == 'sound':
        return 3  # SFX, MUSIC, < BACK
    elif menu == 'graphics':
        return 4  # BACKGROUND, PARALLAX, ACCESSIBILITY, < BACK
    elif menu == 'controls':
        return 6  # 5 control display items + < BACK
    elif menu == 'save':
        return 4  # SLOT 1, SLOT 2, SLOT 3, < BACK
    elif menu == 'load':
        return 5  # AUTO, SLOT 1, SLOT 2, SLOT 3, < BACK
    elif menu == 'birdpedia':
        return 5  # GUIDE, BIRDPEDIA, BATPEDIA, BIOMES, < BACK
    elif menu == 'guide':
        return 5  # HOW TO PLAY, COMMANDS, OBSTACLES, ENEMIES, < BACK
    elif menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies',
                  'birdpedia_list', 'batpedia_list', 'biomes_list'):
        return 1  # Just < BACK (content view)
    return 1


def _handle_settings_enter():
    """Handle ENTER key in settings menu."""
    menu = state.ui.settings_menu
    idx = state.ui.settings_index

    if menu == 'main':
        if idx == 0:  # SOUND
            state.ui.settings_menu = 'sound'
            state.ui.settings_index = 0
        elif idx == 1:  # GRAPHICS
            state.ui.settings_menu = 'graphics'
            state.ui.settings_index = 0
        elif idx == 2:  # CONTROLS
            state.ui.settings_menu = 'controls'
            state.ui.settings_index = 0
        elif idx == 3:  # DIFFICULTY - cycle on enter too
            _cycle_difficulty(1)
        elif idx == 4:  # < BACK
            state.ui.settings_menu = None
            state.ui.settings_index = 0
    elif menu == 'sound':
        if idx == 0:  # SFX toggle
            state.settings.sfx_enabled = not state.settings.sfx_enabled
        elif idx == 1:  # MUSIC toggle
            state.settings.music_enabled = not state.settings.music_enabled
            _apply_music_setting()
        elif idx == 2:  # < BACK
            state.ui.settings_menu = 'main'
            state.ui.settings_index = 0
    elif menu == 'graphics':
        if idx == 0:  # BACKGROUND toggle
            state.settings.background_enabled = not state.settings.background_enabled
        elif idx == 1:  # PARALLAX toggle
            state.settings.parallax_enabled = not state.settings.parallax_enabled
        elif idx == 2:  # ACCESSIBILITY toggle
            _toggle_accessibility()
        elif idx == 3:  # < BACK
            state.ui.settings_menu = 'main'
            state.ui.settings_index = 1
    elif menu == 'controls':
        count = _get_settings_options_count()
        if idx == count - 1:  # < BACK
            state.ui.settings_menu = 'main'
            state.ui.settings_index = 2
        elif idx < count - 1:  # Rebindable control
            # Start rebinding mode
            control_names = ['MOVE_LEFT', 'MOVE_RIGHT', 'BOUNCE', 'SUCTION', 'SWAP']
            if idx < len(control_names):
                state.ui.rebinding_control = control_names[idx]
    elif menu == 'save':
        if idx == 3:  # < BACK
            state.ui.settings_menu = None
            state.ui.settings_index = 0
        elif idx < 3:  # Slot 1-3
            slot = idx + 1
            from src.services import save_manager
            if save_manager.save_game(slot):
                _add_notification(f"Saved to Slot {slot}", title="Save:")
                state.ui.settings_menu = None
                state.ui.settings_index = 0
            else:
                _add_notification("Save failed!", title="Error:")
    elif menu == 'load':
        if idx == 4:  # < BACK
            state.ui.settings_menu = None
            state.ui.settings_index = 0
        elif idx <= 3:  # Slot 0 (auto), 1, 2, 3
            slot = idx  # idx 0 = autosave, idx 1-3 = slots 1-3
            from src.services import save_manager
            slots = save_manager.list_save_slots()
            if slots.get(slot, {}).get('exists'):
                if save_manager.load_game(slot):
                    slot_name = "Autosave" if slot == 0 else f"Slot {slot}"
                    _add_notification(f"Loaded {slot_name}", title="Load:")
                    state.ui.settings_menu = None
                    state.ui.settings_index = 0
                    state.game.paused = False
                else:
                    _add_notification("Load failed!", title="Error:")
            else:
                _add_notification("Slot is empty!", title="Error:")
    elif menu == 'birdpedia':
        if idx == 0:  # GUIDE
            state.ui.settings_menu = 'guide'
            state.ui.settings_index = 0
        elif idx == 1:  # BIRDPEDIA
            state.ui.settings_menu = 'birdpedia_list'
            state.ui.settings_index = 0
        elif idx == 2:  # BATPEDIA
            state.ui.settings_menu = 'batpedia_list'
            state.ui.settings_index = 0
        elif idx == 3:  # BIOMES
            state.ui.settings_menu = 'biomes_list'
            state.ui.settings_index = 0
        elif idx == 4:  # < BACK
            state.ui.settings_menu = None
            state.ui.settings_index = 0
    elif menu == 'guide':
        if idx == 0:  # HOW TO PLAY
            state.ui.settings_menu = 'guide_howto'
            state.ui.settings_index = 0
        elif idx == 1:  # COMMANDS
            state.ui.settings_menu = 'guide_commands'
            state.ui.settings_index = 0
        elif idx == 2:  # OBSTACLES
            state.ui.settings_menu = 'guide_obstacles'
            state.ui.settings_index = 0
        elif idx == 3:  # ENEMIES
            state.ui.settings_menu = 'guide_enemies'
            state.ui.settings_index = 0
        elif idx == 4:  # < BACK
            state.ui.settings_menu = 'birdpedia'
            state.ui.settings_index = 0
    elif menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies',
                  'birdpedia_list', 'batpedia_list', 'biomes_list'):
        # Content views - any key goes back
        _handle_settings_back()


def _handle_settings_back():
    """Handle ESC or < BACK in settings menu."""
    menu = state.ui.settings_menu

    if menu == 'main':
        state.ui.settings_menu = None
        state.ui.settings_index = 0
    elif menu in ('sound', 'graphics', 'controls'):
        state.ui.settings_menu = 'main'
        # Return to appropriate index in main menu
        if menu == 'sound':
            state.ui.settings_index = 0
        elif menu == 'graphics':
            state.ui.settings_index = 1
        else:  # controls
            state.ui.settings_index = 2
    elif menu in ('save', 'load'):
        # Return directly to pause menu
        state.ui.settings_menu = None
        state.ui.settings_index = 0
    elif menu == 'birdpedia':
        # Return directly to pause menu
        state.ui.settings_menu = None
        state.ui.settings_index = 0
    elif menu == 'guide':
        # Return to birdpedia menu
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 0
    elif menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies'):
        # Return to guide menu
        state.ui.settings_menu = 'guide'
        state.ui.settings_index = 0
    elif menu == 'birdpedia_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 1
    elif menu == 'batpedia_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 2
    elif menu == 'biomes_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 3


def _handle_settings_left_right(direction):
    """Handle LEFT/RIGHT for cycling values in settings."""
    menu = state.ui.settings_menu
    idx = state.ui.settings_index
    delta = -1 if direction == 'LEFT' else 1

    if menu == 'main' and idx == 3:  # DIFFICULTY
        _cycle_difficulty(delta)
    elif menu == 'sound':
        if idx == 0:  # SFX
            state.settings.sfx_enabled = not state.settings.sfx_enabled
        elif idx == 1:  # MUSIC
            state.settings.music_enabled = not state.settings.music_enabled
            _apply_music_setting()
    elif menu == 'graphics':
        if idx == 0:  # BACKGROUND
            state.settings.background_enabled = not state.settings.background_enabled
        elif idx == 1:  # PARALLAX
            state.settings.parallax_enabled = not state.settings.parallax_enabled
        elif idx == 2:  # ACCESSIBILITY
            _toggle_accessibility()


def _toggle_accessibility():
    """Toggle accessibility mode and apply related settings."""
    state.settings.accessibility_enabled = not state.settings.accessibility_enabled

    if state.settings.accessibility_enabled:
        # Disable background and parallax for clarity
        state.settings.background_enabled = False
        state.settings.parallax_enabled = False


def _cycle_difficulty(delta):
    """Cycle difficulty setting."""
    state.settings.difficulty = (state.settings.difficulty + delta) % 4


def _apply_music_setting():
    """Apply music enabled/disabled setting."""
    if not AUDIO_AVAILABLE or not audio:
        return

    if state.settings.music_enabled:
        audio.start_music()
    else:
        audio.stop_music()


def _handle_title_input(key):
    """Handle input on title screen. Returns True if handled."""
    if not state.ui.show_title:
        return False

    if key == 'QUIT':
        state.game.quit_requested = True
        state.game.game_over = True
        return True

    # If in load submenu on title screen
    if state.ui.settings_menu == 'load':
        if key == 'UP':
            state.ui.settings_index = (state.ui.settings_index - 1) % 5  # 4 slots + back
            return True
        if key == 'DOWN':
            state.ui.settings_index = (state.ui.settings_index + 1) % 5
            return True
        if key == 'ESC':
            state.ui.settings_menu = None
            return True
        if key == 'ENTER':
            idx = state.ui.settings_index
            if idx == 4:  # BACK
                state.ui.settings_menu = None
            else:
                # Load slot idx (0=autosave, 1-3=manual)
                from src.services import save_manager
                if save_manager.load_game(idx):
                    state.ui.show_title = False
                    state.ui.settings_menu = None
            return True
        return True

    # If in settings submenu on title screen
    if state.ui.settings_menu is not None:
        return _handle_title_settings_input(key)

    if key == 'UP':
        state.ui.title_menu_index = (state.ui.title_menu_index - 1) % 6  # 6 options now
        return True

    if key == 'DOWN':
        state.ui.title_menu_index = (state.ui.title_menu_index + 1) % 6
        return True

    # LEFT/RIGHT on NEW GAME changes difficulty
    if key in ('LEFT', 'RIGHT') and state.ui.title_menu_index == 1:
        delta = 1 if key == 'RIGHT' else -1
        state.settings.difficulty = (state.settings.difficulty + delta) % 4
        return True

    if key == 'ENTER':
        idx = state.ui.title_menu_index
        if idx == 0:  # CONTINUE
            # Try to load the most recent save (by timestamp)
            from src.services import save_manager
            most_recent = save_manager.get_most_recent_save()
            if most_recent is not None and save_manager.load_game(most_recent):
                state.ui.show_title = False
            else:
                # No saves, start new game with default settings
                from src.services import save_manager
                state.init()
                save_manager.load_default_settings()
                state.ui.show_title = False
        elif idx == 1:  # NEW GAME
            from src.services import save_manager
            from src.core import constants
            # Save the difficulty selection before init (which doesn't reset settings)
            selected_difficulty = state.settings.difficulty
            # Load difficulty-specific configuration
            constants.reload_for_difficulty(selected_difficulty)
            state.init()
            save_manager.load_default_settings()
            # Restore the difficulty we selected on title screen
            state.settings.difficulty = selected_difficulty
            state.ui.show_title = False
        elif idx == 2:  # LOAD
            state.ui.settings_menu = 'load'
            state.ui.settings_index = 0
        elif idx == 3:  # BIRDPEDIA
            state.ui.settings_menu = 'birdpedia'
            state.ui.settings_index = 0
        elif idx == 4:  # SETTINGS
            state.ui.settings_menu = 'main'
            state.ui.settings_index = 0
        elif idx == 5:  # QUIT
            state.game.quit_requested = True
            state.game.game_over = True
        return True

    return False


def _handle_title_settings_input(key):
    """Handle settings menu input on title screen. Returns True if handled."""
    from src.services import save_manager

    # Rebinding mode
    if state.ui.rebinding_control is not None:
        if key == 'ESC':
            state.ui.rebinding_control = None
        else:
            valid_keys = ['LEFT', 'RIGHT', 'UP', 'DOWN', 'SPACE', 'ENTER',
                          'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
                          'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
                          'U', 'V', 'W', 'X', 'Y', 'Z',
                          'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j',
                          'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
                          'u', 'v', 'w', 'x', 'y', 'z',
                          '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
            if key in valid_keys:
                state.settings.key_bindings[state.ui.rebinding_control] = key.upper() if len(key) == 1 else key
                state.ui.rebinding_control = None
                # Save default settings
                save_manager.save_default_settings()
        return True

    if key == 'ESC':
        _handle_title_settings_back()
        return True

    if key == 'UP':
        count = _get_settings_options_count()
        state.ui.settings_index = (state.ui.settings_index - 1) % count
        return True

    if key == 'DOWN':
        count = _get_settings_options_count()
        state.ui.settings_index = (state.ui.settings_index + 1) % count
        return True

    if key in ('LEFT', 'RIGHT'):
        _handle_title_settings_left_right(key)
        return True

    if key == 'ENTER':
        _handle_title_settings_enter()
        return True

    return True


def _handle_title_settings_back():
    """Handle ESC or < BACK in title settings menu."""
    from src.services import save_manager
    menu = state.ui.settings_menu

    if menu == 'main':
        state.ui.settings_menu = None
        state.ui.settings_index = 0
        # Save defaults when exiting settings
        save_manager.save_default_settings()
    elif menu in ('sound', 'graphics', 'controls'):
        state.ui.settings_menu = 'main'
        if menu == 'sound':
            state.ui.settings_index = 0
        elif menu == 'graphics':
            state.ui.settings_index = 1
        else:
            state.ui.settings_index = 2
    elif menu == 'birdpedia':
        state.ui.settings_menu = None
        state.ui.settings_index = 0
    elif menu == 'guide':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 0
    elif menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies'):
        state.ui.settings_menu = 'guide'
        state.ui.settings_index = 0
    elif menu == 'birdpedia_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 1
    elif menu == 'batpedia_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 2
    elif menu == 'biomes_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 3


def _handle_title_settings_left_right(key):
    """Handle LEFT/RIGHT in title settings menu."""
    from src.services import save_manager
    menu = state.ui.settings_menu
    idx = state.ui.settings_index
    delta = 1 if key == 'RIGHT' else -1

    if menu == 'main' and idx == 3:  # DIFFICULTY
        state.settings.difficulty = (state.settings.difficulty + delta) % 4
        save_manager.save_default_settings()
    elif menu == 'sound':
        if idx == 0:  # SFX
            state.settings.sfx_enabled = not state.settings.sfx_enabled
            save_manager.save_default_settings()
        elif idx == 1:  # MUSIC
            state.settings.music_enabled = not state.settings.music_enabled
            save_manager.save_default_settings()
    elif menu == 'graphics':
        if idx == 0:  # BACKGROUND
            state.settings.background_enabled = not state.settings.background_enabled
            save_manager.save_default_settings()
        elif idx == 1:  # PARALLAX
            state.settings.parallax_enabled = not state.settings.parallax_enabled
            save_manager.save_default_settings()
        elif idx == 2:  # ACCESSIBILITY
            state.settings.accessibility_enabled = not state.settings.accessibility_enabled
            if state.settings.accessibility_enabled:
                state.settings.background_enabled = False
                state.settings.parallax_enabled = False
            save_manager.save_default_settings()


def _handle_title_settings_enter():
    """Handle ENTER in title settings menu."""
    from src.services import save_manager
    menu = state.ui.settings_menu
    idx = state.ui.settings_index

    if menu == 'main':
        if idx == 0:  # SOUND
            state.ui.settings_menu = 'sound'
            state.ui.settings_index = 0
        elif idx == 1:  # GRAPHICS
            state.ui.settings_menu = 'graphics'
            state.ui.settings_index = 0
        elif idx == 2:  # CONTROLS
            state.ui.settings_menu = 'controls'
            state.ui.settings_index = 0
        elif idx == 3:  # DIFFICULTY (cycle)
            state.settings.difficulty = (state.settings.difficulty + 1) % 4
            save_manager.save_default_settings()
        elif idx == 4:  # < BACK
            _handle_title_settings_back()
    elif menu == 'sound':
        if idx == 0:  # SFX
            state.settings.sfx_enabled = not state.settings.sfx_enabled
            save_manager.save_default_settings()
        elif idx == 1:  # MUSIC
            state.settings.music_enabled = not state.settings.music_enabled
            save_manager.save_default_settings()
        elif idx == 2:  # < BACK
            _handle_title_settings_back()
    elif menu == 'graphics':
        if idx == 0:  # BACKGROUND
            state.settings.background_enabled = not state.settings.background_enabled
            save_manager.save_default_settings()
        elif idx == 1:  # PARALLAX
            state.settings.parallax_enabled = not state.settings.parallax_enabled
            save_manager.save_default_settings()
        elif idx == 2:  # ACCESSIBILITY
            state.settings.accessibility_enabled = not state.settings.accessibility_enabled
            if state.settings.accessibility_enabled:
                state.settings.background_enabled = False
                state.settings.parallax_enabled = False
            save_manager.save_default_settings()
        elif idx == 3:  # < BACK
            _handle_title_settings_back()
    elif menu == 'controls':
        if idx < 5:  # Rebind controls
            control_names = ['MOVE_LEFT', 'MOVE_RIGHT', 'BOUNCE', 'SUCTION', 'SWAP']
            state.ui.rebinding_control = control_names[idx]
        elif idx == 5:  # < BACK
            _handle_title_settings_back()
    elif menu == 'birdpedia':
        if idx == 0:  # GUIDE
            state.ui.settings_menu = 'guide'
            state.ui.settings_index = 0
        elif idx == 1:  # BIRDPEDIA
            state.ui.settings_menu = 'birdpedia_list'
            state.ui.settings_index = 0
        elif idx == 2:  # BATPEDIA
            state.ui.settings_menu = 'batpedia_list'
            state.ui.settings_index = 0
        elif idx == 3:  # BIOMES
            state.ui.settings_menu = 'biomes_list'
            state.ui.settings_index = 0
        elif idx == 4:  # < BACK
            _handle_title_settings_back()
    elif menu == 'guide':
        if idx == 0:  # HOW TO PLAY
            state.ui.settings_menu = 'guide_howto'
            state.ui.settings_index = 0
        elif idx == 1:  # COMMANDS
            state.ui.settings_menu = 'guide_commands'
            state.ui.settings_index = 0
        elif idx == 2:  # OBSTACLES
            state.ui.settings_menu = 'guide_obstacles'
            state.ui.settings_index = 0
        elif idx == 3:  # ENEMIES
            state.ui.settings_menu = 'guide_enemies'
            state.ui.settings_index = 0
        elif idx == 4:  # < BACK
            _handle_title_settings_back()
    elif menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies',
                  'birdpedia_list', 'batpedia_list', 'biomes_list'):
        # Content views - any key goes back
        _handle_title_settings_back()


def process_input(key):
    """Process a single key input and update game state."""
    if key is None:
        return

    # Handle title screen input first
    if _handle_title_input(key):
        return

    # Get the swap key binding
    swap_key = state.settings.key_bindings.get('SWAP', 'SPACE')
    key_upper = key.upper() if isinstance(key, str) and len(key) == 1 else key

    # Detect swap key press (edge detection for any bound key)
    swap_pressed = (key_upper == swap_key)
    swap_just_pressed = swap_pressed and not state.player.last_space_state
    state.player.last_space_state = swap_pressed

    # When paused, handle pause menu navigation
    if state.game.paused:
        # Check if we're in settings submenu
        if state.ui.settings_menu is not None:
            # Check if we're in rebinding mode
            if state.ui.rebinding_control is not None:
                if key == 'QUIT':
                    state.game.quit_requested = True
                    state.game.game_over = True
                elif key == 'ESC':
                    # Cancel rebinding
                    state.ui.rebinding_control = None
                else:
                    # Accept any valid key for rebinding
                    valid_keys = ['LEFT', 'RIGHT', 'UP', 'DOWN', 'SPACE', 'ENTER',
                                  'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J',
                                  'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T',
                                  'U', 'V', 'W', 'X', 'Y', 'Z',
                                  'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j',
                                  'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
                                  'u', 'v', 'w', 'x', 'y', 'z',
                                  '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
                    if key in valid_keys:
                        # Assign the new key
                        state.settings.key_bindings[state.ui.rebinding_control] = key.upper() if len(key) == 1 else key
                        state.ui.rebinding_control = None
                return

            if key == 'QUIT':
                state.game.quit_requested = True
                state.game.game_over = True
            elif key == 'ESC':
                _handle_settings_back()
            elif key == 'UP':
                count = _get_settings_options_count()
                state.ui.settings_index = (state.ui.settings_index - 1) % count
            elif key == 'DOWN':
                count = _get_settings_options_count()
                state.ui.settings_index = (state.ui.settings_index + 1) % count
            elif key in ('LEFT', 'RIGHT'):
                _handle_settings_left_right(key)
            elif key == 'ENTER':
                _handle_settings_enter()
            return

        # Regular pause menu navigation
        if key in ('P', 'p', 'ESC'):
            handle_pause()  # Unpause
        elif key == 'QUIT':
            state.game.quit_requested = True
            state.game.game_over = True
        elif key == 'UP':
            # Navigate menu up
            state.ui.pause_menu_index = (state.ui.pause_menu_index - 1) % 7
        elif key == 'DOWN':
            # Navigate menu down
            state.ui.pause_menu_index = (state.ui.pause_menu_index + 1) % 7
        elif key == 'ENTER':
            # Execute selected menu action
            _execute_pause_menu_action()
        return

    # Get key bindings
    bindings = state.settings.key_bindings

    # Handle keys using configurable bindings
    if swap_just_pressed:
        handle_swap()
    elif key in ('P', 'p'):
        handle_pause()
    elif key_upper == bindings.get('MOVE_LEFT'):
        handle_movement('LEFT')
    elif key_upper == bindings.get('MOVE_RIGHT'):
        handle_movement('RIGHT')
    elif key in ('X', 'x'):
        handle_xp_toggle()
    elif key in ('M', 'm'):
        handle_audio_toggle()
    elif key_upper == bindings.get('BOUNCE'):
        handle_bounce()
    elif key_upper == bindings.get('SUCTION'):
        handle_suction()
    elif key == 'QUIT':
        state.game.quit_requested = True
        state.game.game_over = True
