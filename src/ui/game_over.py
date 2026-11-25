"""Game over screen: final stats, leaderboard name entry and retry/exit menu."""

import time

from src import __version__
from src.core import constants, state
from src.engine.timing import FrameClock
from src.entities.sprites import RED
from src.services.background import background_call
from src.services.optional import firebase_client
from src.ui import controls, terminal
from src.ui.framebuffer import get_framebuffer
from src.ui.keyboard import read_keys
from src.ui.layout import GAME_X_OFFSET, SIDE_PANEL_WIDTH, TOTAL_WIDTH

PANEL_BORDER = "\033[38;5;238m"
PANEL_BG = "\033[38;5;233m"
GREEN = "\033[32m"
YELLOW = "\033[33m"

_BOX_LINES = (
    "##############################",
    "#        GAME  OVER          #",
    "##############################",
)


def session_stats():
    """Final numbers of the session: (elapsed seconds, 'MM:SS' text, points per minute)."""
    time_divider = getattr(constants.game_over, 'time_divider', 3600)
    time_remainder = getattr(constants.game_over, 'time_remainder', 3600)
    minutes_divider = getattr(constants.game_over, 'minutes_divider', 60)

    elapsed = 0
    if getattr(state.game, 'start_time', None):
        elapsed = int(time.time() - state.game.start_time)

    hours = elapsed // time_divider
    minutes = (elapsed % time_remainder) // minutes_divider
    seconds = elapsed % minutes_divider
    if hours > 0:
        elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        elapsed_str = f"{minutes:02d}:{seconds:02d}"

    minutes_played = float(elapsed) / float(minutes_divider) if elapsed > 0 else 0.0
    score = float(state.game.score)
    avg_ppm = score / minutes_played if minutes_played > 0 else score
    return elapsed, elapsed_str, avg_ppm


def _gold_line():
    """The gold of the run: its reward, and what the achievements reached in it paid."""
    from src.engine import meta

    reward = state.meta.run_gold if state.meta.finished else meta.run_gold()
    table = meta.global_achievements()
    extra = sum(
        vars(e).get('gold', 0) if not isinstance(e, dict) else e.get('gold', 0)
        for e in (table.get(a) for a in state.meta.run_achievements)
        if e is not None
    )
    count = len(state.meta.run_achievements)
    if not count:
        return f"Gold Earned:    {reward}"
    return f"Gold Earned:    {reward} + {extra} ({count} achievement{'s' if count > 1 else ''})"


def draw(fb, elapsed_str, selected=0, player_name="", phase="menu", name_max_length=20):
    """Draw the game over screen into the framebuffer.

    phase: 'name' for name input, 'menu' for the retry/exit menu.
    """
    fb.clear()
    width = constants.layout.width
    height = constants.layout.height

    # Header: GAME OVER centered, then a separator
    header = "GAME OVER"
    fb.put_string((TOTAL_WIDTH - len(header)) // 2, 0, header)
    fb.put_string(0, 1, '=' * TOTAL_WIDTH)

    # Dotted side panels
    right_start = GAME_X_OFFSET + width
    for y in range(2, height + 2):
        for panel_x in (0, right_start):
            fb.put(panel_x, y, '|', PANEL_BORDER)
            for x in range(1, SIDE_PANEL_WIDTH - 1):
                if (x + y) % 4 == 0:
                    fb.put(panel_x + x, y, '.', PANEL_BG)
            fb.put(panel_x + SIDE_PANEL_WIDTH - 1, y, '|', PANEL_BORDER)

    # Content - vertically centered
    center_y = height // 2 + 2
    center_x = GAME_X_OFFSET + width // 2

    def centered(y, text, color=''):
        fb.put_string(center_x - len(text) // 2, y, text, color)

    for i, line in enumerate(_BOX_LINES):
        centered(center_y - 6 + i, line, RED)

    stats = (
        f"Final Score:    {int(state.game.score):,}",
        f"Level Reached:  {state.game.level}",
        f"Time Played:    {elapsed_str}",
        _gold_line(),
    )
    for i, line in enumerate(stats):
        centered(center_y - 2 + i, line, YELLOW if line.startswith('Gold') else '')

    if phase == "name":
        name_y = center_y + 4
        centered(name_y, "Enter name for leaderboard:", YELLOW)
        padding = " " * (name_max_length - len(player_name))
        centered(name_y + 1, f"[ {player_name}_{padding} ]", GREEN)
        centered(name_y + 3, controls.hint("({confirm} to confirm, ESC to skip)"))
        footer = controls.hint("Type your name | {confirm} confirm | {delete} delete | ESC skip")
    else:
        menu_y = center_y + 4
        if selected == 0:
            centered(menu_y, "> [ RETRY ] <", GREEN)
            centered(menu_y + 1, "    EXIT")
        else:
            centered(menu_y, "    RETRY")
            centered(menu_y + 1, "> [  EXIT ] <", GREEN)
        footer = controls.hint("{navigate} select | {select} confirm")

    # Floor separator and footer
    floor_y = height + 2
    fb.put_string(0, floor_y, '=' * TOTAL_WIDTH)
    fb.put_string((TOTAL_WIDTH - len(footer)) // 2, floor_y + 1, footer)


def _ask_player_name(fb, clock, elapsed_str, max_length):
    """Name entry phase. Returns the typed name ('' when skipped)."""
    name = ""
    while True:
        draw(fb, elapsed_str, 0, name, "name", max_length)
        terminal.write_frame(fb.render())

        for key in read_keys(text=True):
            if key in ('QUIT', 'ESC'):
                return ""
            if key == 'ENTER':
                return name
            if key == 'BACKSPACE':
                name = name[:-1]
            elif len(name) < max_length:
                if key == 'SPACE':
                    name += " "
                elif len(key) == 1 and key.isprintable():
                    name += key
        clock.wait()


def _ask_retry(fb, clock, elapsed_str, player_name):
    """Menu phase. Returns 0 for RETRY, 1 for EXIT."""
    selected = 0
    while True:
        draw(fb, elapsed_str, selected, player_name, "menu")
        terminal.write_frame(fb.render())

        for key in read_keys():
            if key == 'UP':
                selected = 0
            elif key == 'DOWN':
                selected = 1
            elif key in ('ENTER', 'SPACE'):
                return selected
            elif key in ('QUIT', 'ESC'):
                return 1
        clock.wait()


def _submit_stats(player_name, elapsed, elapsed_str, avg_ppm):
    """Send the final score and a game_over event to Firebase (best effort)."""
    if not firebase_client:
        return
    try:
        if player_name.strip():
            background_call(
                firebase_client.send_score,
                player_name.strip(),
                int(state.game.score),
                elapsed,
                elapsed_str,
                __version__,
                avg_ppm,
            )
        background_call(
            firebase_client.log_event,
            'game_over',
            {
                'score': int(state.game.score),
                'level': state.game.level,
                'time_played_seconds': elapsed,
                'time_played': elapsed_str,
                'version': __version__,
                'avg_ppm': avg_ppm,
            },
        )
    except Exception:
        pass


def show():
    """Run the game over screen. Returns 'retry' to play again, 'exit' to quit."""
    fb = get_framebuffer()
    # The game-over screen replaces the whole frame: force a full redraw
    fb.invalidate()

    name_max_length = getattr(constants.game_over, 'leaderboard_name_max_length', 20)
    elapsed, elapsed_str, avg_ppm = session_stats()
    clock = FrameClock()

    player_name = _ask_player_name(fb, clock, elapsed_str, name_max_length)
    selected = _ask_retry(fb, clock, elapsed_str, player_name)
    _submit_stats(player_name, elapsed, elapsed_str, avg_ppm)

    return 'retry' if selected == 0 else 'exit'
