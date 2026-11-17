"""Colour helpers: theme palette, dynamic colours, HP tinting and modifiers."""

import functools
import os
import re

import src.theme as theme
from src.core import constants
from src.entities.sprites import (
    BAT_TIER1,
    BAT_TIER2,
    BAT_TIER3,
    BAT_TIER4,
    BLUE,
    CLOCKWORK,
    COOKIE,
    CYAN,
    DARK_GRAY,
    DINOSAUR,
    GLITCH,
    GOLD,
    GREEN,
    OBSTACLE_TIER1,
    OBSTACLE_TIER2,
    OBSTACLE_TIER3,
    OBSTACLE_TIER4,
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
    get_dynamic_color,
)

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
    # Handle special cases (sentinel colors with custom rendering)
    if static_color == STEALTH:
        return STEALTH
    if static_color == RAINBOW:
        return RAINBOW  # Custom multicolor rendering
    if static_color == TWISTER:
        return TWISTER  # Custom gray+cyan rendering
    if static_color == RESET:
        return RESET

    # Look up the color name
    color_name = _STATIC_TO_DYNAMIC_NAME.get(static_color)
    if color_name:
        return get_dynamic_color(color_name)

    # Not in map - return as-is
    return static_color


MOD_FAINT = "\033[2m"  # Dim/faint text for background layers

MOD_BOLD = "\033[1m"  # Bold text for foreground (obstacles, birds, bats)

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


def get_shimmer_color(brightness):
    """Get ANSI color for cave shimmer based on brightness (0.0 to 1.0).

    Uses 256-color grayscale: 232 (darkest) to 255 (brightest white).
    """
    # Map brightness to grayscale range 232-255 (24 shades)
    gray_index = int(232 + brightness * 23)
    gray_index = max(232, min(255, gray_index))
    return f"\033[38;5;{gray_index}m"


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


@functools.lru_cache(maxsize=1)
def _truecolor_supported():
    """Whether the terminal advertises 24-bit colour (COLORTERM hint)."""
    return os.environ.get('COLORTERM', '').lower() in ('truecolor', '24bit')


@functools.lru_cache(maxsize=4096)
def _rgb_escape(r: int, g: int, b: int) -> str:
    """Foreground escape for an RGB colour (truecolor or 256-colour fallback)."""
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))

    if _truecolor_supported():
        return f"\033[38;2;{r};{g};{b}m"

    # Fallback: map 0-255 per channel onto the 6x6x6 colour cube
    code = 16 + 36 * int(r * 5 / 255) + 6 * int(g * 5 / 255) + int(b * 5 / 255)
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
            (0, 0, 0),
            (128, 0, 0),
            (0, 128, 0),
            (128, 128, 0),
            (0, 0, 128),
            (128, 0, 128),
            (0, 128, 128),
            (192, 192, 192),
            (128, 128, 128),
            (255, 0, 0),
            (0, 255, 0),
            (255, 255, 0),
            (0, 0, 255),
            (255, 0, 255),
            (0, 255, 255),
            (255, 255, 255),
        ]
        return standard[code]
    if code < 232:
        # 6x6x6 color cube
        code -= 16
        r = (code // 36) * 51
        g = ((code // 6) % 6) * 51
        b = (code % 6) * 51
        return (r, g, b)
    # Grayscale (232-255)
    gray = (code - 232) * 10 + 8
    return (gray, gray, gray)


_ANSI_256_COLOR = re.compile(r'\033\[38;5;(\d+)m')


@functools.lru_cache(maxsize=4096)
def dim_ansi_color(ansi_color: str, hp: int, max_hp: int) -> str:
    """Dim an ANSI 256-color code (like ``ESC[38;5;36m``) by the hp/max_hp ratio.

    Returns an RGB escape code with the dimmed color.
    """
    match = _ANSI_256_COLOR.search(ansi_color)
    if not match:
        # Fallback: return original if can't parse
        return ansi_color

    hp_percentage = hp / max_hp if max_hp > 0 else 0
    r, g, b = _256_to_rgb(int(match.group(1)))
    return _rgb_escape(int(r * hp_percentage), int(g * hp_percentage), int(b * hp_percentage))


# Side panel colors (loaded from theme)
PANEL_BORDER_COLOR = theme.get_color('panels', 'border', 238)

PANEL_BG_COLOR = theme.get_color('panels', 'background', 233)

# Speed gauge gradient colors (level 1-10: green -> yellow -> red)
GAUGE_GRADIENT = theme.get_gradient('gauge', 'gradient')

# Momentum bar gradient (0% -> 100%: red -> yellow -> green)
MOMENTUM_GRADIENT = theme.get_gradient('momentum', 'gradient')

GAUGE_OFF = theme.get_color('gauge', 'off', 238)

GAUGE_BLOCK_ON = "██████"  # Solid block for active segments

GAUGE_BLOCK_OFF = "------"  # Dashes for inactive segments (clearly different)

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


def get_position_color(y_pos):
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


def grade_letter_color(letter, fallback):
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
