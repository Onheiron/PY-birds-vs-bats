#!/usr/bin/env python3
"""
BVB - Ball Versus Bird
Main entry point with clean game loop.
"""

import time
import math

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

# Timing constants for new game loop
FIXED_FPS = 60  # Loop fisso a 60 FPS
FIXED_FRAME_TIME = 1.0 / FIXED_FPS  # ~16.6ms
MAX_LEVEL = 30


def calculate_frames_per_update(level):
    """
    Calcola quanti frame del loop fisso passano tra ogni update della fisica.
    Usa una curva logaritmica: accelera velocemente all'inizio, poi rallenta.

    Level 1:  10 frames/update = 6 updates/sec (lento)
    Level 30: 2 frames/update = 30 updates/sec (veloce ma giocabile)
    """
    # Normalizza level tra 0 e 1
    t = (level - 1) / (MAX_LEVEL - 1) if MAX_LEVEL > 1 else 0
    # Curva logaritmica: cresce veloce all'inizio
    k = 5  # Curvatura
    if t <= 0:
        normalized = 0
    else:
        normalized = math.log(1 + t * k) / math.log(1 + k)
    # Mappa da max_frames (lento) a min_frames (veloce)
    max_frames = 10
    min_frames = 2
    frames = max_frames - normalized * (max_frames - min_frames)
    return max(min_frames, round(frames))


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
    except (KeyboardInterrupt, EOFError):
        # CTRL+C or CTRL+D to skip
        print()  # New line after ^C
        name = ""
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
    """
    Main game loop con timing migliorato.

    Il loop gira a ~60 FPS fissi per input fluido.
    La fisica/logica viene aggiornata ogni N frame, dove N dipende dal livello.
    Questo permette input sempre reattivo mentre il gioco accelera.
    """
    # Initialize terminal and game state
    functions.setup()
    state.init()
    achievements.init_achievements()
    state.game.start_time = time.time()

    # Contatore frame per decidere quando aggiornare la fisica
    render_frame = 0

    try:
        while not state.game.game_over:
            frame_start = time.time()

            # === INPUT (sempre, ogni frame) ===
            key = render.get_key()
            input_handler.process_input(key)

            # Se in pausa, solo render e aspetta
            if state.game.paused:
                render.render_game()
                # Mantieni 60 FPS anche in pausa
                elapsed = time.time() - frame_start
                sleep_time = FIXED_FRAME_TIME - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                continue

            # === PHYSICS/LOGIC UPDATE (ogni N frame basato sul livello) ===
            frames_per_update = calculate_frames_per_update(state.game.level)

            if render_frame % frames_per_update == 0:
                # Update physics (movement)
                physics.update_all()

                # Update game logic (collisions, spawning, powerups)
                game_logic.update_all()

                # Increment game frame counter (usato per spawn timing, etc.)
                state.game.frame_count += 1

            # === RENDER (sempre, ogni frame per fluidità) ===
            render.render_game()

            # Incrementa contatore frame rendering
            render_frame += 1

            # === TIMING: mantieni ~60 FPS ===
            elapsed = time.time() - frame_start
            sleep_time = FIXED_FRAME_TIME - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        # CTRL+C è un'uscita volontaria
        state.game.quit_requested = True
    finally:
        functions.cleanup()
        # Mostra game over screen SOLO se è un game over reale (non quit volontario)
        if state.game.game_over and not state.game.quit_requested:
            show_game_over_screen()


if __name__ == '__main__':
    main()
