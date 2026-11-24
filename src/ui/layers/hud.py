"""Header, starting line, centre of mass, floor, cursor and footer."""

from src.core import constants, state
from src.engine import stats
from src.engine.birds import get_affected_lanes
from src.engine.grades import compute_grade_from_xp, grade_progress
from src.engine.progression import compute_prestige, flock_bonus
from src.entities.sprites import BLUE, DARK_GRAY, GREEN, RED, YELLOW, get_biome_name
from src.ui.colors import (
    HEADER_ACCENT,
    HEADER_BORDER,
    HEADER_LABEL,
    HEADER_VALUE,
    get_position_color,
    grade_letter_color,
)
from src.ui.framebuffer import RegionCache
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT, TOTAL_WIDTH

_header_cache = RegionCache()


def short_number(value):
    """1-999 as is, then 1.455K, 100.233K, 1.200M, 3.5B... so it always fits its box."""
    value = int(value)
    if value < 1000:
        return str(value)
    for unit, size in (('K', 1e3), ('M', 1e6), ('B', 1e9), ('T', 1e12), ('Q', 1e15)):
        if value < size * 1000 or unit == 'Q':
            return f'{value / size:.3f}{unit}'
    return str(value)


def draw_header(fb):
    """Render header to framebuffer - 3 rows with graphical boxes.

    Shows: Lives, Prestige, Score, Biome in styled boxes.
    """
    # Get values
    prestige_val = compute_prestige()
    if prestige_val is None:
        prestige_val = 1.0
    prestige_display = f"{prestige_val:.2f}x"

    score_display = short_number(state.game.score)

    # Lives display (hearts)
    lives_full = "♥" * state.game.lives
    lives_empty = "♡" * (5 - state.game.lives)
    lives_display = lives_full + lives_empty

    # Biome name
    biome_name = get_biome_name(state.game.level_group)

    # The header owns rows 0-3: reuse them while the displayed values are unchanged
    cache_key = (prestige_display, score_display, state.game.lives, biome_name)
    if _header_cache.restore(fb, cache_key, 0, 0):
        return

    # Box positions: the score box is wider, so big numbers keep off its right border
    widths = [18, 18, 21, 18]
    total_boxes_width = sum(widths) + 6  # 4 boxes + spacing
    start_x = (TOTAL_WIDTH - total_boxes_width) // 2
    xs = [start_x + sum(widths[:k]) + 2 * k for k in range(4)]
    box1_x, box2_x, box3_x, box4_x = xs
    box_width = widths[0]
    score_width = widths[2]

    # Row 0: Top borders
    for x, w in zip(xs, widths, strict=True):
        fb.put_string(x, 0, "╔" + "═" * (w - 2) + "╗", HEADER_BORDER)

    # Row 1: Labels with values
    # Box 1: LIVES (hearts centered)
    fb.put(box1_x, 1, '║', HEADER_BORDER)
    fb.put_string(box1_x + 1, 1, " LIVES ", HEADER_LABEL)
    # Draw hearts with colors
    hearts_start = box1_x + 8
    for i, char in enumerate(lives_display):
        if char == '♥':
            fb.put(hearts_start + i, 1, char, RED)
        else:
            fb.put(hearts_start + i, 1, char, HEADER_BORDER)
    # Fill remaining space
    fb.put_string(hearts_start + len(lives_display), 1, " " * (box_width - 9 - len(lives_display)), '')
    fb.put(box1_x + box_width - 1, 1, '║', HEADER_BORDER)

    # Box 2: PRESTIGE
    fb.put(box2_x, 1, '║', HEADER_BORDER)
    fb.put_string(box2_x + 1, 1, " PRESTIGE ", HEADER_LABEL)
    prestige_val_str = f"{prestige_display:>5}"
    fb.put_string(box2_x + 11, 1, prestige_val_str, HEADER_VALUE)
    fb.put(box2_x + box_width - 1, 1, '║', HEADER_BORDER)

    # Box 3: SCORE
    fb.put(box3_x, 1, '║', HEADER_BORDER)
    fb.put_string(box3_x + 1, 1, " SCORE ", HEADER_LABEL)
    score_val = f"{score_display:>{score_width - 10}} "  # a space before the border
    fb.put_string(box3_x + 8, 1, score_val, HEADER_ACCENT)
    fb.put(box3_x + score_width - 1, 1, '║', HEADER_BORDER)

    # Box 4: BIOME
    fb.put(box4_x, 1, '║', HEADER_BORDER)
    biome_truncated = biome_name[: box_width - 3]  # Truncate if too long
    biome_centered = f" {biome_truncated:^{box_width - 3}}"
    fb.put_string(box4_x + 1, 1, biome_centered[: box_width - 2], HEADER_VALUE)
    fb.put(box4_x + box_width - 1, 1, '║', HEADER_BORDER)

    # Row 2: Bottom borders
    for x, w in zip(xs, widths, strict=True):
        fb.put_string(x, 2, "╚" + "═" * (w - 2) + "╝", HEADER_BORDER)

    # Row 3: Separator line (this is where game area starts at row 4)
    fb.put_string(0, 3, "═" * TOTAL_WIDTH, HEADER_BORDER)

    _header_cache.store(fb, cache_key, 0, 0, TOTAL_WIDTH, HEADER_HEIGHT)


def draw_starting_line(fb):
    """Render starting line to framebuffer."""
    starting_line_y = constants.layout.starting_line
    if starting_line_y < 0 or starting_line_y >= constants.layout.height:
        return

    # Determine base character based on active wind effects
    wind_up = state.powerups.wind_boss_up_bonus

    if state.powerups.tailwind_active or wind_up > 0:
        base_char = '^'
        base_color = BLUE
    elif wind_up < 0:  # Wind boss headwind phase
        base_char = 'v'
        base_color = RED
    else:
        base_char = '-'
        base_color = _flock_bonus_color()

    # Render base line first
    for i in range(constants.layout.width):
        char = base_char if i % 2 == 0 else ' '
        fb.put(GAME_X_OFFSET + i, starting_line_y + HEADER_HEIGHT, char, base_color)

    # Overlay spell markers on affected lanes
    for lane_idx in range(constants.layout.num_lanes):
        lane_x = constants.layout.lane_positions[lane_idx]

        # Check for silence spell (x marker, gray)
        if lane_idx in state.spells.silenced_lanes:
            fb.put(GAME_X_OFFSET + lane_x, starting_line_y + HEADER_HEIGHT, 'x', DARK_GRAY)

        # Check for repugnant wind spell (v marker, red)
        elif lane_idx in state.spells.repugnant_wind_lanes:
            fb.put(GAME_X_OFFSET + lane_x, starting_line_y + HEADER_HEIGHT, 'v', RED)

    # TWISTER local tailwind: draw ^ ^ ^ pattern on affected lane regions (same as global tailwind)
    if not state.powerups.tailwind_active:  # Don't overlap with global tailwind
        twister_lanes = set()
        for tw_info in state.special.twister_tailwind.values():
            twister_lanes.update(tw_info.get('lanes', []))

        if twister_lanes:
            # Calculate x ranges for affected lanes
            for lane_idx in twister_lanes:
                if lane_idx < 0 or lane_idx >= constants.layout.num_lanes:
                    continue
                lane_x = constants.layout.lane_positions[lane_idx]
                # Draw same ^ ^ ^ pattern as global tailwind in this lane's area
                lane_start = lane_x - 3 if lane_idx > 0 else 0
                lane_end = lane_x + 4 if lane_idx < constants.layout.num_lanes - 1 else constants.layout.width
                for x in range(lane_start, lane_end):
                    if x % 2 == 0:  # Same alternating pattern as global tailwind
                        fb.put(GAME_X_OFFSET + x, starting_line_y + HEADER_HEIGHT, '^', BLUE)


# Start line colour by flock bonus: light green ×2 (full house), white ×1, light red ×0.5
FLOCK_BONUS_COLORS = {'up': '\033[38;5;120m', 'even': '\033[38;5;255m', 'down': '\033[38;5;210m'}


def _flock_bonus_color():
    """The start line shows the flock bonus by its colour (wind effects draw over it)."""
    mult = flock_bonus()[0]
    return FLOCK_BONUS_COLORS['up' if mult > 1 else 'down' if mult < 1 else 'even']


def draw_center_of_mass(fb):
    """Render a dashed line at the center of mass of active birds.

    Center of mass is calculated as weighted average of bird Y positions,
    where weight = bird speed (faster birds contribute more to the average).

    Line color: gradient from red (bottom) to green (top) with faint modifier.
    Also shows the current multiplier on the right side of the game panel.
    """
    # Calculate center of mass
    total_weight = 0.0
    weighted_sum = 0.0

    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        bird_y = state.birds.y[i]
        # Skip orange birds in dormant state
        if bird_y >= constants.layout.height:
            continue

        # Same weighting as the score's centre of mass
        weight = max(1, state.birds.speeds[i]) * stats.bird(i, 'weight')

        weighted_sum += bird_y * weight
        total_weight += weight

    if total_weight <= 0:
        return  # No active birds

    center_y = weighted_sum / total_weight

    # Convert to screen Y coordinate
    screen_y = int(center_y) + HEADER_HEIGHT + 2

    # Ensure within game area bounds
    if screen_y < HEADER_HEIGHT + 3 or screen_y >= constants.layout.height + HEADER_HEIGHT + 1:
        return

    # Get color based on position (red at bottom -> green at top) with faint
    line_color = get_position_color(center_y)

    # Draw dashed line across the game area
    game_width = constants.layout.width

    for x in range(game_width):
        # Alternate between dash and space for dashed effect
        if x % 2 == 0:
            fb.put(GAME_X_OFFSET + x, screen_y, '-', line_color)


def draw_floor_and_cursor(fb):
    """Render floor and cursor to framebuffer."""
    floor_y = constants.layout.height + HEADER_HEIGHT

    # Floor - FULL width separator
    full_floor = "=" * TOTAL_WIDTH
    fb.put_string(0, floor_y, full_floor)

    # Lost birds - X sul pavimento (DOPO il floor, così non viene sovrascritto)
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            x_pos = state.birds.cols[i]
            fb.put(GAME_X_OFFSET + x_pos, floor_y, 'X', DARK_GRAY)

    # Cursor - render [^] per ogni lane affetta
    affected_lanes = get_affected_lanes()
    fallback_cursor_color = YELLOW if state.player.selected_lane is not None else GREEN

    for lane in affected_lanes:
        if 0 <= lane < len(constants.layout.lane_positions):
            x_pos = constants.layout.lane_positions[lane] - 1  # -1 per centrare [^]

            # Determina colore in base al bird nella lane
            bird_idx = -1
            for bi, bl in enumerate(state.birds.random_lanes):
                if bl == lane:
                    bird_idx = bi
                    break

            if bird_idx >= 0 and not state.birds.lost[bird_idx]:
                letter, _ = compute_grade_from_xp(state.birds.per_bird_xp[bird_idx])
                color = grade_letter_color(letter, fallback_cursor_color)
            else:
                color = fallback_cursor_color

            # [^] on the cursor's own lane (where swaps happen); ·^· on the others of a wide cursor
            left, right = ('[', ']') if lane == state.player.lane else ('·', '·')
            fb.put(GAME_X_OFFSET + x_pos, floor_y + 1, left, color)
            fb.put(GAME_X_OFFSET + x_pos + 1, floor_y + 1, '^', color)
            fb.put(GAME_X_OFFSET + x_pos + 2, floor_y + 1, right, color)

    # Selected lane indicator for swap - mostra [*]
    if state.player.selected_lane is not None:
        sel_x = constants.layout.lane_positions[state.player.selected_lane] - 1
        fb.put(GAME_X_OFFSET + sel_x, floor_y + 1, '[', YELLOW)
        fb.put(GAME_X_OFFSET + sel_x + 1, floor_y + 1, '*', YELLOW)
        fb.put(GAME_X_OFFSET + sel_x + 2, floor_y + 1, ']', YELLOW)


def draw_grade_bars(fb):
    """Under each lane, the grade of its bird and a 2-cell bar of XP towards the next grade."""
    y = constants.layout.height + HEADER_HEIGHT + 2
    for i in range(constants.layout.num_balls):
        if state.birds.lost[i]:
            continue
        letter, _ = compute_grade_from_xp(state.birds.per_bird_xp[i])
        color = grade_letter_color(letter, GREEN)
        progress = grade_progress(state.birds.per_bird_xp[i])
        filled = 2 if progress >= 1 else int(progress * 2 + 1e-9)
        x = GAME_X_OFFSET + constants.layout.lane_positions[state.birds.random_lanes[i]] - 1
        fb.put_string(x, y, letter[0], color)
        for k in range(2):
            fb.put(x + 1 + k, y, '▰' if k < filled else '▱', color if k < filled else DARK_GRAY)


def draw_footer(fb):
    """Render footer: grade bars under the lanes, or the XP overlay when toggled (X key)."""
    footer_y = constants.layout.height + HEADER_HEIGHT + 2
    if not state.ui.show_xp_overlay:
        draw_grade_bars(fb)

    # Only show XP overlay if enabled (toggled with X key)
    if state.ui.show_xp_overlay:
        parts = []
        for i in range(constants.layout.num_balls):
            label, _ = compute_grade_from_xp(state.birds.per_bird_xp[i])
            parts.append(f"{label}({int(state.birds.per_bird_xp[i])})")
        xp_summary = ' '.join(parts)
        xp_line = f"XP: {xp_summary}"
        xp_padding = max(0, (TOTAL_WIDTH - len(xp_line)) // 2)
        fb.put_string(0, footer_y, " " * xp_padding + xp_line[:TOTAL_WIDTH])
