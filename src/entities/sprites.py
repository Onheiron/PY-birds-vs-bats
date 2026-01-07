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
# NOTE: These are loaded once at import time for backwards compatibility.
# For dynamic theme switching (accessibility mode), use get_dynamic_color()

RESET = "\033[0m"
STEALTH = "STEALTH"  # Sentinel for stealth bird type (rendered specially)

# Base colors (non-bird colors used for UI, effects, etc.)
GREEN = theme.get_base_color('green', -2)
CYAN = theme.get_base_color('cyan', -4)
BLACK = theme.get_base_color('black', 16)
DARK_GRAY = theme.get_base_color('dark_gray', 240)

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

# Obstacle tiers
OBSTACLE_TIER1 = theme.get_color('obstacles', 'tier1', 94)
OBSTACLE_TIER2 = theme.get_color('obstacles', 'tier2', 100)
OBSTACLE_TIER3 = theme.get_color('obstacles', 'tier3', 106)
OBSTACLE_TIER4 = theme.get_color('obstacles', 'tier4', 46)

# Bat tiers
BAT_TIER1 = theme.get_color('bats', 'tier1', 54)
BAT_TIER2 = theme.get_color('bats', 'tier2', 92)
BAT_TIER3 = theme.get_color('bats', 'tier3', 129)
BAT_TIER4 = theme.get_color('bats', 'tier4', 201)


# ============================================================================
# DYNAMIC COLOR ACCESS - For runtime theme switching
# ============================================================================
# Color name to theme lookup mapping
_COLOR_MAP = {
    # Base colors
    'GREEN': ('base', 'green', -2),
    'CYAN': ('base', 'cyan', -4),
    'BLACK': ('base', 'black', 16),
    'DARK_GRAY': ('base', 'dark_gray', 240),
    # Bird colors
    'YELLOW': ('birds', 'yellow', 220),
    'RED': ('birds', 'red', -1),
    'BLUE': ('birds', 'blue', -3),
    'WHITE': ('birds', 'white', -5),
    'CLOCKWORK': ('birds', 'clockwork', 244),
    'GOLD': ('birds', 'gold', 228),
    'PURPLE': ('birds', 'purple', 201),
    'ORANGE': ('birds', 'orange', 208),
    'PATCHWORK': ('birds', 'patchwork', 202),
    'COOKIE': ('birds', 'cookie', 180),
    'GLITCH': ('birds', 'glitch', 205),
    'DINOSAUR': ('birds', 'dinosaur', 46),
    # Obstacle tiers
    'OBSTACLE_TIER1': ('obstacles', 'tier1', 94),
    'OBSTACLE_TIER2': ('obstacles', 'tier2', 100),
    'OBSTACLE_TIER3': ('obstacles', 'tier3', 106),
    'OBSTACLE_TIER4': ('obstacles', 'tier4', 46),
    # Bat tiers
    'BAT_TIER1': ('bats', 'tier1', 54),
    'BAT_TIER2': ('bats', 'tier2', 92),
    'BAT_TIER3': ('bats', 'tier3', 129),
    'BAT_TIER4': ('bats', 'tier4', 201),
}


def get_dynamic_color(color_name):
    """Get a color dynamically from the current theme.

    This respects accessibility mode and theme changes at runtime.
    Use this in rendering code instead of the module-level constants
    when dynamic theme switching is needed.

    Args:
        color_name: Name of the color constant (e.g., 'YELLOW', 'RED', 'OBSTACLE_TIER1')

    Returns:
        ANSI escape sequence string for the color
    """
    if color_name == 'STEALTH':
        return STEALTH
    if color_name == 'RESET':
        return RESET

    mapping = _COLOR_MAP.get(color_name)
    if mapping:
        category, name, default = mapping
        if category == 'base':
            return theme.get_base_color(name, default)
        return theme.get_color(category, name, default)

    # Fallback to module constant if exists
    return globals().get(color_name, RESET)

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

# =============================================================================
# BIOME SYSTEM - 6 biomes, one per level group
# =============================================================================
# Biome 1: Windy Woods (Group 1: levels 1-1 to 1-3) - Conifer forest
# Biome 2: The Borders (Group 2: levels 2-1 to 2-3) - Plains with deciduous trees
# Biome 3: Rotten Marshes (Group 3: levels 3-1 to 3-3) - Swampy wetlands
# Biome 4: The Dark Swamp (Group 4: levels 4-1 to 4-3) - Deep dark swamp
# Biome 5: The Void Cave (Group 5: levels 5-1 to 5-3) - Underground cavern
# Biome 6: Mountain Range (Group 6: levels 6-1 to 6-3) - High mountain peaks

BIOME_NAMES = {
    1: "Windy Woods",
    2: "The Borders",
    3: "Rotten Marshes",
    4: "The Dark Swamp",
    5: "The Void Cave",
    6: "Mountain Range",
}

# =============================================================================
# BIOME 1: WINDY WOODS - Conifer forest (original)
# =============================================================================
WOODS_BG_LAYER1 = [
    "^  ^    ^  ^   ^    ^   ",
    " ^^  ^    ^'  ^  ^^   ^ ",
    "^   ^  ^^   ^   ^  ^  '^",
    "  ^^  ^   ^^  ^^   ^^ ^ ",
    " ^  ^^  ^   ^   ^^  ^   ",
    "^    ^ ^^  ^^ ^   ^  ^^ ",
]
WOODS_BG_LAYER2 = [
    "∧       ∧      '    ∧^      ∧   ",
    "                                ",
    "    ∧     '    ^∧           ∧   ",
    "                                ",
    "∧           ∧       ∧     '     ",
    "                                ",
    "        ∧       ∧           ∧   ",
    "           '                    ",
]

# Windy Woods obstacles - conifer tree tops
WOODS_OBSTACLE_T1 = [
    "⋀∧⋀",
    "∧^∧^",
]
WOODS_OBSTACLE_T2 = [
    " ∧⋀^  ",
    "⋀/^\\^⋀",
]
WOODS_OBSTACLE_T3 = [
    "   ⋀Λ⋀   ",
    " Λ^/⋀\\/\\ ",
    "Λ⋀/∧Λ^\\^\\",
]
WOODS_OBSTACLE_T4 = [
    "   ⋀Λ⋀   Λ   ",
    " Λ^/⋀\\/\\/^\\  ",
    "Λ⋀/∧Λ^\\^\\^^\\⋀",
]

# =============================================================================
# BIOME 2: THE BORDERS - Plains with deciduous trees
# =============================================================================
BORDERS_BG_LAYER1 = [
    "'  '    '  '   '    \"   ",
    " ''  '    ''  '   '   ' ",
    "'   '  ''   '   '  '  ''",
    "  ''  \"   ''  '    '' ' ",
    " '  ''  '   '   ''  '   ",
    "'    ' ''   ' '   '  '' ",
]
BORDERS_BG_LAYER2 = [
    "⌒       ⌒           ⌒       ⌒   ",
    "                                ",
    "    ⌢           ⌢           ⌢   ",
    "                                ",
    "⌒           ⌒       ⌒           ",
    "                                ",
    "        ⌢       ⌢           ⌢   ",
    "                                ",
]

# The Borders obstacles - deciduous tree tops with branches
BORDERS_OBSTACLE_T1 = [
    " ⌢/_",
    "∩⏜⋂⌢",
]
BORDERS_OBSTACLE_T2 = [
    "  ⌢/_ ",
    " (  )⌢",
    "⏜  ⏜ ",
]
BORDERS_OBSTACLE_T3 = [
    "  ⌢/_     ",
    " \\(  )⌢⌋  ",
    "⌒⏜(   )⏜⌒ ",
    "   ⏜⏜     ",
]
BORDERS_OBSTACLE_T4 = [
    "    ⌢/_        ",
    "   \\(  )⌢⌋     ",
    " ⌒⏜(    |/ )⏜⌒ ",
    "    ⏜  ⏜⌒      ",
]

# =============================================================================
# BIOME 3: ROTTEN MARSHES - Swampy wetlands
# =============================================================================
MARSHES_BG_LAYER1 = [
    "'  ~    '  ~   '    ~   ",
    " '~  '    '~  ~  '~   ' ",
    "~   '  '~   ~   '  ~  '~",
    "  '~  ~   '~  '~   '~ ~ ",
    " ~  '~  '   ~   '~  ~   ",
    "'    ~ '~  '~ ~   ~  '~ ",
]
MARSHES_BG_LAYER2 = [
    "~       ~           ~       ~   ",
    "                                ",
    "    ≈           ≈           ≈   ",
    "                                ",
    "~           ~       ~           ",
    "                                ",
    "        ≈       ≈           ≈   ",
    "                                ",
]

# Rotten Marshes obstacles - gnarled twisted trees
MARSHES_OBSTACLE_T1 = [
    "_|\\_",
    "‾|⌒\\",
]
MARSHES_OBSTACLE_T2 = [
    "_\\ ‾\\_",
    " \\\\//‾ ",
    " |O \\",
]
MARSHES_OBSTACLE_T3 = [
    " //‾ / //_",
    "_\\\\ | //__",
    "  \\\\Y//‾\\\\",
    "  |() \\   ",
]
MARSHES_OBSTACLE_T4 = [
    " //‾ / ___//   ",
    "_\\\\ | //_\\‾‾   ",
    "  \\\\Y //‾\\\\_//_",
    " \\\\  / \\  ‾‾‾\\\\",
    "   | (o) \\//__  ",
    "\\/       |// //",
]

# =============================================================================
# BIOME 4: THE DARK SWAMP - Deep dark swamp
# =============================================================================
SWAMP_BG_LAYER1 = [
    "~  ≈    ~  ≈   ~    ≈   ",
    " ~≈  ~    ~≈  ≈  ~≈   ~ ",
    "≈   ~  ~≈   ≈   ~  ≈  ~≈",
    "  ~≈  ≈   ~≈  ~≈   ~≈ ≈ ",
    " ≈  ~≈  ~   ≈   ~≈  ≈   ",
    "~    ≈ ~≈  ~≈ ≈   ≈  ~≈ ",
]
SWAMP_BG_LAYER2 = [
    "≀       ≀           ≀       ≀   ",
    "                                ",
    "    ≀≀          ≀≀          ≀≀  ",
    "                                ",
    "≀           ≀       ≀           ",
    "                                ",
    "        ≀≀      ≀≀          ≀≀  ",
    "                                ",
]

# Dark Swamp obstacles - longer twisted branches spanning more lanes
SWAMP_OBSTACLE_T1 = [
    " |\\ ",
    "//¯ ",
]
SWAMP_OBSTACLE_T2 = [
    " _|\\_ ",
    " ¯\\\\/ ",
    " /()  ",
]
SWAMP_OBSTACLE_T3 = [
    "  _|\\__/|_   ",
    "  ¯\\\\__//¯   ",
    "   \\\\||//    ",
    "   /(  )\\    ",
]
SWAMP_OBSTACLE_T4 = [
    " __|\\_____/|\\__  ",
    " ¯\\\\__===__//¯¯  ",
    "  ¯\\\\\\|||///¯    ",
    "   / (===) \\     ",
]

# =============================================================================
# BIOME 5: THE VOID CAVE - Underground cavern
# =============================================================================
CAVE_BG_LAYER1 = [
    "*  °    *  °   *    °   ",
    " *°  *    *°  °  *°   * ",
    "°   *  *°   °   *  °  *°",
    "  *°  °   *°  *°   *° ° ",
    " °  *°  *   °   *°  °   ",
    "*    ° *°  *° °   °  *° ",
]
CAVE_BG_LAYER2 = [
    "•       •           •       •   ",
    "                                ",
    "    ·           ·           ·   ",
    "                                ",
    "•           •       •           ",
    "                                ",
    "        ·       ·           ·   ",
    "                                ",
]

# Void Cave obstacles - rocky formations / stalagmites
CAVE_OBSTACLE_T1 = [
    " /\\ ",
    "⋀/⋀\\",
]
CAVE_OBSTACLE_T2 = [
    " ⋀/\\  ",
    "⋀/⋀^\\ ",
]
CAVE_OBSTACLE_T3 = [
    "  ⋀/\\◠/\\  ",
    " ⋀/⋀^\\⋀⋀\\ ",
    "/⋀/___\\⋀\\ ",
]
CAVE_OBSTACLE_T4 = [
    "   ⋀/\\◠/\\ ⋀/\\   ",
    "  ⋀/⋀^\\⋀⋀\\/⋀^\\  ",
    " /⋀/___\\⋀\\_/⋀\\ ",
    "⋀/_______\\__⋀\\ ",
]

# =============================================================================
# BIOME 6: MOUNTAIN RANGE - High mountain peaks with clouds
# =============================================================================
MOUNTAIN_BG_LAYER1 = [
    "⌒  ⌢    ⌒  ⌢   ⌒    ⌢   ",
    " ⌒⌢  ⌒    ⌒⌢  ⌢  ⌒⌢   ⌒ ",
    "⌢   ⌒  ⌒⌢   ⌢   ⌒  ⌢  ⌒⌢",
    "  ⌒⌢  ⌢   ⌒⌢  ⌒⌢   ⌒⌢ ⌢ ",
    " ⌢  ⌒⌢  ⌒   ⌢   ⌒⌢  ⌢   ",
    "⌒    ⌢ ⌒⌢  ⌒⌢ ⌢   ⌢  ⌒⌢ ",
]
MOUNTAIN_BG_LAYER2 = [
    "☁       ☁           ☁       ☁   ",
    "                                ",
    "    ☁           ☁           ☁   ",
    "                                ",
    "☁           ☁       ☁           ",
    "                                ",
    "        ☁       ☁           ☁   ",
    "                                ",
]

# Mountain Range obstacles - mountain peaks
MOUNTAIN_OBSTACLE_T1 = [
    " /\\ ",
    "/⋀\\",
]
MOUNTAIN_OBSTACLE_T2 = [
    " /\\⋀  ",
    "/⋀\\/\\ ",
]
MOUNTAIN_OBSTACLE_T3 = [
    "   /\\⋀/\\  ",
    "  /⋀\\/⋀\\ ",
    " /___\\/\\ ",
]
MOUNTAIN_OBSTACLE_T4 = [
    "    /\\⋀/\\  ⋀   ",
    "   /⋀\\/⋀\\/⋀\\  ",
    "  /__\\/⋀\\/⋀\\  ",
    " /____\\/____\\ ",
]

# Cloud/fog overlay for Mountain Range (rendered in foreground)
MOUNTAIN_CLOUD_SPRITES = [
    ["  ⌒⌢⌒  ", " ⌢⌒⌢⌒⌢ ", "⌒⌢⌒⌢⌒⌢⌒"],
    [" ☁☁☁ ", "☁☁☁☁☁"],
    ["  ~~~  ", " ~~~~~ ", "~~~~~~~"],
]

# =============================================================================
# BIOME MAPPINGS
# =============================================================================

# Map biome (level_group 1-6) to background patterns
BIOME_BG_LAYER1 = {
    1: WOODS_BG_LAYER1,
    2: BORDERS_BG_LAYER1,
    3: MARSHES_BG_LAYER1,
    4: SWAMP_BG_LAYER1,
    5: CAVE_BG_LAYER1,
    6: MOUNTAIN_BG_LAYER1,
}

BIOME_BG_LAYER2 = {
    1: WOODS_BG_LAYER2,
    2: BORDERS_BG_LAYER2,
    3: MARSHES_BG_LAYER2,
    4: SWAMP_BG_LAYER2,
    5: CAVE_BG_LAYER2,
    6: MOUNTAIN_BG_LAYER2,
}

# Map biome to obstacle sprites by tier
BIOME_OBSTACLES = {
    1: {1: WOODS_OBSTACLE_T1, 2: WOODS_OBSTACLE_T2, 3: WOODS_OBSTACLE_T3, 4: WOODS_OBSTACLE_T4},
    2: {1: BORDERS_OBSTACLE_T1, 2: BORDERS_OBSTACLE_T2, 3: BORDERS_OBSTACLE_T3, 4: BORDERS_OBSTACLE_T4},
    3: {1: MARSHES_OBSTACLE_T1, 2: MARSHES_OBSTACLE_T2, 3: MARSHES_OBSTACLE_T3, 4: MARSHES_OBSTACLE_T4},
    4: {1: SWAMP_OBSTACLE_T1, 2: SWAMP_OBSTACLE_T2, 3: SWAMP_OBSTACLE_T3, 4: SWAMP_OBSTACLE_T4},
    5: {1: CAVE_OBSTACLE_T1, 2: CAVE_OBSTACLE_T2, 3: CAVE_OBSTACLE_T3, 4: CAVE_OBSTACLE_T4},
    6: {1: MOUNTAIN_OBSTACLE_T1, 2: MOUNTAIN_OBSTACLE_T2, 3: MOUNTAIN_OBSTACLE_T3, 4: MOUNTAIN_OBSTACLE_T4},
}

def get_biome_obstacles(level_group):
    """Get obstacle sprites for the current biome."""
    return BIOME_OBSTACLES.get(level_group, BIOME_OBSTACLES[1])

def get_biome_bg(level_group):
    """Get background patterns for the current biome."""
    layer1 = BIOME_BG_LAYER1.get(level_group, BIOME_BG_LAYER1[1])
    layer2 = BIOME_BG_LAYER2.get(level_group, BIOME_BG_LAYER2[1])
    return layer1, layer2

def get_biome_name(level_group):
    """Get the name of the current biome."""
    return BIOME_NAMES.get(level_group, "Unknown")

# =============================================================================
# LEGACY OBSTACLE SPRITES (for backward compatibility)
# =============================================================================
# Default to Windy Woods (biome 1)
OBSTACLE_SPRITE_T1 = WOODS_OBSTACLE_T1
OBSTACLE_SPRITE_T2 = WOODS_OBSTACLE_T2
OBSTACLE_SPRITE_T3 = WOODS_OBSTACLE_T3
OBSTACLE_SPRITE_T4 = WOODS_OBSTACLE_T4

# Mappa tier -> sprite (legacy, use get_biome_obstacles instead)
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
