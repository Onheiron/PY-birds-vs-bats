"""Frame compositor: draws every layer and flushes the framebuffer."""

from src.ui import terminal
from src.ui.framebuffer import get_framebuffer
from src.ui.layers.background import draw_background, draw_cloud_banks, draw_tree_boss_background
from src.ui.layers.birds import draw_birds
from src.ui.layers.bosses import draw_boss
from src.ui.layers.enemies import (
    draw_bats,
    draw_loot,
    draw_mini_bats,
    draw_obstacles,
    draw_portals,
    draw_projectiles,
)
from src.ui.layers.hud import (
    draw_center_of_mass,
    draw_floor_and_cursor,
    draw_footer,
    draw_header,
    draw_starting_line,
)
from src.ui.layers.menus import draw_pause_overlay
from src.ui.layers.panels import (
    draw_level_line,
    draw_notifications,
    draw_right_panel_barriers,
    draw_right_panel_level_signs,
    draw_side_panels,
)

# Extra layers drawn on top of everything, e.g. the watch-mode status bar.
# Each is a callable taking the framebuffer.
OVERLAYS = []


def render_game():
    """Main render function using differential framebuffer."""
    fb = get_framebuffer()

    # Render all components to framebuffer
    draw_side_panels(fb)  # Side panels FIRST (background)
    draw_header(fb)
    draw_background(fb)  # Sfondo alberi PRIMA di tutto il resto
    draw_tree_boss_background(fb)  # Tree Boss faint bg AFTER biome bg (visible on top)
    draw_level_line(fb)  # Level line in game area (before obstacles)
    draw_right_panel_barriers(fb)  # Decorative barriers UNDER level signs
    draw_right_panel_level_signs(fb)  # Level signs on TOP of barriers
    draw_notifications(fb)  # Notification cards in right panel (between level signs)
    draw_starting_line(fb)
    draw_center_of_mass(fb)  # Dark blue dashed line at birds' center of mass
    draw_obstacles(fb)
    draw_portals(fb)  # Cave biome portals
    draw_boss(fb)  # Boss rendered BEFORE bats so bats appear in front
    draw_bats(fb)
    draw_mini_bats(fb)
    draw_loot(fb)
    draw_projectiles(fb)
    draw_birds(fb)
    draw_cloud_banks(fb)  # Mountain Range foreground clouds (on top of birds)
    draw_floor_and_cursor(fb)
    draw_footer(fb)
    draw_pause_overlay(fb)
    for overlay in OVERLAYS:
        overlay(fb)

    # Generate differential output and write to screen
    terminal.write_frame(fb.render())
