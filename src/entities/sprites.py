#!/usr/bin/env python3
"""
Sprite definitions and rendering functions for BVB.
Contains all ASCII art sprites for birds, bats, obstacles, and related rendering helpers.
"""
# Import theme from src (not src.core to avoid circular imports)
import src.theme as theme

# ============================================================================
# ANSI COLOR CODES - Loaded from theme.yml
# ============================================================================

# Base colors (non-bird colors used for UI, effects, etc.)
GREEN = theme.get_base_color('green', -2)
CYAN = theme.get_base_color('cyan', -4)
BLACK = theme.get_base_color('black', 16)
DARK_GRAY = theme.get_base_color('dark_gray', 240)
RESET = "\033[0m"

# Bird colors - MUST match bird_types.py (use 'birds' category)
YELLOW = theme.get_color('birds', 'yellow', 220)
RED = theme.get_color('birds', 'red', -1)
BLUE = theme.get_color('birds', 'blue', -3)
WHITE = theme.get_color('birds', 'white', -5)
CLOCKWORK = theme.get_color('birds', 'clockwork', 244)
GOLD = theme.get_color('birds', 'gold', 228)
PURPLE = theme.get_color('birds', 'purple', 201)
ORANGE = theme.get_color('birds', 'orange', 208)
PATCHWORK = theme.get_color('birds', 'patchwork', 202)
COOKIE = theme.get_color('birds', 'cookie', 180)
GLITCH = theme.get_color('birds', 'glitch', 205)
DINOSAUR = theme.get_color('birds', 'dinosaur', 46)
STEALTH = "STEALTH"  # Sentinel for stealth bird type (rendered specially)

# Obstacle tiers: brown to bright green (4 tiers)
OBSTACLE_TIER1 = theme.get_color('obstacles', 'tier1', 94)
OBSTACLE_TIER2 = theme.get_color('obstacles', 'tier2', 100)
OBSTACLE_TIER3 = theme.get_color('obstacles', 'tier3', 106)
OBSTACLE_TIER4 = theme.get_color('obstacles', 'tier4', 46)

# Bat tiers: dark blue-purple to shocking bright purple (4 tiers)
BAT_TIER1 = theme.get_color('bats', 'tier1', 54)
BAT_TIER2 = theme.get_color('bats', 'tier2', 92)
BAT_TIER3 = theme.get_color('bats', 'tier3', 129)
BAT_TIER4 = theme.get_color('bats', 'tier4', 201)

# Bird sprites - two frames for animation (compact version)
BIRD_UP_1 = [
    " . ",
    '/W\\',
]
BIRD_UP_2 = [
    "_._",
    " W ",
]
BIRD_DOWN_1 = [
    "\\M/",
    " ' ",
]
BIRD_DOWN_2 = [
    "_M_",
    " ' ",
]

# PATCHWORK bird sprites - mixes characters (. ' \ / M W) across frames
BIRD_PATCH_UP_1 = [
    " . ",
    "\\M/",
]
BIRD_PATCH_UP_2 = [
    " ' ",
    "/W\\",
]
BIRD_PATCH_DOWN_1 = [
    "\\M/",
    " ' ",
]
BIRD_PATCH_DOWN_2 = [
    "/W\\",
    " . ",
]

# DINOSAUR legendary bird sprites (3 lines × 5 chars)
DINOSAUR_UP_1 = [
    ' .|. ',
    '/\\O/\\',
    '  "  '
]
DINOSAUR_UP_2 = [
    '_.|._',
    ' \\O/ ',
    '  "  '
]
DINOSAUR_DOWN_1 = [
    '  "  ',
    '\\/O\\/',
    " '|' "
]
DINOSAUR_DOWN_2 = [
    '  "  ',
    '_/O\\_',
    " '|' "
]

# Bat sprites - two frames for animation (compact version)
BAT_FRAME_1 = [
    " _ ^^ _",
    "/|(;;)|\\",
]
BAT_FRAME_2 = [
    "__ ^^ __",
    " /(;;)\\",
]

# Background pattern
BG_PATTERN = "/\\/\\/\\"

# Obstacle sprites - tree tops, tiered by size
# Tier 1: piccolo, 1 lane (3 chars wide)
OBSTACLE_SPRITE_T1 = [
    " ∧ ",
    "/_\\",
]

# Tier 2: medio, 1 lane (5 chars wide, centered)
OBSTACLE_SPRITE_T2 = [
    " ∧/\\ ",
    "/___\\",
]

# Tier 3: grande, 2 lanes (9 chars wide)
OBSTACLE_SPRITE_T3 = [
    "   /\\  ",
    " ∧/vv\\/\\ ",
    "/_\\___\\_\\",
]

# Tier 4: enorme, 3 lanes (13 chars wide)
OBSTACLE_SPRITE_T4 = [
    "         ∧   ",
    "  ∧ /\\  /v\\  ",
    " /v\\vv\\/vvv\\ ",
    "/___\\__\\____\\",
]

# Mappa tier -> sprite
OBSTACLE_SPRITES = {
    1: OBSTACLE_SPRITE_T1,
    2: OBSTACLE_SPRITE_T2,
    3: OBSTACLE_SPRITE_T3,
    4: OBSTACLE_SPRITE_T4,
}

# Larghezza in lane per ogni tier
OBSTACLE_LANE_WIDTH = {
    1: 1,  # 1 lane
    2: 1,  # 1 lane
    3: 2,  # 2 lanes
    4: 3,  # 3 lanes
}

# Legacy: mantieni per compatibilità
OBSTACLE_SPRITE = OBSTACLE_SPRITE_T1

# Base colors (full HP) for color interpolation
BATS_BASE_RGB = (255, 0, 255)   # magenta FF00FF
OBST_BASE_RGB = (0, 255, 0)     # green 00FF00


# Rendering helper functions
def render_patchwork_line(line: str) -> str:
    """Return a string where each character in `line` is colored in a repeating patchwork pattern.

    The returned string does NOT include a cursor positioning escape; caller should place it.
    A final RESET is appended.
    """
    try:
        patch_colors = [RED, YELLOW, BLUE, GREEN, PURPLE, ORANGE, GOLD, CYAN, WHITE]
        parts = []
        for i, ch in enumerate(line):
            # Color each character; keep spacing visible (coloring spaces is acceptable here)
            parts.append(f"{patch_colors[i % len(patch_colors)]}{ch}")
        return "".join(parts) + RESET
    except Exception:
        # Fallback: return unmodified line with default reset
        return line + RESET


def render_clockwork_line(line: str, charge: int, blink_on: bool) -> str:
    """Render a single sprite line for CLOCKWORK birds.

    Only the characters '.' and "'" are colored according to charge and blink state.
    Other characters are rendered in the CLOCKWORK base color. A RESET is appended.
    """
    try:
        # Determine the active highlight color based on charge
        if charge is None:
            charge = 2
        if charge > 1:
            hl = GREEN
        elif charge == 1:
            hl = YELLOW
        else:
            hl = RED

        parts = []
        for ch in line:
            if ch in ('.', "'"):
                # Blink: when blink_on is False render as dark gray, else use highlight
                parts.append((hl if blink_on else DARK_GRAY) + ch)
            else:
                parts.append(CLOCKWORK + ch)
        return "".join(parts) + RESET
    except Exception:
        return CLOCKWORK + line + RESET
