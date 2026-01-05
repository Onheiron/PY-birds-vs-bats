#!/usr/bin/env python3
"""
BVB - Ball Versus Bird
Main entry point with clean game loop.
"""

import time
import math
import re

from src import functions
from src.core import state
from src.core import constants
from src.ui import render
from src.engine import input_handler
from src.engine import physics
from src.engine import game_logic
from src.services import achievements
from src.services import save_manager
from src.entities.sprites import RED, RESET

# Autosave interval in seconds
AUTOSAVE_INTERVAL = 60

try:
    from src.services import firebase_client
except ImportError:
    firebase_client = None

try:
    from src.services import audio
    AUDIO_AVAILABLE = audio.is_audio_available()
except ImportError:
    audio = None
    AUDIO_AVAILABLE = False

GAME_VERSION = "2.0"

# Timing constants for new game loop
FIXED_FPS = 60  # Loop fisso a 60 FPS
FIXED_FRAME_TIME = 1.0 / FIXED_FPS  # ~16.6ms
MAX_LEVEL = 30


def calculate_frames_per_update(speed_level):
    """
    Calcola quanti frame del loop fisso passano tra ogni update della fisica.
    Basato sul livello di velocità (1-10).

    Speed 1:  10 frames/update = 6 updates/sec (lento)
    Speed 10: 2 frames/update = 30 updates/sec (veloce ma giocabile)
    """
    min_speed = getattr(constants.speed, 'min_speed', 1)
    max_speed = getattr(constants.speed, 'max_speed', 10)

    # Normalizza speed tra 0 e 1
    t = (speed_level - min_speed) / (max_speed - min_speed) if max_speed > min_speed else 0
    t = max(0, min(1, t))

    # Mappa da max_frames (lento) a min_frames (veloce)
    max_frames = 10
    min_frames = 2
    frames = max_frames - t * (max_frames - min_frames)
    return max(min_frames, round(frames))


def show_game_over_screen():
    """Display the game over screen with final stats, name input, and menu.

    Uses the same framebuffer system as the game for consistent rendering.

    Returns:
        'retry' to play again, 'exit' to quit
    """
    from src.ui.render import TOTAL_WIDTH, SIDE_PANEL_WIDTH, GAME_X_OFFSET
    import sys

    # Get the existing framebuffer (same one used by the game)
    fb = render.get_framebuffer()

    # CRITICAL: Force full redraw by clearing BOTH buffers
    fb.first_frame = True
    for y in range(fb.height):
        for x in range(fb.width):
            fb.current[y][x] = (' ', '')
            fb.previous[y][x] = ('\x00', '')  # Different char forces redraw

    # Colors
    PANEL_BORDER = "\033[38;5;238m"
    PANEL_BG = "\033[38;5;233m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"

    # Get config values
    time_divider = getattr(constants.game_over, 'time_divider', 3600)
    time_remainder = getattr(constants.game_over, 'time_remainder', 3600)
    minutes_divider = getattr(constants.game_over, 'minutes_divider', 60)
    name_max_length = getattr(constants.game_over, 'leaderboard_name_max_length', 20)

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

    # Calculate avg points per minute for Firebase
    minutes_played = float(elapsed) / float(minutes_divider) if elapsed > 0 else 0.0
    avg_ppm = float(state.game.score) / minutes_played if minutes_played > 0 else float(state.game.score)

    def draw_game_over(selected, player_name="", phase="menu"):
        """Draw game over screen to framebuffer.

        phase: 'name' for name input, 'menu' for retry/exit menu
        """
        fb.clear()

        # Header row 0: GAME OVER centered
        header = "GAME OVER"
        hpad = (TOTAL_WIDTH - len(header)) // 2
        for i, ch in enumerate(header):
            fb.put(hpad + i, 0, ch)

        # Row 1: separator
        for x in range(TOTAL_WIDTH):
            fb.put(x, 1, '=')

        # Side panels for rows 2 to height+1
        for y in range(2, constants.layout.height + 2):
            # Left panel
            fb.put(0, y, '|', PANEL_BORDER)
            for x in range(1, SIDE_PANEL_WIDTH - 1):
                if (x + y) % 4 == 0:
                    fb.put(x, y, '.', PANEL_BG)
            fb.put(SIDE_PANEL_WIDTH - 1, y, '|', PANEL_BORDER)
            # Right panel
            right_start = GAME_X_OFFSET + constants.layout.width
            fb.put(right_start, y, '|', PANEL_BORDER)
            for x in range(1, SIDE_PANEL_WIDTH - 1):
                if (x + y) % 4 == 0:
                    fb.put(right_start + x, y, '.', PANEL_BG)
            fb.put(right_start + SIDE_PANEL_WIDTH - 1, y, '|', PANEL_BORDER)

        # Content - vertically centered
        center_y = constants.layout.height // 2 + 2
        game_center_x = GAME_X_OFFSET + constants.layout.width // 2

        # GAME OVER box
        box_lines = [
            "##############################",
            "#        GAME  OVER          #",
            "##############################",
        ]
        for i, line in enumerate(box_lines):
            y = center_y - 6 + i
            x = game_center_x - len(line) // 2
            fb.put_string(x, y, line, RED)

        # Stats
        stats = [
            f"Final Score:    {int(state.game.score):,}",
            f"Level Reached:  {state.game.level}",
            f"Time Played:    {elapsed_str}",
        ]
        for i, line in enumerate(stats):
            y = center_y - 2 + i
            x = game_center_x - len(line) // 2
            fb.put_string(x, y, line)

        if phase == "name":
            # Name input prompt
            prompt = "Enter name for leaderboard:"
            name_y = center_y + 3
            fb.put_string(game_center_x - len(prompt) // 2, name_y, prompt, YELLOW)

            # Name input field with cursor
            field = f"[ {player_name}_" + " " * (name_max_length - len(player_name)) + " ]"
            fb.put_string(game_center_x - len(field) // 2, name_y + 1, field, GREEN)

            # Instructions
            instr = "(ENTER to confirm, ESC to skip)"
            fb.put_string(game_center_x - len(instr) // 2, name_y + 3, instr)
        else:
            # Menu
            menu_y = center_y + 3
            if selected == 0:
                retry_text = "> [ RETRY ] <"
                exit_text = "    EXIT"
                fb.put_string(game_center_x - len(retry_text) // 2, menu_y, retry_text, GREEN)
                fb.put_string(game_center_x - len(exit_text) // 2, menu_y + 1, exit_text)
            else:
                retry_text = "    RETRY"
                exit_text = "> [  EXIT ] <"
                fb.put_string(game_center_x - len(retry_text) // 2, menu_y, retry_text)
                fb.put_string(game_center_x - len(exit_text) // 2, menu_y + 1, exit_text, GREEN)

        # Floor separator
        floor_y = constants.layout.height + 2
        for x in range(TOTAL_WIDTH):
            fb.put(x, floor_y, '=')

        # Footer
        if phase == "name":
            footer = "Type your name | ENTER confirm | ESC skip"
        else:
            footer = "UP/DOWN select | SPACE confirm"
        fpad = (TOTAL_WIDTH - len(footer)) // 2
        fb.put_string(fpad, floor_y + 1, footer)

        # Render to screen
        output = fb.render()
        try:
            sys.stdout.write(output)
            sys.stdout.flush()
        except BlockingIOError:
            pass

    # Phase 1: Name input
    player_name = ""
    name_done = False

    while not name_done:
        # Always render every frame (like the game does)
        draw_game_over(0, player_name, "name")

        key = render.get_key()
        if key == 'QUIT' or key == 'ESC':
            player_name = ""
            name_done = True
        elif key == 'ENTER':
            name_done = True
        elif key == 'BACKSPACE':
            if player_name:
                player_name = player_name[:-1]
        elif key == 'SPACE':
            if len(player_name) < name_max_length:
                player_name += " "
        elif isinstance(key, str) and len(key) == 1 and key.isprintable():
            if len(player_name) < name_max_length:
                player_name += key

        time.sleep(0.016)

    # Phase 2: Menu selection
    selected = 0
    menu_done = False

    while not menu_done:
        # Always render every frame
        draw_game_over(selected, player_name, "menu")

        key = render.get_key()
        if key == 'UP':
            selected = 0
        elif key == 'DOWN':
            selected = 1
        elif key == 'ENTER' or key == 'SPACE':
            menu_done = True
        elif key == 'QUIT' or key == 'ESC':
            selected = 1
            menu_done = True

        time.sleep(0.016)

    # Submit stats to Firebase
    if firebase_client:
        try:
            if player_name.strip():
                functions.background_call(
                    firebase_client.send_score,
                    player_name.strip(),
                    int(state.game.score),
                    elapsed,
                    elapsed_str,
                    GAME_VERSION,
                    avg_ppm
                )
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

    return 'retry' if selected == 0 else 'exit'


def run_game():
    """
    Run a single game session.

    Returns:
        'retry' if player wants to play again, 'exit' to quit, 'quit' if user pressed Ctrl+C
    """
    # Show title screen first
    state.ui.show_title = True
    state.ui.title_menu_index = 0
    state.ui.settings_menu = None

    # Title screen loop
    try:
        while state.ui.show_title and not state.game.quit_requested:
            frame_start = time.time()

            key = render.get_key()
            input_handler.process_input(key)

            render.render_title_screen()

            elapsed = time.time() - frame_start
            sleep_time = FIXED_FRAME_TIME - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # If user quit from title screen
        if state.game.quit_requested:
            return 'exit'

    except KeyboardInterrupt:
        return 'exit'

    # Game state should already be initialized by title menu handler
    # (either from NEW GAME, CONTINUE, or LOAD)
    achievements.init_achievements()
    state.game.start_time = time.time()
    state.game.last_mile_update = time.time()

    # Start background music with correct level and bird composition
    if AUDIO_AVAILABLE and audio:
        # Stop any existing music first
        audio.stop_music()
        # Sync speed/gear for correct music theme (theme changes with speed, not level milestone)
        audio.update_music_for_level(state.game.speed)
        # Sync game speed for correct tempo
        audio.update_game_speed(state.game.speed)
        # Sync active birds BEFORE starting music (force=True to bypass rate limiter)
        game_logic.sync_active_birds_audio(force=True)
        # Now start fresh music with correct state
        audio.start_music()

    # Contatore frame per decidere quando aggiornare la fisica
    render_frame = 0
    last_autosave = time.time()

    try:
        while not state.game.game_over:
            frame_start = time.time()

            # === INPUT (sempre, ogni frame) ===
            key = render.get_key()
            input_handler.process_input(key)

            # Se in pausa, solo render e aspetta (but don't accumulate miles)
            if state.game.paused:
                state.game.last_mile_update = time.time()  # Reset timer
                render.render_game()
                elapsed = time.time() - frame_start
                sleep_time = FIXED_FRAME_TIME - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                continue

            # === UPDATE MILES (based on real time and current speed) ===
            current_time = time.time()
            if state.game.last_mile_update is not None:
                delta_time = current_time - state.game.last_mile_update
                level_changed = functions.update_miles(delta_time)
                if level_changed:
                    # Play level up sound when reaching a new level milestone
                    if AUDIO_AVAILABLE and audio:
                        audio.play_sfx('level_up')
            state.game.last_mile_update = current_time

            # === PHYSICS/LOGIC UPDATE (ogni N frame basato sulla velocità) ===
            frames_per_update = calculate_frames_per_update(state.game.speed)

            if render_frame % frames_per_update == 0:
                # Update physics (movement)
                physics.update_all()

                # Update game logic (collisions, spawning, powerups)
                game_logic.update_all()

                # Increment game frame counter (usato per spawn timing, etc.)
                state.game.frame_count += 1

            # === AUTOSAVE (ogni 60 secondi) ===
            if time.time() - last_autosave >= AUTOSAVE_INTERVAL:
                save_manager.save_game(0)  # Slot 0 = autosave
                last_autosave = time.time()

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

    # Stop music but keep mixer running for game over sound
    if AUDIO_AVAILABLE and audio:
        audio.stop_music()
        # Play game over sound if it's a real game over
        if state.game.game_over and not state.game.quit_requested:
            audio.play_sfx('game_over')
            time.sleep(1.5)  # Wait for game over sound to finish

    # Return action based on game state
    if state.game.quit_requested:
        return 'quit'

    # Show game over screen and get user choice
    return show_game_over_screen()


def main():
    """
    Main entry point with retry support.

    Il loop gira a ~60 FPS fissi per input fluido.
    La fisica/logica viene aggiornata ogni N frame, dove N dipende dal livello.
    Questo permette input sempre reattivo mentre il gioco accelera.
    """
    # Initialize terminal once
    functions.setup()

    try:
        while True:
            result = run_game()

            if result == 'retry':
                # Reset framebuffer for new game
                render._framebuffer = None
                continue
            else:
                # Exit or quit
                break

    finally:
        # Cleanup audio and terminal
        if AUDIO_AVAILABLE and audio:
            audio.cleanup()
        functions.cleanup()


if __name__ == '__main__':
    main()
