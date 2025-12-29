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
    """Play sound effect if audio is available."""
    if AUDIO_AVAILABLE and audio:
        audio.play_sfx(name)


def _find_bird_in_lane(lane):
    """Return bird index for given lane, or -1 if not found."""
    if lane in state.birds.random_lanes:
        return state.birds.random_lanes.index(lane)
    return -1


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


def _execute_swap():
    """Execute a bird swap between selected lane and current lane."""
    from src.functions import compute_level_from_score, deduct_score

    level = compute_level_from_score(state.game.score)
    swap_cost = 200 * level

    if state.game.score < swap_cost:
        state.player.selected_lane = None
        return

    current_lane = state.player.lane
    selected_lane = state.player.selected_lane

    bird_in_selected = _find_bird_in_lane(selected_lane)
    bird_in_current = _find_bird_in_lane(current_lane)

    if bird_in_selected < 0 or bird_in_current < 0:
        state.player.selected_lane = None
        return

    # Deduct cost
    deduct_score(swap_cost)
    state.game.swaps_used += 1
    achievements.check_achievements_event('swap', state.game.frame_count, state.ui.notifications, swaps=state.game.swaps_used)

    # Handle orange eggs before swap
    for idx, other_idx in [(bird_in_selected, bird_in_current), (bird_in_current, bird_in_selected)]:
        if _is_orange_egg_state(idx):
            old_lane = state.birds.random_lanes[idx]
            new_lane = state.birds.random_lanes[other_idx]
            for loot in state.items.loot_items:
                if loot['type'] == 'orange_egg' and loot['x_pos'] == constants.layout.lane_positions[old_lane]:
                    loot['x_pos'] = constants.layout.lane_positions[new_lane]
                    break

    # Swap lanes
    state.birds.random_lanes[bird_in_selected], state.birds.random_lanes[bird_in_current] = \
        state.birds.random_lanes[bird_in_current], state.birds.random_lanes[bird_in_selected]

    # Update columns
    state.birds.cols[bird_in_selected] = constants.layout.lane_positions[state.birds.random_lanes[bird_in_selected]]
    state.birds.cols[bird_in_current] = constants.layout.lane_positions[state.birds.random_lanes[bird_in_current]]

    # Reset non-orange-egg birds to starting line
    for idx in [bird_in_selected, bird_in_current]:
        if not state.birds.lost[idx] and not _is_orange_egg_state(idx):
            state.birds.y[idx] = constants.layout.starting_line
            _set_ball_vy(idx, -1)

    state.player.selected_lane = None


def _is_orange_egg_state(bird_idx):
    """Check if bird is in orange egg dormant state."""
    return (state.birds.colors[bird_idx] == ORANGE and
            state.birds.speeds[bird_idx] == 0 and
            state.birds.y[bird_idx] == 999)


def handle_bounce():
    """Handle UP key for bouncing birds."""
    lanes = _get_affected_lanes()

    for lane in lanes:
        bird_idx = _find_bird_in_lane(lane)
        if bird_idx < 0 or state.birds.lost[bird_idx]:
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

    # Check allowed uses
    label, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
    allowed_uses = 2 if (label and label.startswith('A')) else 1

    if not _allow_consume_power(bird_idx, allowed_uses):
        return

    bird_color = state.birds.colors[bird_idx]
    bird_lane = state.birds.random_lanes[bird_idx]

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
        # RICOMINCIA - restart game
        _handle_restart()
    elif selected == 1:
        # SALVA & ESCI - save and exit
        _handle_save_and_exit()
    elif selected == 2:
        # BIRDPEDIA - placeholder for now
        _add_notification("Birdpedia", title="Coming Soon:")
    elif selected == 3:
        # IMPOSTAZIONI - placeholder for now
        _add_notification("Impostazioni", title="Coming Soon:")


def _handle_restart():
    """Restart the game from the beginning."""
    from src.core import state as game_state

    # Re-initialize game state
    game_state.init()

    # Unpause
    state.game.paused = False
    state.ui.pause_menu_index = 0

    _add_notification("Nuova partita!", title="Restart:")


def _handle_save_and_exit():
    """Save game and exit."""
    # For now, just exit (save functionality can be added later)
    state.game.quit_requested = True
    state.game.game_over = True


def process_input(key):
    """Process a single key input and update game state."""
    if key is None:
        return

    # Detect space key press (edge detection)
    space_pressed = (key == 'SPACE')
    space_just_pressed = space_pressed and not state.player.last_space_state
    state.player.last_space_state = space_pressed

    # When paused, handle pause menu navigation
    if state.game.paused:
        if key in ('P', 'p', 'ESC'):
            handle_pause()  # Unpause
        elif key == 'QUIT':
            state.game.quit_requested = True
            state.game.game_over = True
        elif key == 'UP':
            # Navigate menu up
            state.ui.pause_menu_index = (state.ui.pause_menu_index - 1) % 4
        elif key == 'DOWN':
            # Navigate menu down
            state.ui.pause_menu_index = (state.ui.pause_menu_index + 1) % 4
        elif key == 'ENTER':
            # Execute selected menu action
            _execute_pause_menu_action()
        return

    # Handle keys
    if key == 'SPACE' and space_just_pressed:
        handle_swap()
    elif key in ('P', 'p'):
        handle_pause()
    elif key == 'LEFT':
        handle_movement('LEFT')
    elif key == 'RIGHT':
        handle_movement('RIGHT')
    elif key in ('X', 'x'):
        handle_xp_toggle()
    elif key in ('M', 'm'):
        handle_audio_toggle()
    elif key == 'UP':
        handle_bounce()
    elif key == 'DOWN':
        handle_suction()
    elif key == 'QUIT':
        state.game.quit_requested = True
        state.game.game_over = True
