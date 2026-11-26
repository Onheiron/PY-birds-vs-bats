#!/usr/bin/env python3
"""BVB - Bird vs Bat. Entry point."""

import os
import sys

USAGE = """\
usage: game.py [--window] [--fullscreen] [--config FILE] [--theme FILE] [--bot PROFILE ...]
               [--version] [--help]

  --window        play in a window of its own instead of this terminal
                  (keyboard and gamepad; F11 toggles full screen)
  --fullscreen    the window full screen (implies --window)

  --config FILE   YAML configuration merged over the defaults in config.yml
                  (try hardmode.yml, or start from config.sample.yml)
  --theme FILE    colour theme (default: theme.yml)
  --bot PROFILE   watch the bot play (perfect, expert, average, novice, me, top);
                  see game.py --bot expert --help for its options
  --version       print the version and exit
  --help          show this message and exit

Controls: arrows move and bounce, SPACE swaps, P pauses, Q quits.
"""


def _window_options():
    """Take --window / --fullscreen out of the arguments; True/False/None for full screen."""
    args = sys.argv[1:]
    fullscreen = '--fullscreen' in args
    window = fullscreen or '--window' in args or os.environ.get('BVB_WINDOW') == '1'
    sys.argv[1:] = [a for a in args if a not in ('--window', '--fullscreen')]
    if not window:
        return None
    # The window draws 24-bit colour: let the game use it
    os.environ['COLORTERM'] = 'truecolor'
    return fullscreen


_instance_lock = None  # held while the game runs


def _only_instance():
    """True if no other copy of the game is running (a lock in ~/.bvb). Where locks are not
    available the game just starts."""
    global _instance_lock
    from pathlib import Path

    from src.services.save_manager import SAVE_DIR_NAME

    try:
        folder = Path.home() / SAVE_DIR_NAME
        folder.mkdir(parents=True, exist_ok=True)
        _instance_lock = open(folder / 'running.lock', 'a+')  # noqa: SIM115 (kept open on purpose)
        if sys.platform.startswith('win'):
            import msvcrt

            msvcrt.locking(_instance_lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(_instance_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, PermissionError):
        return False
    except (OSError, ImportError):
        return True
    return True


def main():
    """Set the terminal up, then run games until the player quits."""
    from src import __version__

    fullscreen = _window_options()
    if fullscreen is not None:
        from src.ui import terminal as terminal_module

        terminal_module.use_window(fullscreen)

    if '--version' in sys.argv[1:]:
        print(f'BVB {__version__}')
        return
    if any(arg == '--bot' or arg.startswith('--bot=') for arg in sys.argv[1:]):
        from src.sim import watch

        watch.main(sys.argv[1:])
        return
    if '--help' in sys.argv[1:] or '-h' in sys.argv[1:]:
        print(USAGE, end='')
        return
    if not _only_instance():
        return  # already open (a launcher that starts the game twice): the first one plays

    # Imported here: loading the game reads the configuration, which may stop
    # with a message for the user, and must not happen for --help or --version.
    from src.engine import loop
    from src.services import save_manager, sound
    from src.ui import terminal
    from src.ui.framebuffer import reset_framebuffer

    terminal.setup()
    try:
        save_manager.load_default_settings()
        save_manager.load_discovery()

        while loop.run_game() == 'retry':
            # Fresh framebuffer: the new game starts with a full redraw
            reset_framebuffer()
    finally:
        from src.services import online

        online.wait_for_sending()  # a game just sent must not be cut off by closing
        sound.cleanup()
        terminal.cleanup()
    from src.core import state

    if state.ui.last_recording:
        print(f'Last game recorded: {state.ui.last_recording}')
        print('Replay it and compare it with the bot: python3 tools/replay.py --bot expert')


if __name__ == '__main__':
    main()
