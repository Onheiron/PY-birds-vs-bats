"""World hazards on screen: darkness, stalactite warnings, lane winds (src/engine/hazards.py)."""

import math

from src.core import constants, state
from src.engine import clock, fx, hazards
from src.entities.sprites import BLUE, RED, YELLOW, get_dynamic_color
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
    """Windy lanes on the starting line, like a tailwind: its dashes turn into ^ (blue) or v (red)."""
    y = constants.layout.starting_line + HEADER_HEIGHT
    positions = constants.layout.lane_positions
    n = constants.layout.num_lanes
    for lane, wind in state.hazards.lane_winds.items():
        char, color = ('^', BLUE) if wind['tail'] else ('v', RED)
        x = positions[lane]
        start = x - 3 if lane > 0 else 0
        end = x + 4 if lane < n - 1 else constants.layout.width
        for col in range(max(0, start), min(constants.layout.width, end)):
            if col % 2 == 0:  # where the line has its dashes
                fb.put(GAME_X_OFFSET + col, y, char, color)


def draw_fx(fb):
    """Short cues from the game logic (src/engine/fx.py): a bite, a blast, a cure..."""
    for cue in fx.live():
        if 0 <= cue['row'] < constants.layout.height and 0 <= cue['col'] < constants.layout.width:
            fb.put(GAME_X_OFFSET + cue['col'], cue['row'] + HEADER_HEIGHT, cue['char'], get_dynamic_color(cue['color']))


def draw_firefly_light(fb):
    """In the dark world, the seconds of firefly light left, top right of the play area."""
    if hazards.setting('darkness') is None:
        return
    left = state.hazards.light_until - clock.now()
    if left > 0:
        fb.put_string(GAME_X_OFFSET + constants.layout.width - 6, HEADER_HEIGHT, f'✦ {math.ceil(left)}s', YELLOW)


def draw_hazards(fb):
    draw_lane_winds(fb)
    draw_darkness(fb)
    draw_stalactite_warnings(fb)
    draw_fx(fb)
    draw_firefly_light(fb)
