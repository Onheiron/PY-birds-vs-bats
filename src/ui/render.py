import os
import sys
import random
import re

if os.name == 'nt':
    import msvcrt

from src.entities.sprites import *
from src.core import constants
# Import theme from src (not src.core to avoid circular imports)
import src.theme as theme
from src.functions import compute_level_from_score, calculate_level_threshold, compute_prestige, compute_grade_from_xp, get_affected_lanes, find_bird_in_lane, get_mph_for_speed, get_level_milestones, compute_level_from_miles
from src.core import state

# =============================================================================
# WIDESCREEN LAYOUT - Dynamic aspect ratio calculation
# =============================================================================
# Terminal characters have approximately 2:1 aspect ratio (height ~= 2x width)
CHAR_ASPECT_RATIO = 2.0

# Header and footer heights
HEADER_HEIGHT = 4  # Header uses 4 rows (0-3), game area starts at row 4
FOOTER_HEIGHT = 2  # Floor (1) + cursor row (1)

# Calculate total height in rows
TOTAL_HEIGHT = HEADER_HEIGHT + constants.layout.height + FOOTER_HEIGHT

# Parse aspect ratio from config (e.g., "16:9" -> 16/9)
def _parse_aspect_ratio():
    """Parse aspect ratio string from config and return as float."""
    try:
        ratio_str = getattr(constants.layout, 'aspect_ratio', '16:9')
        if ':' in ratio_str:
            w, h = ratio_str.split(':')
            return float(w) / float(h)
        return float(ratio_str)
    except (ValueError, AttributeError):
        return 16.0 / 9.0  # Default to 16:9

TARGET_ASPECT_RATIO = _parse_aspect_ratio()

# Calculate required total width for the target aspect ratio
# Height in "pixel units" = rows * char_aspect_ratio (since chars are taller than wide)
# Width in "pixel units" = columns * 1
# For aspect ratio W:H, we need: width / (height * char_aspect) = W/H
# Therefore: width = (height * char_aspect) * (W/H)
_height_in_units = TOTAL_HEIGHT * CHAR_ASPECT_RATIO
_target_width = int(_height_in_units * TARGET_ASPECT_RATIO)

# Calculate panel widths
_min_panel_width = getattr(constants.layout, 'min_panel_width', 20)
_total_panel_space = _target_width - constants.layout.width
_panel_width_each = max(_min_panel_width, _total_panel_space // 2)

# Final dimensions
SIDE_PANEL_WIDTH = _panel_width_each
TOTAL_WIDTH = constants.layout.width + (SIDE_PANEL_WIDTH * 2)
GAME_X_OFFSET = SIDE_PANEL_WIDTH  # X offset where game area starts

# Content width inside panels (excluding borders)
PANEL_CONTENT_WIDTH = 18  # Fixed content width for gauges, signs, etc.

# Pre-build static parts (now with offset consideration)
ceiling = "=" * constants.layout.width
floor = ceiling

# =============================================================================
# PARALLAX BACKGROUND PATTERNS - 3-layer scrolling effect
# =============================================================================
# Layer 1 (slowest): Dense tree pattern - small ^ symbols
# Pattern 6 righe x 24 caratteri - solo cime, piccole e irregolari
TREE_PATTERN = [
    "^  ^    ^  ^   ^    ^   ",
    " ^^  ^    ^^  ^  ^^   ^ ",
    "^   ^  ^^   ^   ^  ^  ^^",
    "  ^^  ^   ^^  ^^   ^^ ^ ",
    " ^  ^^  ^   ^   ^^  ^   ",
    "^    ^ ^^  ^^ ^   ^  ^^ ",
]
TREE_PATTERN_HEIGHT = len(TREE_PATTERN)
TREE_PATTERN_WIDTH = 24

# Layer 2 (medium speed): Sparse taller trees - ∧ symbols
# Pattern 8 righe x 32 caratteri - più sparso e alto
MID_TREE_PATTERN = [
    "∧       ∧           ∧       ∧   ",
    "                                ",
    "    ∧           ∧           ∧   ",
    "                                ",
    "∧           ∧       ∧           ",
    "                                ",
    "        ∧       ∧           ∧   ",
    "                                ",
]
MID_TREE_PATTERN_HEIGHT = len(MID_TREE_PATTERN)
MID_TREE_PATTERN_WIDTH = 32

# Layer 3 (fastest): Obstacles - handled separately in game logic

# Colors for parallax layers (loaded from theme)
TREE_BG_COLOR = theme.get_color('background', 'layer1', 234)
MID_TREE_COLOR = theme.get_color('background', 'layer2', 235)

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
        # Width: game area + side panels for 16:9 widescreen
        _framebuffer = FrameBuffer(TOTAL_WIDTH, total_height)
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
            elif ch == '\r' or ch == '\n':
                last = 'ENTER'
            elif ch == '\x7f' or ch == '\x08':
                last = 'BACKSPACE'
            elif ch == '\x1b':
                # Lone ESC (not part of arrow sequence)
                last = 'ESC'
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

    # Level is now computed from miles in update_miles(), not from score

    # Render all components to framebuffer
    _fb_render_side_panels(fb)  # Side panels FIRST (background)
    _fb_render_header(fb)
    _fb_render_background(fb)  # Sfondo alberi PRIMA di tutto il resto
    _fb_render_level_line(fb)  # Level line in game area (before obstacles)
    _fb_render_right_panel_barriers(fb)  # Decorative barriers UNDER level signs
    _fb_render_right_panel_level_signs(fb)  # Level signs on TOP of barriers
    _fb_render_notifications(fb)  # Notification cards in right panel (between level signs)
    _fb_render_starting_line(fb)
    _fb_render_obstacles(fb)
    _fb_render_bats(fb)
    _fb_render_loot(fb)
    _fb_render_projectiles(fb)
    _fb_render_birds(fb)
    _fb_render_floor_and_cursor(fb)
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

# Side panel colors (loaded from theme)
PANEL_BORDER_COLOR = theme.get_color('panels', 'border', 238)
PANEL_BG_COLOR = theme.get_color('panels', 'background', 233)

# Speed gauge gradient colors (level 1-10: green -> yellow -> red)
GAUGE_GRADIENT = theme.get_gradient('gauge', 'gradient')
# Momentum bar gradient (0% -> 100%: red -> yellow -> green)
MOMENTUM_GRADIENT = theme.get_gradient('momentum', 'gradient')
GAUGE_OFF = theme.get_color('gauge', 'off', 238)
GAUGE_BLOCK_ON = "██████"       # Solid block for active segments
GAUGE_BLOCK_OFF = "------"      # Dashes for inactive segments (clearly different)

# Text colors for left panel (loaded from theme)
PANEL_LABEL_COLOR = theme.get_color('left_panel', 'label', 245)
PANEL_VALUE_COLOR = theme.get_color('left_panel', 'value', 255)

# Header colors (loaded from theme)
HEADER_BORDER = theme.get_color('header', 'border', 240)
HEADER_LABEL = theme.get_color('header', 'label', 245)
HEADER_VALUE = theme.get_color('header', 'value', 255)
HEADER_ACCENT = theme.get_color('header', 'accent', 220)

# Level signs colors (loaded from theme)
LEVEL_LINE_COLOR = theme.get_color('level_signs', 'line', 240)
SIGN_BORDER_COLOR = theme.get_color('level_signs', 'border', 94)
SIGN_TEXT_COLOR = theme.get_color('level_signs', 'text', 230)
SIGN_ARROW_COLOR = theme.get_color('level_signs', 'arrow', 220)

# Notification card colors (loaded from theme)
CARD_BORDER_COLOR = theme.get_color('notifications', 'border', 178)
CARD_TITLE_COLOR = theme.get_color('notifications', 'title', 220)
CARD_TEXT_COLOR = theme.get_color('notifications', 'text', 255)

# Pause menu colors (loaded from theme)
MENU_BORDER_COLOR = theme.get_color('pause_menu', 'border', 245)
MENU_SELECTED_COLOR = theme.get_color('pause_menu', 'selected', 220)
MENU_NORMAL_COLOR = theme.get_color('pause_menu', 'normal', 250)
MENU_ARROW_COLOR = theme.get_color('pause_menu', 'arrow', 214)

# Decorative barriers color (loaded from theme)
DECO_COLOR = theme.get_color('decorative', 'barriers', 22)


def _fb_render_left_panel_content(fb, panel_start_y, panel_end_y):
    """
    Render left panel content (dynamic width):
    - Speed: (label)
      XXX MPH (value)
    - Travelled: (label)
      XXX mls (value)
    - Separator
    - Speed gauge (vertical, extra spacing for red levels 8-10)
    - Separator
    - Momentum: [horizontal bar]

    Components expand with panel width. Min width = 16 chars.
    Labels stay left-aligned with 2-column padding.
    """
    current_speed = state.game.speed
    max_speed = 10
    mph = get_mph_for_speed(current_speed)
    miles = state.game.miles

    # Calculate dynamic widths
    # Available space: SIDE_PANEL_WIDTH - 2 (excluding borders)
    # Min content width: 16 chars (original design)
    # Max padding: 2 columns per side
    available_width = SIDE_PANEL_WIDTH - 2
    min_content_width = 16
    max_padding = 2

    # Calculate content width and padding
    # If panel is small, reduce padding first before shrinking content
    if available_width >= min_content_width + (max_padding * 2):
        # Plenty of space: use max padding and expand content
        left_padding = max_padding + 1  # +1 for border
        content_width = available_width - (max_padding * 2)
    elif available_width >= min_content_width:
        # Tight fit: reduce padding, keep min content width
        remaining = available_width - min_content_width
        left_padding = max(1, remaining // 2 + 1)  # +1 for border
        content_width = min_content_width
    else:
        # Very tight: no padding, use all available
        left_padding = 1
        content_width = max(available_width, min_content_width)

    y = panel_start_y + 1  # Start after a small margin

    # === Speed: XXX MPH (two lines) ===
    fb.put_string(left_padding, y, "Speed:", PANEL_LABEL_COLOR)
    y += 1
    fb.put_string(left_padding, y, f"{mph} MPH", PANEL_VALUE_COLOR)
    y += 2

    # === Travelled: XXX.XXX mls (two lines) ===
    fb.put_string(left_padding, y, "Travelled:", PANEL_LABEL_COLOR)
    y += 1
    fb.put_string(left_padding, y, f"{miles:.3f} mls", PANEL_VALUE_COLOR)
    y += 2

    # === Calculate Momentum first (needed for spacer rows) ===
    # Momentum = progress from current speed threshold to next speed threshold
    # For speed 1, we go from 0 to threshold(2)
    # For speed N (N>1), we go from threshold(N) to threshold(N+1)
    score = state.game.score

    if current_speed >= max_speed:
        momentum_pct = 100.0
    else:
        if current_speed == 1:
            # At speed 1, progress goes from 0 to threshold for speed 2
            prev_threshold = 0
        else:
            # At speed N, progress goes from threshold(N) to threshold(N+1)
            prev_threshold = calculate_level_threshold(current_speed)

        next_threshold = calculate_level_threshold(current_speed + 1)
        score_range = next_threshold - prev_threshold
        score_progress = score - prev_threshold

        if score_range > 0:
            momentum_pct = min(100.0, max(0.0, (score_progress / score_range) * 100))
        else:
            momentum_pct = 0.0

    # === Gear title ===
    separator = "─" * content_width
    fb.put_string(left_padding, y, "Gear:", PANEL_LABEL_COLOR)
    y += 1

    # === Separator ===
    fb.put_string(left_padding, y, separator, GAUGE_OFF)
    y += 1

    # === Speed Gauge (vertical, with spacer rows between some levels) ===
    # Spacer rows (block without numbers) between: 10-9, 9-8, 8-7, 7-6, 6-5
    gauge_x = left_padding
    gauge_start_y = y

    # Calculate dynamic block width
    # Format: "XX - ██████ - XX" = 2 + 3 + block + 3 + 2 = 10 + block
    block_width = content_width - 10
    gauge_block_on = "█" * block_width
    gauge_block_off = "-" * block_width
    # Spacer format: "     ██████     " - centered block with 5 spaces each side (total = content_width)
    spacer_padding = (content_width - block_width) // 2
    spacer_padding_left = " " * spacer_padding
    spacer_padding_right = " " * (content_width - block_width - spacer_padding)

    # Levels that have a spacer row AFTER them (going top to bottom)
    levels_with_spacer_after = [10, 9, 8, 7]

    # Build list of rows to draw (level number or None for spacer)
    gauge_rows = []
    for level in range(max_speed, 0, -1):  # 10 down to 1
        gauge_rows.append(level)
        if level in levels_with_spacer_after:
            gauge_rows.append(None)  # Spacer row

    total_gauge_rows = len(gauge_rows)

    # Draw gauge
    for row_idx, level in enumerate(gauge_rows):
        row_y = gauge_start_y + row_idx

        if row_y < panel_start_y or row_y >= panel_end_y:
            continue

        if level is None:
            # Spacer row - find which level it belongs to (the one above)
            level_above = None
            for i in range(row_idx - 1, -1, -1):
                if gauge_rows[i] is not None:
                    level_above = gauge_rows[i]
                    break

            if level_above is not None:
                # Use gradient color based on level
                active_color = GAUGE_GRADIENT[level_above - 1]

                # Spacer AFTER level N is between level N and level N-1
                # It should light up when:
                # - level_above is already active (current_speed >= level_above), OR
                # - We're one level below (current_speed == level_above - 1) AND momentum >= 50%
                level_below = level_above - 1

                if current_speed >= level_above:
                    # Level above is already reached, spacer is active
                    is_active = True
                elif current_speed == level_below and momentum_pct >= 50:
                    # We're at the level below and momentum >= 50%, light up spacer
                    is_active = True
                else:
                    is_active = False

                color = active_color if is_active else GAUGE_OFF
                block = gauge_block_on if is_active else gauge_block_off

                # Spacer row: just the block, no numbers (centered)
                line = f"{spacer_padding_left}{block}{spacer_padding_right}"
                fb.put_string(gauge_x, row_y, line, color)
        else:
            # Normal level row with numbers - use gradient color
            active_color = GAUGE_GRADIENT[level - 1]

            is_active = level <= current_speed
            color = active_color if is_active else GAUGE_OFF
            block = gauge_block_on if is_active else gauge_block_off

            level_str = f"{level:2d}"
            line = f"{level_str} - {block} - {level_str}"
            fb.put_string(gauge_x, row_y, line, color)

    y = gauge_start_y + total_gauge_rows

    # === Separator ===
    fb.put_string(left_padding, y, separator, GAUGE_OFF)
    y += 2  # Skip a line after separator

    # === Momentum: [horizontal bar] ===
    momentum_label = "Momentum:"
    fb.put_string(left_padding, y, momentum_label, PANEL_LABEL_COLOR)
    y += 2  # Skip a line between label and bar

    # Draw horizontal bar (dynamic width) with gradient colors (red -> yellow -> green)
    bar_width = content_width
    filled = int((momentum_pct / 100.0) * bar_width)
    gradient_len = len(MOMENTUM_GRADIENT)

    for i in range(bar_width):
        if i < filled:
            # Map position in bar to position in gradient (interpolate)
            gradient_idx = int((i / max(1, bar_width - 1)) * (gradient_len - 1))
            char_color = MOMENTUM_GRADIENT[gradient_idx]
            fb.put(left_padding + i, y, '█', char_color)
        else:
            fb.put(left_padding + i, y, '─', GAUGE_OFF)

    # Show percentage centered below the bar
    y += 1
    pct_str = f"{momentum_pct:.0f}%"
    pct_x = left_padding + (bar_width - len(pct_str)) // 2
    fb.put_string(pct_x, y, pct_str, PANEL_VALUE_COLOR)


def _calculate_level_line_y():
    """Calculate the Y position of the level line based on time to next level.

    Returns:
        (line_y, is_on_screen, unused) where:
        - line_y: screen Y position (in game area coordinates, 0 = top of game)
        - is_on_screen: True if the line should be visible
        - unused: kept for compatibility, always 0
    """
    miles = state.game.miles
    milestones = get_level_milestones()
    current_level = state.game.level

    # Current level threshold (where next level starts)
    if current_level <= len(milestones):
        current_threshold = milestones[current_level - 1]
    else:
        current_threshold = milestones[-1]

    miles_to_next = max(0, current_threshold - miles)

    current_speed = state.game.speed
    mph = current_speed * 40
    miles_per_second = mph / 3600.0 if mph > 0 else 0.001

    # Time until we reach next level (in seconds)
    time_to_level = miles_to_next / miles_per_second if miles_per_second > 0 else 999999

    # Scroll speed: 1 row per 5 frames, assume ~60 fps = 12 rows/second
    scroll_rows_per_second = 12.0

    panel_height = constants.layout.height

    # The line travels the FULL screen height (top to bottom)
    full_travel_distance = panel_height

    # Time for line to travel from top to bottom of screen
    time_for_full_travel = full_travel_distance / scroll_rows_per_second

    if time_to_level >= time_for_full_travel:
        # Line hasn't entered screen yet
        return -1, False, 0
    else:
        # Line is on screen - calculate position
        # Line goes from top (0) to bottom (panel_height)
        line_progress = 1.0 - (time_to_level / time_for_full_travel)
        line_progress = max(0, min(1, line_progress))
        line_y = int(line_progress * full_travel_distance)

        return line_y, True, 0


def _fb_render_level_line(fb):
    """Render the level line in the game area (dashed line showing next level)."""
    line_y, is_on_screen, progress = _calculate_level_line_y()

    if not is_on_screen:
        return

    # Screen Y position (add header offset)
    screen_y = line_y + HEADER_HEIGHT

    # Make sure it's in visible game area
    if screen_y < HEADER_HEIGHT or screen_y >= constants.layout.height + HEADER_HEIGHT:
        return

    # Draw dashed line across game width - darker than START line
    line_pattern = "· · · · · · · · · · · · · · · · · · · · · · · "

    for i, char in enumerate(line_pattern[:constants.layout.width]):
        if char != ' ':
            fb.put(GAME_X_OFFSET + i, screen_y, char, LEVEL_LINE_COLOR)


def _fb_render_right_panel_level_signs(fb):
    """Render level signs in right panel.

    Top sign: Next level - stays at top until "level line" would enter screen,
              then scrolls down synchronized with the level line.
              When scrolling, shows < on the left side pointing to the line.
    Bottom sign: Current level - shows distance traveled since reaching it
    """
    panel_start_y = HEADER_HEIGHT
    panel_end_y = constants.layout.height + HEADER_HEIGHT
    panel_height = panel_end_y - panel_start_y
    right_start = GAME_X_OFFSET + constants.layout.width

    # Get level info
    miles = state.game.miles
    milestones = get_level_milestones()
    current_level = state.game.level
    current_group = state.game.level_group
    current_sub = state.game.level_sub

    # Panel inner area (excluding borders)
    inner_start_x = right_start + 1

    # Sign dimensions: 16 chars wide
    # Signs stay at LEFT of panel (close to game area), padding goes to the right
    sign_width = 16
    sign_x = inner_start_x  # No centering - stick to left edge

    # === Calculate thresholds ===
    if current_level > 1:
        prev_threshold = milestones[current_level - 2]
    else:
        prev_threshold = 0

    if current_level <= len(milestones):
        current_threshold = milestones[current_level - 1]
    else:
        current_threshold = milestones[-1]

    # Next level info
    next_level = current_level + 1
    if next_level <= 18:
        next_group = ((next_level - 1) // 3) + 1
        next_sub = ((next_level - 1) % 3) + 1
    else:
        next_group, next_sub = 6, 3

    # Distance to next level
    miles_to_next = max(0, current_threshold - miles)

    # Distance from previous level
    miles_from_prev = max(0, miles - prev_threshold)

    # Get level line position to sync the sign
    line_y, is_scrolling, _ = _calculate_level_line_y()

    # Calculate sign Y position - sign follows the line directly
    if not is_scrolling:
        # Sign stays at top with down arrow
        top_sign_y = panel_start_y + 1
    else:
        # Sign follows the line - position sign so its middle row (row 1) aligns with line
        # line_y is in game coords (0 = top of game area)
        # panel_start_y + line_y = screen position of line
        # We want sign row 1 (the Level label) to be at the line
        top_sign_y = panel_start_y + line_y - 1  # -1 so row 1 aligns with line

    # === TOP SIGN ===
    # When NOT scrolling (at top):
    #   ╔══/\══════════╗
    #   ║ Level X-Y   ║
    #   ║ x.x miles   ║
    #   ╚══════════════╝
    #
    # When scrolling (with < on left side):
    #   ╔══════════════╗
    #  <║ Level X-Y   ║
    #   ║ x.x miles   ║
    #   ╚══════════════╝

    if top_sign_y >= panel_start_y and top_sign_y < panel_end_y - 4:
        if not is_scrolling:
            # At top - show down arrow
            fb.put_string(sign_x, top_sign_y, "╔══", SIGN_BORDER_COLOR)
            fb.put(sign_x + 3, top_sign_y, '/', SIGN_ARROW_COLOR)
            fb.put(sign_x + 4, top_sign_y, '\\', SIGN_ARROW_COLOR)
            fb.put_string(sign_x + 5, top_sign_y, "══════════╗", SIGN_BORDER_COLOR)
        else:
            # Scrolling - closed top, < on left of second row
            fb.put_string(sign_x, top_sign_y, "╔══════════════╗", SIGN_BORDER_COLOR)

        # Row 2: Level label (with < when scrolling)
        level_str = f"Level {next_group}-{next_sub}"
        if is_scrolling:
            fb.put(sign_x - 1, top_sign_y + 1, '<', SIGN_ARROW_COLOR)
        fb.put(sign_x, top_sign_y + 1, '║', SIGN_BORDER_COLOR)
        fb.put(sign_x + 1, top_sign_y + 1, ' ', SIGN_TEXT_COLOR)
        fb.put_string(sign_x + 2, top_sign_y + 1, f"{level_str:<12}", SIGN_TEXT_COLOR)
        fb.put(sign_x + 14, top_sign_y + 1, ' ', SIGN_TEXT_COLOR)
        fb.put(sign_x + 15, top_sign_y + 1, '║', SIGN_BORDER_COLOR)

        # Row 3: Distance remaining
        dist_str = f"{miles_to_next:.1f} miles"
        fb.put(sign_x, top_sign_y + 2, '║', SIGN_BORDER_COLOR)
        fb.put(sign_x + 1, top_sign_y + 2, ' ', SIGN_TEXT_COLOR)
        fb.put_string(sign_x + 2, top_sign_y + 2, f"{dist_str:<12}", SIGN_TEXT_COLOR)
        fb.put(sign_x + 14, top_sign_y + 2, ' ', SIGN_TEXT_COLOR)
        fb.put(sign_x + 15, top_sign_y + 2, '║', SIGN_BORDER_COLOR)

        # Row 4: bottom border (always closed)
        fb.put_string(sign_x, top_sign_y + 3, "╚══════════════╝", SIGN_BORDER_COLOR)

    # === BOTTOM SIGN: Current level (with up arrow) ===
    # ╔══════════════╗
    # ║ Level X-Y   ║
    # ║ x.x miles   ║
    # ╚══\/══════════╝

    bottom_sign_y = panel_end_y - 5

    if bottom_sign_y > panel_start_y + 5:
        # Row 1: top border (16 chars)
        fb.put_string(sign_x, bottom_sign_y, "╔══════════════╗", SIGN_BORDER_COLOR)

        # Row 2: Level label (left-aligned)
        level_str = f"Level {current_group}-{current_sub}"
        fb.put(sign_x, bottom_sign_y + 1, '║', SIGN_BORDER_COLOR)
        fb.put(sign_x + 1, bottom_sign_y + 1, ' ', SIGN_TEXT_COLOR)
        fb.put_string(sign_x + 2, bottom_sign_y + 1, f"{level_str:<12}", SIGN_TEXT_COLOR)
        fb.put(sign_x + 14, bottom_sign_y + 1, ' ', SIGN_TEXT_COLOR)
        fb.put(sign_x + 15, bottom_sign_y + 1, '║', SIGN_BORDER_COLOR)

        # Row 3: Distance from previous (left-aligned)
        dist_str = f"{miles_from_prev:.1f} miles"
        fb.put(sign_x, bottom_sign_y + 2, '║', SIGN_BORDER_COLOR)
        fb.put(sign_x + 1, bottom_sign_y + 2, ' ', SIGN_TEXT_COLOR)
        fb.put_string(sign_x + 2, bottom_sign_y + 2, f"{dist_str:<12}", SIGN_TEXT_COLOR)
        fb.put(sign_x + 14, bottom_sign_y + 2, ' ', SIGN_TEXT_COLOR)
        fb.put(sign_x + 15, bottom_sign_y + 2, '║', SIGN_BORDER_COLOR)

        # Row 4: bottom border with up arrow (16 chars)
        fb.put_string(sign_x, bottom_sign_y + 3, "╚══", SIGN_BORDER_COLOR)
        fb.put(sign_x + 3, bottom_sign_y + 3, '\\', SIGN_ARROW_COLOR)
        fb.put(sign_x + 4, bottom_sign_y + 3, '/', SIGN_ARROW_COLOR)
        fb.put_string(sign_x + 5, bottom_sign_y + 3, "══════════╝", SIGN_BORDER_COLOR)


def _fb_render_side_panels(fb):
    """
    Render left and right side panels (placeholder for Steam Deck 16:9 layout).
    Panels are ONLY in the middle section (between header and footer).
    Header (rows 0-3) and footer span full width.
    """
    # Panel area: from row HEADER_HEIGHT (after header) to row height+HEADER_HEIGHT (before floor)
    panel_start_y = HEADER_HEIGHT
    panel_end_y = constants.layout.height + HEADER_HEIGHT  # exclusive (floor row)

    right_start = GAME_X_OFFSET + constants.layout.width

    # Left panel - clear and draw borders
    for y in range(panel_start_y, panel_end_y):
        # Outer border
        fb.put(0, y, '│', PANEL_BORDER_COLOR)
        # Clear inner content
        for x in range(1, SIDE_PANEL_WIDTH - 1):
            fb.put(x, y, ' ', '')
        # Inner border (separates panel from game)
        fb.put(SIDE_PANEL_WIDTH - 1, y, '│', PANEL_BORDER_COLOR)

    # Render left panel content (speed info, gauge, momentum)
    _fb_render_left_panel_content(fb, panel_start_y, panel_end_y)

    # Right panel - vertical border only (background rendered separately)
    for y in range(panel_start_y, panel_end_y):
        # Inner border (separates game from panel)
        fb.put(right_start, y, '│', PANEL_BORDER_COLOR)
        # Outer border
        fb.put(right_start + SIDE_PANEL_WIDTH - 1, y, '│', PANEL_BORDER_COLOR)


def _fb_render_background(fb):
    """Render parallax scrolling background for game area and right panel.

    3 layers with different scroll speeds (slowest to fastest):
    - Layer 1: Dense tree pattern (^) - slowest, darkest
    - Layer 2: Sparse tall trees (∧) - medium speed, slightly lighter
    - Layer 3: Obstacles - fastest (rendered separately)
    """
    bg_offset = state.ui.bg_offset
    mid_offset = state.ui.bg_mid_offset

    # Right panel start position
    right_panel_start = GAME_X_OFFSET + constants.layout.width + 1  # After game area + border
    right_panel_inner_width = SIDE_PANEL_WIDTH - 2  # Exclude borders

    # Game area goes from row HEADER_HEIGHT to row height+HEADER_HEIGHT-1
    for screen_y in range(constants.layout.height):
        # === Layer 1: Slowest background (dense small trees) ===
        pattern_y = (screen_y - bg_offset) % TREE_PATTERN_HEIGHT
        pattern_line = TREE_PATTERN[pattern_y]

        # Fill game area by repeating pattern horizontally
        for screen_x in range(constants.layout.width):
            pattern_x = screen_x % TREE_PATTERN_WIDTH
            char = pattern_line[pattern_x]
            if char != ' ':
                fb.put(GAME_X_OFFSET + screen_x, screen_y + HEADER_HEIGHT, char, TREE_BG_COLOR)

        # Also render in right panel (continuing the pattern)
        for panel_x in range(right_panel_inner_width):
            pattern_x = (constants.layout.width + panel_x) % TREE_PATTERN_WIDTH
            char = pattern_line[pattern_x]
            if char != ' ':
                fb.put(right_panel_start + panel_x, screen_y + HEADER_HEIGHT, char, TREE_BG_COLOR)

        # === Layer 2: Medium speed (sparse tall trees) ===
        mid_pattern_y = (screen_y - mid_offset) % MID_TREE_PATTERN_HEIGHT
        mid_pattern_line = MID_TREE_PATTERN[mid_pattern_y]

        # Fill game area
        for screen_x in range(constants.layout.width):
            pattern_x = screen_x % MID_TREE_PATTERN_WIDTH
            char = mid_pattern_line[pattern_x]
            if char != ' ':
                fb.put(GAME_X_OFFSET + screen_x, screen_y + HEADER_HEIGHT, char, MID_TREE_COLOR)

        # Also render in right panel
        for panel_x in range(right_panel_inner_width):
            pattern_x = (constants.layout.width + panel_x) % MID_TREE_PATTERN_WIDTH
            char = mid_pattern_line[pattern_x]
            if char != ' ':
                fb.put(right_panel_start + panel_x, screen_y + HEADER_HEIGHT, char, MID_TREE_COLOR)


def _fb_render_header(fb):
    """Render header to framebuffer - 3 rows with graphical boxes.

    Shows: Lives, Prestige, Score in styled boxes.
    """
    # Get values
    prestige_val = compute_prestige()
    if prestige_val is None:
        prestige_val = 1.0
    prestige_display = f"{prestige_val:.2f}x"

    score_display = f"{int(state.game.score):,}"

    # Lives display (hearts)
    lives_full = "♥" * state.game.lives
    lives_empty = "♡" * (5 - state.game.lives)
    lives_display = lives_full + lives_empty

    # Calculate box positions - 3 boxes evenly spaced
    box_width = 18
    total_boxes_width = box_width * 3 + 4  # 3 boxes + spacing
    start_x = (TOTAL_WIDTH - total_boxes_width) // 2

    box1_x = start_x
    box2_x = start_x + box_width + 2
    box3_x = start_x + (box_width + 2) * 2

    # Row 0: Top borders
    fb.put_string(box1_x, 0, "╔" + "═" * (box_width - 2) + "╗", HEADER_BORDER)
    fb.put_string(box2_x, 0, "╔" + "═" * (box_width - 2) + "╗", HEADER_BORDER)
    fb.put_string(box3_x, 0, "╔" + "═" * (box_width - 2) + "╗", HEADER_BORDER)

    # Row 1: Labels with values
    # Box 1: LIVES (hearts centered)
    fb.put(box1_x, 1, '║', HEADER_BORDER)
    fb.put_string(box1_x + 1, 1, " LIVES ", HEADER_LABEL)
    # Draw hearts with colors
    hearts_start = box1_x + 8
    for i, char in enumerate(lives_display):
        if char == '♥':
            fb.put(hearts_start + i, 1, char, RED)
        else:
            fb.put(hearts_start + i, 1, char, HEADER_BORDER)
    # Fill remaining space
    fb.put_string(hearts_start + len(lives_display), 1, " " * (box_width - 9 - len(lives_display)), '')
    fb.put(box1_x + box_width - 1, 1, '║', HEADER_BORDER)

    # Box 2: PRESTIGE
    fb.put(box2_x, 1, '║', HEADER_BORDER)
    fb.put_string(box2_x + 1, 1, " PRESTIGE ", HEADER_LABEL)
    prestige_val_str = f"{prestige_display:>5}"
    fb.put_string(box2_x + 11, 1, prestige_val_str, HEADER_VALUE)
    fb.put(box2_x + box_width - 1, 1, '║', HEADER_BORDER)

    # Box 3: SCORE
    fb.put(box3_x, 1, '║', HEADER_BORDER)
    fb.put_string(box3_x + 1, 1, " SCORE ", HEADER_LABEL)
    score_val = f"{score_display:>9}"
    fb.put_string(box3_x + 8, 1, score_val, HEADER_ACCENT)
    fb.put(box3_x + box_width - 1, 1, '║', HEADER_BORDER)

    # Row 2: Bottom borders
    fb.put_string(box1_x, 2, "╚" + "═" * (box_width - 2) + "╝", HEADER_BORDER)
    fb.put_string(box2_x, 2, "╚" + "═" * (box_width - 2) + "╝", HEADER_BORDER)
    fb.put_string(box3_x, 2, "╚" + "═" * (box_width - 2) + "╝", HEADER_BORDER)

    # Row 3: Separator line (this is where game area starts at row 4)
    fb.put_string(0, 3, "═" * TOTAL_WIDTH, HEADER_BORDER)


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
        fb.put(GAME_X_OFFSET + i, starting_line_y + HEADER_HEIGHT, char, color)


def _fb_render_obstacles(fb):
    """Render obstacles to framebuffer."""
    for obs in state.enemies.obstacles:
        tier = obs.get('tier', 1)
        max_hp = constants.obstacle.max_hp_by_tier.get(tier, obs.get('hp', 1))
        obs_color = color_from_hp(constants.colors.obstacles_base_rgb, obs.get('hp', 0), max_hp)

        # Usa lo sprite del tier corretto
        sprite = OBSTACLE_SPRITES.get(tier, OBSTACLE_SPRITE_T1)
        sprite_width = max(len(line) for line in sprite)
        lane_width = OBSTACLE_LANE_WIDTH.get(tier, 1)

        # Calcola la posizione x centrale per lo sprite
        start_lane = obs['lane']
        end_lane = min(start_lane + lane_width - 1, constants.layout.num_lanes - 1)

        # Centro tra la prima e l'ultima lane occupata
        start_x = constants.layout.lane_positions[start_lane]
        end_x = constants.layout.lane_positions[end_lane]
        center_x = (start_x + end_x) // 2
        x_offset = sprite_width // 2

        for line_idx, line in enumerate(sprite):
            y_pos = obs['y_pos'] + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':  # Solo caratteri non-spazio
                        x_pos = center_x - x_offset + i
                        if 0 <= x_pos < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, obs_color)


def _fb_render_right_panel_barriers(fb):
    """Render decorative barriers in right panel."""
    # Right panel position
    right_panel_start = GAME_X_OFFSET + constants.layout.width + 1  # After game area + border
    right_panel_inner_width = SIDE_PANEL_WIDTH - 2

    for barrier in state.enemies.right_panel_barriers:
        tier = barrier.get('tier', 1)
        sprite = OBSTACLE_SPRITES.get(tier, OBSTACLE_SPRITE_T1)
        sprite_width = max(len(line) for line in sprite)

        # Use stored x_offset for horizontal position variation
        x_offset = barrier.get('x_offset', 0)
        base_x = right_panel_start + x_offset

        for line_idx, line in enumerate(sprite):
            y_pos = barrier['y_pos'] + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':
                        x_pos = base_x + i
                        # Make sure it stays within panel bounds
                        if right_panel_start <= x_pos < right_panel_start + right_panel_inner_width:
                            fb.put(x_pos, y_pos + HEADER_HEIGHT, char, DECO_COLOR)


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
                        fb.put(GAME_X_OFFSET + bat['x_pos'] + i, y_pos + HEADER_HEIGHT, char, bat_color)


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

            fb.put(GAME_X_OFFSET + loot['x_pos'], y_pos + HEADER_HEIGHT, char, color)


def _fb_render_projectiles(fb):
    """Render projectiles to framebuffer."""
    for proj in state.special.red_projectiles:
        y_pos = proj['y_pos']
        if 0 <= y_pos < constants.layout.height:
            symbol = '•' if proj.get('powered', False) else '⋅'  # • piccolo, non ● grande
            proj_color = proj.get('color', RED)
            fb.put(GAME_X_OFFSET + proj['x_pos'], y_pos + HEADER_HEIGHT, symbol, proj_color)


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
                x_off = len(line) // 2
                for ci, char in enumerate(line):
                    if char != ' ':
                        fb.put(GAME_X_OFFSET + x_pos - x_off + ci, by + HEADER_HEIGHT, char, bird_color)

        # Purple bird charging orb
        if state.birds.colors[i] == PURPLE and state.special.purple_state[i] == 2:
            start_frame = state.special.purple_charge_started_frame[i]
            if state.game.frame_count >= start_frame:
                elapsed_seconds = int((state.game.frame_count - start_frame) * constants.timing.base_sleep)
                s = max(0, min(3, elapsed_seconds))
                sym = '⋅' if s <= 0 else ('•' if s == 1 else '●')
                orb_y = y_pos + 1
                if 0 <= orb_y < constants.layout.height:
                    fb.put(GAME_X_OFFSET + x_pos, orb_y + HEADER_HEIGHT, sym, PURPLE)


def _fb_render_floor_and_cursor(fb):
    """Render floor and cursor to framebuffer."""
    floor_y = constants.layout.height + HEADER_HEIGHT

    # Floor - FULL width separator
    full_floor = "=" * TOTAL_WIDTH
    fb.put_string(0, floor_y, full_floor)

    # Lost birds - X sul pavimento (DOPO il floor, così non viene sovrascritto)
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            x_pos = state.birds.cols[i]
            fb.put(GAME_X_OFFSET + x_pos, floor_y, 'X', DARK_GRAY)

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
            fb.put(GAME_X_OFFSET + x_pos, floor_y + 1, '[', color)
            fb.put(GAME_X_OFFSET + x_pos + 1, floor_y + 1, '^', color)
            fb.put(GAME_X_OFFSET + x_pos + 2, floor_y + 1, ']', color)

    # Selected lane indicator for swap - mostra [*]
    if state.player.selected_lane is not None:
        sel_x = constants.layout.lane_positions[state.player.selected_lane] - 1
        fb.put(GAME_X_OFFSET + sel_x, floor_y + 1, '[', YELLOW)
        fb.put(GAME_X_OFFSET + sel_x + 1, floor_y + 1, '*', YELLOW)
        fb.put(GAME_X_OFFSET + sel_x + 2, floor_y + 1, ']', YELLOW)


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
    """Render footer to framebuffer - only XP overlay when enabled."""
    # Footer position: after floor and cursor
    footer_y = constants.layout.height + HEADER_HEIGHT + 2

    # Only show XP overlay if enabled (toggled with X key)
    if state.ui.show_xp_overlay:
        parts = []
        for i in range(constants.layout.num_balls):
            label, _ = compute_grade_from_xp(state.birds.per_bird_xp[i])
            parts.append(f"{label}({int(state.birds.per_bird_xp[i])})")
        xp_summary = ' '.join(parts)
        xp_line = f"XP: {xp_summary}"
        xp_padding = max(0, (TOTAL_WIDTH - len(xp_line)) // 2)
        fb.put_string(0, footer_y, " " * xp_padding + xp_line[:TOTAL_WIDTH])


def _fb_render_notifications(fb):
    """Render notification cards in right panel between level signs."""
    # Filter expired notifications (support both old tuple and new dict format)
    active_notifications = []
    for n in state.ui.notifications:
        if isinstance(n, dict):
            if n.get('expire_frame', 0) > state.game.frame_count:
                active_notifications.append(n)
        else:
            # Old tuple format (text, expire_frame) - convert on the fly
            if len(n) >= 2 and n[1] > state.game.frame_count:
                active_notifications.append({'title': '', 'text': n[0], 'expire_frame': n[1]})

    state.ui.notifications[:] = active_notifications

    if not active_notifications:
        return

    # Right panel positioning
    panel_start_y = HEADER_HEIGHT
    panel_end_y = constants.layout.height + HEADER_HEIGHT
    right_start = GAME_X_OFFSET + constants.layout.width
    inner_start_x = right_start + 1

    # Card dimensions: dynamic width based on panel, 4 rows high
    # Cards stay at LEFT of panel (close to game area), padding goes to the right
    # ╔══════════════════════════════════════╗
    # ║ Title:                               ║
    # ║ Text here                            ║
    # ╚══════════════════════════════════════╝
    card_width = SIDE_PANEL_WIDTH - 2  # Full panel width minus side borders
    card_height = 4
    card_x = inner_start_x  # No centering - stick to left edge
    inner_width = card_width - 2  # Space inside the card (between ║ and ║)

    # Top sign ends at row: panel_start_y + 1 + 4 = panel_start_y + 5
    # Bottom sign starts at: panel_end_y - 5
    # Available space: from panel_start_y + 6 to panel_end_y - 6
    top_sign_bottom = panel_start_y + 5
    bottom_sign_top = panel_end_y - 5

    # Space between signs for notification cards
    available_start = top_sign_bottom + 1
    available_end = bottom_sign_top - 1

    # Calculate how many cards fit (each is 4 rows + 1 spacing)
    available_rows = available_end - available_start
    cards_per_screen = max(1, available_rows // (card_height + 1))

    # Limit to max_stack from config
    try:
        max_cards = min(cards_per_screen, constants.notifications.max_stack)
    except AttributeError:
        max_cards = min(cards_per_screen, 3)

    # Draw notification cards (newest at top)
    for i, notif in enumerate(active_notifications[:max_cards]):
        card_y = available_start + i * (card_height + 1)

        if card_y + card_height > available_end:
            break

        text_max_len = inner_width - 2  # Leave 1 space padding on each side
        title = notif.get('title', '')[:text_max_len]
        text = notif.get('text', '')[:text_max_len]

        # Build border strings dynamically
        top_border = "╔" + "═" * (card_width - 2) + "╗"
        bottom_border = "╚" + "═" * (card_width - 2) + "╝"

        # Row 1: top border
        fb.put_string(card_x, card_y, top_border, CARD_BORDER_COLOR)

        # Row 2: title (or first line of text if no title)
        fb.put(card_x, card_y + 1, '║', CARD_BORDER_COLOR)
        if title:
            fb.put_string(card_x + 1, card_y + 1, f" {title:<{text_max_len}}", CARD_TITLE_COLOR)
        else:
            fb.put_string(card_x + 1, card_y + 1, f" {text:<{text_max_len}}", CARD_TEXT_COLOR)
        fb.put(card_x + card_width - 1, card_y + 1, '║', CARD_BORDER_COLOR)

        # Row 3: text (or empty if no title)
        fb.put(card_x, card_y + 2, '║', CARD_BORDER_COLOR)
        if title:
            fb.put_string(card_x + 1, card_y + 2, f" {text:<{text_max_len}}", CARD_TEXT_COLOR)
        else:
            fb.put_string(card_x + 1, card_y + 2, " " * inner_width, '')  # Empty
        fb.put(card_x + card_width - 1, card_y + 2, '║', CARD_BORDER_COLOR)

        # Row 4: bottom border
        fb.put_string(card_x, card_y + 3, bottom_border, CARD_BORDER_COLOR)


def _fb_render_pause_overlay(fb):
    """Render pause overlay and menu to framebuffer."""
    if not state.game.paused:
        return

    # "PAUSED" text in game area (centered)
    pause_y = constants.layout.height // 2 + HEADER_HEIGHT
    pause_x = max(0, (constants.layout.width // 2) - 3)
    fb.put_string(GAME_X_OFFSET + pause_x, pause_y, "PAUSED", YELLOW)

    # Pause menu in right panel
    right_start = GAME_X_OFFSET + constants.layout.width
    inner_start_x = right_start + 1

    # Menu options (in English)
    PAUSE_MENU_OPTIONS = [
        "RESUME",
        "RESTART",
        "SAVE & EXIT",
        "BIRDPEDIA",
        "GUIDE",
        "SETTINGS"
    ]

    # Menu dimensions - full panel width
    menu_width = SIDE_PANEL_WIDTH - 2  # Full panel width minus side borders
    inner_width = menu_width - 2  # Space inside the menu box (between ║ and ║)
    menu_x = inner_start_x  # Stick to left edge

    # Position menu below notifications area (roughly middle of panel)
    panel_start_y = HEADER_HEIGHT
    panel_end_y = constants.layout.height + HEADER_HEIGHT
    menu_start_y = panel_start_y + 8  # Below top level sign

    # Build dynamic border strings
    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = menu_start_y

    # Top border
    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    # Title - centered
    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title = "PAUSED"
    title_padded = title.center(inner_width)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    # Separator
    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    # Menu options
    selected_idx = state.ui.pause_menu_index
    option_text_width = inner_width - 2  # Space for option text (minus "> ")

    for i, option in enumerate(PAUSE_MENU_OPTIONS):
        fb.put(menu_x, y, '║', MENU_BORDER_COLOR)

        if i == selected_idx:
            # Selected option: show arrow and highlight
            fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(menu_x + 2, y, f" {option:<{option_text_width}}", MENU_SELECTED_COLOR)
        else:
            # Unselected option
            fb.put_string(menu_x + 1, y, f"  {option:<{option_text_width}}", MENU_NORMAL_COLOR)

        fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    # Bottom border
    fb.put_string(menu_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    # Hint at bottom (in English)
    hint = "↑↓ Navigate  ⏎ Select"
    fb.put_string(menu_x, y, hint[:menu_width], MENU_BORDER_COLOR)