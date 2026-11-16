#!/usr/bin/env python3
"""BVB - Bird vs Bat. Entry point."""

from src.engine import loop
from src.services import optional, save_manager, sound
from src.ui import terminal
from src.ui.framebuffer import reset_framebuffer


def main():
    """Set the terminal up, then run games until the player quits."""
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
