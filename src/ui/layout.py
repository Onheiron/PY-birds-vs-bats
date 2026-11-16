"""Screen layout: widescreen dimensions derived from the config."""

from src.core import constants

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
