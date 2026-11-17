#!/usr/bin/env python3
"""BVB - Bird vs Bat. Entry point."""

import sys

USAGE = """\
usage: game.py [--config FILE] [--theme FILE] [--version] [--help]

  --config FILE   YAML configuration merged over the defaults in config.yml
                  (try hardmode.yml, or start from config.sample.yml)
  --theme FILE    colour theme (default: theme.yml)
  --version       print the version and exit
  --help          show this message and exit

Controls: arrows move and bounce, SPACE swaps, P pauses, Q quits.
"""


def main():
    """Set the terminal up, then run games until the player quits."""
    from src import __version__

    if '--version' in sys.argv[1:]:
        print(f'BVB {__version__}')
        return
    if '--help' in sys.argv[1:] or '-h' in sys.argv[1:]:
        print(USAGE, end='')
        return

    # Imported here: loading the game reads the configuration, which may stop
    # with a message for the user, and must not happen for --help or --version.
    from src.engine import loop
    from src.services import optional, save_manager, sound
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
        sound.cleanup()
        optional.close_firebase()
        terminal.cleanup()


if __name__ == '__main__':
    main()
