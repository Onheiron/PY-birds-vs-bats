"""Terminal control: raw mode, alternate screen, cursor and frame output."""

import contextlib
import os
import sys

if os.name != 'nt':
    import termios
    import tty

# Alternate screen (keeps the user's scrollback intact), hidden cursor, cleared
_ENTER_GAME_SCREEN = "\033[?1049h\033[?25l\033[2J\033[H"
_LEAVE_GAME_SCREEN = "\033[0m\033[?25h\033[?1049l"
# Synchronized output: the terminal applies a whole frame at once (no tearing).
# Terminals without support ignore these. Set BVB_SYNC_OUTPUT=0 to disable.
_SYNC_BEGIN = "\033[?2026h"
_SYNC_END = "\033[?2026l"

_saved_termios = None
# Window mode (src/ui/window.py): None, or {'fullscreen': bool} once asked for
_window_mode = None
_sync_output = os.environ.get('BVB_SYNC_OUTPUT', '1') != '0'


def _enable_windows_ansi():
    """Turn on ANSI escape processing in the Windows console."""
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def use_window(fullscreen=False):
    """Play in a window of its own (a terminal emulator) instead of this terminal."""
    global _window_mode
    _window_mode = {'fullscreen': fullscreen}


def setup():
    """Prepare the terminal for the game: raw input, hidden cursor, clean screen."""
    global _saved_termios

    if _window_mode is not None:
        from src.ui import window

        window.open_window(fullscreen=_window_mode['fullscreen'])
        return

    # Sprites use box-drawing and block characters: make sure they can be encoded
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    if os.name == 'nt':
        _enable_windows_ansi()
    elif sys.stdin.isatty():
        fd = sys.stdin.fileno()
        _saved_termios = termios.tcgetattr(fd)
        tty.setraw(fd)

    sys.stdout.write(_ENTER_GAME_SCREEN)
    sys.stdout.flush()


def cleanup():
    """Restore the terminal to the state it was in before setup()."""
    global _saved_termios

    from src.ui import window

    if window.active():
        window.close_window()
        return

    if _saved_termios is not None:
        try:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _saved_termios)
        except Exception:
            # Last resort: ask the tty driver for sane defaults
            os.system('stty sane 2>/dev/null')
        _saved_termios = None

    try:
        sys.stdout.write(_LEAVE_GAME_SCREEN)
        sys.stdout.flush()
    except Exception:
        pass


def write_frame(output):
    """Send one frame of differential output to the terminal."""
    if not output:
        return
    from src.ui import window

    if window.active():
        window.get().write(output)
        return
    stream = sys.stdout
    if _sync_output:
        stream.write(_SYNC_BEGIN + output + _SYNC_END)
    else:
        stream.write(output)
    stream.flush()
