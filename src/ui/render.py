"""Frame compositor: draws every layer and flushes the framebuffer."""

from src.ui import terminal
from src.ui.framebuffer import get_framebuffer
from src.ui.layers.background import _fb_render_background, _fb_render_cloud_banks, _fb_render_tree_boss_background
from src.ui.layers.birds import _fb_render_birds
from src.ui.layers.bosses import _fb_render_boss
from src.ui.layers.enemies import (
    _fb_render_bats,
    _fb_render_loot,
    _fb_render_mini_bats,
    _fb_render_obstacles,
    _fb_render_portals,
    _fb_render_projectiles,
)
from src.ui.layers.hud import (
    _fb_render_center_of_mass,
    _fb_render_floor_and_cursor,
    _fb_render_footer,
    _fb_render_header,
    _fb_render_starting_line,
)
from src.ui.layers.menus import _fb_render_pause_overlay
from src.ui.layers.panels import (
    _fb_render_level_line,
    _fb_render_notifications,
    _fb_render_right_panel_barriers,
    _fb_render_right_panel_level_signs,
    _fb_render_side_panels,
)


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
    _fb_render_portals(fb)  # Cave biome portals
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
    terminal.write_frame(fb.render())
