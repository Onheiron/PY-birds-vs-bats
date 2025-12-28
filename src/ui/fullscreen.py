#!/usr/bin/env python3
"""
Fullscreen terminal support for BVB.
Handles terminal sizing, maximization, and font size recommendations.
"""

import os
import sys
import shutil
import subprocess


def _get_dimensions():
    """Get game dimensions from render module or use defaults."""
    try:
        from src.ui import render
        return render.TOTAL_WIDTH, render.TOTAL_HEIGHT
    except Exception:
        # Fallback defaults
        SIDE_PANEL_WIDTH = 20
        GAME_WIDTH = 45
        GAME_HEIGHT = 20
        return GAME_WIDTH + (SIDE_PANEL_WIDTH * 2), GAME_HEIGHT + 8


def _get_min_size():
    """Get minimum required terminal size."""
    total_w, total_h = _get_dimensions()
    return total_w, total_h


def get_terminal_size():
    """Get current terminal size (columns, rows)."""
    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return size.columns, size.lines
    except Exception:
        return 80, 24


def enter_fullscreen_mode():
    """
    Attempt to maximize/fullscreen the terminal window.
    Uses various escape sequences and methods for different terminals.
    """
    # Enter alternate screen buffer (preserves scrollback)
    sys.stdout.write("\033[?1049h")

    # Try to maximize window - works on xterm, iTerm2, some other terminals
    # CSI 9;1t = maximize window
    sys.stdout.write("\033[9;1t")

    # Try fullscreen toggle for macOS Terminal.app
    # This uses a specific escape sequence
    sys.stdout.write("\033[10;2t")  # Attempt fullscreen

    sys.stdout.flush()


def exit_fullscreen_mode():
    """
    Exit fullscreen/maximized mode and restore terminal.
    """
    # Exit alternate screen buffer
    sys.stdout.write("\033[?1049l")

    # Restore window size (if it was changed)
    sys.stdout.write("\033[9;0t")

    sys.stdout.flush()


def calculate_optimal_font_size(screen_width=None, screen_height=None):
    """
    Calculate the optimal terminal font size to fill the screen.

    Returns a tuple of (font_size, explanation_string).
    """
    total_width, total_height = _get_dimensions()

    # If no screen size provided, try to detect it
    if screen_width is None or screen_height is None:
        # Try to get screen resolution on macOS
        try:
            result = subprocess.run(
                ['system_profiler', 'SPDisplaysDataType'],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout
            # Parse resolution from output
            for line in output.split('\n'):
                if 'Resolution' in line:
                    # Extract "1920 x 1080" or similar
                    parts = line.split(':')[-1].strip()
                    nums = [int(s) for s in parts.replace('x', ' ').split() if s.isdigit()]
                    if len(nums) >= 2:
                        screen_width, screen_height = nums[0], nums[1]
                        break
        except Exception:
            pass

    # Fallback to common resolutions
    if screen_width is None:
        screen_width = 1920
    if screen_height is None:
        screen_height = 1080

    # Calculate font size to fit game perfectly
    # Terminal cell is roughly 0.5:1 aspect ratio (width:height)
    # So a font of size N has cells approximately N/2 wide and N tall

    # For the game to fit:
    # screen_width >= total_width * (font_size * 0.6)  [monospace char width]
    # screen_height >= total_height * (font_size * 1.2) [line height]

    # Account for window chrome (title bar, padding) - approximately 50px
    usable_width = screen_width - 50
    usable_height = screen_height - 100

    # Calculate max font size that fits
    # For most monospace fonts, char_width ≈ 0.6 * font_size, line_height ≈ 1.2 * font_size
    max_font_by_width = usable_width / (total_width * 0.6)
    max_font_by_height = usable_height / (total_height * 1.2)

    optimal_font = int(min(max_font_by_width, max_font_by_height))

    # Clamp to reasonable range
    optimal_font = max(10, min(48, optimal_font))

    return optimal_font, f"Screen: {screen_width}x{screen_height}, Optimal font: {optimal_font}pt"


def check_terminal_size():
    """
    Check if terminal is large enough for the game.
    Returns (ok, message) tuple.
    """
    cols, rows = get_terminal_size()
    min_cols, min_rows = _get_min_size()

    if cols >= min_cols and rows >= min_rows:
        return True, f"Terminal size OK: {cols}x{rows}"

    missing_cols = max(0, min_cols - cols)
    missing_rows = max(0, min_rows - rows)

    msg = f"Terminal too small: {cols}x{rows} (need {min_cols}x{min_rows})"
    if missing_cols > 0:
        msg += f"\n  - Need {missing_cols} more columns"
    if missing_rows > 0:
        msg += f"\n  - Need {missing_rows} more rows"

    return False, msg


def show_fullscreen_instructions():
    """
    Print instructions for the user to set up fullscreen mode.
    """
    cols, rows = get_terminal_size()
    min_cols, min_rows = _get_min_size()
    font_size, explanation = calculate_optimal_font_size()

    print("\033[2J\033[H")  # Clear screen
    print("=" * 60)
    print("  BVB FULLSCREEN SETUP")
    print("=" * 60)
    print()
    print(f"  Current terminal: {cols} cols x {rows} rows")
    print(f"  Required minimum: {min_cols} cols x {min_rows} rows")
    print()
    print(f"  {explanation}")
    print()
    print("  To fill your screen with the game:")
    print()
    print("  iTerm2:")
    print("    1. Press Cmd+Enter for native fullscreen")
    print("    2. Go to Preferences → Profiles → Text")
    print(f"    3. Set font size to approximately {font_size}pt")
    print()
    print("  Terminal.app:")
    print("    1. Press Cmd+Ctrl+F for fullscreen")
    print("    2. Go to Preferences → Profiles → Text")
    print(f"    3. Set font size to approximately {font_size}pt")
    print()
    print("  Steam Deck / Console Mode:")
    print("    1. Maximize the terminal window")
    print(f"    2. Adjust font to {font_size}pt or larger")
    print()
    print("=" * 60)
    print()

    return font_size


def apply_macos_fullscreen():
    """
    Try to trigger fullscreen on macOS using AppleScript.
    This works for Terminal.app.
    """
    if sys.platform != 'darwin':
        return False

    try:
        # Check which terminal we're in
        term_program = os.environ.get('TERM_PROGRAM', '')

        if term_program == 'Apple_Terminal':
            # AppleScript to toggle fullscreen in Terminal.app
            script = '''
            tell application "Terminal"
                tell front window
                    set zoomed to true
                end tell
            end tell
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True, timeout=2)
            return True

        elif term_program == 'iTerm.app':
            # AppleScript for iTerm2
            script = '''
            tell application "iTerm2"
                tell current session of current window
                    set columns to 200
                    set rows to 50
                end tell
            end tell
            '''
            subprocess.run(['osascript', '-e', script], capture_output=True, timeout=2)
            return True

    except Exception:
        pass

    return False


def setup_fullscreen():
    """
    Main entry point to set up fullscreen mode.
    Call this at game startup.

    Returns True if terminal is ready, False if user needs to resize manually.
    """
    # First, try to maximize/fullscreen the window
    enter_fullscreen_mode()

    # Try macOS-specific fullscreen
    apply_macos_fullscreen()

    # Small delay to let window resize
    import time
    time.sleep(0.1)

    # Check if we have enough space now
    ok, msg = check_terminal_size()

    return ok
