import os
import sys
import random
import re

if os.name == 'nt':
    import msvcrt

from src.entities.sprites import *
from src.entities.sprites import get_dynamic_color
from src.core import constants
# Import theme from src (not src.core to avoid circular imports)
import src.theme as theme
from src.functions import compute_gear_from_momentum, calculate_gear_threshold, compute_prestige, compute_grade_from_xp, get_affected_lanes, find_bird_in_lane, get_mph_for_speed, get_level_milestones
from src.core import state


# ============================================================================
# DYNAMIC COLOR MAPPING - For accessibility mode theme switching
# ============================================================================
# Maps static color values to their dynamic color names
_STATIC_TO_DYNAMIC_NAME = {}


def _build_color_map():
    """Build the static-to-dynamic color name mapping."""
    global _STATIC_TO_DYNAMIC_NAME
    _STATIC_TO_DYNAMIC_NAME = {
        YELLOW: 'YELLOW',
        RED: 'RED',
        BLUE: 'BLUE',
        WHITE: 'WHITE',
        CLOCKWORK: 'CLOCKWORK',
        GOLD: 'GOLD',
        PURPLE: 'PURPLE',
        ORANGE: 'ORANGE',
        PATCHWORK: 'PATCHWORK',
        COOKIE: 'COOKIE',
        GLITCH: 'GLITCH',
        DINOSAUR: 'DINOSAUR',
        GREEN: 'GREEN',
        CYAN: 'CYAN',
        DARK_GRAY: 'DARK_GRAY',
        OBSTACLE_TIER1: 'OBSTACLE_TIER1',
        OBSTACLE_TIER2: 'OBSTACLE_TIER2',
        OBSTACLE_TIER3: 'OBSTACLE_TIER3',
        OBSTACLE_TIER4: 'OBSTACLE_TIER4',
        BAT_TIER1: 'BAT_TIER1',
        BAT_TIER2: 'BAT_TIER2',
        BAT_TIER3: 'BAT_TIER3',
        BAT_TIER4: 'BAT_TIER4',
    }

# Build the map at import time
_build_color_map()


def get_render_color(static_color):
    """Convert a static color to its dynamic equivalent.

    This respects accessibility mode - when enabled, returns the
    accessible theme color instead of the original.

    Args:
        static_color: A color value from state.birds.colors or similar

    Returns:
        The dynamic color from current theme, or the original if not mapped
    """
    # Handle special cases
    if static_color == STEALTH:
        return STEALTH
    if static_color == RESET:
        return RESET

    # Look up the color name
    color_name = _STATIC_TO_DYNAMIC_NAME.get(static_color)
    if color_name:
        return get_dynamic_color(color_name)

    # Not in map - return as-is
    return static_color

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
# ANSI TEXT MODIFIERS - For layer depth effects
# =============================================================================
MOD_FAINT = "\033[2m"   # Dim/faint text for background layers
MOD_BOLD = "\033[1m"    # Bold text for foreground (obstacles, birds, bats)
MOD_NORMAL = "\033[0m"  # Normal text for everything else


def apply_faint(color):
    """Apply faint modifier to a color code for background layers."""
    if not color:
        return MOD_FAINT
    # Prepend faint modifier as separate sequence before color
    return MOD_FAINT + color


def apply_bold(color):
    """Apply bold modifier to a color code for foreground game elements."""
    if not color:
        return MOD_BOLD
    # Prepend bold modifier as separate sequence before color
    return MOD_BOLD + color


# =============================================================================
# PARALLAX BACKGROUND PATTERNS - 3-layer scrolling effect
# =============================================================================
# Backgrounds are now biome-specific, loaded from sprites.py
# Use get_current_biome_bg() to get the current patterns

from src.entities.sprites import (get_biome_bg, WOODS_BG_LAYER1, WOODS_BG_LAYER2)

# Default patterns (Windy Woods) - used as fallback
TREE_PATTERN = WOODS_BG_LAYER1
TREE_PATTERN_HEIGHT = len(TREE_PATTERN)
TREE_PATTERN_WIDTH = 24

MID_TREE_PATTERN = WOODS_BG_LAYER2
MID_TREE_PATTERN_HEIGHT = len(MID_TREE_PATTERN)
MID_TREE_PATTERN_WIDTH = 32

# Layer 3 (fastest): Obstacles - handled separately in game logic

# Colors for parallax layers (loaded from theme)
TREE_BG_COLOR = theme.get_color('background', 'layer1', 234)
MID_TREE_COLOR = theme.get_color('background', 'layer2', 235)

# Biome names for theme lookup (level_group -> theme key)
BIOME_THEME_KEYS = {
    1: 'windy_woods',
    2: 'the_borders',
    3: 'rotten_marshes',
    4: 'the_dark_swamp',
    5: 'the_void_cave',
    6: 'mountain_range',
}


def get_biome_colors(level_group):
    """Get colors for the current biome's background layers from theme."""
    biome_key = BIOME_THEME_KEYS.get(level_group, 'windy_woods')
    layer1 = theme.get_biome_color(biome_key, 'bg_layer1', 235)
    layer2 = theme.get_biome_color(biome_key, 'bg_layer2', 236)
    return layer1, layer2


def get_biome_obstacle_color(level_group):
    """Get base color for obstacles in the current biome from theme."""
    biome_key = BIOME_THEME_KEYS.get(level_group, 'windy_woods')
    return theme.get_biome_color(biome_key, 'obstacles', 94)

def get_current_biome_bg():
    """Get background patterns for the current biome based on level_group."""
    level_group = state.game.level_group
    layer1, layer2 = get_biome_bg(level_group)
    return layer1, layer2

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
                        # Always reset first to clear any modifiers (bold/faint)
                        # then apply new color
                        if color:
                            line_chars.append(RESET + color)
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
                                # Always reset first to clear any modifiers (bold/faint)
                                # then apply new color
                                if color:
                                    output.append(RESET + color)
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


def color_from_hp_to_red(base_rgb: tuple, hp: int, max_hp: int) -> str:
    """Color that fades from base_rgb to red as HP decreases (stays visible)."""
    hp_percentage = hp / max_hp if max_hp > 0 else 0
    try:
        # At full HP: base color, at low HP: bright red
        # Interpolate from base_rgb to (255, 50, 50)
        target_r, target_g, target_b = 255, 50, 50
        r = int(base_rgb[0] * hp_percentage + target_r * (1 - hp_percentage))
        g = int(base_rgb[1] * hp_percentage + target_g * (1 - hp_percentage))
        b = int(base_rgb[2] * hp_percentage + target_b * (1 - hp_percentage))
    except Exception:
        r, g, b = 255, 50, 50
    return _rgb_escape(r, g, b)


# 256-color to RGB conversion table for the 6x6x6 color cube (indices 16-231)
def _256_to_rgb(code):
    """Convert 256-color code to RGB tuple."""
    if code < 16:
        # Standard colors - approximate values
        standard = [
            (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
            (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
            (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
            (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)
        ]
        return standard[code]
    elif code < 232:
        # 6x6x6 color cube
        code -= 16
        r = (code // 36) * 51
        g = ((code // 6) % 6) * 51
        b = (code % 6) * 51
        return (r, g, b)
    else:
        # Grayscale (232-255)
        gray = (code - 232) * 10 + 8
        return (gray, gray, gray)


def dim_ansi_color(ansi_color: str, hp: int, max_hp: int) -> str:
    """Dim an ANSI 256-color code based on HP percentage.
    
    Takes a color like '\033[38;5;36m' and dims it based on hp/max_hp ratio.
    Returns an RGB escape code with the dimmed color.
    """
    hp_percentage = hp / max_hp if max_hp > 0 else 0
    
    # Extract the color code from the ANSI sequence
    # Format: \033[38;5;XXXm
    import re
    match = re.search(r'\033\[38;5;(\d+)m', ansi_color)
    if not match:
        # Fallback: return original if can't parse
        return ansi_color
    
    color_code = int(match.group(1))
    
    # Convert to RGB
    r, g, b = _256_to_rgb(color_code)
    
    # Apply HP-based dimming
    r = int(r * hp_percentage)
    g = int(g * hp_percentage)
    b = int(b * hp_percentage)
    
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


def render_game():
    """Main render function using differential framebuffer."""
    fb = get_framebuffer()

    # Level is now computed from miles in update_miles(), not from score

    # Render all components to framebuffer
    _fb_render_side_panels(fb)  # Side panels FIRST (background)
    _fb_render_header(fb)
    _fb_render_background(fb)  # Sfondo alberi PRIMA di tutto il resto
    _fb_render_tree_boss_background(fb)  # Tree Boss faint bg AFTER biome bg (visible on top)
    _fb_render_level_line(fb)  # Level line in game area (before obstacles)
    _fb_render_right_panel_barriers(fb)  # Decorative barriers UNDER level signs
    _fb_render_right_panel_level_signs(fb)  # Level signs on TOP of barriers
    _fb_render_notifications(fb)  # Notification cards in right panel (between level signs)
    _fb_render_starting_line(fb)
    _fb_render_center_of_mass(fb)  # Dark blue dashed line at birds' center of mass
    _fb_render_obstacles(fb)
    _fb_render_boss(fb)  # Boss rendered BEFORE bats so bats appear in front
    _fb_render_bats(fb)
    _fb_render_mini_bats(fb)
    _fb_render_loot(fb)
    _fb_render_projectiles(fb)
    _fb_render_birds(fb)
    _fb_render_cloud_banks(fb)  # Mountain Range foreground clouds (on top of birds)
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
    # Now uses state.game.momentum (not score) for speed calculation
    # For speed 1, we go from 0 to threshold(2)
    # For speed N (N>1), we go from threshold(N) to threshold(N+1)
    momentum = state.game.momentum

    if current_speed >= max_speed:
        momentum_pct = 100.0
    else:
        if current_speed == 1:
            # At speed 1, progress goes from 0 to threshold for speed 2
            prev_threshold = 0
        else:
            # At speed N, progress goes from threshold(N) to threshold(N+1)
            prev_threshold = calculate_gear_threshold(current_speed)

        next_threshold = calculate_gear_threshold(current_speed + 1)
        momentum_range = next_threshold - prev_threshold
        momentum_progress = momentum - prev_threshold

        if momentum_range > 0:
            momentum_pct = min(100.0, max(0.0, (momentum_progress / momentum_range) * 100))
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


# Characters to hide in tree/branch rendering (overlap markers)
TREE_HIDDEN_CHARS = set('12345o')


def _fb_render_tree_boss_background(fb):
    """Render Tree Boss background tree (on top of biome background).

    This is called AFTER the biome background to create a layered effect.
    The tree is rendered with ANSI faint modifier to appear ghostly/atmospheric.
    The background scrolls down along with the branches.

    Sprite convention:
    - 'x' = solid fill (renders as space, overwrites biome background)
    - ' ' = transparent (biome background shows through, nothing rendered)
    - '1'-'5' = branch overlap markers (render as solid fill, hidden)
    - 'o' = flower position marker (render as solid fill, hidden)
    - Other chars = tree outline (rendered with faint color)
    """
    boss = state.enemies.boss
    if boss is None:
        return

    # Only render for tree boss type
    if boss.get('boss_type') != 'tree':
        return

    from src.entities.sprites import TREE_BOSS_BACKGROUND

    # Use WHITE color BUT faint for tree outline
    tree_outline_color = apply_faint("\033[1;37m")  # White faint

    # Start from left edge (x=0)
    tree_x_offset = 0

    # Get vertical offset for scrolling (background comes from above)
    bg_y_offset = boss.get('bg_y_offset', 0)

    # Tree is exactly 45 chars wide (same as game panel), so no overflow
    max_tree_x = constants.layout.width

    for line_idx, line in enumerate(TREE_BOSS_BACKGROUND):
        y_pos = line_idx + bg_y_offset  # Apply scroll offset
        if 0 <= y_pos < constants.layout.height:
            for i, char in enumerate(line):
                x_pos = tree_x_offset + i
                if 0 <= x_pos < max_tree_x:
                    screen_x = GAME_X_OFFSET + x_pos
                    if char == 'x' or char in TREE_HIDDEN_CHARS:
                        # Solid fill - render space to overwrite biome background
                        fb.put(screen_x, y_pos + HEADER_HEIGHT, ' ', '')
                    elif char != ' ':
                        # Tree outline character - render with white faint color
                        fb.put(screen_x, y_pos + HEADER_HEIGHT, char, tree_outline_color)


def _fb_render_background(fb):
    """Render parallax scrolling background for game area and right panel.

    3 layers with different scroll speeds (slowest to fastest):
    - Layer 1: Dense pattern - slowest, darkest (biome-specific)
    - Layer 2: Sparse pattern - medium speed, slightly lighter (biome-specific)
    - Layer 3: Obstacles - fastest (rendered separately)

    Can be disabled via config:
    - background.enabled: false  -> disables all background layers
    - background.parallax: false -> disables only the middle layer
    """
    # First, fill the entire game area with spaces to clear any artifacts
    for screen_y in range(constants.layout.height):
        for screen_x in range(constants.layout.width):
            fb.put(GAME_X_OFFSET + screen_x, screen_y + HEADER_HEIGHT, ' ', '')

    # Check if background is enabled (runtime settings override config)
    bg_enabled = state.settings.background_enabled
    if not bg_enabled:
        return

    bg_offset = state.ui.bg_offset
    mid_offset = state.ui.bg_mid_offset

    # Check if parallax is enabled (runtime settings override config)
    parallax_enabled = state.settings.parallax_enabled

    # Get biome-specific background patterns and colors
    layer1_pattern, layer2_pattern = get_current_biome_bg()
    layer1_height = len(layer1_pattern)
    layer1_width = len(layer1_pattern[0]) if layer1_pattern else 24
    layer2_height = len(layer2_pattern)
    layer2_width = len(layer2_pattern[0]) if layer2_pattern else 32

    # Get biome-specific colors
    layer1_color, layer2_color = get_biome_colors(state.game.level_group)

    # Right panel start position
    right_panel_start = GAME_X_OFFSET + constants.layout.width + 1  # After game area + border
    right_panel_inner_width = SIDE_PANEL_WIDTH - 2  # Exclude borders

    # Game area goes from row HEADER_HEIGHT to row height+HEADER_HEIGHT-1
    for screen_y in range(constants.layout.height):
        # === Layer 1: Slowest background (biome-specific pattern) ===
        pattern_y = (screen_y - bg_offset) % layer1_height
        pattern_line = layer1_pattern[pattern_y]
        # Apply faint modifier for background depth effect
        layer1_faint = apply_faint(layer1_color)

        # Fill game area by repeating pattern horizontally
        for screen_x in range(constants.layout.width):
            pattern_x = screen_x % layer1_width
            char = pattern_line[pattern_x] if pattern_x < len(pattern_line) else ' '
            if char != ' ':
                fb.put(GAME_X_OFFSET + screen_x, screen_y + HEADER_HEIGHT, char, layer1_faint)

        # Also render in right panel (continuing the pattern)
        for panel_x in range(right_panel_inner_width):
            pattern_x = (constants.layout.width + panel_x) % layer1_width
            char = pattern_line[pattern_x] if pattern_x < len(pattern_line) else ' '
            if char != ' ':
                fb.put(right_panel_start + panel_x, screen_y + HEADER_HEIGHT, char, layer1_faint)

        # === Layer 2: Medium speed (biome-specific pattern) - only if parallax enabled ===
        if parallax_enabled:
            mid_pattern_y = (screen_y - mid_offset) % layer2_height
            mid_pattern_line = layer2_pattern[mid_pattern_y]
            # Apply faint modifier for background depth effect
            layer2_faint = apply_faint(layer2_color)

            # Fill game area
            for screen_x in range(constants.layout.width):
                pattern_x = screen_x % layer2_width
                char = mid_pattern_line[pattern_x] if pattern_x < len(mid_pattern_line) else ' '
                if char != ' ':
                    fb.put(GAME_X_OFFSET + screen_x, screen_y + HEADER_HEIGHT, char, layer2_faint)

            # Also render in right panel
            for panel_x in range(right_panel_inner_width):
                pattern_x = (constants.layout.width + panel_x) % layer2_width
                char = mid_pattern_line[pattern_x] if pattern_x < len(mid_pattern_line) else ' '
                if char != ' ':
                    fb.put(right_panel_start + panel_x, screen_y + HEADER_HEIGHT, char, layer2_faint)


def _fb_render_header(fb):
    """Render header to framebuffer - 3 rows with graphical boxes.

    Shows: Lives, Prestige, Score, Biome in styled boxes.
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

    # Biome name
    biome_name = get_biome_name(state.game.level_group)

    # Calculate box positions - 4 boxes evenly spaced
    box_width = 18
    total_boxes_width = box_width * 4 + 6  # 4 boxes + spacing
    start_x = (TOTAL_WIDTH - total_boxes_width) // 2

    box1_x = start_x
    box2_x = start_x + box_width + 2
    box3_x = start_x + (box_width + 2) * 2
    box4_x = start_x + (box_width + 2) * 3

    # Row 0: Top borders
    fb.put_string(box1_x, 0, "╔" + "═" * (box_width - 2) + "╗", HEADER_BORDER)
    fb.put_string(box2_x, 0, "╔" + "═" * (box_width - 2) + "╗", HEADER_BORDER)
    fb.put_string(box3_x, 0, "╔" + "═" * (box_width - 2) + "╗", HEADER_BORDER)
    fb.put_string(box4_x, 0, "╔" + "═" * (box_width - 2) + "╗", HEADER_BORDER)

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

    # Box 4: BIOME
    fb.put(box4_x, 1, '║', HEADER_BORDER)
    biome_truncated = biome_name[:box_width - 3]  # Truncate if too long
    biome_centered = f" {biome_truncated:^{box_width - 3}}"
    fb.put_string(box4_x + 1, 1, biome_centered[:box_width - 2], HEADER_VALUE)
    fb.put(box4_x + box_width - 1, 1, '║', HEADER_BORDER)

    # Row 2: Bottom borders
    fb.put_string(box1_x, 2, "╚" + "═" * (box_width - 2) + "╝", HEADER_BORDER)
    fb.put_string(box2_x, 2, "╚" + "═" * (box_width - 2) + "╝", HEADER_BORDER)
    fb.put_string(box3_x, 2, "╚" + "═" * (box_width - 2) + "╝", HEADER_BORDER)
    fb.put_string(box4_x, 2, "╚" + "═" * (box_width - 2) + "╝", HEADER_BORDER)

    # Row 3: Separator line (this is where game area starts at row 4)
    fb.put_string(0, 3, "═" * TOTAL_WIDTH, HEADER_BORDER)


def _fb_render_starting_line(fb):
    """Render starting line to framebuffer."""
    starting_line_y = constants.layout.starting_line
    if starting_line_y < 0 or starting_line_y >= constants.layout.height:
        return

    # Determine base character based on active wind effects
    wind_up = state.powerups.wind_boss_up_bonus
    wind_down = state.powerups.wind_boss_down_penalty

    if state.powerups.tailwind_active:
        base_char = '^'
        base_color = BLUE
    elif wind_up > 0:  # Wind boss tailwind phase
        base_char = '^'
        base_color = BLUE
    elif wind_up < 0:  # Wind boss headwind phase
        base_char = 'v'
        base_color = RED
    else:
        base_char = '-'
        base_color = ''

    # Render base line first
    for i in range(constants.layout.width):
        char = base_char if i % 2 == 0 else ' '
        fb.put(GAME_X_OFFSET + i, starting_line_y + HEADER_HEIGHT, char, base_color)

    # Overlay spell markers on affected lanes
    for lane_idx in range(constants.layout.num_lanes):
        lane_x = constants.layout.lane_positions[lane_idx]

        # Check for silence spell (x marker, gray)
        if lane_idx in state.spells.silenced_lanes:
            fb.put(GAME_X_OFFSET + lane_x, starting_line_y + HEADER_HEIGHT, 'x', DARK_GRAY)

        # Check for repugnant wind spell (v marker, red)
        elif lane_idx in state.spells.repugnant_wind_lanes:
            fb.put(GAME_X_OFFSET + lane_x, starting_line_y + HEADER_HEIGHT, 'v', RED)


def _compute_momentum_factor(y_pos):
    """Compute MOMENTUM factor based on Y position (center of mass).

    Returns factor for momentum change:
    - -1.0 at starting_line (bottom) → momentum decreases
    -  0.0 at zero height (configurable via momentum_zero_height)
    - +2.0 at ceiling (top) → momentum increases fast
    """
    starting_line = constants.layout.starting_line
    ceiling = 1

    # Get zero height from config (0.0 = bottom, 1.0 = top)
    zero_fraction = getattr(constants.speed, 'momentum_zero_height', 0.33)
    zero_point = starting_line - (starting_line - ceiling) * zero_fraction

    if y_pos >= starting_line:
        return -1.0
    elif y_pos >= zero_point:
        # Between starting_line and zero point: -1.0 -> 0.0
        t = (starting_line - y_pos) / (starting_line - zero_point)
        return -1.0 + t * 1.0
    elif y_pos > ceiling:
        # Between zero point and ceiling: 0.0 -> +2.0
        t = (zero_point - y_pos) / (zero_point - ceiling)
        return t * 2.0
    else:
        return 2.0


def _get_position_color(y_pos):
    """Get color for center of mass line based on Y position.

    Red at bottom (starting_line) -> Green at top (ceiling).
    Uses faint modifier (ANSI code 2) for subtlety.
    """
    starting_line = constants.layout.starting_line
    ceiling = 1

    # Normalize position: 0 = bottom, 1 = top
    if starting_line == ceiling:
        t = 0.5
    else:
        t = (starting_line - y_pos) / (starting_line - ceiling)
    t = max(0.0, min(1.0, t))

    # Interpolate RGB from red (255, 0, 0) to green (0, 255, 0)
    r = int(255 * (1 - t))
    g = int(255 * t)
    b = 0

    # Convert to 256-color approximation
    # Use the 6x6x6 color cube (colors 16-231)
    r6 = int(r / 255 * 5)
    g6 = int(g / 255 * 5)
    b6 = int(b / 255 * 5)
    color_code = 16 + 36 * r6 + 6 * g6 + b6

    # Return ANSI with faint modifier (2m)
    return f"\033[2;38;5;{color_code}m"


def _fb_render_center_of_mass(fb):
    """Render a dashed line at the center of mass of active birds.

    Center of mass is calculated as weighted average of bird Y positions,
    where weight = bird speed (faster birds contribute more to the average).

    Line color: gradient from red (bottom) to green (top) with faint modifier.
    Also shows the current multiplier on the right side of the game panel.
    """
    # Calculate center of mass
    total_weight = 0.0
    weighted_sum = 0.0

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        bird_y = state.birds.y[i]
        # Skip orange birds in dormant state
        if bird_y >= constants.layout.height:
            continue

        bird_speed = state.birds.speeds[i]
        weight = max(1, bird_speed)  # Minimum weight of 1

        weighted_sum += bird_y * weight
        total_weight += weight

    if total_weight <= 0:
        return  # No active birds

    center_y = weighted_sum / total_weight

    # Convert to screen Y coordinate
    screen_y = int(center_y) + HEADER_HEIGHT + 2

    # Ensure within game area bounds
    if screen_y < HEADER_HEIGHT + 3 or screen_y >= constants.layout.height + HEADER_HEIGHT + 1:
        return

    # Get color based on position (red at bottom -> green at top) with faint
    line_color = _get_position_color(center_y)

    # Draw dashed line across the game area
    game_width = constants.layout.width

    for x in range(game_width):
        # Alternate between dash and space for dashed effect
        if x % 2 == 0:
            fb.put(GAME_X_OFFSET + x, screen_y, '-', line_color)


def _fb_render_obstacles(fb):
    """Render obstacles to framebuffer using biome-specific sprites and colors."""
    from src.entities.sprites import get_biome_obstacles, BOSS_DEAD, BAT_ARMOR, WIND_BOSS_DEAD

    # Get obstacle sprites for current biome (fallback)
    biome_obstacles = get_biome_obstacles(state.game.level_group)
    # Get biome base color for obstacles
    biome_base_color = get_biome_obstacle_color(state.game.level_group)

    for obs in state.enemies.obstacles:
        tier = obs.get('tier', 1)
        is_boss_corpse = obs.get('is_boss_corpse', False)
        is_wind_boss_corpse = obs.get('is_wind_boss_corpse', False)

        if is_boss_corpse:
            # Special rendering for boss corpse
            if is_wind_boss_corpse:
                sprite = WIND_BOSS_DEAD
            else:
                sprite = BOSS_DEAD
            obs_hp = obs.get('hp', 0)
            obs_max = obs.get('max_hp', obs_hp if obs_hp > 0 else 1)
            # Use red fade like the boss
            obs_color = apply_bold(color_from_hp_to_red(constants.colors.bats_base_rgb, obs_hp, obs_max))

            # Boss corpse uses exact x_pos, not centered on lane
            x_start = obs.get('x_pos', 0)
            for line_idx, line in enumerate(sprite):
                y_pos = obs['y_pos'] + line_idx
                if 0 <= y_pos < constants.layout.height:
                    for i, char in enumerate(line):
                        if char != ' ':
                            x_pos = x_start + i
                            if 0 <= x_pos < constants.layout.width:
                                fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, obs_color)
        else:
            # Normal obstacle rendering
            # Calculate color based on HP - dims biome color as obstacle takes damage
            max_hp = constants.obstacle.max_hp_by_tier.get(tier, obs.get('hp', 1))
            obs_color = apply_bold(dim_ansi_color(biome_base_color, obs.get('hp', 0), max_hp))

            # Usa sprite salvata nell'ostacolo (variante + flip), o fallback a default bioma
            sprite = obs.get('sprite')
            if sprite is None:
                sprite = biome_obstacles.get(tier, biome_obstacles.get(1, OBSTACLE_SPRITE_T1))

            sprite_width = max(len(line) for line in sprite)

            # Posizione x centrata sulla lane
            start_lane = obs['lane']
            center_x = constants.layout.lane_positions[start_lane]
            x_offset = sprite_width // 2

            for line_idx, line in enumerate(sprite):
                y_pos = obs['y_pos'] + line_idx
                if 0 <= y_pos < constants.layout.height:
                    for i, char in enumerate(line):
                        if char != ' ':  # Solo caratteri non-spazio
                            x_pos = center_x - x_offset + i
                            if 0 <= x_pos < constants.layout.width:
                                fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, obs_color)

            # Render flower if present
            flower = obs.get('flower')
            if flower and flower.get('active'):
                _fb_render_obstacle_flower(fb, obs, flower, center_x, x_offset)


def _fb_render_obstacle_flower(fb, obs, flower, center_x, x_offset):
    """Render a flower on a swamp obstacle."""
    from src.entities.sprites import FLOWER_COLORS, FLOWER_GROWTH_FRAMES, FLOWER_MATURE_FRAME

    frame = flower.get('frame', 0)
    flower_type = flower.get('type', 'red')
    rel_x = flower.get('rel_x', 0)
    rel_y = flower.get('rel_y', 0)

    # Calculate absolute position
    flower_x = center_x - x_offset + rel_x
    flower_y = obs['y_pos'] + rel_y

    if not (0 <= flower_y < constants.layout.height and 0 <= flower_x < constants.layout.width):
        return

    # Simple single-char representation for obstacle flowers
    # o -> O -> @ -> @ -> @ -> * (mature)
    simple_chars = ['o', 'O', '@', '@', '@', '*']
    if frame < len(simple_chars):
        char = simple_chars[frame]
    else:
        char = '*'

    # Color based on flower type - ALWAYS show color (not dim gray)
    flower_color = FLOWER_COLORS.get(flower_type, FLOWER_COLORS['red'])

    fb.put(GAME_X_OFFSET + flower_x, flower_y + HEADER_HEIGHT, char, flower_color)


def _fb_render_right_panel_barriers(fb):
    """Render decorative barriers in right panel using biome-specific sprites and colors."""
    from src.entities.sprites import get_biome_obstacles

    # Right panel position
    right_panel_start = GAME_X_OFFSET + constants.layout.width + 1  # After game area + border
    right_panel_inner_width = SIDE_PANEL_WIDTH - 2

    # Get obstacle sprites and color for current biome
    biome_obstacles = get_biome_obstacles(state.game.level_group)
    biome_obs_color = get_biome_obstacle_color(state.game.level_group)

    for barrier in state.enemies.right_panel_barriers:
        tier = barrier.get('tier', 1)
        sprite = biome_obstacles.get(tier, biome_obstacles.get(1, OBSTACLE_SPRITE_T1))
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
                            fb.put(x_pos, y_pos + HEADER_HEIGHT, char, biome_obs_color)


def _fb_render_bats(fb):
    """Render bats to framebuffer."""
    from src.entities.sprites import (
        ARMORED_BAT_FRAME_1, ARMORED_BAT_FRAME_2, BAT_ARMOR,
        DIVER_BAT_FRAME_1, DIVER_BAT_FRAME_2, DIVER_BAT_DIVE, DIVER_BAT_STUNNED,
        SPELLCASTER_BAT_FRAME_1, SPELLCASTER_BAT_FRAME_2, SPELLCASTER_BAT_CASTING
    )

    for bat in state.enemies.bats:
        bat_hp = bat.get('hp', 0)
        bat_max = bat.get('max_hp', bat_hp if bat_hp > 0 else 1)
        is_armored = bat.get('armored', False)
        is_diver = bat.get('diver', False)
        is_spellcaster = bat.get('spellcaster', False)
        diver_state = bat.get('diver_state', 'flying')
        spell_state = bat.get('spell_state', 'idle')

        # Apply bold modifier for foreground game elements
        bat_color = apply_bold(color_from_hp(constants.colors.bats_base_rgb, bat_hp, bat_max))

        # Choose sprite based on bat type and state
        if is_spellcaster:
            # Spellcaster bat sprites based on casting state
            if spell_state == 'casting':
                bat_sprite = SPELLCASTER_BAT_CASTING
            else:
                bat_sprite = SPELLCASTER_BAT_FRAME_1 if (state.game.frame_count // 3) % 2 == 0 else SPELLCASTER_BAT_FRAME_2
        elif is_armored:
            bat_sprite = ARMORED_BAT_FRAME_1 if (state.game.frame_count // 4) % 2 == 0 else ARMORED_BAT_FRAME_2
        elif is_diver:
            # Diver bat sprites based on state
            if diver_state == 'diving':
                bat_sprite = DIVER_BAT_DIVE
            elif diver_state in ('stunned', 'returning'):
                bat_sprite = DIVER_BAT_STUNNED
            else:  # flying
                bat_sprite = DIVER_BAT_FRAME_1 if (state.game.frame_count // 3) % 2 == 0 else DIVER_BAT_FRAME_2
        else:
            bat_sprite = BAT_FRAME_1 if (state.game.frame_count // 3) % 2 == 0 else BAT_FRAME_2

        for line_idx, line in enumerate(bat_sprite):
            y_pos = bat['y_pos'] + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':  # Solo caratteri non-spazio
                        char_color = bat_color
                        # Spellcaster star is colored differently when casting
                        if is_spellcaster and char == '*':
                            if spell_state == 'casting':
                                char_color = PURPLE  # Magic star glows purple when casting
                            else:
                                char_color = YELLOW  # Normal star is yellow
                        # For armored bats, color the outer parentheses with armor color
                        elif is_armored and line_idx == 1:  # Bottom line has the armor ()
                            if char == '(' or char == ')':
                                line_before = line[:i]
                                open_count = line_before.count('(')
                                close_count = line_before.count(')')
                                if (char == '(' and open_count == 0) or (char == ')' and i == len(line) - line[::-1].index(')') - 1):
                                    char_color = BAT_ARMOR
                        fb.put(GAME_X_OFFSET + bat['x_pos'] + i, y_pos + HEADER_HEIGHT, char, char_color)


def _fb_render_mini_bats(fb):
    """Render mini bats to framebuffer."""
    from src.entities.sprites import (
        MINI_BAT_FRAME_1, MINI_BAT_FRAME_2, MINI_BAT_ANIM_FRAMES,
        JUMPSCARE_BAT_FRAME_1, JUMPSCARE_BAT_FRAME_2, JUMPSCARE_BAT_SCARY_FACE
    )

    for mb in state.enemies.mini_bats:
        mb_hp = mb.get('hp', 0)
        mb_max = mb.get('max_hp', mb_hp if mb_hp > 0 else 1)
        # Use bat color but slightly different hue (more purple/pink)
        mb_color = apply_bold(color_from_hp((200, 50, 255), mb_hp, mb_max))

        mb_state = mb.get('state', 'active')
        anim_frame = mb.get('anim_frame', 0)
        is_jumpscare = mb.get('is_jumpscare', False)

        # Determine what to render based on state
        if mb_state == 'spawning':
            # Spawn animation: · → • → ⛌ → 〇
            if anim_frame < len(MINI_BAT_ANIM_FRAMES):
                char = MINI_BAT_ANIM_FRAMES[anim_frame]
                y_pos = mb['y_pos']
                if 0 <= y_pos < constants.layout.height:
                    fb.put(GAME_X_OFFSET + mb['x_pos'], y_pos + HEADER_HEIGHT, char, mb_color)

        elif mb_state == 'hiding':
            # Hide animation: reverse of spawn (〇 → ⛌ → • → ·)
            if 0 <= anim_frame < len(MINI_BAT_ANIM_FRAMES):
                char = MINI_BAT_ANIM_FRAMES[anim_frame]
                y_pos = mb['y_pos']
                if 0 <= y_pos < constants.layout.height:
                    fb.put(GAME_X_OFFSET + mb['x_pos'], y_pos + HEADER_HEIGHT, char, mb_color)

        else:  # 'active'
            y_pos = mb['y_pos']

            # Jumpscare bat with scary face active
            if is_jumpscare and mb.get('scary_face_timer', 0) > 0:
                # Render scary face sprite (3 lines tall)
                for line_offset, line in enumerate(JUMPSCARE_BAT_SCARY_FACE):
                    render_y = y_pos - 1 + line_offset
                    if 0 <= render_y < constants.layout.height:
                        sprite_width = len(line)
                        start_x = mb['x_pos'] - sprite_width // 2
                        for i, char in enumerate(line):
                            x = start_x + i
                            if 0 <= x < constants.layout.width:
                                fb.put(GAME_X_OFFSET + x, render_y + HEADER_HEIGHT, char, mb_color)
            elif is_jumpscare:
                # Jumpscare bat uses multi-line Diver Bat sprite
                sprite = JUMPSCARE_BAT_FRAME_1 if (state.game.frame_count // 4) % 2 == 0 else JUMPSCARE_BAT_FRAME_2
                for line_offset, line in enumerate(sprite):
                    render_y = y_pos + line_offset
                    if 0 <= render_y < constants.layout.height:
                        sprite_width = len(line)
                        start_x = mb['x_pos'] - sprite_width // 2
                        for i, char in enumerate(line):
                            x = start_x + i
                            if 0 <= x < constants.layout.width:
                                fb.put(GAME_X_OFFSET + x, render_y + HEADER_HEIGHT, char, mb_color)
            else:
                # Normal mini bat - single line sprite
                sprite = MINI_BAT_FRAME_1 if (state.game.frame_count // 4) % 2 == 0 else MINI_BAT_FRAME_2
                if 0 <= y_pos < constants.layout.height:
                    sprite_width = len(sprite)
                    start_x = mb['x_pos'] - sprite_width // 2
                    for i, char in enumerate(sprite):
                        x = start_x + i
                        if 0 <= x < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x, y_pos + HEADER_HEIGHT, char, mb_color)


def _fb_render_boss(fb):
    """Render boss to framebuffer."""
    boss = state.enemies.boss
    if boss is None:
        return

    # Route to specific boss renderer if applicable
    boss_type = boss.get('boss_type', 'normal')
    if boss_type == 'wind':
        _fb_render_wind_boss(fb)
        return
    elif boss_type == 'jelly':
        _fb_render_jelly_boss(fb)
        return
    elif boss_type == 'tree':
        _fb_render_tree_boss(fb)
        return

    from src.entities.sprites import (
        BOSS_FRAME_1, BOSS_FRAME_2, BOSS_SCREAM, BOSS_DEAD, BAT_ARMOR
    )

    boss_hp = boss.get('hp', 0)
    boss_max = boss.get('max_hp', boss_hp if boss_hp > 0 else 1)
    boss_state = boss.get('state', 'active')

    # Choose sprite based on state
    if boss_state == 'dying' or boss_state == 'dead':
        boss_sprite = BOSS_DEAD
    elif boss_state == 'screaming':
        boss_sprite = BOSS_SCREAM
    else:
        # Alternate between frames
        anim_frame = boss.get('anim_frame', 0)
        boss_sprite = BOSS_FRAME_1 if anim_frame == 0 else BOSS_FRAME_2

    # Color based on HP - fades to red instead of dark (stays visible)
    boss_color = apply_bold(color_from_hp_to_red(constants.colors.bats_base_rgb, boss_hp, boss_max))

    for line_idx, line in enumerate(boss_sprite):
        y_pos = boss['y_pos'] + line_idx
        if 0 <= y_pos < constants.layout.height:
            for i, char in enumerate(line):
                if char != ' ':
                    x_pos = boss['x_pos'] + i
                    if 0 <= x_pos < constants.layout.width:
                        # Color outer parentheses with armor color
                        char_color = boss_color
                        if line_idx == 1:  # Middle line has the armor ()
                            if char == '(' or char == ')':
                                line_before = line[:i]
                                open_count = line_before.count('(')
                                # First ( and last ) are the armor
                                if (char == '(' and open_count == 0) or (char == ')' and i == len(line) - line[::-1].index(')') - 1):
                                    char_color = BAT_ARMOR
                        fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, char_color)


def _fb_render_wind_boss(fb):
    """Render Wind Boss to framebuffer."""
    boss = state.enemies.boss
    if boss is None:
        return

    from src.entities.sprites import (
        WIND_BOSS_MAX_UP, WIND_BOSS_PUSH_1, WIND_BOSS_PUSH_2, WIND_BOSS_PUSH_3, WIND_BOSS_PUSH_4,
        WIND_BOSS_MAX_DOWN, WIND_BOSS_PULL_1, WIND_BOSS_PULL_2, WIND_BOSS_PULL_3, WIND_BOSS_PULL_4,
        WIND_BOSS_DEAD
    )

    boss_hp = boss.get('hp', 0)
    boss_max = boss.get('max_hp', boss_hp if boss_hp > 0 else 1)
    boss_state = boss.get('state', 'active')
    anim_frame = boss.get('anim_frame', 0)

    # Map animation frame to sprite
    sprite_map = [
        WIND_BOSS_MAX_UP,   # 0
        WIND_BOSS_PUSH_1,   # 1
        WIND_BOSS_PUSH_2,   # 2
        WIND_BOSS_PUSH_3,   # 3
        WIND_BOSS_PUSH_4,   # 4
        WIND_BOSS_MAX_DOWN, # 5
        WIND_BOSS_PULL_1,   # 6
        WIND_BOSS_PULL_2,   # 7
        WIND_BOSS_PULL_3,   # 8
        WIND_BOSS_PULL_4,   # 9
    ]

    if boss_state == 'dying' or boss_state == 'dead':
        boss_sprite = WIND_BOSS_DEAD
    else:
        boss_sprite = sprite_map[anim_frame % len(sprite_map)]

    # Color based on HP
    boss_color = apply_bold(color_from_hp_to_red(constants.colors.bats_base_rgb, boss_hp, boss_max))

    for line_idx, line in enumerate(boss_sprite):
        y_pos = boss['y_pos'] + line_idx
        if 0 <= y_pos < constants.layout.height:
            for i, char in enumerate(line):
                if char != ' ':
                    x_pos = boss['x_pos'] + i
                    if 0 <= x_pos < constants.layout.width:
                        fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, boss_color)


def _fb_render_jelly_boss(fb):
    """Render Jelly Boss to framebuffer."""
    boss = state.enemies.boss
    if boss is None:
        return

    from src.entities.sprites import JELLY_BOSS_FRAMES, JELLY_BOSS_DEAD

    boss_hp = boss.get('hp', 0)
    boss_max = boss.get('max_hp', boss_hp if boss_hp > 0 else 1)
    boss_state = boss.get('state', 'active')
    anim_frame = boss.get('anim_frame', 0)

    # Choose sprite based on state
    if boss_state == 'dying' or boss_state == 'dead':
        boss_sprite = JELLY_BOSS_DEAD
    else:
        boss_sprite = JELLY_BOSS_FRAMES[anim_frame % len(JELLY_BOSS_FRAMES)]

    # Color based on HP - jelly boss uses a purple-ish base color
    jelly_base_rgb = (180, 100, 220)  # Purple/jelly color
    boss_color = apply_bold(color_from_hp_to_red(jelly_base_rgb, boss_hp, boss_max))

    for line_idx, line in enumerate(boss_sprite):
        y_pos = boss['y_pos'] + line_idx
        if 0 <= y_pos < constants.layout.height:
            for i, char in enumerate(line):
                if char != ' ':
                    x_pos = boss['x_pos'] + i
                    if 0 <= x_pos < constants.layout.width:
                        fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, boss_color)

    # Render bat spawn animation if active
    bat_anim = boss.get('bat_spawn_anim')
    if bat_anim and bat_anim.get('active'):
        anim_x = bat_anim.get('x_pos', 0)
        anim_y = bat_anim.get('y_pos', 0)
        anim_char = bat_anim.get('char', 'o')
        if 0 <= anim_y < constants.layout.height and 0 <= anim_x < constants.layout.width:
            # Spawn animation uses bright color
            spawn_color = "\033[1;35m"  # Bright magenta
            # Handle multi-char like "()"
            for i, c in enumerate(anim_char):
                fb.put(GAME_X_OFFSET + anim_x + i, anim_y + HEADER_HEIGHT, c, spawn_color)


def _fb_render_tree_boss(fb):
    """Render Tree Boss foreground elements (branches, flowers, status indicators).

    Note: The background tree is rendered separately by _fb_render_tree_boss_background()
    which is called BEFORE the biome background for proper layering.
    """
    boss = state.enemies.boss
    if boss is None:
        return

    from src.entities.sprites import (
        TREE_BOSS_BRANCHES, FLOWER_GROWTH_FRAMES, FLOWER_COLORS
    )

    # =========================================================================
    # 1. RENDER FOREGROUND BRANCHES (tangible, white bold, fades to red when damaged)
    # =========================================================================
    branches = boss.get('branches', [])

    # Branch base color (white, like tree background but bold/foreground)
    branch_base_rgb = (255, 255, 255)  # White

    for branch_idx, branch in enumerate(branches):
        if branch.get('destroyed'):
            continue  # Don't render destroyed branches

        branch_x = branch.get('x_pos', 0)
        branch_y = branch.get('y_pos', 0)
        branch_hp = branch.get('hp', 1)
        branch_max_hp = branch.get('max_hp', 1)
        sprite_idx = branch.get('sprite_idx', branch_idx % len(TREE_BOSS_BRANCHES))

        # Get branch sprite
        if sprite_idx < len(TREE_BOSS_BRANCHES):
            branch_sprite = TREE_BOSS_BRANCHES[sprite_idx]
        else:
            branch_sprite = TREE_BOSS_BRANCHES[0]

        # Color based on HP - white when full, fades to red as damaged
        branch_color = apply_bold(color_from_hp_to_red(branch_base_rgb, branch_hp, branch_max_hp))

        # Render branch sprite
        # Hide digits 1-5 (overlap markers) and 'o' (flower position markers)
        for line_idx, line in enumerate(branch_sprite):
            y_pos = branch_y + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ' and char not in TREE_HIDDEN_CHARS:
                        x_pos = branch_x + i
                        if 0 <= x_pos < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x_pos, y_pos + HEADER_HEIGHT, char, branch_color)

        # =====================================================================
        # 3. RENDER FLOWER on this branch (if active)
        # =====================================================================
        flower = branch.get('flower')
        if flower and flower.get('active'):
            flower_type = flower.get('type', 'red')
            flower_frame = flower.get('frame', 0)

            # Get flower sprite lines based on growth frame (can be multi-line)
            if flower_frame < len(FLOWER_GROWTH_FRAMES):
                flower_lines = FLOWER_GROWTH_FRAMES[flower_frame]
            else:
                flower_lines = FLOWER_GROWTH_FRAMES[-1]  # Mature flower

            # Get flower color
            flower_color = FLOWER_COLORS.get(flower_type, '\033[1;37m')  # Default white

            # Get flower position from branch (stored when flower spawns)
            flower_rel_x = flower.get('rel_x', 0)
            flower_rel_y = flower.get('rel_y', 0)

            # Calculate actual position
            flower_base_x = branch_x + flower_rel_x
            flower_base_y = branch_y + flower_rel_y

            # Render each line of the flower sprite (from bottom to top for multi-line)
            for line_offset, flower_line in enumerate(reversed(flower_lines)):
                flower_y = flower_base_y - line_offset
                # Center the flower line
                line_width = len(flower_line)
                flower_x = flower_base_x - line_width // 2

                if 0 <= flower_y < constants.layout.height:
                    for char_idx, char in enumerate(flower_line):
                        x_pos = flower_x + char_idx
                        if char != ' ' and 0 <= x_pos < constants.layout.width:
                            fb.put(GAME_X_OFFSET + x_pos, flower_y + HEADER_HEIGHT, char, flower_color)

    # =========================================================================
    # 4. RENDER STATUS INDICATORS for stunned/frozen/poisoned birds
    # =========================================================================
    import time as time_module
    import math
    now = time_module.time()

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


def _fb_render_cloud_banks(fb):
    """Render Mountain Range cloud banks (foreground fog that obscures game area)."""
    # Only render in Mountain Range biome
    if state.game.level_group != 6:
        return

    # Cloud color - semi-transparent white/gray
    CLOUD_COLOR = "\033[38;5;251m"  # Light gray

    # Cloud characters for different densities
    cloud_chars = ['░', '▒', '▓', '~', '⌒', '⌢']

    for cloud in state.enemies.cloud_banks:
        x_pos = cloud['x_pos']
        y_pos = cloud['y_pos']
        width = cloud['width']
        height = cloud['height']

        for dy in range(height):
            screen_y = y_pos + dy
            if 0 <= screen_y < constants.layout.height:
                for dx in range(width):
                    screen_x = x_pos + dx
                    if 0 <= screen_x < constants.layout.width:
                        # Create cloud pattern - denser in middle
                        dist_from_center_x = abs(dx - width // 2) / (width // 2 + 1)
                        dist_from_center_y = abs(dy - height // 2) / (height // 2 + 1)
                        density = 1 - (dist_from_center_x + dist_from_center_y) / 2

                        # Random character based on density
                        if density > 0.6:
                            char = '▓'
                        elif density > 0.4:
                            char = '▒'
                        elif density > 0.2:
                            char = '░'
                        else:
                            char = '~' if (dx + dy) % 3 == 0 else ' '

                        if char != ' ':
                            fb.put(GAME_X_OFFSET + screen_x, screen_y + HEADER_HEIGHT, char, CLOUD_COLOR)


def _fb_render_loot(fb):
    """Render loot items to framebuffer."""
    # Use dynamic colors for accessibility support
    loot_symbols = {
        'yellow_egg': ('⬯', 'YELLOW'), 'red_egg': ('⬯', 'RED'), 'blue_egg': ('⬯', 'BLUE'),
        'white_egg': ('⬯', 'WHITE'), 'clockwork_egg': ('⬯', 'CLOCKWORK'), 'gold_egg': ('⬯', 'GOLD'),
        'stealth_egg': ('⬯', 'DARK_GRAY'), 'patchwork_egg': ('⬯', 'PATCHWORK'),
        'orange_egg': ('⬯', 'ORANGE'), 'cookie_egg': ('⬯', 'COOKIE'), 'cookie_crumb': ('•', 'COOKIE'),
        'dinosaur_egg': ('⬯', 'DINOSAUR'), 'glitch_egg': ('⬯', 'GLITCH'), 'purple_egg': ('⬯', 'PURPLE'),
    }

    for loot in state.items.loot_items:
        y_pos = loot['y_pos']
        if 0 <= y_pos < constants.layout.height:
            loot_type = loot['type']
            rarity = loot.get('rarity', 'common')

            # Colore basato su rarity (use dynamic colors)
            if rarity == 'common':
                power_color = get_dynamic_color('YELLOW')
            elif rarity == 'uncommon':
                power_color = get_dynamic_color('RED')
            elif rarity == 'rare':
                power_color = get_dynamic_color('BLUE')
            else:
                power_color = get_dynamic_color('WHITE')

            if loot_type in loot_symbols:
                char, color_name = loot_symbols[loot_type]
                color = get_dynamic_color(color_name)
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

        # Get dynamic color for accessibility mode support
        bird_color = get_render_color(state.birds.colors[i])
        x_pos = state.birds.cols[i]

        # Check if bird is frozen or stunned (no animation)
        is_frozen = i in state.special.frozen_birds
        is_stunned = i in state.special.stunned_birds

        # Choose sprite based on direction and animation frame
        if is_frozen or is_stunned:
            # Frozen/stunned birds don't animate - use static sprite based on direction
            if state.birds.vy[i] == -1:
                sprite = BIRD_UP_1
            else:
                sprite = BIRD_DOWN_1
        else:
            # Normal animation
            if state.birds.vy[i] == -1:  # Moving up
                sprite = BIRD_UP_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_UP_2
            else:  # Moving down or stationary
                sprite = BIRD_DOWN_1 if (state.game.frame_count // 3) % 2 == 0 else BIRD_DOWN_2

        # Special handling for different bird types
        if is_frozen:
            # Frozen birds turn light blue (cyan)
            bird_color = '\033[1;96m'  # Bright cyan (light blue)
        elif state.birds.colors[i] == STEALTH:
            tangible = i in state.special.stealth_timers and state.special.stealth_timers.get(i, 0) > 0
            bird_color = get_render_color(WHITE) if tangible else get_render_color(DARK_GRAY)
        elif state.birds.colors[i] == BLUE and state.birds.power_used[i]:
            bird_color = get_render_color(CYAN)

        # Apply bold modifier for foreground game elements
        bird_color = apply_bold(bird_color)

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
                    fb.put(GAME_X_OFFSET + x_pos, orb_y + HEADER_HEIGHT, sym, get_render_color(PURPLE))


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

    # Menu dimensions - full panel width
    menu_width = SIDE_PANEL_WIDTH - 2
    inner_width = menu_width - 2
    menu_x = inner_start_x

    # Position menu
    panel_start_y = HEADER_HEIGHT
    menu_start_y = panel_start_y + 8

    # Check if we're in a settings submenu
    if state.ui.settings_menu is not None:
        _fb_render_settings_menu(fb, menu_x, menu_start_y, menu_width, inner_width)
    else:
        _fb_render_pause_menu(fb, menu_x, menu_start_y, menu_width, inner_width)


def _fb_render_pause_menu(fb, menu_x, menu_start_y, menu_width, inner_width):
    """Render the main pause menu."""
    PAUSE_MENU_OPTIONS = [
        "RESUME",
        "RESTART",
        "SAVE",
        "LOAD",
        "BIRDPEDIA",
        "SETTINGS",
        "MAIN MENU"
    ]

    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = menu_start_y

    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title_padded = "PAUSED".center(inner_width)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    selected_idx = state.ui.pause_menu_index
    option_text_width = inner_width - 2

    for i, option in enumerate(PAUSE_MENU_OPTIONS):
        fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
        if i == selected_idx:
            fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(menu_x + 2, y, f" {option:<{option_text_width}}", MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, y, f"  {option:<{option_text_width}}", MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    fb.put_string(menu_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    hint = "↑↓ Navigate  ⏎ Select"
    fb.put_string(menu_x, y, hint[:menu_width], MENU_BORDER_COLOR)


def _fb_render_settings_menu(fb, menu_x, menu_start_y, menu_width, inner_width):
    """Render the settings submenu based on current settings_menu state."""
    # Define all settings menus
    DIFFICULTY_NAMES = ["EASY", "NORMAL", "HARD", "HELL"]

    def get_toggle(value):
        return "ON" if value else "OFF"

    def get_difficulty():
        return DIFFICULTY_NAMES[state.settings.difficulty]

    # Build menu options based on current submenu
    if state.ui.settings_menu == 'main':
        title = "SETTINGS"
        options = [
            ("SOUND", "submenu"),
            ("GRAPHICS", "submenu"),
            ("CONTROLS", "submenu"),
            (f"DIFFICULTY      < {get_difficulty()} >", "cycle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'sound':
        title = "SOUND"
        options = [
            (f"SFX             < {get_toggle(state.settings.sfx_enabled)} >", "toggle"),
            (f"MUSIC           < {get_toggle(state.settings.music_enabled)} >", "toggle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'graphics':
        title = "GRAPHICS"
        options = [
            (f"BACKGROUND      < {get_toggle(state.settings.background_enabled)} >", "toggle"),
            (f"PARALLAX        < {get_toggle(state.settings.parallax_enabled)} >", "toggle"),
            (f"ACCESSIBILITY   < {get_toggle(state.settings.accessibility_enabled)} >", "toggle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'controls':
        title = "CONTROLS"
        # Build options dynamically from key bindings
        bindings = state.settings.key_bindings
        rebinding = state.ui.rebinding_control
        blink_on = (state.game.frame_count // 5) % 2 == 0  # Blink every 5 frames

        def get_key_display(control_name):
            key = bindings.get(control_name, '?')
            # If currently rebinding this control, show blinking or prompt
            if rebinding == control_name:
                return "___" if blink_on else "   "
            # Convert key names to symbols
            symbols = {'LEFT': '←', 'RIGHT': '→', 'UP': '↑', 'DOWN': '↓', 'SPACE': 'SPC'}
            return symbols.get(key, key)

        options = [
            (f"MOVE LEFT       {get_key_display('MOVE_LEFT'):>5}", "rebind"),
            (f"MOVE RIGHT      {get_key_display('MOVE_RIGHT'):>5}", "rebind"),
            (f"BOUNCE          {get_key_display('BOUNCE'):>5}", "rebind"),
            (f"SUCTION         {get_key_display('SUCTION'):>5}", "rebind"),
            (f"SWAP            {get_key_display('SWAP'):>5}", "rebind"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'save':
        title = "SAVE GAME"
        # Get save slot info
        from src.services import save_manager
        slots = save_manager.list_save_slots()

        def get_slot_info(slot_num):
            slot = slots.get(slot_num, {})
            if slot.get('exists'):
                level = slot.get('level_display', '?')
                ts = slot.get('timestamp', '')
                ts_display = save_manager.format_timestamp_display(ts) if ts else '???'
                return f"SLOT {slot_num} Lv{level} {ts_display}"
            return f"SLOT {slot_num}  (empty)"

        options = [
            (get_slot_info(1), "slot"),
            (get_slot_info(2), "slot"),
            (get_slot_info(3), "slot"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'load':
        title = "LOAD GAME"
        # Get save slot info
        from src.services import save_manager
        slots = save_manager.list_save_slots()

        def get_slot_info(slot_num):
            slot = slots.get(slot_num, {})
            label = "AUTO" if slot_num == 0 else f"SLOT {slot_num}"
            if slot.get('exists'):
                level = slot.get('level_display', '?')
                ts = slot.get('timestamp', '')
                ts_display = save_manager.format_timestamp_display(ts) if ts else '???'
                return f"{label} Lv{level} {ts_display}"
            return f"{label}  (empty)"

        options = [
            (get_slot_info(0), "slot"),
            (get_slot_info(1), "slot"),
            (get_slot_info(2), "slot"),
            (get_slot_info(3), "slot"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'birdpedia':
        title = "BIRDPEDIA"
        options = [
            ("GUIDE", "submenu"),
            ("BIRD-DEX", "submenu"),
            ("BAT-DEX", "submenu"),
            ("BIOMES", "submenu"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'guide':
        title = "GUIDE"
        options = [
            ("HOW TO PLAY", "submenu"),
            ("COMMANDS", "submenu"),
            ("OBSTACLES", "submenu"),
            ("ENEMIES", "submenu"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'guide_howto':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'howto')
        return
    elif state.ui.settings_menu == 'guide_commands':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'commands')
        return
    elif state.ui.settings_menu == 'guide_obstacles':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'obstacles')
        return
    elif state.ui.settings_menu == 'guide_enemies':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'enemies')
        return
    elif state.ui.settings_menu == 'birdpedia_list':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'birds')
        return
    elif state.ui.settings_menu == 'batpedia_list':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'bats')
        return
    elif state.ui.settings_menu == 'biomes_list':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'biomes')
        return
    else:
        return

    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = menu_start_y

    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title_padded = title.center(inner_width)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    selected_idx = state.ui.settings_index
    option_text_width = inner_width - 2

    for i, (option_text, option_type) in enumerate(options):
        fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
        if i == selected_idx:
            fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(menu_x + 2, y, f" {option_text:<{option_text_width}}"[:option_text_width+1], MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, y, f"  {option_text:<{option_text_width}}"[:option_text_width+2], MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    fb.put_string(menu_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    # Hint based on menu type and state
    if state.ui.settings_menu == 'controls':
        if state.ui.rebinding_control is not None:
            hint = "Press new key...  ESC Cancel"
        else:
            hint = "↑↓ Navigate  ⏎ Rebind  ESC Back"
    elif state.ui.settings_menu in ('save', 'load'):
        hint = "↑↓ Navigate  ⏎ Select  ESC Back"
    elif state.ui.settings_menu in ('birdpedia', 'guide'):
        hint = "↑↓ Navigate  ⏎ Select  ESC Back"
    else:
        hint = "↑↓ Navigate  ←→ Change  ⏎ Select"
    fb.put_string(menu_x, y, hint[:menu_width], MENU_BORDER_COLOR)


def _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, content_type):
    """Render birdpedia content pages."""
    from src.entities.sprites import (YELLOW, RED, BLUE, WHITE, PURPLE, ORANGE,
                                      STEALTH, CLOCKWORK, GOLD, PATCHWORK,
                                      COOKIE, DINOSAUR, GLITCH)

    # Get discovery state
    discovered_birds = state.discovery.birds
    discovered_bats = state.discovery.bats
    discovered_obstacles = state.discovery.obstacles

    # Bird entries with discovery check
    BIRD_ENTRIES = [
        ('YELLOW', "\x1b[93mYELLOW\x1b[0m - Bounces adjacent birds"),
        ('RED', "\x1b[91mRED\x1b[0m - Fires projectiles"),
        ('BLUE', "\x1b[94mBLUE\x1b[0m - Speed boost"),
        ('WHITE', "\x1b[97mWHITE\x1b[0m - Affects 4 lanes"),
        ('PURPLE', "\x1b[95mPURPLE\x1b[0m - Charge & launch"),
        ('ORANGE', "\x1b[38;5;208mORANGE\x1b[0m - Lays eggs, respawns"),
        ('STEALTH', "\x1b[90mSTEALTH\x1b[0m - Goes invisible"),
        ('CLOCKWORK', "\x1b[38;5;130mCLOCKWORK\x1b[0m - Wind-up speed"),
        ('GOLD', "\x1b[33mGOLD\x1b[0m - Extra points"),
        ('PATCHWORK', "\x1b[38;5;213mPATCHWORK\x1b[0m - Random powers"),
        ('COOKIE', "\x1b[38;5;215mCOOKIE\x1b[0m - Drops XP crumbs"),
        ('DINOSAUR', "\x1b[32mDINOSAUR\x1b[0m - Multi-press bounce"),
        ('GLITCH', "\x1b[38;5;51mGLITCH\x1b[0m - Unpredictable"),
    ]

    # Bat entries with discovery check
    BAT_ENTRIES = [
        ('BASIC', ["BASIC BAT", "  Standard flying enemy.", "  Scares birds on contact.", ""]),
        ('FAST', ["FAST BAT", "  Moves quickly across lanes.", "  Harder to avoid.", ""]),
        ('DIVE', ["DIVE BAT", "  Dives down at birds.", "  Very dangerous!", ""]),
        ('BOSS', ["BOSS BAT", "  Huge and powerful!", "  Requires many hits.", ""]),
    ]

    # Build dynamic bird list
    def get_bird_lines():
        lines = []
        discovered_count = 0
        for name, text in BIRD_ENTRIES:
            if name in discovered_birds:
                lines.append(text)
                discovered_count += 1
            else:
                lines.append("\x1b[90m??? - ???\x1b[0m")
        lines.append("")
        lines.append(f"Discovered: {discovered_count}/{len(BIRD_ENTRIES)}")
        return lines

    # Build dynamic bat list
    def get_bat_lines():
        lines = []
        discovered_count = 0
        for name, entry_lines in BAT_ENTRIES:
            if name in discovered_bats:
                lines.extend(entry_lines)
                discovered_count += 1
            else:
                lines.extend(["\x1b[90m??? BAT\x1b[0m", "  ???", "  ???", ""])
        lines.append(f"Discovered: {discovered_count}/{len(BAT_ENTRIES)}")
        return lines

    # Content definitions
    CONTENT = {
        'howto': {
            'title': 'HOW TO PLAY',
            'lines': [
                "Guide your birds to the finish",
                "line at the top of the screen!",
                "",
                "Birds bounce between the start",
                "and finish lines automatically.",
                "",
                "Press UP when a bird is falling",
                "to bounce it back up.",
                "",
                "Press UP when a bird is rising",
                "to activate its special power!",
                "",
                "Collect loot for score & XP.",
                "Avoid obstacles and enemies.",
                "",
                "Don't let birds fall off the",
                "bottom - you'll lose a life!",
            ]
        },
        'commands': {
            'title': 'COMMANDS',
            'lines': [
                "MOVEMENT:",
                "  LEFT/RIGHT - Move cursor",
                "  UP - Bounce / Power",
                "  DOWN - Suction (if active)",
                "",
                "SELECTION:",
                "  SPACE - Start/Execute swap",
                "",
                "GAME:",
                "  P - Pause game",
                "  X - Toggle XP overlay",
                "  M - Mute/Unmute audio",
                "  Q - Quit game",
                "",
                "Controls can be rebound in",
                "the SETTINGS > CONTROLS menu.",
            ]
        },
        'obstacles': {
            'title': 'OBSTACLES',
            'lines': [
                "TREE - Blocks bird movement." if 'TREE' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Birds bounce off trees." if 'TREE' in discovered_obstacles else "",
                "",
                "ROCK - Stuns birds on contact." if 'ROCK' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Stunned birds can't bounce." if 'ROCK' in discovered_obstacles else "",
                "",
                "CLOUD - Slows bird speed." if 'CLOUD' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Temporary speed reduction." if 'CLOUD' in discovered_obstacles else "",
                "",
                "BARRIER - Right panel hazard." if 'BARRIER' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Destroys loot on contact." if 'BARRIER' in discovered_obstacles else "",
                "",
                f"Discovered: {len(discovered_obstacles)}/4",
            ]
        },
        'enemies': {
            'title': 'ENEMIES',
            'lines': [
                "BAT - Flying enemy.",
                "  Scares birds on contact!",
                "  Scared birds fall faster",
                "  and cannot be bounced.",
                "",
                "RED projectiles can destroy",
                "bats for bonus points.",
                "",
                "BLUE birds near YELLOW birds",
                "can be cured of fear when",
                "the yellow bird bounces.",
                "",
                "More enemies appear at higher",
                "speed levels.",
            ]
        },
        'birds': {
            'title': 'BIRD-DEX',
            'lines': get_bird_lines()
        },
        'bats': {
            'title': 'BAT-DEX',
            'lines': get_bat_lines()
        },
        'biomes': {
            'title': 'BIOMES',
            'lines': [
                "WINDY WOODS (1-1 to 1-3)",
                "  Dense conifer forest.",
                "  Gentle start, basic obstacles.",
                "",
                "THE BORDERS (2-1 to 2-3)",
                "  Open plains, deciduous trees.",
                "  More space, faster foes.",
                "",
                "ROTTEN MARSHES (3-1 to 3-3)",
                "  Swampy wetlands, reeds.",
                "  Watch for murky waters!",
                "",
                "THE DARK SWAMP (4-1 to 4-3)",
                "  Deep dark swamp, twisted trees.",
                "  Visibility reduced, danger rises.",
                "",
                "THE VOID CAVE (5-1 to 5-3)",
                "  Underground cavern, stalactites.",
                "  No light, maximum peril!",
                "",
                "MOUNTAIN RANGE (6-1 to 6-3)",
                "  High peaks, thin air.",
                "  Cloud banks obscure vision!",
            ]
        }
    }

    content = CONTENT.get(content_type, {'title': 'UNKNOWN', 'lines': []})
    title = content['title']
    lines = content['lines']

    # Calculate height needed (title + separator + content + separator + back + bottom + hint)
    content_height = len(lines) + 7

    # Expand menu width for content
    expanded_width = min(40, menu_width + 10)
    expanded_x = menu_x - 5

    # Clear the entire area first to avoid showing previous menu underneath
    for clear_y in range(menu_start_y, menu_start_y + content_height + 2):
        for clear_x in range(expanded_x - 2, expanded_x + expanded_width + 2):
            if 0 <= clear_x < fb.width and 0 <= clear_y < fb.height:
                fb.put(clear_x, clear_y, ' ', '')

    top_border = "╔" + "═" * (expanded_width - 2) + "╗"
    separator_border = "╠" + "═" * (expanded_width - 2) + "╣"
    bottom_border = "╚" + "═" * (expanded_width - 2) + "╝"

    y = menu_start_y

    # Top border
    fb.put_string(expanded_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    # Title
    fb.put(expanded_x, y, '║', MENU_BORDER_COLOR)
    title_padded = title.center(expanded_width - 2)
    fb.put_string(expanded_x + 1, y, title_padded, YELLOW)
    fb.put(expanded_x + expanded_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    # Separator
    fb.put_string(expanded_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    # Content lines
    content_width = expanded_width - 4
    for line in lines:
        fb.put(expanded_x, y, '║', MENU_BORDER_COLOR)
        # Handle ANSI color codes - they don't take display width
        display_line = f" {line}"
        if '\x1b[' in line:
            # Line has color codes, write directly
            fb.put_string(expanded_x + 1, y, display_line, MENU_NORMAL_COLOR)
        else:
            # Pad plain lines
            fb.put_string(expanded_x + 1, y, f" {line:<{content_width}}"[:content_width+1], MENU_NORMAL_COLOR)
        fb.put(expanded_x + expanded_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    # Separator before back
    fb.put_string(expanded_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    # Back option (always selected)
    fb.put(expanded_x, y, '║', MENU_BORDER_COLOR)
    back_text = "< BACK"
    fb.put(expanded_x + 1, y, '>', MENU_ARROW_COLOR)
    fb.put_string(expanded_x + 2, y, f" {back_text:<{content_width}}"[:content_width+1], MENU_SELECTED_COLOR)
    fb.put(expanded_x + expanded_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    # Bottom border
    fb.put_string(expanded_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    # Hint
    hint = "⏎ or ESC to go back"
    fb.put_string(expanded_x, y, hint[:expanded_width], MENU_BORDER_COLOR)


# =============================================================================
# TITLE SCREEN RENDERING
# =============================================================================

# ASCII art logo for title screen
TITLE_LOGO = [
    "    ▄▄▄                                          ▄▄▄                 ",
    "   ██▀▀█▄            █▄                         ██▀▀█▄       █▄      ",
    "   ██ ▄█▀ ▀▀ ▄       ██                         ██ ▄█▀      ▄██▄     ",
    "   ██▀▀█▄ ██ ████▄▄████ ▄██▀█  ▀█▄ ██▀▄██▀█     ██▀▀█▄ ▄▀▀█▄ ██ ▄██▀█",
    " ▄ ██  ▄█ ██ ██   ██ ██ ▀███▄   ██▄██ ▀███▄   ▄ ██  ▄█ ▄█▀██ ██ ▀███▄",
    " ▀██████▀▄██▄█▀  ▄█▀████▄▄██▀    ▀█▀ █▄▄██▀   ▀██████▀▄▀█▄██▄███▄▄██▀",
]

TITLE_MENU_OPTIONS = ["CONTINUE", "NEW GAME", "LOAD", "BIRDPEDIA", "SETTINGS", "QUIT"]


def render_title_screen():
    """Render the title screen with logo and menu."""
    fb = get_framebuffer()

    # Difficulty names for display
    DIFFICULTY_NAMES = ["EASY", "NORMAL", "HARD", "HELL"]

    # Clear the screen with dark background
    for y in range(fb.height):
        for x in range(fb.width):
            fb.put(x, y, ' ', '')

    # Calculate centering
    logo_width = max(len(line) for line in TITLE_LOGO)
    logo_x = max(0, (TOTAL_WIDTH - logo_width) // 2)
    logo_y = 3  # Start a few lines from top

    # Render logo
    for i, line in enumerate(TITLE_LOGO):
        fb.put_string(logo_x, logo_y + i, line, YELLOW)

    # Menu area (below logo)
    menu_y = logo_y + len(TITLE_LOGO) + 3
    menu_width = 28  # Wider to fit difficulty selector
    menu_x = (TOTAL_WIDTH - menu_width) // 2

    # Menu box
    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    fb.put_string(menu_x, menu_y, top_border, MENU_BORDER_COLOR)
    menu_y += 1

    selected_idx = state.ui.title_menu_index

    for i, option in enumerate(TITLE_MENU_OPTIONS):
        fb.put(menu_x, menu_y, '║', MENU_BORDER_COLOR)

        # Special handling for NEW GAME - show difficulty selector
        if option == "NEW GAME":
            diff_name = DIFFICULTY_NAMES[state.settings.difficulty]
            option_text = f"NEW GAME  < {diff_name:^6} >"
            option_padded = option_text.center(menu_width - 2)
        else:
            option_padded = option.center(menu_width - 2)

        if i == selected_idx:
            fb.put_string(menu_x + 1, menu_y, option_padded, MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, menu_y, option_padded, MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, menu_y, '║', MENU_BORDER_COLOR)
        menu_y += 1

    fb.put_string(menu_x, menu_y, bottom_border, MENU_BORDER_COLOR)
    menu_y += 1

    # Hint - different when on NEW GAME
    if selected_idx == 1:  # NEW GAME
        hint = "↑↓ Navigate  ←→ Difficulty  ⏎ Start"
    else:
        hint = "↑↓ Navigate  ⏎ Select"
    hint_x = (TOTAL_WIDTH - len(hint)) // 2
    fb.put_string(hint_x, menu_y + 1, hint, MENU_BORDER_COLOR)

    # If in submenu, render overlay
    if state.ui.settings_menu == 'load':
        _fb_render_title_load_menu(fb, logo_y + len(TITLE_LOGO) + 2)
    elif state.ui.settings_menu is not None:
        # Render settings submenu overlay
        _fb_render_title_settings_menu(fb, logo_y + len(TITLE_LOGO) + 2)

    # Generate output and display
    output = fb.render()
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except BlockingIOError:
        pass


def _fb_render_title_load_menu(fb, start_y):
    """Render load menu overlay on title screen."""
    from src.services import save_manager
    slots = save_manager.list_save_slots()

    menu_width = 30
    menu_x = (TOTAL_WIDTH - menu_width) // 2

    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = start_y

    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    # Title
    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title_padded = "LOAD GAME".center(menu_width - 2)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    selected_idx = state.ui.settings_index
    option_text_width = menu_width - 4

    # Slot options: autosave + 3 manual slots + back
    for slot in range(0, 4):  # 0=autosave, 1-3=manual
        slot_info = slots.get(slot, {})
        if slot == 0:
            label = "AUTO"
        else:
            label = f"SLOT {slot}"

        if slot_info.get('exists'):
            level = slot_info.get('level_display', '?')
            ts = slot_info.get('timestamp', '')
            ts_display = save_manager.format_timestamp_display(ts) if ts else '???'
            option_text = f"{label}: Lv{level} {ts_display}"
        else:
            option_text = f"{label}: (empty)"

        fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
        if slot == selected_idx:
            fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(menu_x + 2, y, f" {option_text:<{option_text_width}}"[:option_text_width+1], MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, y, f"  {option_text:<{option_text_width}}"[:option_text_width+2], MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    # BACK option
    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    if 4 == selected_idx:
        fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
        fb.put_string(menu_x + 2, y, f" {'< BACK':<{option_text_width}}"[:option_text_width+1], MENU_SELECTED_COLOR)
    else:
        fb.put_string(menu_x + 1, y, f"  {'< BACK':<{option_text_width}}"[:option_text_width+2], MENU_NORMAL_COLOR)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    hint = "↑↓ Navigate  ⏎ Select  ESC Back"
    hint_x = (TOTAL_WIDTH - len(hint)) // 2
    fb.put_string(hint_x, y, hint, MENU_BORDER_COLOR)


def _fb_render_title_settings_menu(fb, start_y):
    """Render settings menu overlay on title screen."""
    DIFFICULTY_NAMES = ["EASY", "NORMAL", "HARD", "HELL"]

    def get_toggle(value):
        return "ON" if value else "OFF"

    def get_difficulty():
        return DIFFICULTY_NAMES[state.settings.difficulty]

    menu_width = 30
    menu_x = (TOTAL_WIDTH - menu_width) // 2

    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = start_y

    # Build menu based on current submenu
    if state.ui.settings_menu == 'main':
        title = "SETTINGS"
        options = [
            ("SOUND", "submenu"),
            ("GRAPHICS", "submenu"),
            ("CONTROLS", "submenu"),
            (f"DIFFICULTY    < {get_difficulty()} >", "cycle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'sound':
        title = "SOUND"
        options = [
            (f"SFX           < {get_toggle(state.settings.sfx_enabled)} >", "toggle"),
            (f"MUSIC         < {get_toggle(state.settings.music_enabled)} >", "toggle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'graphics':
        title = "GRAPHICS"
        options = [
            (f"BACKGROUND    < {get_toggle(state.settings.background_enabled)} >", "toggle"),
            (f"PARALLAX      < {get_toggle(state.settings.parallax_enabled)} >", "toggle"),
            (f"ACCESSIBILITY < {get_toggle(state.settings.accessibility_enabled)} >", "toggle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'controls':
        title = "CONTROLS"
        bindings = state.settings.key_bindings
        rebinding = state.ui.rebinding_control
        blink_on = (state.game.frame_count // 5) % 2 == 0

        def get_key_display(control_name):
            key = bindings.get(control_name, '?')
            if rebinding == control_name:
                return "___" if blink_on else "   "
            symbols = {'LEFT': '←', 'RIGHT': '→', 'UP': '↑', 'DOWN': '↓', 'SPACE': 'SPC'}
            return symbols.get(key, key)

        options = [
            (f"MOVE LEFT       {get_key_display('MOVE_LEFT'):>5}", "rebind"),
            (f"MOVE RIGHT      {get_key_display('MOVE_RIGHT'):>5}", "rebind"),
            (f"BOUNCE          {get_key_display('BOUNCE'):>5}", "rebind"),
            (f"SUCTION         {get_key_display('SUCTION'):>5}", "rebind"),
            (f"SWAP            {get_key_display('SWAP'):>5}", "rebind"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'birdpedia':
        title = "BIRDPEDIA"
        options = [
            ("GUIDE", "submenu"),
            ("BIRD-DEX", "submenu"),
            ("BAT-DEX", "submenu"),
            ("BIOMES", "submenu"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'guide':
        title = "GUIDE"
        options = [
            ("HOW TO PLAY", "submenu"),
            ("COMMANDS", "submenu"),
            ("OBSTACLES", "submenu"),
            ("ENEMIES", "submenu"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies',
                                     'birdpedia_list', 'batpedia_list', 'biomes_list'):
        # Render content view using the shared function
        content_map = {
            'guide_howto': 'howto',
            'guide_commands': 'commands',
            'guide_obstacles': 'obstacles',
            'guide_enemies': 'enemies',
            'birdpedia_list': 'birds',
            'batpedia_list': 'bats',
            'biomes_list': 'biomes',
        }
        _fb_render_birdpedia_content(fb, menu_x, start_y, menu_width, menu_width - 2,
                                     content_map[state.ui.settings_menu])
        return
    else:
        return

    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    # Title
    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title_padded = title.center(menu_width - 2)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    selected_idx = state.ui.settings_index
    option_text_width = menu_width - 4

    for i, (option_text, option_type) in enumerate(options):
        fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
        if i == selected_idx:
            fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(menu_x + 2, y, f" {option_text:<{option_text_width}}"[:option_text_width+1], MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, y, f"  {option_text:<{option_text_width}}"[:option_text_width+2], MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    fb.put_string(menu_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    # Hint based on menu type
    if state.ui.settings_menu == 'controls':
        if state.ui.rebinding_control is not None:
            hint = "Press new key...  ESC Cancel"
        else:
            hint = "↑↓ Navigate  ⏎ Rebind  ESC Back"
    elif state.ui.settings_menu in ('birdpedia', 'guide'):
        hint = "↑↓ Navigate  ⏎ Select  ESC Back"
    else:
        hint = "↑↓ Navigate  ←→ Change  ⏎ Select"
    hint_x = (TOTAL_WIDTH - len(hint)) // 2
    fb.put_string(hint_x, y, hint, MENU_BORDER_COLOR)