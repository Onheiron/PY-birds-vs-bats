import os
import sys
import random

from sprites import *

import constants
from functions import *
import render
import state

# Pre-build static parts
ceiling = "=" * constants.WIDTH
floor = ceiling

# Color helpers: map HP ratio to RGB truecolor escape
def _rgb_escape(r: int, g: int, b: int) -> str:
    # Decide if terminal likely supports truecolor (COLORTERM hint).
    try:
        ct = os.environ.get('COLORTERM', '').lower()
    except Exception:
        ct = ''
    truecolor = ct in ('truecolor', '24bit')

    # Clamp values
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))

    if truecolor:
        return f"\033[38;2;{r};{g};{b}m"

    # Fallback to 256-color approximation: map RGB -> 6x6x6 cube index
    def _rgb_to_256(rr, gg, bb):
        # map 0-255 -> 0-5
        r6 = int(rr * 5 / 255)
        g6 = int(gg * 5 / 255)
        b6 = int(bb * 5 / 255)
        return 16 + (36 * r6) + (6 * g6) + b6

    code = _rgb_to_256(r, g, b)
    return f"\033[38;5;{code}m"

def color_from_hp(base_rgb: tuple, hp: int, max_hp: int) -> str:
    hp_percentage = hp / max_hp if max_hp > 0 else 0
    try:
        r = int(base_rgb[0] * hp_percentage)
        g = int(base_rgb[1] * hp_percentage)
        b = int(base_rgb[2] * hp_percentage)
    except Exception:
        r = g = b = 0
    return _rgb_escape(r, g, b)

def get_key():
    """Non-blocking key read for Windows and Unix"""
    if os.name == 'nt':
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key == b'\xe0':  # Arrow key prefix
                key = msvcrt.getch()
                if key == b'K':  # Left
                    return 'LEFT'
                elif key == b'M':  # Right
                    return 'RIGHT'
                elif key == b'H':  # Up
                    return 'UP'
                elif key == b'P':  # Down
                    return 'DOWN'
            elif key == b' ':  # Space
                return 'SPACE'
            elif key == b'\x03':  # Ctrl+C
                return 'QUIT'
            return None
        return None
    else:
        # Unix/macOS version - truly non-blocking with fcntl
        # Read all available input to avoid buffer buildup of repeated keys.
        # Non-blocking read will return available bytes or '' if none.
        buf = sys.stdin.read(4096)

        if not buf:
            return None

        # Parse the buffer and pick the last meaningful key event.
        last = None
        i = 0
        L = len(buf)
        while i < L:
            ch = buf[i]
            # Escape sequences (arrows) are 3 chars: \x1b[A etc.
            if ch == '\x1b' and i + 2 < L:
                seq = buf[i:i+3]
                if seq == '\x1b[D':
                    last = 'LEFT'
                    i += 3
                    continue
                elif seq == '\x1b[C':
                    last = 'RIGHT'
                    i += 3
                    continue
                elif seq == '\x1b[A':
                    last = 'UP'
                    i += 3
                    continue
                elif seq == '\x1b[B':
                    last = 'DOWN'
                    i += 3
                    continue
            # Single-char controls
            if ch == ' ':
                last = 'SPACE'
            elif ch == '\x03' or ch == 'q':
                last = 'QUIT'
            else:
                # printable char
                if len(ch) == 1 and ch.isprintable():
                    last = ch
            i += 1

        return last
    
def render_clockwork_line(line, charge, blink_on):
    """Render a CLOCKWORK bird line with special coloring."""
    colored = ""
    for ch in line:
        if ch == '.':
            if charge == 0:
                colored += f"{DARK_GRAY}{ch}{RESET}"
            elif charge == 1:
                colored += f"{ORANGE}{ch}{RESET}"
            elif charge == 2:
                colored += f"{YELLOW}{ch}{RESET}"
            else:
                colored += f"{GREEN}{ch}{RESET}"
        elif ch == "'":
            if blink_on:
                colored += f"{YELLOW}{ch}{RESET}"
            else:
                colored += f"{DARK_GRAY}{ch}{RESET}"
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


def render_header(output, ceiling):
    """Rendering header con score, level, lives, prestige"""
    # Recompute level from current score
    level = compute_level_from_score(state.score)
    next_level_score = calculate_level_threshold(level + 1)
    lives_display = "●" * state.lives + "◌" * (5 - state.lives)
    
    # Compute prestige for display
    prestige_val = compute_prestige()
    if prestige_val is None:
        prestige_val = 1.0
    prestige_display = f"{prestige_val:.2f}x"
    
    base_score_line = f"SCORE: {int(state.score)}  |  LEVEL: {level}  |  NEXT: {next_level_score}  |  LIVES: {lives_display}  |  PRESTIGE: {prestige_display}"
    
    output += f"\033[1;1H{base_score_line}\n"
    output += f"\033[2;1H{ceiling}\n"
    
    # Render notifications
    active_notifications = [n for n in state.notifications if n[1] > state.frame_count]
    if active_notifications:
        text, exp = active_notifications[0]
        footer_y = constants.HEIGHT + 3
        display_text = text[:constants.WIDTH]
        output += f"\033[{footer_y};1H{YELLOW}{display_text}{RESET}\n"
    state.notifications[:] = active_notifications
    
    return output

def render_starting_line(output):
    """Rendering linea di partenza con indicatori power-up"""
    starting_line_y = constants.STARTING_LINE + 2
    if 3 <= starting_line_y < constants.HEIGHT + 2:
        # Tailwind: blue carets, normale: dashed line
        if state.powerups.get('tailwind_active'):
            dashed_line = "^ " * (constants.WIDTH // 2)
            output += f"\033[{starting_line_y};1H{BLUE}{dashed_line[:constants.WIDTH]}{RESET}"
        else:
            dashed_line = "- " * (constants.WIDTH // 2)
            output += f"\033[{starting_line_y};1H{DARK_GRAY}{dashed_line[:constants.WIDTH]}{RESET}"
        
        # Power-up indicators on affected lanes
        lanes_to_check = get_affected_lanes()
        for lane in lanes_to_check:
            lane_x = constants.LANE_POSITIONS[lane]
            bird_in_lane = find_bird_in_lane(lane)
            
            if bird_in_lane >= 0 and not state.ball_lost[bird_in_lane]:
                # Bounce boost: blue ^
                if state.powerups['bounce_boost_active'] and state.ball_vy[bird_in_lane] == 1:
                    output += f"\033[{starting_line_y};{lane_x}H{BLUE}\033[1m^{RESET}"
                # Suction: red v
                elif state.powerups['suction_active'] and state.ball_vy[bird_in_lane] == -1:
                    output += f"\033[{starting_line_y};{lane_x}H{RED}\033[1mv{RESET}"
    
    return output

def render_obstacles(output):
    """Rendering ostacoli"""
    for obs in state.obstacles:
        max_hp = constants.OBSTACLE_MAX_HP_BY_TIER.get(obs.get('tier', 1), obs.get('hp', 1))
        obs_color = render.color_from_hp(constants.OBSTACLES_BASE_COLOR_RGB, obs.get('hp', 0), max_hp)
        
        for line_idx, line in enumerate(OBSTACLE_SPRITE):
            y_pos = obs['y_pos'] + line_idx + 2
            if 3 <= y_pos < constants.HEIGHT + 2:
                x_pos = constants.LANE_POSITIONS[obs['lane']] - 1
                output += f"\033[{y_pos};{x_pos}H{obs_color}{line}{RESET}"
    
    return output

def render_bats(output):
    """Rendering pipistrelli"""
    for bat in state.bats:
        bat_hp = bat.get('hp', 0)
        bat_max = bat.get('max_hp', bat_hp if bat_hp > 0 else 1)
        bat_color = render.color_from_hp(constants.BATS_BASE_COLOR_RGB, bat_hp, bat_max)
        
        bat_sprite = BAT_FRAME_1 if (state.frame_count // 3) % 2 == 0 else BAT_FRAME_2
        
        for line_idx, line in enumerate(bat_sprite):
            y_pos = bat['y_pos'] + line_idx + 2
            if 3 <= y_pos < constants.HEIGHT + 2:
                output += f"\033[{y_pos};{bat['x_pos']}H{bat_color}{line}{RESET}"
    
    return output

def render_loot(output):
    """Rendering loot items (uova e power-up)"""
    for loot in state.loot_items:
        y_pos = loot['y_pos'] + 2
        if 3 <= y_pos < constants.HEIGHT + 2:
            loot_type = loot['type']
            rarity = loot['rarity']
            
            # Determine color based on rarity
            if rarity == 'common':
                power_color = YELLOW
            elif rarity == 'uncommon':
                power_color = RED
            elif rarity == 'rare':
                power_color = BLUE
            else:
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
                output += f"\033[{y_pos};{loot['x_pos']}H{COOKIE}•{RESET}"
            elif loot_type == 'dinosaur_egg':
                output += f"\033[{y_pos};{loot['x_pos']}H{DINOSAUR}⬯{RESET}"
            elif loot_type == 'glitch_egg':
                output += f"\033[{y_pos};{loot['x_pos']}H{GLITCH}⬯{RESET}"
            # Cursor power-ups
            elif 'wide_cursor' in loot_type:
                output += f"\033[{y_pos};{loot['x_pos']}H{power_color}↔{RESET}"
            elif 'bounce_boost' in loot_type:
                output += f"\033[{y_pos};{loot['x_pos']}H{power_color}↺{RESET}"
            elif 'suction' in loot_type:
                output += f"\033[{y_pos};{loot['x_pos']}H{power_color}⥥{RESET}"
            elif 'tailwind' in loot_type:
                output += f"\033[{y_pos};{loot['x_pos']}H{power_color}༄{RESET}"
            elif 'shuffle' in loot_type:
                output += f"\033[{y_pos};{loot['x_pos']}H{power_color}𖦹{RESET}"
    
    return output

def render_projectiles(output):
    """Rendering proiettili"""
    for proj in state.red_projectiles:
        y_pos = proj['y_pos'] + 2
        if 3 <= y_pos < constants.HEIGHT + 2:
            symbol = "•" if proj.get('powered', False) else "⋅"
            proj_color = proj.get('color', RED)
            output += f"\033[{y_pos};{proj['x_pos']}H{proj_color}{symbol}{RESET}"
    
    return output

def render_birds(output):
    """Rendering uccelli attivi"""
    for b in range(constants.NUM_BALLS):
        if not state.ball_lost[b]:
            # Check if slowed
            is_slowed = b in state.speed_boosts and state.speed_boosts[b] < 0 and state.ball_vy[b] == 1
            
            # Choose sprite based on direction and animation
            if state.ball_vy[b] == -1:  # Moving up
                if state.ball_colors[b] == CLOCKWORK:
                    try:
                        c = state.clockwork_charge.get(b, constants.CLOCKWORK_INITIAL_CHARGE)
                    except Exception:
                        c = constants.CLOCKWORK_INITIAL_CHARGE
                    if c == 0:
                        sprite = BIRD_UP_2
                    elif c == 1:
                        sprite = BIRD_UP_1 if (state.frame_count // 6) % 2 == 0 else BIRD_UP_2
                    else:
                        sprite = BIRD_UP_1 if (state.frame_count // 3) % 2 == 0 else BIRD_UP_2
                else:
                    if state.ball_colors[b] == DINOSAUR:
                        sprite = DINOSAUR_UP_1 if (state.frame_count // 3) % 2 == 0 else DINOSAUR_UP_2
                    elif state.ball_colors[b] == BLUE and state.bird_power_used[b]:
                        sprite = BIRD_UP_1
                    else:
                        sprite = BIRD_UP_1 if (state.frame_count // 3) % 2 == 0 else BIRD_UP_2
            else:  # Moving down
                if is_slowed:
                    sprite = BIRD_DOWN_2
                else:
                    if state.ball_colors[b] == CLOCKWORK:
                        c = state.clockwork_charge.get(b, constants.CLOCKWORK_INITIAL_CHARGE)
                        if c == 0:
                            sprite = BIRD_DOWN_2
                        elif c == 1:
                            sprite = BIRD_DOWN_1 if (state.frame_count // 6) % 2 == 0 else BIRD_DOWN_2
                        else:
                            sprite = BIRD_DOWN_1 if (state.frame_count // 3) % 2 == 0 else BIRD_DOWN_2
                    else:
                        if state.ball_colors[b] == DINOSAUR:
                            sprite = DINOSAUR_DOWN_1 if (state.frame_count // 3) % 2 == 0 else DINOSAUR_DOWN_2
                        else:
                            sprite = BIRD_DOWN_1 if (state.frame_count // 3) % 2 == 0 else BIRD_DOWN_2
                    
                        # GLITCH: mix sprite pieces
                        if state.ball_colors[b] == GLITCH:
                            if state.ball_vy[b] == -1:
                                f1, f2 = BIRD_UP_1, BIRD_UP_2
                            else:
                                f1, f2 = BIRD_DOWN_1, BIRD_DOWN_2
                            
                            mixed = []
                            for li in range(min(len(f1), len(f2))):
                                line1, line2 = f1[li], f2[li]
                                maxlen = max(len(line1), len(line2))
                                line1, line2 = line1.ljust(maxlen), line2.ljust(maxlen)
                                chars = [random.choice([c1, c2]) for c1, c2 in zip(line1, line2)]
                                mixed.append(''.join(chars))
                            sprite = mixed
            
            # Choose color
            if state.ball_colors[b] == STEALTH:
                tangible = b in state.stealth_timers and state.stealth_timers.get(b, 0) > 0
                period = max(4, int(2 / constants.BASE_SLEEP))
                phase = (state.frame_count % period) / period
                color = DARK_GRAY if phase < 0.5 else "\033[8m"
                if tangible:
                    color = WHITE
            elif state.ball_colors[b] == BLUE and state.bird_power_used[b]:
                color = CYAN
            else:
                color = state.ball_colors[b]
            
            # Draw bird sprite
            for line_idx, line in enumerate(sprite):
                y_pos = state.ball_y[b] + line_idx + 2
                if 3 <= y_pos < constants.HEIGHT + 2:
                    x_offset = len(line) // 2
                    
                    if state.ball_colors[b] == CLOCKWORK:
                        c = state.clockwork_charge.get(b, constants.CLOCKWORK_INITIAL_CHARGE)
                        blink_period = max(1, int(0.6 / constants.BASE_SLEEP))
                        blink_on = ((state.frame_count // blink_period) % 2) == 0
                        colored = render_clockwork_line(line, c, blink_on)
                        output += f"\033[{y_pos};{state.ball_cols[b]-x_offset}H{colored}"
                    elif state.ball_colors[b] == PATCHWORK:
                        colored = render_patchwork_line(line)
                        output += f"\033[{y_pos};{state.ball_cols[b]-x_offset}H{colored}"
                    else:
                        output += f"\033[{y_pos};{state.ball_cols[b]-x_offset}H{color}{line}{RESET}"
                
                # PURPLE charging orb
                if state.ball_colors[b] == PURPLE and state.purple_state[b] == 2:
                    start_frame = state.purple_charge_started_frame[b]
                    if state.frame_count >= start_frame:
                        elapsed_seconds = int((state.frame_count - start_frame) * constants.BASE_SLEEP)
                        s = max(0, min(3, elapsed_seconds))
                        sym = '⋅' if s <= 0 else ('•' if s == 1 else '●')
                        orb_y = state.ball_y[b] + 1 + 2 - 1
                        if 3 <= orb_y < constants.HEIGHT + 2:
                            output += f"\033[{orb_y};{state.ball_cols[b]}H{PURPLE}{sym}{RESET}"
    
    return output

def render_floor_and_cursor(output, floor):
    """Rendering pavimento, uccelli persi e cursore giocatore"""
    # Floor
    output += f"\033[{constants.HEIGHT+2};1H{floor}\n"
    
    # Lost birds on floor
    for b in range(constants.NUM_BALLS):
        if state.ball_lost[b]:
            output += f"\033[{constants.HEIGHT+2};{state.ball_cols[b]}H\033[90mX{RESET}"
    
    # Player cursor
    cursor_x = constants.LANE_POSITIONS[state.player_lane] - 1
    fallback_cursor_color = YELLOW if state.selected_lane is not None else GREEN
    
    def _grade_letter_color(letter):
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
    
    # Wide cursor or normal
    if state.powerups['wide_cursor_active']:
        half_width = state.powerups['wide_cursor_lanes'] // 2
        cursor_str = ""
        for offset in range(-half_width, half_width + 1):
            lane = state.player_lane + offset
            if 0 <= lane < 9:
                lane_x = constants.LANE_POSITIONS[lane] - 1
                bird_idx = state.random_lanes.index(lane) if lane in state.random_lanes else -1
                
                if bird_idx >= 0 and not state.ball_lost[bird_idx]:
                    letter, _ = compute_grade_from_xp(state.per_bird_xp[bird_idx])
                    color = _grade_letter_color(letter)
                else:
                    color = fallback_cursor_color
                
                glyph = '^'
                cursor_str += f"\033[{constants.HEIGHT+3};{lane_x}H{color}\033[1m[{glyph}]{RESET}"
        output += cursor_str + "\n"
    else:
        bird_idx = state.random_lanes.index(state.player_lane) if state.player_lane in state.random_lanes else -1
        if bird_idx >= 0 and not state.ball_lost[bird_idx]:
            letter, _ = compute_grade_from_xp(state.per_bird_xp[bird_idx])
            color = _grade_letter_color(letter)
        else:
            color = fallback_cursor_color
        
        glyph = '^'
        output += f"\033[{constants.HEIGHT+3};{cursor_x}H{color}\033[1m[{glyph}]{RESET}\n"
    
    # Highlight selected lane in swap mode
    if state.selected_lane is not None:
        selected_x = constants.LANE_POSITIONS[state.selected_lane] - 1
        output += f"\033[{constants.HEIGHT+3};{selected_x}H{YELLOW}\033[1m[*]{RESET}"
    
    return output

def render_footer(output):
    """Rendering footer con comandi e XP overlay opzionale"""
    active_balls = sum(1 for lost in state.ball_lost if not lost)
    swap_hint = " | Press SPACE again to swap or cancel" if state.selected_lane is not None else ""
    output += f"\033[{constants.HEIGHT+4};1HUse ← → to move, ↑ to bounce, Ctrl+C to quit | Birds: {active_balls}/{constants.NUM_BALLS}{swap_hint}"
    
    if state.show_xp_overlay:
        parts = []
        for i in range(constants.NUM_BALLS):
            label, _ = compute_grade_from_xp(state.per_bird_xp[i])
            parts.append(f"{label}({int(state.per_bird_xp[i])})")
        xp_summary = ' '.join(parts)
        output += f"\033[{constants.HEIGHT+5};1HXP: {xp_summary[:constants.WIDTH]}{RESET}"
    
    return output

def render_pause_overlay(output):
    """Rendering overlay PAUSED"""
    if state.paused:
        pause_y = 2 + (constants.HEIGHT // 2)
        pause_x = max(1, (constants.WIDTH // 2) - 3)
        output += f"\033[{pause_y};{pause_x}H{YELLOW}\033[1mPAUSED{RESET}"
    return output

def render_game():
    ###########################################################################
    ### -------- RENDERING SCHERMO --------
    ###########################################################################

    # Build output buffer
    output = "\033[2J\033[H"
    
    # Recompute level for rendering
    state.level = compute_level_from_score(state.score)
    
    # Render all components using dedicated functions
    output = render_header(output, ceiling)
    output = render_starting_line(output)
    output = render_obstacles(output)
    output = render_bats(output)
    output = render_loot(output)
    output = render_projectiles(output)
    output = render_birds(output)
    output = render_floor_and_cursor(output, floor)
    output = render_footer(output)
    output = render_pause_overlay(output)

    # === Output su schermo ===
    # Write all at once - handle blocking errors gracefully
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except BlockingIOError:
        # Buffer full, skip this frame
        pass