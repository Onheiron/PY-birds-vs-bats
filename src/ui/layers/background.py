"""Parallax background, cave shimmer and foreground clouds."""

from src.core import constants, state
from src.entities.sprites import TREE_BOSS_BACKGROUND, WOODS_BG_LAYER1, WOODS_BG_LAYER2, get_biome_bg
from src.ui.colors import apply_faint, get_biome_colors, get_shimmer_color
from src.ui.framebuffer import BLANK
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT, SIDE_PANEL_WIDTH

# Default patterns (Windy Woods) - used as fallback
TREE_PATTERN = WOODS_BG_LAYER1

TREE_PATTERN_HEIGHT = len(TREE_PATTERN)

TREE_PATTERN_WIDTH = 24

MID_TREE_PATTERN = WOODS_BG_LAYER2

MID_TREE_PATTERN_HEIGHT = len(MID_TREE_PATTERN)

MID_TREE_PATTERN_WIDTH = 32


def get_current_biome_bg():
    """Get background patterns for the current biome based on level_group."""
    level_group = state.game.level_group
    layer1, layer2 = get_biome_bg(level_group)
    return layer1, layer2


# Characters to hide in tree/branch rendering (overlap markers)
TREE_HIDDEN_CHARS = set('12345o')


def draw_tree_boss_background(fb):
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

    # Get vertical offset for scrolling (background comes from above)
    bg_y_offset = boss.get('bg_y_offset', 0)

    height = constants.layout.height
    rows = fb.current
    for line_idx, cells in enumerate(_tree_boss_background_cells()):
        y_pos = line_idx + bg_y_offset  # Apply scroll offset
        if 0 <= y_pos < height:
            row = rows[y_pos + HEADER_HEIGHT]
            for screen_x, cell in cells:
                row[screen_x] = cell


_tree_boss_cells = {}


def _tree_boss_background_cells():
    """Per-line [(screen_x, cell)] for the Tree Boss background (cached per width)."""
    width = constants.layout.width  # Tree is as wide as the game panel
    lines = _tree_boss_cells.get(width)
    if lines is None:
        # WHITE but faint for the tree outline
        outline_color = apply_faint("\033[1;37m")
        lines = []
        for line in TREE_BOSS_BACKGROUND:
            cells = []
            for x_pos, char in enumerate(line[:width]):
                if char == 'x' or char in TREE_HIDDEN_CHARS:
                    # Solid fill - a space that overwrites the biome background
                    cells.append((GAME_X_OFFSET + x_pos, BLANK))
                elif char != ' ':
                    cells.append((GAME_X_OFFSET + x_pos, (char, outline_color)))
            lines.append(cells)
        _tree_boss_cells[width] = lines
    return lines


# Cave shimmer brightness is a pure function of a 0-99 pseudo-random seed.
_SHIMMER_COLORS = [get_shimmer_color(seed / 100.0 * 0.4 + 0.05) for seed in range(100)]

_sparse_rows = {}  # (pattern line, pattern width, span) -> [(x, char)] for non-space cells
_static_rows = {}  # pattern lines + colours -> composed row of cells
_frame_memo = [None, None]  # [key, rows] of the last composed background


def _sparse_row(line, pattern_width, span):
    """Non-space cells of a pattern line tiled horizontally over ``span`` columns."""
    key = (line, pattern_width, span)
    cells = _sparse_rows.get(key)
    if cells is None:
        line_len = len(line)
        cells = []
        for x in range(span):
            pattern_x = x % pattern_width
            if pattern_x < line_len and line[pattern_x] != ' ':
                cells.append((x, line[pattern_x]))
        _sparse_rows[key] = cells
    return cells


def _static_row(line1, width1, color1, line2, width2, color2, span):
    """Compose both parallax layers of one row with flat colours (cached)."""
    key = (line1, width1, color1, line2, width2, color2, span)
    row = _static_rows.get(key)
    if row is None:
        row = [BLANK] * span
        for x, char in _sparse_row(line1, width1, span):
            row[x] = (char, color1)
        if line2 is not None:
            for x, char in _sparse_row(line2, width2, span):
                row[x] = (char, color2)
        _static_rows[key] = row
    return row


def _shimmer_row(line1, width1, line2, width2, screen_y, phase, span):
    """Compose one row where every background char flickers (Void Cave)."""
    colors = _SHIMMER_COLORS
    row = [BLANK] * span
    base = screen_y * 137 + phase * 31
    for x, char in _sparse_row(line1, width1, span):
        row[x] = (char, colors[(x * 73 + base) % 100])
    if line2 is not None:
        base = screen_y * 151 + phase * 47
        for x, char in _sparse_row(line2, width2, span):
            row[x] = (char, colors[(x * 97 + base) % 100])
    return row


def draw_background(fb):
    """Render parallax scrolling background for game area and right panel.

    3 layers with different scroll speeds (slowest to fastest):
    - Layer 1: Dense pattern - slowest, darkest (biome-specific)
    - Layer 2: Sparse pattern - medium speed, slightly lighter (biome-specific)
    - Layer 3: Obstacles - fastest (rendered separately)

    Can be disabled via settings:
    - background off -> disables all background layers
    - parallax off   -> disables only the middle layer

    The pattern continues seamlessly from the game area into the right panel.
    Composed rows are cached: the background only changes when it scrolls.
    """
    width = constants.layout.width
    height = constants.layout.height
    rows = fb.current
    game_end = GAME_X_OFFSET + width

    if not state.settings.background_enabled:
        blank = [BLANK] * width
        for screen_y in range(height):
            rows[screen_y + HEADER_HEIGHT][GAME_X_OFFSET:game_end] = blank
        return

    level_group = state.game.level_group
    layer1_pattern, layer2_pattern = get_current_biome_bg()
    layer1_color, layer2_color = get_biome_colors(level_group)
    parallax_enabled = state.settings.parallax_enabled
    bg_offset = state.ui.bg_offset
    mid_offset = state.ui.bg_mid_offset

    # Cave shimmer (biome 5): colours depend on position and animation phase
    shimmer = state.ui.cave_shimmer if level_group == 5 else None
    phase = shimmer.get('phase', 0) if shimmer else None

    memo_key = (level_group, bg_offset, mid_offset, phase, parallax_enabled, layer1_color, layer2_color, width, height)
    if _frame_memo[0] == memo_key:
        composed = _frame_memo[1]
    else:
        layer1_height = len(layer1_pattern)
        layer1_width = len(layer1_pattern[0]) if layer1_pattern else 24
        layer2_height = len(layer2_pattern)
        layer2_width = len(layer2_pattern[0]) if layer2_pattern else 32
        layer1_faint = apply_faint(layer1_color)
        layer2_faint = apply_faint(layer2_color)
        # Game area plus the inner right panel (borders excluded)
        span = width + SIDE_PANEL_WIDTH - 2

        composed = []
        for screen_y in range(height):
            line1 = layer1_pattern[(screen_y - bg_offset) % layer1_height]
            line2 = layer2_pattern[(screen_y - mid_offset) % layer2_height] if parallax_enabled else None
            if shimmer:
                row = _shimmer_row(line1, layer1_width, line2, layer2_width, screen_y, phase, span)
            else:
                row = _static_row(line1, layer1_width, layer1_faint, line2, layer2_width, layer2_faint, span)
            composed.append((row[:width], row[width:]))
        _frame_memo[0] = memo_key
        _frame_memo[1] = composed

    right_panel_start = game_end + 1  # After game area + border
    right_panel_end = right_panel_start + SIDE_PANEL_WIDTH - 2
    for screen_y, (game_cells, panel_cells) in enumerate(composed):
        row = rows[screen_y + HEADER_HEIGHT]
        row[GAME_X_OFFSET:game_end] = game_cells
        row[right_panel_start:right_panel_end] = panel_cells


def draw_cloud_banks(fb):
    """Render Mountain Range cloud banks (foreground fog that obscures game area)."""
    # Only render in Mountain Range biome
    if state.game.level_group != 6:
        return

    # Cloud color - semi-transparent white/gray
    CLOUD_COLOR = "\033[38;5;251m"  # Light gray

    # Cloud characters for different densities

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
