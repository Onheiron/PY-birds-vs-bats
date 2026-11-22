"""World hazards on screen: darkness, stalactite warnings, lane winds (src/engine/hazards.py)."""

from src.core import constants, state
from src.engine import hazards
from src.entities.sprites import BLUE, RED, YELLOW
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT

DARK_CELL = (' ', '')


def _column_lanes():
    """For every column of the play area, the lane it belongs to (the nearest one)."""
    positions = constants.layout.lane_positions
    return [
        min(range(len(positions)), key=lambda lane: abs(positions[lane] - x)) for x in range(constants.layout.width)
    ]


def draw_darkness(fb):
    """In a dark world only the lit lanes can be seen (drawn over everything but the cursor)."""
    if not hazards.dark():
        return
    lit = hazards.lit_lanes()
    lanes = _column_lanes()
    dark_columns = [x for x in range(constants.layout.width) if lanes[x] not in lit]
    for y in range(constants.layout.height):
        row = y + HEADER_HEIGHT
        for x in dark_columns:
            fb.put(GAME_X_OFFSET + x, row, *DARK_CELL)


def draw_stalactite_warnings(fb):
    """Cracks at the top of a lane where a stalactite is about to fall (visible in the dark too)."""
    for warning in state.hazards.stalactite_warnings:
        x = constants.layout.lane_positions[warning['lane']]
        fb.put(GAME_X_OFFSET + x, HEADER_HEIGHT, 'v' if state.game.frame_count // 4 % 2 else '¦', YELLOW)


def draw_lane_winds(fb):
    """Tailwind (^, blue) and headwind (v, red) on the starting line under the windy lanes."""
    y = constants.layout.starting_line + HEADER_HEIGHT
    positions = constants.layout.lane_positions
    for lane, wind in state.hazards.lane_winds.items():
        char, color = ('^', BLUE) if wind['tail'] else ('v', RED)
        x = positions[lane]
        for dx in (-2, 0, 2):
            if 0 <= x + dx < constants.layout.width:
                fb.put(GAME_X_OFFSET + x + dx, y, char, color)


def draw_hazards(fb):
    draw_lane_winds(fb)
    draw_darkness(fb)
    draw_stalactite_warnings(fb)
