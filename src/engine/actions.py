"""Player actions during play: move, swap, bounce and toggles."""

import random

from src.core import constants, state
from src.engine import clock, events
from src.engine.birds import (
    check_pending_transforms,
    get_affected_lanes,
    is_orange_egg_state,
    reset_bird_power,
    set_ball_vy,
)
from src.engine.notifications import notify
from src.engine.powers import activate_bird_power
from src.engine.progression import calculate_gear_threshold, compute_gear_from_momentum, deduct_momentum
from src.entities import bird_types
from src.entities.sprites import CLOCKWORK, DINOSAUR, GLITCH, ORANGE, PURPLE, RAINBOW
from src.services.sound import get_audio


def _find_all_birds_in_lane(lane):
    """Return list of all bird indices in given lane."""
    return [i for i, bird_lane in enumerate(state.birds.random_lanes) if bird_lane == lane]


def handle_pause():
    """Toggle pause state."""
    state.game.paused = not state.game.paused
    msg = 'PAUSED' if state.game.paused else 'RESUMED'
    notify(msg)


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
    events.emit('swap', swaps=state.game.swaps_used)

    # Handle orange eggs before swap
    for idx, other_idx in [(bird_in_selected, bird_in_current), (bird_in_current, bird_in_selected)]:
        if is_orange_egg_state(idx):
            old_lane = state.birds.home_lanes[idx]
            new_lane = state.birds.home_lanes[other_idx]
            for loot in state.items.loot_items:
                if loot['type'] == 'orange_egg' and loot['x_pos'] == constants.layout.lane_positions[old_lane]:
                    loot['x_pos'] = constants.layout.lane_positions[new_lane]
                    break

    # Swap home_lanes
    state.birds.home_lanes[bird_in_selected], state.birds.home_lanes[bird_in_current] = (
        state.birds.home_lanes[bird_in_current],
        state.birds.home_lanes[bird_in_selected],
    )

    # Swap physical lanes too
    state.birds.random_lanes[bird_in_selected], state.birds.random_lanes[bird_in_current] = (
        state.birds.random_lanes[bird_in_current],
        state.birds.random_lanes[bird_in_selected],
    )

    # Update columns
    state.birds.cols[bird_in_selected] = constants.layout.lane_positions[state.birds.random_lanes[bird_in_selected]]
    state.birds.cols[bird_in_current] = constants.layout.lane_positions[state.birds.random_lanes[bird_in_current]]

    # Reset non-orange-egg birds to starting line (in their new home lane)
    for idx in [bird_in_selected, bird_in_current]:
        if not state.birds.lost[idx] and not is_orange_egg_state(idx):
            # Reset to home lane and starting position
            state.birds.random_lanes[idx] = state.birds.home_lanes[idx]
            state.birds.cols[idx] = constants.layout.lane_positions[state.birds.home_lanes[idx]]
            state.birds.y[idx] = constants.layout.starting_line
            set_ball_vy(idx, -1)

    state.player.selected_lane = None


def handle_bounce():
    """Handle UP key for bouncing birds.

    Processes ALL birds in the affected lanes (multiple birds can be in same lane due to portals).
    """
    # Record last UP press time (for Purple hold-to-charge)
    state.special.last_up_time = clock.now()

    lanes = get_affected_lanes()

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

            # BLEEDING BIRDS: each UP press costs a bleed counter, bird dies when counter depleted
            if bird_idx in state.special.bleeding_birds:
                bleed_info = state.special.bleeding_birds[bird_idx]
                bleed_info['lives_lost'] = bleed_info.get('lives_lost', 0) + 1
                if bleed_info['lives_lost'] >= bleed_info.get('lives_needed', 3):
                    # Lives depleted - bird dies!
                    if not state.birds.lost[bird_idx]:
                        dead_color = state.birds.colors[bird_idx]
                        state.birds.lost[bird_idx] = True
                        state.birds.y[bird_idx] = constants.layout.height - 1
                        state.game.lives -= 1
                        del state.special.bleeding_birds[bird_idx]
                        events.emit('bird_lost', bird=bird_idx, color=dead_color, cause='bleeding')
                        # Check if a pending bird can now transform

                        check_pending_transforms(dead_color)
                        if state.game.lives <= 0:
                            state.game.game_over = True
                    continue  # Bird is dead, skip bounce
                # Bird still alive - continue to normal bounce processing below

            # FROZEN BIRDS: button press attempts to thaw
            if bird_idx in state.special.frozen_birds:
                frozen_info = state.special.frozen_birds[bird_idx]
                frozen_info['thaw_attempts_done'] = frozen_info.get('thaw_attempts_done', 0) + 1
                if frozen_info['thaw_attempts_done'] >= frozen_info.get('thaw_attempts_needed', 3):
                    # Bird thawed!
                    del state.special.frozen_birds[bird_idx]
                    # Reset to normal state - bounce up
                    state.birds.vy[bird_idx] = -1
                    reset_bird_power(bird_idx)
                continue  # Don't process normal bounce while frozen

            # POISONED BIRDS: button press decrements heal counter, bird is cured when counter reaches 0
            if bird_idx in state.special.poisoned_birds:
                poison_info = state.special.poisoned_birds[bird_idx]
                poison_info['cure_attempts_done'] = poison_info.get('cure_attempts_done', 0) + 1
                if poison_info['cure_attempts_done'] >= poison_info.get('cure_attempts_needed', 3):
                    # Heal counter reached 0 - bird is cured!
                    del state.special.poisoned_birds[bird_idx]
                # Continue to normal bounce processing (poisoned birds can still bounce)

            # RAINBOW: chance to recharge on ANY UP press (regardless of direction)
            if bird_color == RAINBOW:
                recharge_chance = getattr(constants.rainbow, 'recharge_chance', 0.25)
                if random.random() < recharge_chance:
                    recharge_amount = getattr(constants.rainbow, 'recharge_amount', 25)
                    max_charge = getattr(constants.rainbow, 'max_charge', 100)
                    current = state.special.rainbow_charge.get(bird_idx, 0)
                    state.special.rainbow_charge[bird_idx] = min(max_charge, current + recharge_amount)

            # Bird moving down - bounce it up
            if state.birds.vy[bird_idx] == 1:
                _bounce_bird_up(bird_idx)
            # Bird moving up - activate power
            elif state.birds.vy[bird_idx] == -1:
                activate_bird_power(bird_idx)


def _recover_orange_bird(bird_idx, lane):
    """Recover an orange bird from egg state."""
    state.birds.y[bird_idx] = constants.layout.starting_line
    set_ball_vy(bird_idx, -1)
    reset_bird_power(bird_idx)
    state.birds.speeds[bird_idx] = 5

    # Remove the orange egg loot item
    for loot in state.items.loot_items[:]:
        if (
            loot.get('type') == 'orange_egg'
            and loot.get('x_pos') == constants.layout.lane_positions[lane]
            and loot.get('y_pos') == constants.layout.starting_line
        ):
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

    set_ball_vy(bird_idx, -1)
    reset_bird_power(bird_idx)
    # play_sfx('bounce')  # Disabled - too frequent, clashes with music

    # CLOCKWORK charge restoration
    if bird_color == CLOCKWORK:
        charge = state.special.clockwork_charge.get(bird_idx)
        if charge is None:
            state.special.clockwork_charge[bird_idx] = constants.clockwork.initial_charge
        elif charge == 0:
            state.special.clockwork_charge[bird_idx] = 1
            state.birds.speeds[bird_idx] = 1




def _handle_dinosaur_bounce(bird_idx):
    """Handle dinosaur multi-press bounce."""
    cnt = state.special.dinosaur_up_presses.get(bird_idx, 0) + 1
    state.special.dinosaur_up_presses[bird_idx] = cnt

    chunk = constants.dinosaur.press_chunk
    if chunk > 0 and cnt % chunk == 0:
        if cnt >= constants.dinosaur.presses_to_bounce:
            set_ball_vy(bird_idx, -1)
            state.birds.speeds[bird_idx] = bird_types.BIRD_TYPES.get('DINOSAUR', {}).get('speed', 4)
            state.special.dinosaur_up_presses[bird_idx] = 0
            reset_bird_power(bird_idx)
        else:
            state.birds.speeds[bird_idx] = max(1, state.birds.speeds[bird_idx] - 1)


def handle_xp_toggle():
    """Toggle XP overlay display."""
    state.ui.show_xp_overlay = not state.ui.show_xp_overlay
    msg = 'XP overlay: ON' if state.ui.show_xp_overlay else 'XP overlay: OFF'
    notify(msg)


def handle_audio_toggle():
    """Toggle audio on/off (mute/unmute)."""
    audio = get_audio()
    if audio is None:
        notify('Audio not available')
        return

    # Toggle audio state
    current = getattr(audio, '_audio_enabled', True)
    new_state = not current
    audio.set_audio_enabled(new_state)

    if new_state:
        # Re-enable audio and restart music
        audio.start_music()
        notify('Audio: ON')
    else:
        notify('Audio: OFF')
