"""Game loops: title screen and play session.

The loop renders at a fixed 60 FPS so input stays responsive, while physics
and game logic advance every N frames, N shrinking as the gear goes up.
"""

import copy
import time

from src.core import state
from src.engine import clock, events, input_handler, menus, meta, progression, recorder, systems
from src.engine.timing import FrameClock, frames_per_update
from src.entities.bird_types import get_bird_type_by_color
from src.services import save_manager, sound
from src.ui import game_over, render
from src.ui.keyboard import read_keys
from src.ui.layers.title import render_title_screen

# Seconds between automatic saves to slot 0
AUTOSAVE_INTERVAL = 60

# Side effects that react to game events
sound.subscribe()
meta.subscribe()


class Session:
    """Advances the simulation of one play session, frame by frame."""

    def __init__(self):
        self.frame = 0

    def step(self):
        """Advance one render frame: miles always, physics/logic every N frames."""
        game = state.game
        now = time.time()
        sound.follow_pause(game.paused)  # the music holds while paused

        if game.paused or state.choice.active is not None:
            # Neither miles nor game time advance while paused or choosing a card
            if game.last_mile_update is not None:
                clock.hold(now - game.last_mile_update)
            game.last_mile_update = now
            return

        # Miles depend on real time and current gear
        if game.last_mile_update is not None:
            if progression.update_miles(now - game.last_mile_update):
                events.emit('level_up', level=game.level)
        game.last_mile_update = now

        if self.frame % frames_per_update(game.speed) == 0:
            systems.run_tick()
            game.frame_count += 1  # game-time counter (spawn timing, effects)

        self.frame += 1


def _discover_current_birds():
    """Record every bird type of the starting flock in the Birdpedia."""
    for color in state.birds.colors:
        bird_type = get_bird_type_by_color(color)
        if bird_type:
            save_manager.discover_bird(bird_type)


def run_title_screen():
    """Show the title screen until a game starts. Returns False if the user quit."""
    state.ui.show_title = True
    menus.open_title()

    clock = FrameClock()
    try:
        while state.ui.show_title and not state.game.quit_requested:
            for key in read_keys():
                input_handler.process_input(key)
            render_title_screen()
            clock.wait()
    except KeyboardInterrupt:
        return False
    return not state.game.quit_requested


def run_session():
    """Play until game over, quit or return to the title screen."""
    # Game state was initialised by the title menu (NEW GAME, CONTINUE or LOAD)
    if state.meta.profile is None:
        state.meta.profile = save_manager.load_profile()
    init_time = state.game.start_time  # when state.init dealt the flock
    profile = copy.deepcopy(state.meta.profile)
    meta.start_run()

    # One instant per frame (see src/engine/recorder.py): what makes a replay exact
    real_time = time.time
    frame_time = recorder.FrameTime(real_time)
    time.time = frame_time
    state.game.start_time = state.game.last_mile_update = frame_time.tick()
    record = recorder.Recorder(init_time, state.game.start_time, profile)

    save_manager.load_discovery()
    _discover_current_birds()
    sound.start_session_music()

    session = Session()
    clock = FrameClock()
    last_autosave = time.time()

    try:
        while not state.game.game_over:
            held = state.game.paused or state.choice.active is not None
            now = frame_time.tick(held)
            keys = read_keys()
            record.frame(now, keys, held)
            for key in keys:
                input_handler.process_input(key)

            session.step()

            if not state.game.paused and time.time() - last_autosave >= AUTOSAVE_INTERVAL:
                save_manager.save_game(0)  # Slot 0 = autosave
                last_autosave = time.time()

            render.render_game()
            clock.wait()
    except KeyboardInterrupt:
        # Ctrl+C is a deliberate exit
        state.game.quit_requested = True
    finally:
        time.time = real_time
        if not (state.game.lives <= 0):
            # Quit or back to the title: keep the game for CONTINUE
            was_title = state.ui.show_title
            state.ui.show_title = False
            save_manager.checkpoint()
            state.ui.show_title = was_title
        # Game over, quit or back to the title: the run's gold goes to the profile
        meta.end_run()
        state.ui.last_recording = record.save()


def run_game():
    """Run one full cycle: title screen, session, game over screen.

    Returns 'retry' to start over from the title screen, 'exit' or 'quit' to stop.
    """
    if not run_title_screen():
        return 'exit'

    run_session()

    # Stop the music but keep the mixer running for the game over jingle
    sound.stop_music()
    real_game_over = state.game.game_over and not state.game.quit_requested and not state.ui.show_title
    if real_game_over and sound.get_audio() is not None and state.settings.sfx_enabled:
        sound.play_sfx('game_over')
        time.sleep(1.5)  # Let the jingle finish

    if state.game.quit_requested:
        return 'quit'
    if state.ui.show_title:
        # Returning to the main menu
        return 'retry'
    return game_over.show()
