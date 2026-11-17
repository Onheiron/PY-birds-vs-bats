"""Birds and their status indicators."""

import math
import random

from src.core import constants, state
from src.engine import clock
from src.entities.sprites import (
    BIRD_DOWN_1,
    BIRD_DOWN_2,
    BIRD_UP_1,
    BIRD_UP_2,
    BLUE,
    CLOCKWORK,
    CYAN,
    DARK_GRAY,
    DINOSAUR,
    DINOSAUR_DOWN_1,
    DINOSAUR_DOWN_2,
    DINOSAUR_UP_1,
    DINOSAUR_UP_2,
    GREEN,
    ORANGE,
    PATCHWORK,
    PURPLE,
    RAINBOW,
    RED,
    RESET,
    STEALTH,
    TWISTER,
    WHITE,
    YELLOW,
)
from src.ui.colors import apply_bold, get_render_color
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT


def render_clockwork_line(line, charge, blink_on):
    """Render a CLOCKWORK bird line with special coloring.

    Beak (') color based on charge:
    - charge 3 (full): normal clockwork color
    - charge 1-2 (discharging): yellow blinking
    - charge 0 (empty): red blinking
    """
    colored = ""
    for ch in line:
        if ch == "'":
            # Beak - shows charge status
            if charge == 0:
                # Empty: red blinking
                beak_color = RED if blink_on else DARK_GRAY
            elif charge < 3:
                # Discharging: yellow blinking
                beak_color = YELLOW if blink_on else DARK_GRAY
            else:
                # Full: normal
                beak_color = CLOCKWORK
            colored += f"{beak_color}{ch}{RESET}"
        else:
            colored += f"{CLOCKWORK}{ch}{RESET}"
    return colored


def render_patchwork_line(line):
    """Render a PATCHWORK bird line with random colors."""
    colors = [RED, YELLOW, BLUE, GREEN, PURPLE, ORANGE, CYAN]
    colored = ""
    for ch in line:
        if ch != ' ':
            color = random.choice(colors)
            colored += f"{color}{ch}{RESET}"
        else:
            colored += ch
    return colored


def draw_bird_status_indicators(fb):
    """Render status indicators (stunned/frozen/poisoned/bleeding) above affected birds.

    This is extracted from Tree Boss rendering so it can be reused by Owl Boss and other bosses.
    """

    now = clock.now()

    # Stunned birds get a lightning indicator with countdown
    for bird_idx in state.special.stunned_birds:
        if bird_idx < constants.layout.num_balls and not state.birds.lost[bird_idx]:
            stun_info = state.special.stunned_birds[bird_idx]
            # Only show for time-based stuns (from flowers)
            if isinstance(stun_info, dict) and stun_info.get('type') == 'flower':
                bird_x = state.birds.cols[bird_idx]
                bird_y = state.birds.y[bird_idx]
                end_time = stun_info.get('end_time', now)
                # Use ceil so counter never shows 0 until actually expired
                remaining_secs = max(1, math.ceil(end_time - now)) if end_time > now else 0

                # Show stun indicator above bird
                if 0 <= bird_y - 1 < constants.layout.height and 0 <= bird_x < constants.layout.width:
                    # Use * instead of ⚡ (unicode width issues) + digit
                    indicator = f"*{remaining_secs}"
                    stun_color = "\033[1;33m"  # Bright yellow
                    for i, c in enumerate(indicator):
                        if bird_x + i < constants.layout.width:
                            fb.put(GAME_X_OFFSET + bird_x + i, bird_y - 1 + HEADER_HEIGHT, c, stun_color)

    # Frozen birds get a snowflake indicator
    for bird_idx in state.special.frozen_birds:
        if bird_idx < constants.layout.num_balls and not state.birds.lost[bird_idx]:
            bird_x = state.birds.cols[bird_idx]
            bird_y = state.birds.y[bird_idx]
            frozen_info = state.special.frozen_birds[bird_idx]
            remaining = frozen_info.get('thaw_attempts_needed', 3) - frozen_info.get('thaw_attempts_done', 0)

            # Show frozen indicator above bird
            if 0 <= bird_y - 1 < constants.layout.height and 0 <= bird_x < constants.layout.width:
                # Show remaining thaw attempts as number
                indicator = f"❄{remaining}"
                ice_color = "\033[1;36m"  # Bright cyan
                for i, c in enumerate(indicator):
                    if bird_x + i < constants.layout.width:
                        fb.put(GAME_X_OFFSET + bird_x + i, bird_y - 1 + HEADER_HEIGHT, c, ice_color)

    # Poisoned birds get a skull indicator with countdown
    for bird_idx in state.special.poisoned_birds:
        if bird_idx < constants.layout.num_balls and not state.birds.lost[bird_idx]:
            bird_x = state.birds.cols[bird_idx]
            bird_y = state.birds.y[bird_idx]
            poison_info = state.special.poisoned_birds[bird_idx]
            death_time = poison_info.get('death_time', now)
            # Use ceil so counter never shows 0 until actually expired
            remaining_secs = max(1, math.ceil(death_time - now)) if death_time > now else 0
            cure_remaining = poison_info.get('cure_attempts_needed', 3) - poison_info.get('cure_attempts_done', 0)

            # Show poison indicator above bird (skull + time until death / presses to heal)
            if 0 <= bird_y - 1 < constants.layout.height and 0 <= bird_x < constants.layout.width:
                indicator = f"☠{remaining_secs}s♥{cure_remaining}"
                poison_color = "\033[1;32m"  # Bright green (poison)
                for i, c in enumerate(indicator):
                    if bird_x + i < constants.layout.width:
                        fb.put(GAME_X_OFFSET + bird_x + i, bird_y - 1 + HEADER_HEIGHT, c, poison_color)

    # Bleeding birds get a blood drop indicator with countdown (DON'T PRESS UP!)
    for bird_idx in state.special.bleeding_birds:
        if bird_idx < constants.layout.num_balls and not state.birds.lost[bird_idx]:
            bird_x = state.birds.cols[bird_idx]
            bird_y = state.birds.y[bird_idx]
            bleed_info = state.special.bleeding_birds[bird_idx]
            end_time = bleed_info.get('end_time', now)
            # Use ceil so counter never shows 0 until actually expired
            remaining_secs = max(1, math.ceil(end_time - now)) if end_time > now else 0
            # Get remaining lives (UP presses before death)
            lives_remaining = bleed_info.get('lives_needed', 3) - bleed_info.get('lives_lost', 0)

            # Show bleed indicator above bird (time + lives remaining)
            if 0 <= bird_y - 1 < constants.layout.height and 0 <= bird_x < constants.layout.width:
                indicator = f"!{remaining_secs}s♥{lives_remaining}"
                bleed_color = "\033[1;31m"  # Bright red (blood)
                for i, c in enumerate(indicator):
                    if bird_x + i < constants.layout.width:
                        fb.put(GAME_X_OFFSET + bird_x + i, bird_y - 1 + HEADER_HEIGHT, c, bleed_color)


def draw_birds(fb):
    """Render birds to framebuffer."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            # X sul pavimento viene disegnata in draw_floor_and_cursor
            continue

        y_pos = state.birds.y[i]
        if y_pos < 0 or y_pos >= constants.layout.height:
            continue

        # Get dynamic color for accessibility mode support
        bird_color = get_render_color(state.birds.colors[i])
        x_pos = state.birds.cols[i]

        # Check if bird is frozen or stunned (no animation)
        is_frozen = i in state.special.frozen_birds
        is_stunned = i in state.special.stunned_birds

        # Choose sprite based on direction and animation frame
        is_dinosaur = state.birds.colors[i] == DINOSAUR
        if is_frozen or is_stunned:
            # Frozen/stunned birds don't animate - use static sprite based on direction
            if state.birds.vy[i] == -1:
                sprite = DINOSAUR_UP_1 if is_dinosaur else BIRD_UP_1
            else:
                sprite = DINOSAUR_DOWN_1 if is_dinosaur else BIRD_DOWN_1
        else:
            # Normal animation
            if state.birds.vy[i] == -1:  # Moving up
                if is_dinosaur:
                    sprite = DINOSAUR_UP_1 if (state.game.frame_count // 3) % 2 == 0 else DINOSAUR_UP_2
                else:
                    sprite = BIRD_UP_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_UP_2
            else:  # Moving down or stationary
                if is_dinosaur:
                    sprite = DINOSAUR_DOWN_1 if (state.game.frame_count // 3) % 2 == 0 else DINOSAUR_DOWN_2
                else:
                    sprite = BIRD_DOWN_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_DOWN_2

        # Special handling for different bird types
        if is_frozen:
            # Frozen birds turn light blue (cyan)
            bird_color = '\033[1;96m'  # Bright cyan (light blue)
        elif state.birds.colors[i] == STEALTH:
            tangible = i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0
            if tangible:
                bird_color = get_render_color(WHITE)
            else:
                # Smooth flicker: 6-step gradient from bright to dim and back
                stealth_phase = (state.game.frame_count // 3) % 6
                stealth_colors = [
                    '\033[38;5;255m',  # Bright white
                    '\033[38;5;250m',  # Light gray
                    '\033[38;5;245m',  # Medium gray
                    '\033[38;5;240m',  # Dark gray
                    '\033[38;5;245m',  # Medium gray (going back up)
                    '\033[38;5;250m',  # Light gray (going back up)
                ]
                bird_color = stealth_colors[stealth_phase]
        elif state.birds.colors[i] == BLUE and state.birds.power_used[i]:
            bird_color = get_render_color(CYAN)

        # Apply bold modifier for foreground game elements
        bird_color = apply_bold(bird_color)

        # Patchwork uses multicolor rendering (fixed colors by position)
        is_patchwork = state.birds.colors[i] == PATCHWORK and not is_frozen
        # Fixed color pattern: left=YELLOW, center=RED, right=BLUE
        patchwork_colors = [YELLOW, RED, BLUE]

        # Clockwork uses special beak coloring based on charge
        is_clockwork = state.birds.colors[i] == CLOCKWORK and not is_frozen
        clockwork_charge = state.special.clockwork_charge.get(i, 2) if is_clockwork else 0
        clockwork_blink = (state.game.frame_count // 5) % 2 == 0  # Blink every 5 frames

        # RAINBOW uses animated multicolor that fades based on charge
        is_rainbow = state.birds.colors[i] == RAINBOW and not is_frozen
        # Bright vivid rainbow colors (256-color ANSI)
        rainbow_colors = [
            '\033[38;5;196m',  # Bright red
            '\033[38;5;208m',  # Bright orange
            '\033[38;5;226m',  # Bright yellow
            '\033[38;5;46m',  # Bright green
            '\033[38;5;51m',  # Bright cyan
            '\033[38;5;21m',  # Bright blue
            '\033[38;5;201m',  # Bright magenta/pink
        ]
        rainbow_charge = state.special.rainbow_charge.get(i, 100) if is_rainbow else 100
        # Fade factor: at 100% charge = full brightness, at 0% = very dim
        rainbow_brightness = max(0.2, rainbow_charge / 100.0)

        # TWISTER uses gray body with cyan wings
        is_twister = state.birds.colors[i] == TWISTER and not is_frozen

        # Render bird sprite
        for line_idx, line in enumerate(sprite):
            by = y_pos + line_idx
            if 0 <= by < constants.layout.height:
                x_off = len(line) // 2
                for ci, char in enumerate(line):
                    if char != ' ':
                        if is_patchwork:
                            # Color based on horizontal position only (stable across frames)
                            char_color = apply_bold(patchwork_colors[ci % 3])
                        elif is_clockwork and char in ("'", "."):
                            # Clockwork beak (. when up, ' when down) - shows charge status
                            if clockwork_charge == 0:
                                # Empty: red blinking
                                char_color = apply_bold(RED if clockwork_blink else DARK_GRAY)
                            elif clockwork_charge < 3:
                                # Discharging: yellow blinking
                                char_color = apply_bold(YELLOW if clockwork_blink else CLOCKWORK)
                            else:
                                # Full: green blinking
                                char_color = apply_bold(GREEN if clockwork_blink else CLOCKWORK)
                        elif is_rainbow:
                            # Fast animated rainbow colors cycling + fade based on charge
                            color_idx = (state.game.frame_count // 2 + ci * 2 + line_idx) % len(rainbow_colors)
                            base_color = rainbow_colors[color_idx]
                            # Apply brightness fade based on charge
                            if rainbow_brightness < 0.3:
                                char_color = '\033[38;5;240m'  # Dark gray - dying
                            elif rainbow_brightness < 0.5:
                                char_color = '\033[38;5;245m'  # Medium gray - fading
                            else:
                                char_color = base_color  # Full vivid colors
                        elif is_twister:
                            # Gray body with cyan wings
                            if char in ('<', '>', '/', '\\', '_'):
                                char_color = apply_bold(CYAN)
                            else:
                                char_color = apply_bold(DARK_GRAY)
                        else:
                            char_color = bird_color
                        fb.put(GAME_X_OFFSET + x_pos - x_off + ci, by + HEADER_HEIGHT, char, char_color)

        # Purple bird charging orb
        if state.birds.colors[i] == PURPLE and state.special.purple_state[i] == 2:
            start_time = state.special.purple_charge_started_frame[i]  # Now stores timestamp
            elapsed_seconds = int(clock.now() - start_time)
            s = max(0, min(3, elapsed_seconds))
            sym = '⋅' if s <= 0 else ('•' if s == 1 else '●')
            orb_y = y_pos + 1
            if 0 <= orb_y < constants.layout.height:
                fb.put(GAME_X_OFFSET + x_pos, orb_y + HEADER_HEIGHT, sym, get_render_color(PURPLE))
