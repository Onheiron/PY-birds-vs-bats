"""Input dispatcher: routes each key to menus or gameplay actions."""

from src.core import state
from src.engine.actions import (
    handle_audio_toggle,
    handle_bounce,
    handle_movement,
    handle_pause,
    handle_suction,
    handle_swap,
    handle_xp_toggle,
)
from src.engine.menus import (
    _execute_pause_menu_action,
    _get_settings_options_count,
    _handle_settings_back,
    _handle_settings_enter,
    _handle_settings_left_right,
    _handle_title_input,
)


def process_input(key):
    """Process a single key input and update game state."""
    if key is None:
        return

    # Handle title screen input first
    if _handle_title_input(key):
        return

    # Get the swap key binding
    swap_key = state.settings.key_bindings.get('SWAP', 'SPACE')
    key_upper = key.upper() if isinstance(key, str) and len(key) == 1 else key

    # Detect swap key press (edge detection for any bound key)
    swap_pressed = key_upper == swap_key
    swap_just_pressed = swap_pressed and not state.player.last_space_state
    state.player.last_space_state = swap_pressed

    # When paused, handle pause menu navigation
    if state.game.paused:
        # Check if we're in settings submenu
        if state.ui.settings_menu is not None:
            # Check if we're in rebinding mode
            if state.ui.rebinding_control is not None:
                if key == 'QUIT':
                    state.game.quit_requested = True
                    state.game.game_over = True
                elif key == 'ESC':
                    # Cancel rebinding
                    state.ui.rebinding_control = None
                else:
                    # Accept any valid key for rebinding
                    valid_keys = [
                        'LEFT',
                        'RIGHT',
                        'UP',
                        'DOWN',
                        'SPACE',
                        'ENTER',
                        'A',
                        'B',
                        'C',
                        'D',
                        'E',
                        'F',
                        'G',
                        'H',
                        'I',
                        'J',
                        'K',
                        'L',
                        'M',
                        'N',
                        'O',
                        'P',
                        'Q',
                        'R',
                        'S',
                        'T',
                        'U',
                        'V',
                        'W',
                        'X',
                        'Y',
                        'Z',
                        'a',
                        'b',
                        'c',
                        'd',
                        'e',
                        'f',
                        'g',
                        'h',
                        'i',
                        'j',
                        'k',
                        'l',
                        'm',
                        'n',
                        'o',
                        'p',
                        'q',
                        'r',
                        's',
                        't',
                        'u',
                        'v',
                        'w',
                        'x',
                        'y',
                        'z',
                        '0',
                        '1',
                        '2',
                        '3',
                        '4',
                        '5',
                        '6',
                        '7',
                        '8',
                        '9',
                    ]
                    if key in valid_keys:
                        # Assign the new key
                        state.settings.key_bindings[state.ui.rebinding_control] = key.upper() if len(key) == 1 else key
                        state.ui.rebinding_control = None
                return

            if key == 'QUIT':
                state.game.quit_requested = True
                state.game.game_over = True
            elif key == 'ESC':
                _handle_settings_back()
            elif key == 'UP':
                count = _get_settings_options_count()
                state.ui.settings_index = (state.ui.settings_index - 1) % count
            elif key == 'DOWN':
                count = _get_settings_options_count()
                state.ui.settings_index = (state.ui.settings_index + 1) % count
            elif key in ('LEFT', 'RIGHT'):
                _handle_settings_left_right(key)
            elif key == 'ENTER':
                _handle_settings_enter()
            return

        # Regular pause menu navigation
        if key in ('P', 'p', 'ESC'):
            handle_pause()  # Unpause
        elif key == 'QUIT':
            state.game.quit_requested = True
            state.game.game_over = True
        elif key == 'UP':
            # Navigate menu up
            state.ui.pause_menu_index = (state.ui.pause_menu_index - 1) % 7
        elif key == 'DOWN':
            # Navigate menu down
            state.ui.pause_menu_index = (state.ui.pause_menu_index + 1) % 7
        elif key == 'ENTER':
            # Execute selected menu action
            _execute_pause_menu_action()
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
    elif key_upper == bindings.get('SUCTION'):
        handle_suction()
    elif key == 'QUIT':
        state.game.quit_requested = True
        state.game.game_over = True
