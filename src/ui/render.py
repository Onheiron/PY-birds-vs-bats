import os
import sys
import random
import re

if os.name == 'nt':
    import msvcrt

from src.entities.sprites import *
from src.core import constants
from src.functions import compute_level_from_score, calculate_level_threshold, compute_prestige, compute_grade_from_xp, get_affected_lanes, find_bird_in_lane
from src.core import state

# Pre-build static parts
ceiling = "=" * constants.layout.width
floor = ceiling

# =============================================================================
# FRAMEBUFFER - Double buffering per rendering differenziale
# =============================================================================

class FrameBuffer:
    """
    Virtual framebuffer for differential rendering.
    Stores character and color for each cell, outputs only changed cells.
    """

    def __init__(self, width, height):
        self.width = width
        self.height = height
        # Each cell: (char, color_code)
        # Current frame being built
        self.current = [[(' ', '') for _ in range(width)] for _ in range(height)]
        # Previous frame (already displayed)
        self.previous = [[(' ', '') for _ in range(width)] for _ in range(height)]
        self.first_frame = True

    def clear(self):
        """Clear current buffer to spaces."""
        for y in range(self.height):
            for x in range(self.width):
                self.current[y][x] = (' ', '')

    def put(self, x, y, char, color=''):
        """Put a character at position with optional color."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.current[y][x] = (char, color)

    def put_string(self, x, y, text, color=''):
        """Put a string starting at position."""
        # Strip ANSI codes from text to get actual characters
        clean_text = re.sub(r'\033\[[0-9;]*m', '', text)
        for i, char in enumerate(clean_text):
            if x + i < self.width:
                self.put(x + i, y, char, color)

    def put_colored_string(self, x, y, text):
        """Put string that may contain ANSI color codes."""
        # Parse text extracting color codes and characters
        current_color = ''
        pos = 0
        i = 0
        while i < len(text):
            if text[i] == '\033':
                # Find end of ANSI sequence
                end = text.find('m', i)
                if end != -1:
                    code = text[i:end+1]
                    if code == RESET:
                        current_color = ''
                    else:
                        current_color = code
                    i = end + 1
                    continue
            # Regular character
            if x + pos < self.width and 0 <= y < self.height:
                self.current[y][x + pos] = (text[i], current_color)
            pos += 1
            i += 1

    def render(self):
        """Generate output string with only changed cells."""
        output = []
        last_color = ''

        if self.first_frame:
            # First frame: clear screen and render everything
            output.append("\033[2J\033[H")
            self.first_frame = False

            for y in range(self.height):
                output.append(f"\033[{y+1};1H")  # Move to line start
                line_chars = []
                for x in range(self.width):
                    char, color = self.current[y][x]
                    if color != last_color:
                        if color:
                            line_chars.append(color)
                        else:
                            line_chars.append(RESET)
                        last_color = color
                    line_chars.append(char)
                output.append(''.join(line_chars))
        else:
            # Differential rendering: only output changed cells
            for y in range(self.height):
                x = 0
                while x < self.width:
                    if self.current[y][x] != self.previous[y][x]:
                        # Find run of changed cells
                        run_start = x
                        while x < self.width and self.current[y][x] != self.previous[y][x]:
                            x += 1

                        # Output this run
                        output.append(f"\033[{y+1};{run_start+1}H")
                        for rx in range(run_start, x):
                            char, color = self.current[y][rx]
                            if color != last_color:
                                if color:
                                    output.append(color)
                                else:
                                    output.append(RESET)
                                last_color = color
                            output.append(char)
                    else:
                        x += 1

        # Reset color at end
        if last_color:
            output.append(RESET)

        # Swap buffers
        self.previous, self.current = self.current, self.previous
        # Clear new current buffer
        for y in range(self.height):
            for x in range(self.width):
                self.current[y][x] = (' ', '')

        return ''.join(output)


# Global framebuffer instance
_framebuffer = None

def get_framebuffer():
    """Get or create the global framebuffer."""
    global _framebuffer
    if _framebuffer is None:
        # Height: header(2) + game area + floor(1) + cursor(1) + notification(1) + footer(2) + extra
        total_height = constants.layout.height + 8
        # Width: molto più largo per header con prestige
        _framebuffer = FrameBuffer(constants.layout.width + 60, total_height)
    return _framebuffer

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
    level = compute_level_from_score(state.game.score)
    next_level_score = calculate_level_threshold(level + 1)
    lives_display = "●" * state.game.lives + "◌" * (5 - state.game.lives)
    
    # Compute prestige for display
    prestige_val = compute_prestige()
    if prestige_val is None:
        prestige_val = 1.0
    prestige_display = f"{prestige_val:.2f}x"
    
    base_score_line = f"SCORE: {int(state.game.score)}  |  LEVEL: {level}  |  NEXT: {next_level_score}  |  LIVES: {lives_display}  |  PRESTIGE: {prestige_display}"
    
    output += f"\033[1;1H{base_score_line}\n"
    output += f"\033[2;1H{ceiling}\n"
    
    # Render notifications
    active_notifications = [n for n in state.ui.notifications if n[1] > state.game.frame_count]
    if active_notifications:
        text, exp = active_notifications[0]
        footer_y = constants.layout.height + 3
        display_text = text[:constants.layout.width]
        output += f"\033[{footer_y};1H{YELLOW}{display_text}{RESET}\n"
    state.ui.notifications[:] = active_notifications
    
    return output

def render_starting_line(output):
    """Rendering linea di partenza con indicatori power-up"""
    starting_line_y = constants.layout.starting_line + 2
    if 3 <= starting_line_y < constants.layout.height + 2:
        # Tailwind: blue carets, normale: dashed line
        if state.powerups.tailwind_active:
            dashed_line = "^ " * (constants.layout.width // 2)
            output += f"\033[{starting_line_y};1H{BLUE}{dashed_line[:constants.layout.width]}{RESET}"
        else:
            dashed_line = "- " * (constants.layout.width // 2)
            output += f"\033[{starting_line_y};1H{DARK_GRAY}{dashed_line[:constants.layout.width]}{RESET}"
        
        # Power-up indicators on affected lanes
        lanes_to_check = get_affected_lanes()
        for lane in lanes_to_check:
            lane_x = constants.layout.lane_positions[lane]
            bird_in_lane = find_bird_in_lane(lane)
            
            if bird_in_lane >= 0 and not state.birds.lost[bird_in_lane]:
                # Bounce boost: blue ^
                if state.powerups.bounce_boost_active and state.birds.vy[bird_in_lane] == 1:
                    output += f"\033[{starting_line_y};{lane_x}H{BLUE}\033[1m^{RESET}"
                # Suction: red v
                elif state.powerups.suction_active and state.birds.vy[bird_in_lane] == -1:
                    output += f"\033[{starting_line_y};{lane_x}H{RED}\033[1mv{RESET}"
    
    return output

def render_obstacles(output):
    """Rendering ostacoli"""
    for obs in state.enemies.obstacles:
        max_hp = constants.obstacle.max_hp_by_tier.get(obs.get('tier', 1), obs.get('hp', 1))
        obs_color = color_from_hp(constants.colors.obstacles_base_rgb, obs.get('hp', 0), max_hp)
        
        for line_idx, line in enumerate(OBSTACLE_SPRITE):
            y_pos = obs['y_pos'] + line_idx + 2
            if 3 <= y_pos < constants.layout.height + 2:
                x_pos = constants.layout.lane_positions[obs['lane']] - 1
                output += f"\033[{y_pos};{x_pos}H{obs_color}{line}{RESET}"
    
    return output

def render_bats(output):
    """Rendering pipistrelli"""
    for bat in state.enemies.bats:
        bat_hp = bat.get('hp', 0)
        bat_max = bat.get('max_hp', bat_hp if bat_hp > 0 else 1)
        bat_color = color_from_hp(constants.colors.bats_base_rgb, bat_hp, bat_max)
        
        bat_sprite = BAT_FRAME_1 if (state.game.frame_count // 3) % 2 == 0 else BAT_FRAME_2
        
        for line_idx, line in enumerate(bat_sprite):
            y_pos = bat['y_pos'] + line_idx + 2
            if 3 <= y_pos < constants.layout.height + 2:
                output += f"\033[{y_pos};{bat['x_pos']}H{bat_color}{line}{RESET}"
    
    return output

def render_loot(output):
    """Rendering loot items (uova e power-up)"""
    for loot in state.items.loot_items:
        y_pos = loot['y_pos'] + 2
        if 3 <= y_pos < constants.layout.height + 2:
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
    for proj in state.special.red_projectiles:
        y_pos = proj['y_pos'] + 2
        if 3 <= y_pos < constants.layout.height + 2:
            symbol = "•" if proj.get('powered', False) else "⋅"
            proj_color = proj.get('color', RED)
            output += f"\033[{y_pos};{proj['x_pos']}H{proj_color}{symbol}{RESET}"
    
    return output

def render_birds(output):
    """Rendering uccelli attivi"""
    for b in range(constants.layout.num_balls):
        if not state.birds.lost[b]:
            # Check if slowed
            is_slowed = b in state.special.speed_boosts and state.special.speed_boosts[b] < 0 and state.birds.vy[b] == 1
            
            # Choose sprite based on direction and animation
            if state.birds.vy[b] == -1:  # Moving up
                if state.birds.colors[b] == CLOCKWORK:
                    try:
                        c = state.special.clockwork_charge.get(b, constants.clockwork.initial_charge)
                    except Exception:
                        c = constants.clockwork.initial_charge
                    if c == 0:
                        sprite = BIRD_UP_2
                    elif c == 1:
                        sprite = BIRD_UP_1 if (state.game.frame_count // 6) % 2 == 0 else BIRD_UP_2
                    else:
                        sprite = BIRD_UP_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_UP_2
                else:
                    if state.birds.colors[b] == DINOSAUR:
                        sprite = DINOSAUR_UP_1 if (state.game.frame_count // 3) % 2 == 0 else DINOSAUR_UP_2
                    elif state.birds.colors[b] == BLUE and state.birds.power_used[b]:
                        sprite = BIRD_UP_1
                    else:
                        sprite = BIRD_UP_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_UP_2
            else:  # Moving down
                if is_slowed:
                    sprite = BIRD_DOWN_2
                else:
                    if state.birds.colors[b] == CLOCKWORK:
                        c = state.special.clockwork_charge.get(b, constants.clockwork.initial_charge)
                        if c == 0:
                            sprite = BIRD_DOWN_2
                        elif c == 1:
                            sprite = BIRD_DOWN_1 if (state.game.frame_count // 6) % 2 == 0 else BIRD_DOWN_2
                        else:
                            sprite = BIRD_DOWN_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_DOWN_2
                    else:
                        if state.birds.colors[b] == DINOSAUR:
                            sprite = DINOSAUR_DOWN_1 if (state.game.frame_count // 3) % 2 == 0 else DINOSAUR_DOWN_2
                        else:
                            sprite = BIRD_DOWN_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_DOWN_2
                    
                        # GLITCH: mix sprite pieces
                        if state.birds.colors[b] == GLITCH:
                            if state.birds.vy[b] == -1:
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
            if state.birds.colors[b] == STEALTH:
                tangible = b in state.special.stealth_timers and state.special.stealth_timers.get(b, 0) > 0
                period = max(4, int(2 / constants.timing.base_sleep))
                phase = (state.game.frame_count % period) / period
                color = DARK_GRAY if phase < 0.5 else "\033[8m"
                if tangible:
                    color = WHITE
            elif state.birds.colors[b] == BLUE and state.birds.power_used[b]:
                color = CYAN
            else:
                color = state.birds.colors[b]
            
            # Draw bird sprite
            for line_idx, line in enumerate(sprite):
                y_pos = state.birds.y[b] + line_idx + 2
                if 3 <= y_pos < constants.layout.height + 2:
                    x_offset = len(line) // 2
                    
                    if state.birds.colors[b] == CLOCKWORK:
                        c = state.special.clockwork_charge.get(b, constants.clockwork.initial_charge)
                        blink_period = max(1, int(0.6 / constants.timing.base_sleep))
                        blink_on = ((state.game.frame_count // blink_period) % 2) == 0
                        colored = render_clockwork_line(line, c, blink_on)
                        output += f"\033[{y_pos};{state.birds.cols[b]-x_offset}H{colored}"
                    elif state.birds.colors[b] == PATCHWORK:
                        colored = render_patchwork_line(line)
                        output += f"\033[{y_pos};{state.birds.cols[b]-x_offset}H{colored}"
                    else:
                        output += f"\033[{y_pos};{state.birds.cols[b]-x_offset}H{color}{line}{RESET}"
                
                # PURPLE charging orb
                if state.birds.colors[b] == PURPLE and state.special.purple_state[b] == 2:
                    start_frame = state.special.purple_charge_started_frame[b]
                    if state.game.frame_count >= start_frame:
                        elapsed_seconds = int((state.game.frame_count - start_frame) * constants.timing.base_sleep)
                        s = max(0, min(3, elapsed_seconds))
                        sym = '⋅' if s <= 0 else ('•' if s == 1 else '●')
                        orb_y = state.birds.y[b] + 1 + 2 - 1
                        if 3 <= orb_y < constants.layout.height + 2:
                            output += f"\033[{orb_y};{state.birds.cols[b]}H{PURPLE}{sym}{RESET}"
    
    return output

def render_floor_and_cursor(output, floor):
    """Rendering pavimento, uccelli persi e cursore giocatore"""
    # Floor
    output += f"\033[{constants.layout.height+2};1H{floor}\n"
    
    # Lost birds on floor
    for b in range(constants.layout.num_balls):
        if state.birds.lost[b]:
            output += f"\033[{constants.layout.height+2};{state.birds.cols[b]}H\033[90mX{RESET}"
    
    # Player cursor
    cursor_x = constants.layout.lane_positions[state.player.lane] - 1
    fallback_cursor_color = YELLOW if state.player.selected_lane is not None else GREEN
    
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
    if state.powerups.wide_cursor_active:
        half_width = state.powerups.wide_cursor_lanes // 2
        cursor_str = ""
        for offset in range(-half_width, half_width + 1):
            lane = state.player.lane + offset
            if 0 <= lane < 9:
                lane_x = constants.layout.lane_positions[lane] - 1
                bird_idx = state.birds.random_lanes.index(lane) if lane in state.birds.random_lanes else -1
                
                if bird_idx >= 0 and not state.birds.lost[bird_idx]:
                    letter, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
                    color = _grade_letter_color(letter)
                else:
                    color = fallback_cursor_color
                
                glyph = '^'
                cursor_str += f"\033[{constants.layout.height+3};{lane_x}H{color}\033[1m[{glyph}]{RESET}"
        output += cursor_str + "\n"
    else:
        bird_idx = state.birds.random_lanes.index(state.player.lane) if state.player.lane in state.birds.random_lanes else -1
        if bird_idx >= 0 and not state.birds.lost[bird_idx]:
            letter, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
            color = _grade_letter_color(letter)
        else:
            color = fallback_cursor_color
        
        glyph = '^'
        output += f"\033[{constants.layout.height+3};{cursor_x}H{color}\033[1m[{glyph}]{RESET}\n"
    
    # Highlight selected lane in swap mode
    if state.player.selected_lane is not None:
        selected_x = constants.layout.lane_positions[state.player.selected_lane] - 1
        output += f"\033[{constants.layout.height+3};{selected_x}H{YELLOW}\033[1m[*]{RESET}"
    
    return output

def render_footer(output):
    """Rendering footer con comandi e XP overlay opzionale"""
    active_balls = sum(1 for lost in state.birds.lost if not lost)
    swap_hint = " | Press SPACE again to swap or cancel" if state.player.selected_lane is not None else ""
    output += f"\033[{constants.layout.height+4};1HUse ← → to move, ↑ to bounce, Ctrl+C to quit | Birds: {active_balls}/{constants.layout.num_balls}{swap_hint}"
    
    if state.ui.show_xp_overlay:
        parts = []
        for i in range(constants.layout.num_balls):
            label, _ = compute_grade_from_xp(state.birds.per_bird_xp[i])
            parts.append(f"{label}({int(state.birds.per_bird_xp[i])})")
        xp_summary = ' '.join(parts)
        output += f"\033[{constants.layout.height+5};1HXP: {xp_summary[:constants.layout.width]}{RESET}"
    
    return output

def render_pause_overlay(output):
    """Rendering overlay PAUSED"""
    if state.game.paused:
        pause_y = 2 + (constants.layout.height // 2)
        pause_x = max(1, (constants.layout.width // 2) - 3)
        output += f"\033[{pause_y};{pause_x}H{YELLOW}\033[1mPAUSED{RESET}"
    return output

def render_game():
    """Main render function using differential framebuffer."""
    fb = get_framebuffer()

    # Recompute level for rendering
    state.game.level = compute_level_from_score(state.game.score)

    # Render all components to framebuffer
    _fb_render_header(fb)
    _fb_render_starting_line(fb)
    _fb_render_obstacles(fb)
    _fb_render_bats(fb)
    _fb_render_loot(fb)
    _fb_render_projectiles(fb)
    _fb_render_birds(fb)
    _fb_render_notifications(fb)  # PRIMA del cursore, così il cursore sovrascrive
    _fb_render_floor_and_cursor(fb)  # DOPO le notifiche
    _fb_render_footer(fb)
    _fb_render_pause_overlay(fb)

    # Generate differential output and write to screen
    output = fb.render()
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except BlockingIOError:
        pass


# =============================================================================
# FRAMEBUFFER RENDER FUNCTIONS
# =============================================================================

def _fb_render_header(fb):
    """Render header to framebuffer."""
    level = state.game.level
    next_level_score = calculate_level_threshold(level + 1)
    lives_display = "●" * state.game.lives + "◌" * (5 - state.game.lives)

    prestige_val = compute_prestige()
    if prestige_val is None:
        prestige_val = 1.0

    score_line = f"Score: {int(state.game.score):,} | Level: {level} | Next: {int(next_level_score):,} | Lives: {lives_display} | Prestige: x{prestige_val:.2f}"
    fb.put_string(0, 0, score_line[:fb.width])
    fb.put_string(0, 1, ceiling[:fb.width])


def _fb_render_starting_line(fb):
    """Render starting line to framebuffer."""
    starting_line_y = constants.layout.starting_line
    if starting_line_y < 0 or starting_line_y >= constants.layout.height:
        return

    if state.powerups.tailwind_active:
        line = "^ " * (constants.layout.width // 2)
        color = BLUE
    else:
        line = "- " * (constants.layout.width // 2)
        color = ''

    for i, char in enumerate(line[:constants.layout.width]):
        fb.put(i, starting_line_y + 2, char, color)


def _fb_render_obstacles(fb):
    """Render obstacles to framebuffer."""
    for obs in state.enemies.obstacles:
        max_hp = constants.obstacle.max_hp_by_tier.get(obs.get('tier', 1), obs.get('hp', 1))
        obs_color = color_from_hp(constants.colors.obstacles_base_rgb, obs.get('hp', 0), max_hp)

        for line_idx, line in enumerate(OBSTACLE_SPRITE):
            y_pos = obs['y_pos'] + line_idx
            if 0 <= y_pos < constants.layout.height:
                x_pos = constants.layout.lane_positions[obs['lane']] - 1
                for i, char in enumerate(line):
                    if char != ' ':  # Solo caratteri non-spazio
                        fb.put(x_pos + i, y_pos + 2, char, obs_color)


def _fb_render_bats(fb):
    """Render bats to framebuffer."""
    for bat in state.enemies.bats:
        bat_hp = bat.get('hp', 0)
        bat_max = bat.get('max_hp', bat_hp if bat_hp > 0 else 1)
        bat_color = color_from_hp(constants.colors.bats_base_rgb, bat_hp, bat_max)

        bat_sprite = BAT_FRAME_1 if (state.game.frame_count // 3) % 2 == 0 else BAT_FRAME_2

        for line_idx, line in enumerate(bat_sprite):
            y_pos = bat['y_pos'] + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':  # Solo caratteri non-spazio
                        fb.put(bat['x_pos'] + i, y_pos + 2, char, bat_color)


def _fb_render_loot(fb):
    """Render loot items to framebuffer."""
    loot_symbols = {
        'yellow_egg': ('⬯', YELLOW), 'red_egg': ('⬯', RED), 'blue_egg': ('⬯', BLUE),
        'white_egg': ('⬯', WHITE), 'clockwork_egg': ('⬯', CLOCKWORK), 'gold_egg': ('⬯', GOLD),
        'stealth_egg': ('⬯', DARK_GRAY), 'patchwork_egg': ('⬯', PATCHWORK),
        'orange_egg': ('⬯', ORANGE), 'cookie_egg': ('⬯', COOKIE), 'cookie_crumb': ('•', COOKIE),
        'dinosaur_egg': ('⬯', DINOSAUR), 'glitch_egg': ('⬯', GLITCH), 'purple_egg': ('⬯', PURPLE),
    }

    for loot in state.items.loot_items:
        y_pos = loot['y_pos']
        if 0 <= y_pos < constants.layout.height:
            loot_type = loot['type']
            rarity = loot.get('rarity', 'common')

            # Colore basato su rarity
            if rarity == 'common':
                power_color = YELLOW
            elif rarity == 'uncommon':
                power_color = RED
            elif rarity == 'rare':
                power_color = BLUE
            else:
                power_color = WHITE

            if loot_type in loot_symbols:
                char, color = loot_symbols[loot_type]
            elif 'wide_cursor' in loot_type:
                char = '↔'
                color = power_color
            elif 'bounce_boost' in loot_type:
                char = '↺'  # Originale
                color = power_color
            elif 'suction' in loot_type:
                char = '⥥'  # Originale
                color = power_color
            elif 'tailwind' in loot_type:
                char = '༄'  # Originale
                color = power_color
            elif 'shuffle' in loot_type:
                char = '𖦹'  # Originale
                color = power_color
            else:
                char = '?'
                color = WHITE

            fb.put(loot['x_pos'], y_pos + 2, char, color)


def _fb_render_projectiles(fb):
    """Render projectiles to framebuffer."""
    for proj in state.special.red_projectiles:
        y_pos = proj['y_pos']
        if 0 <= y_pos < constants.layout.height:
            symbol = '•' if proj.get('powered', False) else '⋅'  # • piccolo, non ● grande
            proj_color = proj.get('color', RED)
            fb.put(proj['x_pos'], y_pos + 2, symbol, proj_color)


def _fb_render_birds(fb):
    """Render birds to framebuffer."""
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            # X sul pavimento viene disegnata in _fb_render_floor_and_cursor
            continue

        y_pos = state.birds.y[i]
        if y_pos < 0 or y_pos >= constants.layout.height:
            continue

        bird_color = state.birds.colors[i]
        x_pos = state.birds.cols[i]

        # Choose sprite based on direction and animation frame
        if state.birds.vy[i] == -1:  # Moving up
            sprite = BIRD_UP_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_UP_2
        else:  # Moving down or stationary
            sprite = BIRD_DOWN_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_DOWN_2

        # Special handling for different bird types
        if bird_color == STEALTH:
            tangible = i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0
            bird_color = WHITE if tangible else DARK_GRAY
        elif bird_color == BLUE and state.birds.power_used[i]:
            bird_color = CYAN

        # Render bird sprite
        for line_idx, line in enumerate(sprite):
            by = y_pos + line_idx
            if 0 <= by < constants.layout.height:
                x_offset = len(line) // 2
                for ci, char in enumerate(line):
                    if char != ' ':
                        fb.put(x_pos - x_offset + ci, by + 2, char, bird_color)

        # Purple bird charging orb
        if state.birds.colors[i] == PURPLE and state.special.purple_state[i] == 2:
            start_frame = state.special.purple_charge_started_frame[i]
            if state.game.frame_count >= start_frame:
                elapsed_seconds = int((state.game.frame_count - start_frame) * constants.timing.base_sleep)
                s = max(0, min(3, elapsed_seconds))
                sym = '⋅' if s <= 0 else ('•' if s == 1 else '●')
                orb_y = y_pos + 1
                if 0 <= orb_y < constants.layout.height:
                    fb.put(x_pos, orb_y + 2, sym, PURPLE)


def _fb_render_floor_and_cursor(fb):
    """Render floor and cursor to framebuffer."""
    floor_y = constants.layout.height + 2

    # Floor
    fb.put_string(0, floor_y, floor[:fb.width])

    # Lost birds - X sul pavimento (DOPO il floor, così non viene sovrascritto)
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            x_pos = state.birds.cols[i]
            fb.put(x_pos, floor_y, 'X', DARK_GRAY)

    # Cursor - render [^] per ogni lane affetta
    affected_lanes = get_affected_lanes()
    fallback_cursor_color = YELLOW if state.player.selected_lane is not None else GREEN

    for lane in affected_lanes:
        if 0 <= lane < len(constants.layout.lane_positions):
            x_pos = constants.layout.lane_positions[lane] - 1  # -1 per centrare [^]

            # Determina colore in base al bird nella lane
            bird_idx = -1
            for bi, bl in enumerate(state.birds.random_lanes):
                if bl == lane:
                    bird_idx = bi
                    break

            if bird_idx >= 0 and not state.birds.lost[bird_idx]:
                letter, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
                color = _grade_letter_color(letter, fallback_cursor_color)
            else:
                color = fallback_cursor_color

            # Render [^]
            fb.put(x_pos, floor_y + 1, '[', color)
            fb.put(x_pos + 1, floor_y + 1, '^', color)
            fb.put(x_pos + 2, floor_y + 1, ']', color)

    # Selected lane indicator for swap - mostra [*]
    if state.player.selected_lane is not None:
        sel_x = constants.layout.lane_positions[state.player.selected_lane] - 1
        fb.put(sel_x, floor_y + 1, '[', YELLOW)
        fb.put(sel_x + 1, floor_y + 1, '*', YELLOW)
        fb.put(sel_x + 2, floor_y + 1, ']', YELLOW)


def _grade_letter_color(letter, fallback):
    """Helper per colore cursore basato su grade."""
    if letter and isinstance(letter, str) and len(letter) > 0:
        prefix = letter[0]
    else:
        return fallback
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
    return fallback


def _fb_render_footer(fb):
    """Render footer to framebuffer."""
    # height+2=floor, +3=cursore/notifica, +4=footer
    footer_y = constants.layout.height + 4
    active_balls = sum(1 for lost in state.birds.lost if not lost)
    swap_hint = " | SPACE to swap" if state.player.selected_lane is not None else ""
    footer_text = f"← → move | ↑ bounce | Ctrl+C quit | Birds: {active_balls}/{constants.layout.num_balls}{swap_hint}"
    fb.put_string(0, footer_y, footer_text[:fb.width])

    if state.ui.show_xp_overlay:
        parts = []
        for i in range(constants.layout.num_balls):
            label, _ = compute_grade_from_xp(state.birds.per_bird_xp[i])
            parts.append(f"{label}({int(state.birds.per_bird_xp[i])})")
        xp_summary = ' '.join(parts)
        fb.put_string(0, footer_y + 1, f"XP: {xp_summary[:fb.width-4]}")


def _fb_render_notifications(fb):
    """Render notifications to framebuffer."""
    active_notifications = [n for n in state.ui.notifications if n[1] > state.game.frame_count]
    if active_notifications:
        text, _ = active_notifications[0]
        # Stessa riga del cursore (height+3), ma renderizzata PRIMA
        # così il cursore la sovrascrive dove serve
        notif_y = constants.layout.height + 3
        fb.put_string(0, notif_y, text[:fb.width], YELLOW)
    state.ui.notifications[:] = active_notifications


def _fb_render_pause_overlay(fb):
    """Render pause overlay to framebuffer."""
    if state.game.paused:
        pause_y = constants.layout.height // 2 + 2
        pause_x = max(0, (constants.layout.width // 2) - 3)
        fb.put_string(pause_x, pause_y, "PAUSED", YELLOW)