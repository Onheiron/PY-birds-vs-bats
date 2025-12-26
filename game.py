#!/usr/bin/env python3
"""
BVB - Ball Versus Bird
Main entry point with clean game loop.
"""

import time

from src import functions
from src.core import state
from src.core import constants
from src.ui import render
from src.engine import input_handler
from src.engine import physics
from src.engine import game_logic
from src.services import achievements
from src.entities.sprites import RED, RESET

try:
    from src.services import firebase_client
except ImportError:
    firebase_client = None

GAME_VERSION = "2.0"


def show_game_over_screen():
    """Display the game over screen with final stats and leaderboard submission."""
    # Get config values with defaults
    separator_width = getattr(constants.game_over, 'separator_width', 50)
    time_divider = getattr(constants.game_over, 'time_divider', 3600)
    time_remainder = getattr(constants.game_over, 'time_remainder', 3600)
    minutes_divider = getattr(constants.game_over, 'minutes_divider', 60)
    name_max_length = getattr(constants.game_over, 'leaderboard_name_max_length', 20)

    # Clear screen and show cursor
    print("\033[2J\033[H\033[?25h")

    # Calculate elapsed time
    elapsed = 0
    if hasattr(state.game, 'start_time') and state.game.start_time:
        elapsed = int(time.time() - state.game.start_time)

    hours = elapsed // time_divider
    minutes = (elapsed % time_remainder) // minutes_divider
    seconds = elapsed % minutes_divider

    if hours > 0:
        elapsed_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        elapsed_str = f"{minutes:02d}:{seconds:02d}"

    # Calculate avg points per minute
    minutes_played = float(elapsed) / float(minutes_divider) if elapsed > 0 else 0.0
    avg_ppm = float(state.game.score) / minutes_played if minutes_played > 0 else float(state.game.score)

    # Display game over screen
    print("\r")
    print("\r")
    print("\r")
    print("\r")
    print(f"{RED}{'=' * separator_width}{RESET}\r")
    print(f"{RED}                   GAME OVER                     {RESET}\r")
    print(f"{RED}{'=' * separator_width}{RESET}\r")
    print("\r")
    print(f"  Final Score:      {int(state.game.score)}\r")
    print(f"  Level Reached:    {state.game.level}\r")
    print("\r")
    print(f"  Time Played:      {elapsed_str} ({elapsed} s)\r")
    print(f"{RED}{'=' * separator_width}{RESET}\r")
    print("\r")

    # Prompt for leaderboard name
    try:
        name = input("Enter name for leaderboard (leave blank to skip): ").strip()[:name_max_length]
    except Exception:
        name = ""

    # Submit to Firebase if available
    if firebase_client:
        try:
            if name:
                functions.background_call(
                    firebase_client.send_score,
                    name,
                    int(state.game.score),
                    elapsed,
                    elapsed_str,
                    GAME_VERSION,
                    avg_ppm
                )
            # Log game over event
            functions.background_call(
                firebase_client.log_event,
                'game_over',
                {
                    'score': int(state.game.score),
                    'level': state.game.level,
                    'time_played_seconds': elapsed,
                    'time_played': elapsed_str,
                    'version': GAME_VERSION,
                    'avg_ppm': avg_ppm
                }
            )
        except Exception:
            pass


def main():
    """Main game loop."""
    # Initialize terminal and game state
    functions.setup()
    state.init()
    achievements.init_achievements()
    state.game.start_time = time.time()

    try:
        while not state.game.game_over:
            # Read input
            key = render.get_key()

            # Process input
            input_handler.process_input(key)

            # If paused, just render and sleep
            if state.game.paused:
                render.render_game()
                time.sleep(constants.timing.base_sleep)
                continue

            # Update physics (movement)
            physics.update_all()

            # Update game logic (collisions, spawning, powerups)
            game_logic.update_all()

            # Render
            render.render_game()

            # Increment frame counter
            state.game.frame_count += 1

            # Sleep for frame timing
            time.sleep(game_logic.calculate_frame_sleep())

    except KeyboardInterrupt:
        pass
    finally:
        # Show game over screen if game ended normally
        if state.game.game_over:
            functions.cleanup()
            show_game_over_screen()
        else:
            functions.cleanup()


if __name__ == '__main__':
    main()
