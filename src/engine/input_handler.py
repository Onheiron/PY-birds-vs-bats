"""Input dispatcher: routes each key to menus or gameplay actions."""

from src.core import state
from src.engine import choices, menus
from src.engine.actions import (
    handle_audio_toggle,
    handle_bounce,
    handle_movement,
    handle_pause,
    handle_swap,
    handle_xp_toggle,
)


def process_input(key):
    """Process a single key input and update game state."""
    if key is None:
        return

    # On the title screen every key belongs to the menu
    if state.ui.show_title:
        menus.handle_key(key)
        return

    # Get the swap key binding
    swap_key = state.settings.key_bindings.get('SWAP', 'SPACE')
    key_upper = key.upper() if isinstance(key, str) and len(key) == 1 else key

    # Detect swap key press (edge detection for any bound key)
    swap_pressed = key_upper == swap_key
    swap_just_pressed = swap_pressed and not state.player.last_space_state
    state.player.last_space_state = swap_pressed

    # While paused every key belongs to the pause menu
    if state.game.paused:
        menus.ensure_pause_root()
        menus.handle_key(key)
        return

    # While a choice is on screen (egg cards, pacts) keys pick an option; P still pauses
    if state.choice.active is not None:
        if key in ('P', 'p'):
            handle_pause()
        elif key == 'QUIT':
            state.game.quit_requested = True
            state.game.game_over = True
        else:
            choices.handle_key(key)
        return

    # Get key bindings
    bindings = state.settings.key_bindings

    # Handle keys using configurable bindings
    if swap_just_pressed:
        handle_swap()
    elif key in ('P', 'p'):
        handle_pause()
    elif key_upper == bindings.get('MOVE_LEFT'):
        handle_movement('LEFT')
    elif key_upper == bindings.get('MOVE_RIGHT'):
        handle_movement('RIGHT')
    elif key in ('X', 'x'):
        handle_xp_toggle()
    elif key in ('M', 'm'):
        handle_audio_toggle()
    elif key_upper == bindings.get('BOUNCE'):
        handle_bounce()
    elif key == 'QUIT':
        state.game.quit_requested = True
        state.game.game_over = True
