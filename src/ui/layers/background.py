"""Parallax background, cave shimmer and foreground clouds."""

from src.core import constants
from src.core import state
from src.entities.sprites import WOODS_BG_LAYER1
from src.entities.sprites import WOODS_BG_LAYER2
from src.entities.sprites import get_biome_bg
from src.ui.colors import apply_faint, get_biome_colors, get_shimmer_color
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

    # Check if cave shimmer is active (biome 5)
    cave_shimmer_active = state.game.level_group == 5 and state.ui.cave_shimmer
    shimmer_phase = state.ui.cave_shimmer.get('phase', 0) if cave_shimmer_active else 0

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
                if cave_shimmer_active:
                    # Compute pseudo-random brightness based on position and phase
                    seed = (screen_x * 73 + screen_y * 137 + shimmer_phase * 31) % 100
                    brightness = seed / 100.0 * 0.4 + 0.05  # Range 0.05 to 0.45 (darker)
                    color = get_shimmer_color(brightness)
                else:
                    color = layer1_faint
                fb.put(GAME_X_OFFSET + screen_x, screen_y + HEADER_HEIGHT, char, color)

        # Also render in right panel (continuing the pattern)
        for panel_x in range(right_panel_inner_width):
            pattern_x = (constants.layout.width + panel_x) % layer1_width
            char = pattern_line[pattern_x] if pattern_x < len(pattern_line) else ' '
            if char != ' ':
                if cave_shimmer_active:
                    seed = ((constants.layout.width + panel_x) * 73 + screen_y * 137 + shimmer_phase * 31) % 100
                    brightness = seed / 100.0 * 0.4 + 0.05
                    color = get_shimmer_color(brightness)
                else:
                    color = layer1_faint
                fb.put(right_panel_start + panel_x, screen_y + HEADER_HEIGHT, char, color)

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
                    if cave_shimmer_active:
                        # Different seed pattern for layer 2
                        seed = (screen_x * 97 + screen_y * 151 + shimmer_phase * 47) % 100
                        brightness = seed / 100.0 * 0.4 + 0.05  # Range 0.05 to 0.45 (darker)
                        color = get_shimmer_color(brightness)
                    else:
                        color = layer2_faint
                    fb.put(GAME_X_OFFSET + screen_x, screen_y + HEADER_HEIGHT, char, color)

            # Also render in right panel
            for panel_x in range(right_panel_inner_width):
                pattern_x = (constants.layout.width + panel_x) % layer2_width
                char = mid_pattern_line[pattern_x] if pattern_x < len(mid_pattern_line) else ' '
                if char != ' ':
                    if cave_shimmer_active:
                        seed = ((constants.layout.width + panel_x) * 97 + screen_y * 151 + shimmer_phase * 47) % 100
                        brightness = seed / 100.0 * 0.4 + 0.05
                        color = get_shimmer_color(brightness)
                    else:
                        color = layer2_faint
                    fb.put(right_panel_start + panel_x, screen_y + HEADER_HEIGHT, char, color)


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
