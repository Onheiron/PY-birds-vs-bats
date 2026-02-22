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
# New birds
RAINBOW = "RAINBOW"  # Sentinel for animated multicolor
TWISTER = "TWISTER"  # Sentinel for gray body + cyan wings
FROSTY = theme.get_color('birds', 'frosty', 159)  # Cyan/ice blue
POISON = theme.get_color('birds', 'poison', 118)  # Acid green
BERSERK = theme.get_color('birds', 'berserk', 124)  # Dark red
ROCK = theme.get_color('birds', 'rock', 94)  # Brown

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

# Armored bat armor color (cyan/light blue)
BAT_ARMOR = theme.get_color('bats', 'armor', 39)  # Light cyan-blue for armor


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
    'FROSTY': ('birds', 'frosty', 159),
    'POISON': ('birds', 'poison', 118),
    'BERSERK': ('birds', 'berserk', 124),
    'ROCK': ('birds', 'rock', 94),
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
    'BAT_ARMOR': ('bats', 'armor', 39),
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
    " _ ⋀⋀ _",
    "/|(;;)|\\",
]
BAT_FRAME_2 = [
    "__ ⋀⋀ __",
    " /(;;)\\",
]

# Armored bat sprites - heavier variant with armor plates
# The outer () are colored with BAT_ARMOR to show the armor
ARMORED_BAT_FRAME_1 = [
    "___  ⋀⋀  ___",
    " ¯/((;;))\\¯",
]
ARMORED_BAT_FRAME_2 = [
    " __  ⋀⋀  __",
    "//|((;;))|\\\\",
]

# Mini bat sprites - small bats that hide in tier 3+ obstacles (5 chars wide)
MINI_BAT_FRAME_1 = "¯/O\\¯"
MINI_BAT_FRAME_2 = "/|O|\\"

# Mini bat spawn/hide animation frames (in order)
MINI_BAT_ANIM_FRAMES = ['·', '•', '*', 'O']

# Diver bat sprites - bats that dive down at high speed
DIVER_BAT_FRAME_1 = [
    "__ ⋀⋀ __",
    "‾/(oo)\\‾",
]
DIVER_BAT_FRAME_2 = [
    " _ ⋀⋀ _ ",
    "/|(--)|\\"
]
DIVER_BAT_DIVE = [
    "__ ⋀⋀ __",
    "‾/(><)\\‾",
]
DIVER_BAT_STUNNED = [
    " _ ⋀⋀ _",
    "/|(@@)|\\"
]

# Jumpscare bat sprites - rare mini bat variant (uses Diver Bat base)
JUMPSCARE_BAT_FRAME_1 = DIVER_BAT_FRAME_1
JUMPSCARE_BAT_FRAME_2 = DIVER_BAT_FRAME_2

# Jumpscare bat scary face sprite (3 lines tall)
JUMPSCARE_BAT_SCARY_FACE = [
    "\\\\ ⋀_⋀ //",
    "‾/(o_o)\\‾",
    "  'U'  "
]

# Spellcaster bat sprites - bats that cast spells (3 lines tall with star)
SPELLCASTER_BAT_FRAME_1 = [
    "   *    ",
    "__ /\\ __",
    "‾/(oo)\\‾",
]
SPELLCASTER_BAT_FRAME_2 = [
    "    *   ",
    "__ /\\ __",
    "/|(--)|\\"
]
SPELLCASTER_BAT_CASTING = [
    "   *    ",
    "\\\\ /\\ //",
    "¯/(@@)\\¯",
]

# =============================================================================
# PORTAL SPRITES - Cave biome portals (biome 5)
# =============================================================================
# Portals appear in pairs - birds teleport between them, obstacles are destroyed

PORTAL_FRAME_1 = [
    "  _  ",
    "\\(@)\\",
    "  ‾  ",
]

PORTAL_FRAME_2 = [
    "___  ",
    "'(O)'",
    "  ‾‾‾",
]

# Portal colors (loaded from theme.yml - portals.color)
PORTAL_COLOR = theme.get_color('portals', 'color', 17)  # Default: very dark blue

# =============================================================================
# BOSS SPRITES - End of biome bosses
# =============================================================================
# Boss for biome 1 (Windy Woods) - appears at level 1-3
# The outer () are colored with BAT_ARMOR to show the armor

BOSS_FRAME_1 = [
    " ____  ⋀___⋀  ____",
    "  --/((•,^,•))\\-- ",
    "      (( x ))      ",
]

BOSS_FRAME_2 = [
    "  ___  ⋀___⋀  ___",
    " /-//((·,^,·))\\\\-\\",
    "   /  (( x ))  \\  ",
]

BOSS_SCREAM = [
    " ____  ⋀___⋀  ____",
    "  --/((>,O,<))\\-- ",
    "      (( x ))      ",
]

BOSS_DEAD = [
    "  ___  ⋀___⋀  ___",
    " /-//((x,^,x))\\\\-\\",
    "   /  (( x ))  \\  ",
]

# =============================================================================
# WIND BOSS - Boss for level 2-3 (The Borders)
# Flaps wings up and down creating tailwind/headwind effects
# =============================================================================

# Animation sequence: max_up -> push_down (1-4) -> max_down -> pull_up (1-4) -> repeat
WIND_BOSS_MAX_UP = [
    "    \\             /",
    "‾\\‾‾‾\\   /\\_/\\   /‾‾‾/‾",
    " /|   \\((> Y <))/   |\\",
    "  /---((  '‾'  ))---\\ ",
    "        W ‾‾‾ W         ",
]

WIND_BOSS_PUSH_1 = [
    "______   /\\_/\\    ______",
    " /    \\((> Y <)) /    \\",
    " ‾‾/  ((  '‾'  ))  \\‾‾ ",
    "        W ‾‾‾ W        ",
]

WIND_BOSS_PUSH_2 = [
    "  ____   /\\_/\\    ____   ",
    "‾‾    \\((> Y <)) /    ‾‾",
    " / |  ((  '‾'  ))  | \\   ",
    "        W ‾‾‾ W          ",
]

WIND_BOSS_PUSH_3 = [
    "    __   /\\_/\\    __   ",
    "/‾‾   \\((> Y <)) /   ‾‾\\",
    " //   ((  '‾'  ))   \\\\   ",
    "    ‾‾  W ‾‾‾ W  ‾‾     ",
]

WIND_BOSS_PUSH_4 = [
    "         /\\_/\\       ",
    "______ ((> Y <)) ______",
    " //  _((  '‾'  ))_  \\\\   ",
    "/\\/\\/   W ‾‾‾ W   \\/\\/\\ ",
]

WIND_BOSS_MAX_DOWN = [
    "         /\\_/\\       ",
    "______ ((o Y o)) ______",
    " //  _((  '‾'  ))_  \\\\   ",
    "/\\/\\/   W ‾‾‾ W   \\/\\/\\ ",
]

WIND_BOSS_PULL_1 = [
    "    __   /\\_/\\    __   ",
    "/‾‾   \\((o Y o)) /   ‾‾\\",
    " //   ((  '‾'  ))   \\\\   ",
    "    ‾‾  W ‾‾‾ W  ‾‾     ",
]

WIND_BOSS_PULL_2 = [
    "  ____   /\\_/\\    ____   ",
    "‾‾    \\((= Y =)) /    ‾‾",
    " / |  ((  '‾'  ))  | \\   ",
    "        W ‾‾‾ W           ",
]

WIND_BOSS_PULL_3 = [
    "______   /\\_/\\    ______",
    " /    \\((- Y -)) /    \\",
    " ‾‾/  ((  '‾'  ))  \\‾‾ ",
    "        W ‾‾‾ W         ",
]

WIND_BOSS_PULL_4 = [
    "    \\             /",
    "‾\\‾‾‾\\   /\\_/\\   /‾‾‾/‾",
    " /|   \\((- Y -))/   |\\",
    "  /---((  '‾'  ))---\\ ",
    "        W ‾‾‾ W         ",
]

WIND_BOSS_DEAD = [
    "         /\\_/\\       ",
    "______ ((x Y x)) ______",
    " //  _((  '‾'  ))_  \\\\   ",
    "/\\/\\/   W ‾‾‾ W   \\/\\/\\ ",
]

# Animation sequence for wind boss (indices into sprite list)
WIND_BOSS_ANIM_SEQUENCE = [
    'max_up',      # 0 - wings fully up (tailwind)
    'push_1',      # 1 - pushing down
    'push_2',      # 2 - pushing down
    'push_3',      # 3 - pushing down
    'push_4',      # 4 - pushing down
    'max_down',    # 5 - wings fully down (headwind starts)
    'pull_1',      # 6 - pulling up
    'pull_2',      # 7 - pulling up
    'pull_3',      # 8 - pulling up
    'pull_4',      # 9 - pulling up (back to max_up)
]

# =============================================================================
# JELLY BOSS - Boss for level 3-3 (Rotten Marshes)
# Oscillates and spawns bats from its head
# =============================================================================

JELLY_BOSS_FRAME_1 = [
    " ____             ____",
    "  /--\\   /\\_/\\   / --\\",
    "   /-_\\((^ Y ^))/_-\\  ",
    "      (( )'‾'( ))     ",
    "      ((   x   ))     ",
    "        W ‾‾‾ W        ",
]

JELLY_BOSS_FRAME_2 = [
    "                       ",
    "/‾‾‾‾\\   /\\_/\\   /‾‾‾‾\\",
    "/\\/‾\\_\\((> Y <))/_/‾\\/\\",
    "     ((  )'‾'(  ))     ",
    "      ((   x   ))     ",
    "        W ‾‾‾ W        ",
]

JELLY_BOSS_FRAME_3 = [
    "                       ",
    "_----_   /\\_/\\   _----_",
    "/\\/-\\_(( > Y < ))_/-\\/\\",
    "     ((   )‾(   ))     ",
    "      ((   x   ))     ",
    "        W ‾‾‾ W        ",
]

JELLY_BOSS_FRAME_4 = [
    "                       ",
    "         /\\_/\\         ",
    "/‾‾‾\\((  )•Y•(  ))/‾‾‾\\",
    "/‾/‾‾ ((  )‾(  )) ‾‾\\‾\\",
    "      ((   x   ))     ",
    "        W ‾‾‾ W        ",
]

JELLY_BOSS_FRAME_5 = [
    "                       ",
    "         /\\_/\\         ",
    "_---\\((  )•o•(  ))/---_",
    "//--\\_((  )|(  ))_/--\\\\",
    "      ((   x   ))     ",
    "        W ‾‾‾ W        ",
]

JELLY_BOSS_FRAME_6 = [
    "                       ",
    "       _⋀/(o)\\⋀_      ",
    "  ___((   )U(   ))___ ",
    " /-\\\\_  ((     )) _//-\\",
    " ' '  ((   x   ))  ' '",
    "        W ‾‾‾ W        ",
]

JELLY_BOSS_FRAME_7 = [
    "                       ",
    "        /\\_o_/\\       ",
    " _---\\(( @ x @ ))/---_",
    " //--\\_((  ~  ))_/--\\\\",
    "      ((   x   ))     ",
    "        W ‾‾‾ W        ",
]

JELLY_BOSS_FRAME_8 = [
    "                       ",
    "         /\\_/\\         ",
    " /‾‾‾\\(( > Y < ))/‾‾‾\\ ",
    " /‾/‾‾((  '‾'  )) ‾‾\\‾\\",
    "      ((   x   ))      ",
    "        W ‾‾‾ W         ",
]

JELLY_BOSS_FRAME_9 = [
    "                       ",
    "_----_   /\\_/\\   _----_",
    "/\\/-\\_(( • Y • ))_/-\\/\\",
    "      (( )'‾'( ))      ",
    "     ((    x    ))     ",
    "        W ‾‾‾ W         ",
]

JELLY_BOSS_FRAME_10 = [
    "                       ",
    "/‾‾‾‾\\   /\\_/\\   /‾‾‾‾\\",
    "/\\/‾\\_\\((> Y <))/_/‾\\/\\",
    "      (( )'‾'( ))      ",
    "     ((    x    ))     ",
    "        W ‾‾‾ W        ",
]

JELLY_BOSS_DEAD = [
    "                       ",
    "         /\\_/\\         ",
    " /‾‾‾\\(( x _ x ))/‾‾‾\\ ",
    " /‾/‾‾((  '‾'  )) ‾‾\\‾\\",
    "      ((   x   ))      ",
    "        W ‾‾‾ W         ",
]

# All jelly boss frames in sequence (1-10)
JELLY_BOSS_FRAMES = [
    JELLY_BOSS_FRAME_1,
    JELLY_BOSS_FRAME_2,
    JELLY_BOSS_FRAME_3,
    JELLY_BOSS_FRAME_4,
    JELLY_BOSS_FRAME_5,
    JELLY_BOSS_FRAME_6,
    JELLY_BOSS_FRAME_7,
    JELLY_BOSS_FRAME_8,  # Frame 8 - spawn bat here
    JELLY_BOSS_FRAME_9,
    JELLY_BOSS_FRAME_10,
]

# Animation frames for bat spawning from jelly boss (o -> O -> () -> bat)
JELLY_SPAWN_ANIM_FRAMES = ['o', 'O', '()', '/(@)\\', 'bat']

# =============================================================================
# TREE BOSS SPRITES - Giant tree spanning the entire game screen
# =============================================================================
# The tree boss has:
# - A large BACKGROUND tree (rendered with faint font, behind everything)
# - 5 FOREGROUND branches (tangible, birds collide with them)
# - FLOWERS that grow on branches (3 colors: red, blue, green)

# Background tree - 22 rows, 45 chars wide (fits game panel exactly)
# This is rendered with ANSI faint (\033[2m) behind everything
# 'x' = solid fill (replaces biome background with space)
# ' ' = transparent (biome background shows through)
# Digits 1-5 mark branch overlay positions (hidden at render time)
TREE_BOSS_BACKGROUND = [
    "                                             ",
    "                     ||\\\\                    ",
    "     |\\  /|          //x\\\\             /|    ",
    "     \\x\\|x|    *     \\\\xx||            ||   |\\",
    "*\\ \\\\*/||xxx\\\\  \\\\_// |xxx\\        /x| |//____/",
    "_\\\\_|x|||xxxx|   |x| ||xx||   \\\\|x|__||xx/‾‾‾\\\\",
    "\\\\__xxxxxxxx|| _  \\x\\|/xxxx\\     \\\\xxxx| __||‾‾",
    "//‾‾\\\\xxxxxx\\\\//  ||xxxxxxxx\\  ||xxxx//‾‾‾‾*",
    "_____||x/|xxx||  //xxxxxxUxx| //xx5x||___//__/",
    "‾//‾‾\\\\(@)x3xx\\\\||xxxxx|||4x|//xxxxx//‾‾‾‾‾\\\\‾",
    "     ||xx|xxxxx\\\\\\\\xxx\\|\\xxx||xx|\\x/x|__//___*",
    " *    \\xxx\\xxxxx||||xxx(@)xxx/xx(@)x/‾‾‾‾\\\\‾‾",
    "__\\_   \\_xxxxx\\\\xx\\\\xxx||xx/xxxx/xxx__//__",
    "‾‾//\\____\\x\\\\xxxx\\xx\\_xx\\xx//xxx__/‾\\\\‾‾*",
    "    * /‾‾‾\\\\|xx\\\\xxxxx\\\\‾‾x/2xx/    *",
    "          |||xxx|xxxxxx|xxUxx|/---\\\\__\\\\--*-/",
    "     /‾‾\\  \\\\xxUxx/1x//.\\\\xxx|||/‾‾\\____/‾‾‾\\",
    "    |x/xx\\ |||YxxxUx((x@x))x\\x||__ ~   \\\\   *",
    "    ~~ ~~~ ///xxxWxxxxxYxxxxxxx\\-__‾    /",
    "       --‾‾x/x/xx|||///xx|\\__|x\\‾  ‾\\  ~~~",
    "      /‾‾‾‾|xx@xxx\\|||xxx(@)xx\\x|   ~~",
    "     ~~   /x/‾‾‾‾--/x/--_____-\\x-‾‾‾\\x\\",
    "          ~~~~~~~~~~~  ~~~~  ~~~~~~~  ~~~~~",
]

# Foreground branch sprites - these are TANGIBLE (birds collide with them)
# Each branch is positioned so its numbered area overlaps with the tree background
# 'o' characters mark possible flower spawn positions
# Digits (1-5) mark overlap areas with tree (hidden at render time)

TREE_BOSS_BRANCH_1 = [  # Overlaps area 1 in tree (row 15)
    "o     o",
    "\\\\___//__",
    "//‾‾//‾\\ \\",
    "o   o  /1|",
]

TREE_BOSS_BRANCH_2 = [  # Overlaps area 2 in tree (row 13)
    "o   o",
    "\\\\__\\\\__o",
    "___//‾‾\\\\‾",
    "2___/    o",
]

TREE_BOSS_BRANCH_3 = [  # Overlaps area 3 in tree (row 9)
    "o",
    "_//_    o",
    "‾‾‾\\\\___\\\\",
    "//‾‾‾\\3\\",
    "o",
]

TREE_BOSS_BRANCH_4 = [  # Overlaps area 4 in tree (row 9)
    "o  o",
    "\\\\//",
    "o  ||",
    "\\\\//",
    "||",
    "/4|",
]

TREE_BOSS_BRANCH_5 = [  # Overlaps area 5 in tree (row 7)
    "\\5|    o   o",
    "\\\\____\\\\_//",
    "‾‾‾‾‾\\\\‾‾o",
]

# All branches in a list for easy iteration
TREE_BOSS_BRANCHES = [
    TREE_BOSS_BRANCH_1,
    TREE_BOSS_BRANCH_2,
    TREE_BOSS_BRANCH_3,
    TREE_BOSS_BRANCH_4,
    TREE_BOSS_BRANCH_5,
]

# Flower spawn positions for each branch (relative x,y within branch sprite)
# These are the coordinates of 'o' characters in each branch
TREE_BOSS_BRANCH_FLOWER_POSITIONS = [
    # Branch 1 flower positions: o at (0,0), (6,0), (0,3), (4,3)
    [(0, 0), (6, 0), (0, 3), (4, 3)],
    # Branch 2 flower positions: o at (0,0), (4,0), (8,1), (9,3)
    [(0, 0), (4, 0), (8, 1), (9, 3)],
    # Branch 3 flower positions: o at (0,0), (8,1), (0,4)
    [(0, 0), (8, 1), (0, 4)],
    # Branch 4 flower positions: o at (0,0), (3,0), (0,2)
    [(0, 0), (3, 0), (0, 2)],
    # Branch 5 flower positions: o at (7,0), (11,0), (9,2)
    [(7, 0), (11, 0), (9, 2)],
]

# =============================================================================
# FLOWER SPRITES - 6 growth frames for each color
# Flowers grow on branches and have special effects when mature
# Some frames are multi-line sprites
# =============================================================================

# Growth frames (same for all colors, color applied at render time)
# Each frame is a list of lines (single char frames are 1-element lists)
FLOWER_FRAME_0 = ["o"]           # Small bud (frame 0)
FLOWER_FRAME_1 = ["O"]           # Medium bud (frame 1)
FLOWER_FRAME_2 = ["()"]          # Opening (frame 2)
FLOWER_FRAME_3 = ["(@)"]         # Closed flower (frame 3)
FLOWER_FRAME_4 = ["\\|/", "(@)"]  # Petals appearing (frame 4, 2 lines)
FLOWER_FRAME_5 = [" _|\\⋀/|_", " \\(>@<)/"]  # Mature flower (frame 5, 2 lines)

FLOWER_GROWTH_FRAMES = [
    FLOWER_FRAME_0,
    FLOWER_FRAME_1,
    FLOWER_FRAME_2,
    FLOWER_FRAME_3,
    FLOWER_FRAME_4,
    FLOWER_FRAME_5,
]

# Mature frame index (when flower effect activates)
FLOWER_MATURE_FRAME = 5

# Flower colors (for rendering)
# Red flower: bleed effect (countdown, press up = instant death)
# Yellow flower: stun effect (3 seconds)
# Blue flower: freeze effect
# Green flower: poison effect
FLOWER_COLORS = {
    'red': '\033[1;31m',      # Bright red (bleed)
    'yellow': '\033[1;33m',   # Bright yellow (stun)
    'blue': '\033[1;34m',     # Bright blue (freeze)
    'green': '\033[1;32m',    # Bright green (poison)
}

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

# Windy Woods obstacles - conifer tree tops (multiple variants per tier)
WOODS_OBSTACLE_T1_V1 = [
    "⋀∧⋀",
    "∧^∧^",
]
WOODS_OBSTACLE_T1_V2 = [
    " ∧⋀ ",
    "^∧^∧",
]
WOODS_OBSTACLE_T2_V1 = [
    " ∧⋀^  ",
    "⋀/^\\^⋀",
]
WOODS_OBSTACLE_T2_V2 = [
    "  ^∧  ",
    " ⋀/\\⋀ ",
    "∧/^^\\∧",
]
WOODS_OBSTACLE_T3_V1 = [
    "   ⋀Λ⋀   ",
    " Λ^/⋀\\/\\ ",
    "Λ⋀/∧Λ^\\^\\",
]
WOODS_OBSTACLE_T3_V2 = [
    "  ⋀ Λ ⋀  ",
    " Λ/⋀Λ⋀\\ ",
    "∧/^^Λ^^\\∧",
]
WOODS_OBSTACLE_T4_V1 = [
    "   ⋀Λ⋀   Λ   ",
    " Λ^/⋀\\/\\/^\\  ",
    "Λ⋀/∧Λ^\\^\\^^\\⋀",
]
WOODS_OBSTACLE_T4_V2 = [
    "    ⋀Λ⋀  Λ⋀   ",
    "  Λ/⋀Λ\\/\\/Λ\\  ",
    " Λ⋀/∧Λ^\\^\\^^\\⋀ ",
]

# Default variants (first variant)
WOODS_OBSTACLE_T1 = WOODS_OBSTACLE_T1_V1
WOODS_OBSTACLE_T2 = WOODS_OBSTACLE_T2_V1
WOODS_OBSTACLE_T3 = WOODS_OBSTACLE_T3_V1
WOODS_OBSTACLE_T4 = WOODS_OBSTACLE_T4_V1

# All variants per tier (for random selection)
WOODS_OBSTACLE_VARIANTS = {
    1: [WOODS_OBSTACLE_T1_V1, WOODS_OBSTACLE_T1_V2],
    2: [WOODS_OBSTACLE_T2_V1, WOODS_OBSTACLE_T2_V2],
    3: [WOODS_OBSTACLE_T3_V1, WOODS_OBSTACLE_T3_V2],
    4: [WOODS_OBSTACLE_T4_V1, WOODS_OBSTACLE_T4_V2],
}

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
    " _|\\_o",
    " ¯\\\\/ ",
    " /()  ",
]
SWAMP_OBSTACLE_T3 = [
    "  _|\\__/|_o  ",
    " o¯\\\\__//¯   ",
    "   \\\\||//    ",
    "   /(  )\\    ",
]
SWAMP_OBSTACLE_T4 = [
    "o__|\\_____/|\\__  ",
    " ¯\\\\__===__//¯¯o ",
    " o¯\\\\\\|||///¯    ",
    "   / (===) \\     ",
]

# Flower positions for swamp obstacles (relative x,y within sprite)
# These are the coordinates of 'o' characters in each tier
SWAMP_OBSTACLE_FLOWER_POSITIONS = {
    1: [],  # T1 has no 'o' markers
    2: [(5, 0)],  # T2: o at col 5, row 0
    3: [(10, 0), (1, 1)],  # T3: o at (10,0) and (1,1)
    4: [(0, 0), (15, 1), (1, 2)],  # T4: o at (0,0), (15,1), (1,2)
}

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

# Varianti sprite per bioma (se non definite, usa sprite singola)
BIOME_OBSTACLE_VARIANTS = {
    1: WOODS_OBSTACLE_VARIANTS,  # Windy Woods ha varianti
    # Altri biomi possono usare varianti in futuro
}


def get_biome_obstacles(level_group):
    """Get obstacle sprites for the current biome."""
    return BIOME_OBSTACLES.get(level_group, BIOME_OBSTACLES[1])


def get_random_obstacle_sprite(level_group, tier, allow_flip=True):
    """Seleziona una sprite casuale per un ostacolo, eventualmente flippata.

    Args:
        level_group: bioma corrente (1-6)
        tier: tier dell'ostacolo (1-4)
        allow_flip: se True, può flippare orizzontalmente la sprite

    Returns:
        tuple: (sprite, flipped) dove sprite è la lista di stringhe e flipped è bool
    """
    import random

    # Controlla se ci sono varianti per questo bioma
    variants = BIOME_OBSTACLE_VARIANTS.get(level_group, {})

    if tier in variants and variants[tier]:
        # Seleziona variante casuale
        sprite = random.choice(variants[tier])
    else:
        # Usa sprite default del bioma
        biome_sprites = BIOME_OBSTACLES.get(level_group, BIOME_OBSTACLES[1])
        sprite = biome_sprites.get(tier, OBSTACLE_SPRITE_T1)

    # Eventualmente flippa
    flipped = False
    if allow_flip and random.random() < 0.5:
        sprite = flip_sprite_horizontal(sprite)
        flipped = True

    return sprite, flipped

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

# Larghezza in lane per ogni tier (DEPRECATED - usa get_obstacle_sprite_width)
OBSTACLE_LANE_WIDTH = {
    1: 1,  # 1 lane
    2: 1,  # 1 lane
    3: 2,  # 2 lanes
    4: 3,  # 3 lanes
}


def flip_sprite_horizontal(sprite):
    """Flippa una sprite orizzontalmente.

    Args:
        sprite: lista di stringhe rappresentanti le righe della sprite

    Returns:
        lista di stringhe con la sprite flippata
    """
    if not sprite:
        return sprite

    # Mappa caratteri che devono essere invertiti
    flip_map = {
        '/': '\\', '\\': '/',
        '(': ')', ')': '(',
        '[': ']', ']': '[',
        '{': '}', '}': '{',
        '<': '>', '>': '<',
        '⌋': '⌊', '⌊': '⌋',
        '⌉': '⌈', '⌈': '⌉',
    }

    flipped = []
    for line in sprite:
        # Inverti la linea carattere per carattere
        flipped_line = ''
        for ch in reversed(line):
            flipped_line += flip_map.get(ch, ch)
        flipped.append(flipped_line)

    return flipped


def get_obstacle_sprite_width(sprite):
    """Calcola la larghezza effettiva di una sprite (max lunghezza linee non-spazio)."""
    if not sprite:
        return 0
    max_width = 0
    for line in sprite:
        # Trova primo e ultimo carattere non-spazio
        first_char = -1
        last_char = -1
        for i, ch in enumerate(line):
            if ch != ' ':
                if first_char == -1:
                    first_char = i
                last_char = i
        if first_char != -1:
            line_width = last_char - first_char + 1
            max_width = max(max_width, line_width)
    return max_width


def get_obstacle_hitbox_lanes(obs_lane, sprite_width, lane_positions, num_lanes):
    """Calcola quali lane sono coperte da un ostacolo basandosi sulla larghezza sprite.

    Args:
        obs_lane: lane iniziale dell'ostacolo (0-based)
        sprite_width: larghezza sprite in caratteri
        lane_positions: lista posizioni X delle lane
        num_lanes: numero totale di lane

    Returns:
        set di lane coperte dall'ostacolo
    """
    if obs_lane >= num_lanes:
        return set()

    # Posizione X centrale dell'ostacolo (centro della lane iniziale)
    center_x = lane_positions[obs_lane]

    # Estensione orizzontale della sprite dal centro
    half_width = sprite_width // 2
    left_x = center_x - half_width
    right_x = center_x + half_width

    # Trova quali lane sono coperte
    covered_lanes = set()
    for lane_idx, lane_x in enumerate(lane_positions):
        # Una lane è coperta se il suo centro è dentro l'estensione della sprite
        # oppure se la sprite tocca la lane (margine di 2 caratteri per lato)
        if left_x - 2 <= lane_x <= right_x + 2:
            covered_lanes.add(lane_idx)

    return covered_lanes

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
