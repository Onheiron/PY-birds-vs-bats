"""Side panels: gauges, level signs, barriers and notification cards."""

from src.core import constants, state
from src.engine.progression import calculate_gear_threshold, get_level_milestones, get_mph_for_speed
from src.entities.sprites import OBSTACLE_SPRITE_T1, get_biome_obstacles
from src.ui.colors import (
    CARD_BORDER_COLOR,
    CARD_TEXT_COLOR,
    CARD_TITLE_COLOR,
    GAUGE_GRADIENT,
    GAUGE_OFF,
    LEVEL_LINE_COLOR,
    MOMENTUM_GRADIENT,
    PANEL_BORDER_COLOR,
    PANEL_LABEL_COLOR,
    PANEL_VALUE_COLOR,
    SIGN_ARROW_COLOR,
    SIGN_BORDER_COLOR,
    SIGN_TEXT_COLOR,
    get_biome_obstacle_color,
)
from src.ui.framebuffer import BLANK
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT, SIDE_PANEL_WIDTH


def _fb_render_left_panel_content(fb, panel_start_y, panel_end_y):
    """
    Render left panel content (dynamic width):
    - Speed: (label)
      XXX MPH (value)
    - Travelled: (label)
      XXX mls (value)
    - Separator
    - Speed gauge (vertical, extra spacing for red levels 8-10)
    - Separator
    - Momentum: [horizontal bar]

    Components expand with panel width. Min width = 16 chars.
    Labels stay left-aligned with 2-column padding.
    """
    current_speed = state.game.speed
    max_speed = 10
    mph = get_mph_for_speed(current_speed)
    miles = state.game.miles

    # Calculate dynamic widths
    # Available space: SIDE_PANEL_WIDTH - 2 (excluding borders)
    # Min content width: 16 chars (original design)
    # Max padding: 2 columns per side
    available_width = SIDE_PANEL_WIDTH - 2
    min_content_width = 16
    max_padding = 2

    # Calculate content width and padding
    # If panel is small, reduce padding first before shrinking content
    if available_width >= min_content_width + (max_padding * 2):
        # Plenty of space: use max padding and expand content
        left_padding = max_padding + 1  # +1 for border
        content_width = available_width - (max_padding * 2)
    elif available_width >= min_content_width:
        # Tight fit: reduce padding, keep min content width
        remaining = available_width - min_content_width
        left_padding = max(1, remaining // 2 + 1)  # +1 for border
        content_width = min_content_width
    else:
        # Very tight: no padding, use all available
        left_padding = 1
        content_width = max(available_width, min_content_width)

    y = panel_start_y + 1  # Start after a small margin

    # === Speed: XXX MPH (two lines) ===
    fb.put_string(left_padding, y, "Speed:", PANEL_LABEL_COLOR)
    y += 1
    fb.put_string(left_padding, y, f"{mph} MPH", PANEL_VALUE_COLOR)
    y += 2

    # === Travelled: XXX.XXX mls (two lines) ===
    fb.put_string(left_padding, y, "Travelled:", PANEL_LABEL_COLOR)
    y += 1
    fb.put_string(left_padding, y, f"{miles:.3f} mls", PANEL_VALUE_COLOR)
    y += 2

    # === Calculate Momentum first (needed for spacer rows) ===
    # Momentum = progress from current speed threshold to next speed threshold
    # Now uses state.game.momentum (not score) for speed calculation
    # For speed 1, we go from 0 to threshold(2)
    # For speed N (N>1), we go from threshold(N) to threshold(N+1)
    momentum = state.game.momentum

    if current_speed >= max_speed:
        momentum_pct = 100.0
    else:
        if current_speed == 1:
            # At speed 1, progress goes from 0 to threshold for speed 2
            prev_threshold = 0
        else:
            # At speed N, progress goes from threshold(N) to threshold(N+1)
            prev_threshold = calculate_gear_threshold(current_speed)

        next_threshold = calculate_gear_threshold(current_speed + 1)
        momentum_range = next_threshold - prev_threshold
        momentum_progress = momentum - prev_threshold

        if momentum_range > 0:
            momentum_pct = min(100.0, max(0.0, (momentum_progress / momentum_range) * 100))
        else:
            momentum_pct = 0.0

    # === Gear title ===
    separator = "─" * content_width
    fb.put_string(left_padding, y, "Gear:", PANEL_LABEL_COLOR)
    y += 1

    # === Separator ===
    fb.put_string(left_padding, y, separator, GAUGE_OFF)
    y += 1

    # === Speed Gauge (vertical, with spacer rows between some levels) ===
    # Spacer rows (block without numbers) between: 10-9, 9-8, 8-7, 7-6, 6-5
    gauge_x = left_padding
    gauge_start_y = y

    # Calculate dynamic block width
    # Format: "XX - ██████ - XX" = 2 + 3 + block + 3 + 2 = 10 + block
    block_width = content_width - 10
    gauge_block_on = "█" * block_width
    gauge_block_off = "-" * block_width
    # Spacer format: "     ██████     " - centered block with 5 spaces each side (total = content_width)
    spacer_padding = (content_width - block_width) // 2
    spacer_padding_left = " " * spacer_padding
    spacer_padding_right = " " * (content_width - block_width - spacer_padding)

    # Levels that have a spacer row AFTER them (going top to bottom)
    levels_with_spacer_after = [10, 9, 8, 7]

    # Build list of rows to draw (level number or None for spacer)
    gauge_rows = []
    for level in range(max_speed, 0, -1):  # 10 down to 1
        gauge_rows.append(level)
        if level in levels_with_spacer_after:
            gauge_rows.append(None)  # Spacer row

    total_gauge_rows = len(gauge_rows)

    # Draw gauge
    for row_idx, level in enumerate(gauge_rows):
        row_y = gauge_start_y + row_idx

        if row_y < panel_start_y or row_y >= panel_end_y:
            continue

        if level is None:
            # Spacer row - find which level it belongs to (the one above)
            level_above = None
            for i in range(row_idx - 1, -1, -1):
                if gauge_rows[i] is not None:
                    level_above = gauge_rows[i]
                    break

            if level_above is not None:
                # Use gradient color based on level
                active_color = GAUGE_GRADIENT[level_above - 1]

                # Spacer AFTER level N is between level N and level N-1
                # It should light up when:
                # - level_above is already active (current_speed >= level_above), OR
                # - We're one level below (current_speed == level_above - 1) AND momentum >= 50%
                level_below = level_above - 1

                if current_speed >= level_above:
                    # Level above is already reached, spacer is active
                    is_active = True
                elif current_speed == level_below and momentum_pct >= 50:
                    # We're at the level below and momentum >= 50%, light up spacer
                    is_active = True
                else:
                    is_active = False

                color = active_color if is_active else GAUGE_OFF
                block = gauge_block_on if is_active else gauge_block_off

                # Spacer row: just the block, no numbers (centered)
                line = f"{spacer_padding_left}{block}{spacer_padding_right}"
                fb.put_string(gauge_x, row_y, line, color)
        else:
            # Normal level row with numbers - use gradient color
            active_color = GAUGE_GRADIENT[level - 1]

            is_active = level <= current_speed
            color = active_color if is_active else GAUGE_OFF
            block = gauge_block_on if is_active else gauge_block_off

            level_str = f"{level:2d}"
            line = f"{level_str} - {block} - {level_str}"
            fb.put_string(gauge_x, row_y, line, color)

    y = gauge_start_y + total_gauge_rows

    # === Separator ===
    fb.put_string(left_padding, y, separator, GAUGE_OFF)
    y += 2  # Skip a line after separator

    # === Momentum: [horizontal bar] ===
    momentum_label = "Momentum:"
    fb.put_string(left_padding, y, momentum_label, PANEL_LABEL_COLOR)
    y += 2  # Skip a line between label and bar

    # Draw horizontal bar (dynamic width) with gradient colors (red -> yellow -> green)
    bar_width = content_width
    filled = int((momentum_pct / 100.0) * bar_width)
    gradient_len = len(MOMENTUM_GRADIENT)

    for i in range(bar_width):
        if i < filled:
            # Map position in bar to position in gradient (interpolate)
            gradient_idx = int((i / max(1, bar_width - 1)) * (gradient_len - 1))
            char_color = MOMENTUM_GRADIENT[gradient_idx]
            fb.put(left_padding + i, y, '█', char_color)
        else:
            fb.put(left_padding + i, y, '─', GAUGE_OFF)

    # Show percentage centered below the bar
    y += 1
    pct_str = f"{momentum_pct:.0f}%"
    pct_x = left_padding + (bar_width - len(pct_str)) // 2
    fb.put_string(pct_x, y, pct_str, PANEL_VALUE_COLOR)


def _calculate_level_line_y():
    """Calculate the Y position of the level line based on time to next level.

    Returns:
        (line_y, is_on_screen, unused) where:
        - line_y: screen Y position (in game area coordinates, 0 = top of game)
        - is_on_screen: True if the line should be visible
        - unused: kept for compatibility, always 0
    """
    miles = state.game.miles
    milestones = get_level_milestones()
    current_level = state.game.level

    # Current level threshold (where next level starts)
    if current_level <= len(milestones):
        current_threshold = milestones[current_level - 1]
    else:
        current_threshold = milestones[-1]

    miles_to_next = max(0, current_threshold - miles)

    current_speed = state.game.speed
    mph = current_speed * 40
    miles_per_second = mph / 3600.0 if mph > 0 else 0.001

    # Time until we reach next level (in seconds)
    time_to_level = miles_to_next / miles_per_second if miles_per_second > 0 else 999999

    # Scroll speed: 1 row per 5 frames, assume ~60 fps = 12 rows/second
    scroll_rows_per_second = 12.0

    panel_height = constants.layout.height

    # The line travels the FULL screen height (top to bottom)
    full_travel_distance = panel_height

    # Time for line to travel from top to bottom of screen
    time_for_full_travel = full_travel_distance / scroll_rows_per_second

    if time_to_level >= time_for_full_travel:
        # Line hasn't entered screen yet
        return -1, False, 0
    # Line is on screen - calculate position
    # Line goes from top (0) to bottom (panel_height)
    line_progress = 1.0 - (time_to_level / time_for_full_travel)
    line_progress = max(0, min(1, line_progress))
    line_y = int(line_progress * full_travel_distance)

    return line_y, True, 0


def _fb_render_level_line(fb):
    """Render the level line in the game area (dashed line showing next level)."""
    line_y, is_on_screen, progress = _calculate_level_line_y()

    if not is_on_screen:
        return

    # Screen Y position (add header offset)
    screen_y = line_y + HEADER_HEIGHT

    # Make sure it's in visible game area
    if screen_y < HEADER_HEIGHT or screen_y >= constants.layout.height + HEADER_HEIGHT:
        return

    # Draw dashed line across game width - darker than START line
    line_pattern = "· · · · · · · · · · · · · · · · · · · · · · · "

    for i, char in enumerate(line_pattern[: constants.layout.width]):
        if char != ' ':
            fb.put(GAME_X_OFFSET + i, screen_y, char, LEVEL_LINE_COLOR)


def _fb_render_right_panel_level_signs(fb):
    """Render level signs in right panel.

    Top sign: Next level - stays at top until "level line" would enter screen,
              then scrolls down synchronized with the level line.
              When scrolling, shows < on the left side pointing to the line.
    Bottom sign: Current level - shows distance traveled since reaching it
    """
    panel_start_y = HEADER_HEIGHT
    panel_end_y = constants.layout.height + HEADER_HEIGHT
    panel_end_y - panel_start_y
    right_start = GAME_X_OFFSET + constants.layout.width

    # Get level info
    miles = state.game.miles
    milestones = get_level_milestones()
    current_level = state.game.level
    current_group = state.game.level_group
    current_sub = state.game.level_sub

    # Panel inner area (excluding borders)
    inner_start_x = right_start + 1

    # Sign dimensions: 16 chars wide
    # Signs stay at LEFT of panel (close to game area), padding goes to the right
    sign_x = inner_start_x  # No centering - stick to left edge

    # === Calculate thresholds ===
    if current_level > 1:
        prev_threshold = milestones[current_level - 2]
    else:
        prev_threshold = 0

    if current_level <= len(milestones):
        current_threshold = milestones[current_level - 1]
    else:
        current_threshold = milestones[-1]

    # Next level info
    next_level = current_level + 1
    if next_level <= 18:
        next_group = ((next_level - 1) // 3) + 1
        next_sub = ((next_level - 1) % 3) + 1
    else:
        next_group, next_sub = 6, 3

    # Distance to next level
    miles_to_next = max(0, current_threshold - miles)

    # Distance from previous level
    miles_from_prev = max(0, miles - prev_threshold)

    # Get level line position to sync the sign
    line_y, is_scrolling, _ = _calculate_level_line_y()

    # Calculate sign Y position - sign follows the line directly
    if not is_scrolling:
        # Sign stays at top with down arrow
        top_sign_y = panel_start_y + 1
    else:
        # Sign follows the line - position sign so its middle row (row 1) aligns with line
        # line_y is in game coords (0 = top of game area)
        # panel_start_y + line_y = screen position of line
        # We want sign row 1 (the Level label) to be at the line
        top_sign_y = panel_start_y + line_y - 1  # -1 so row 1 aligns with line

    # === TOP SIGN ===
    # When NOT scrolling (at top):
    #   ╔══/\══════════╗
    #   ║ Level X-Y   ║
    #   ║ x.x miles   ║
    #   ╚══════════════╝
    #
    # When scrolling (with < on left side):
    #   ╔══════════════╗
    #  <║ Level X-Y   ║
    #   ║ x.x miles   ║
    #   ╚══════════════╝

    if top_sign_y >= panel_start_y and top_sign_y < panel_end_y - 4:
        if not is_scrolling:
            # At top - show down arrow
            fb.put_string(sign_x, top_sign_y, "╔══", SIGN_BORDER_COLOR)
            fb.put(sign_x + 3, top_sign_y, '/', SIGN_ARROW_COLOR)
            fb.put(sign_x + 4, top_sign_y, '\\', SIGN_ARROW_COLOR)
            fb.put_string(sign_x + 5, top_sign_y, "══════════╗", SIGN_BORDER_COLOR)
        else:
            # Scrolling - closed top, < on left of second row
            fb.put_string(sign_x, top_sign_y, "╔══════════════╗", SIGN_BORDER_COLOR)

        # Row 2: Level label (with < when scrolling)
        level_str = f"Level {next_group}-{next_sub}"
        if is_scrolling:
            fb.put(sign_x - 1, top_sign_y + 1, '<', SIGN_ARROW_COLOR)
        fb.put(sign_x, top_sign_y + 1, '║', SIGN_BORDER_COLOR)
        fb.put(sign_x + 1, top_sign_y + 1, ' ', SIGN_TEXT_COLOR)
        fb.put_string(sign_x + 2, top_sign_y + 1, f"{level_str:<12}", SIGN_TEXT_COLOR)
        fb.put(sign_x + 14, top_sign_y + 1, ' ', SIGN_TEXT_COLOR)
        fb.put(sign_x + 15, top_sign_y + 1, '║', SIGN_BORDER_COLOR)

        # Row 3: Distance remaining
        dist_str = f"{miles_to_next:.1f} miles"
        fb.put(sign_x, top_sign_y + 2, '║', SIGN_BORDER_COLOR)
        fb.put(sign_x + 1, top_sign_y + 2, ' ', SIGN_TEXT_COLOR)
        fb.put_string(sign_x + 2, top_sign_y + 2, f"{dist_str:<12}", SIGN_TEXT_COLOR)
        fb.put(sign_x + 14, top_sign_y + 2, ' ', SIGN_TEXT_COLOR)
        fb.put(sign_x + 15, top_sign_y + 2, '║', SIGN_BORDER_COLOR)

        # Row 4: bottom border (always closed)
        fb.put_string(sign_x, top_sign_y + 3, "╚══════════════╝", SIGN_BORDER_COLOR)

    # === BOTTOM SIGN: Current level (with up arrow) ===
    # ╔══════════════╗
    # ║ Level X-Y   ║
    # ║ x.x miles   ║
    # ╚══\/══════════╝

    bottom_sign_y = panel_end_y - 5

    if bottom_sign_y > panel_start_y + 5:
        # Row 1: top border (16 chars)
        fb.put_string(sign_x, bottom_sign_y, "╔══════════════╗", SIGN_BORDER_COLOR)

        # Row 2: Level label (left-aligned)
        level_str = f"Level {current_group}-{current_sub}"
        fb.put(sign_x, bottom_sign_y + 1, '║', SIGN_BORDER_COLOR)
        fb.put(sign_x + 1, bottom_sign_y + 1, ' ', SIGN_TEXT_COLOR)
        fb.put_string(sign_x + 2, bottom_sign_y + 1, f"{level_str:<12}", SIGN_TEXT_COLOR)
        fb.put(sign_x + 14, bottom_sign_y + 1, ' ', SIGN_TEXT_COLOR)
        fb.put(sign_x + 15, bottom_sign_y + 1, '║', SIGN_BORDER_COLOR)

        # Row 3: Distance from previous (left-aligned)
        dist_str = f"{miles_from_prev:.1f} miles"
        fb.put(sign_x, bottom_sign_y + 2, '║', SIGN_BORDER_COLOR)
        fb.put(sign_x + 1, bottom_sign_y + 2, ' ', SIGN_TEXT_COLOR)
        fb.put_string(sign_x + 2, bottom_sign_y + 2, f"{dist_str:<12}", SIGN_TEXT_COLOR)
        fb.put(sign_x + 14, bottom_sign_y + 2, ' ', SIGN_TEXT_COLOR)
        fb.put(sign_x + 15, bottom_sign_y + 2, '║', SIGN_BORDER_COLOR)

        # Row 4: bottom border with up arrow (16 chars)
        fb.put_string(sign_x, bottom_sign_y + 3, "╚══", SIGN_BORDER_COLOR)
        fb.put(sign_x + 3, bottom_sign_y + 3, '\\', SIGN_ARROW_COLOR)
        fb.put(sign_x + 4, bottom_sign_y + 3, '/', SIGN_ARROW_COLOR)
        fb.put_string(sign_x + 5, bottom_sign_y + 3, "══════════╝", SIGN_BORDER_COLOR)


def _fb_render_side_panels(fb):
    """
    Render left and right side panels (placeholder for Steam Deck 16:9 layout).
    Panels are ONLY in the middle section (between header and footer).
    Header (rows 0-3) and footer span full width.
    """
    # Panel area: from row HEADER_HEIGHT (after header) to row height+HEADER_HEIGHT (before floor)
    panel_start_y = HEADER_HEIGHT
    panel_end_y = constants.layout.height + HEADER_HEIGHT  # exclusive (floor row)

    right_start = GAME_X_OFFSET + constants.layout.width

    # Left panel - clear and draw borders
    border = ('│', PANEL_BORDER_COLOR)
    left_panel = [border] + [BLANK] * (SIDE_PANEL_WIDTH - 2) + [border]
    for y in range(panel_start_y, panel_end_y):
        fb.put_cells(0, y, left_panel)

    # Render left panel content (speed info, gauge, momentum)
    _fb_render_left_panel_content(fb, panel_start_y, panel_end_y)

    # Right panel - vertical borders only (background rendered separately)
    rows = fb.current
    outer_x = right_start + SIDE_PANEL_WIDTH - 1
    for y in range(panel_start_y, panel_end_y):
        row = rows[y]
        row[right_start] = border
        row[outer_x] = border


def _fb_render_right_panel_barriers(fb):
    """Render decorative barriers in right panel using biome-specific sprites and colors."""

    # Right panel position
    right_panel_start = GAME_X_OFFSET + constants.layout.width + 1  # After game area + border
    right_panel_inner_width = SIDE_PANEL_WIDTH - 2

    # Get obstacle sprites and color for current biome
    biome_obstacles = get_biome_obstacles(state.game.level_group)
    biome_obs_color = get_biome_obstacle_color(state.game.level_group)

    for barrier in state.enemies.right_panel_barriers:
        tier = barrier.get('tier', 1)
        sprite = biome_obstacles.get(tier, biome_obstacles.get(1, OBSTACLE_SPRITE_T1))
        max(len(line) for line in sprite)

        # Use stored x_offset for horizontal position variation
        x_offset = barrier.get('x_offset', 0)
        base_x = right_panel_start + x_offset

        for line_idx, line in enumerate(sprite):
            y_pos = barrier['y_pos'] + line_idx
            if 0 <= y_pos < constants.layout.height:
                for i, char in enumerate(line):
                    if char != ' ':
                        x_pos = base_x + i
                        # Make sure it stays within panel bounds
                        if right_panel_start <= x_pos < right_panel_start + right_panel_inner_width:
                            fb.put(x_pos, y_pos + HEADER_HEIGHT, char, biome_obs_color)


def _fb_render_notifications(fb):
    """Render notification cards in right panel between level signs."""
    # Filter expired notifications (support both old tuple and new dict format)
    active_notifications = []
    for n in state.ui.notifications:
        if isinstance(n, dict):
            if n.get('expire_frame', 0) > state.game.frame_count:
                active_notifications.append(n)
        else:
            # Old tuple format (text, expire_frame) - convert on the fly
            if len(n) >= 2 and n[1] > state.game.frame_count:
                active_notifications.append({'title': '', 'text': n[0], 'expire_frame': n[1]})

    state.ui.notifications[:] = active_notifications

    if not active_notifications:
        return

    # Right panel positioning
    panel_start_y = HEADER_HEIGHT
    panel_end_y = constants.layout.height + HEADER_HEIGHT
    right_start = GAME_X_OFFSET + constants.layout.width
    inner_start_x = right_start + 1

    # Card dimensions: dynamic width based on panel, 4 rows high
    # Cards stay at LEFT of panel (close to game area), padding goes to the right
    # ╔══════════════════════════════════════╗
    # ║ Title:                               ║
    # ║ Text here                            ║
    # ╚══════════════════════════════════════╝
    card_width = SIDE_PANEL_WIDTH - 2  # Full panel width minus side borders
    card_height = 4
    card_x = inner_start_x  # No centering - stick to left edge
    inner_width = card_width - 2  # Space inside the card (between ║ and ║)

    # Top sign ends at row: panel_start_y + 1 + 4 = panel_start_y + 5
    # Bottom sign starts at: panel_end_y - 5
    # Available space: from panel_start_y + 6 to panel_end_y - 6
    top_sign_bottom = panel_start_y + 5
    bottom_sign_top = panel_end_y - 5

    # Space between signs for notification cards
    available_start = top_sign_bottom + 1
    available_end = bottom_sign_top - 1

    # Calculate how many cards fit (each is 4 rows + 1 spacing)
    available_rows = available_end - available_start
    cards_per_screen = max(1, available_rows // (card_height + 1))

    # Limit to max_stack from config
    try:
        max_cards = min(cards_per_screen, constants.notifications.max_stack)
    except AttributeError:
        max_cards = min(cards_per_screen, 3)

    # Draw notification cards (newest at top)
    for i, notif in enumerate(active_notifications[:max_cards]):
        card_y = available_start + i * (card_height + 1)

        if card_y + card_height > available_end:
            break

        text_max_len = inner_width - 2  # Leave 1 space padding on each side
        title = notif.get('title', '')[:text_max_len]
        text = notif.get('text', '')[:text_max_len]

        # Build border strings dynamically
        top_border = "╔" + "═" * (card_width - 2) + "╗"
        bottom_border = "╚" + "═" * (card_width - 2) + "╝"

        # Row 1: top border
        fb.put_string(card_x, card_y, top_border, CARD_BORDER_COLOR)

        # Row 2: title (or first line of text if no title)
        fb.put(card_x, card_y + 1, '║', CARD_BORDER_COLOR)
        if title:
            fb.put_string(card_x + 1, card_y + 1, f" {title:<{text_max_len}}", CARD_TITLE_COLOR)
        else:
            fb.put_string(card_x + 1, card_y + 1, f" {text:<{text_max_len}}", CARD_TEXT_COLOR)
        fb.put(card_x + card_width - 1, card_y + 1, '║', CARD_BORDER_COLOR)

        # Row 3: text (or empty if no title)
        fb.put(card_x, card_y + 2, '║', CARD_BORDER_COLOR)
        if title:
            fb.put_string(card_x + 1, card_y + 2, f" {text:<{text_max_len}}", CARD_TEXT_COLOR)
        else:
            fb.put_string(card_x + 1, card_y + 2, " " * inner_width, '')  # Empty
        fb.put(card_x + card_width - 1, card_y + 2, '║', CARD_BORDER_COLOR)

        # Row 4: bottom border
        fb.put_string(card_x, card_y + 3, bottom_border, CARD_BORDER_COLOR)
