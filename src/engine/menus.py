"""Pause, settings and title menu navigation."""

from src.core import constants, state
from src.core import state as game_state
from src.engine.actions import handle_pause
from src.engine.notifications import _add_notification
from src.services import save_manager
from src.services.sound import apply_music_setting


def _execute_pause_menu_action():
    """Execute the currently selected pause menu action."""

    selected = state.ui.pause_menu_index

    if selected == 0:
        # RESUME - unpause the game
        handle_pause()
    elif selected == 1:
        # RESTART - restart game
        _handle_restart()
    elif selected == 2:
        # SAVE - open save menu
        state.ui.settings_menu = 'save'
        state.ui.settings_index = 0
    elif selected == 3:
        # LOAD - open load menu
        state.ui.settings_menu = 'load'
        state.ui.settings_index = 0
    elif selected == 4:
        # BIRDPEDIA - open birdpedia menu
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 0
    elif selected == 5:
        # SETTINGS - enter settings menu
        state.ui.settings_menu = 'main'
        state.ui.settings_index = 0
    elif selected == 6:
        # MAIN MENU - return to title screen
        state.game.paused = False
        state.ui.pause_menu_index = 0
        state.ui.settings_menu = None
        state.ui.show_title = True
        state.ui.title_menu_index = 0
        state.game.game_over = True  # End current game loop to return to title


def _handle_restart():
    """Restart the game from the beginning."""

    # Re-initialize game state
    game_state.init()

    # Unpause
    state.game.paused = False
    state.ui.pause_menu_index = 0

    _add_notification("New game!", title="Restart:")


def _get_settings_options_count():
    """Return the number of options in the current settings submenu."""
    menu = state.ui.settings_menu
    if menu == 'main':
        return 5  # SOUND, GRAPHICS, CONTROLS, DIFFICULTY, < BACK
    if menu == 'sound':
        return 3  # SFX, MUSIC, < BACK
    if menu == 'graphics':
        return 4  # BACKGROUND, PARALLAX, ACCESSIBILITY, < BACK
    if menu == 'controls':
        return 6  # 5 control display items + < BACK
    if menu == 'save':
        return 4  # SLOT 1, SLOT 2, SLOT 3, < BACK
    if menu == 'load':
        return 5  # AUTO, SLOT 1, SLOT 2, SLOT 3, < BACK
    if menu == 'birdpedia':
        return 5  # GUIDE, BIRDPEDIA, BATPEDIA, BIOMES, < BACK
    if menu == 'guide':
        return 5  # HOW TO PLAY, COMMANDS, OBSTACLES, ENEMIES, < BACK
    if menu in (
        'guide_howto',
        'guide_commands',
        'guide_obstacles',
        'guide_enemies',
        'birdpedia_list',
        'batpedia_list',
        'biomes_list',
    ):
        return 1  # Just < BACK (content view)
    return 1


def _handle_settings_enter():
    """Handle ENTER key in settings menu."""
    menu = state.ui.settings_menu
    idx = state.ui.settings_index

    if menu == 'main':
        if idx == 0:  # SOUND
            state.ui.settings_menu = 'sound'
            state.ui.settings_index = 0
        elif idx == 1:  # GRAPHICS
            state.ui.settings_menu = 'graphics'
            state.ui.settings_index = 0
        elif idx == 2:  # CONTROLS
            state.ui.settings_menu = 'controls'
            state.ui.settings_index = 0
        elif idx == 3:  # DIFFICULTY - cycle on enter too
            _cycle_difficulty(1)
        elif idx == 4:  # < BACK
            state.ui.settings_menu = None
            state.ui.settings_index = 0
    elif menu == 'sound':
        if idx == 0:  # SFX toggle
            state.settings.sfx_enabled = not state.settings.sfx_enabled
        elif idx == 1:  # MUSIC toggle
            state.settings.music_enabled = not state.settings.music_enabled
            apply_music_setting()
        elif idx == 2:  # < BACK
            state.ui.settings_menu = 'main'
            state.ui.settings_index = 0
    elif menu == 'graphics':
        if idx == 0:  # BACKGROUND toggle
            state.settings.background_enabled = not state.settings.background_enabled
        elif idx == 1:  # PARALLAX toggle
            state.settings.parallax_enabled = not state.settings.parallax_enabled
        elif idx == 2:  # ACCESSIBILITY toggle
            _toggle_accessibility()
        elif idx == 3:  # < BACK
            state.ui.settings_menu = 'main'
            state.ui.settings_index = 1
    elif menu == 'controls':
        count = _get_settings_options_count()
        if idx == count - 1:  # < BACK
            state.ui.settings_menu = 'main'
            state.ui.settings_index = 2
        elif idx < count - 1:  # Rebindable control
            # Start rebinding mode
            control_names = ['MOVE_LEFT', 'MOVE_RIGHT', 'BOUNCE', 'SUCTION', 'SWAP']
            if idx < len(control_names):
                state.ui.rebinding_control = control_names[idx]
    elif menu == 'save':
        if idx == 3:  # < BACK
            state.ui.settings_menu = None
            state.ui.settings_index = 0
        elif idx < 3:  # Slot 1-3
            slot = idx + 1

            if save_manager.save_game(slot):
                _add_notification(f"Saved to Slot {slot}", title="Save:")
                state.ui.settings_menu = None
                state.ui.settings_index = 0
            else:
                _add_notification("Save failed!", title="Error:")
    elif menu == 'load':
        if idx == 4:  # < BACK
            state.ui.settings_menu = None
            state.ui.settings_index = 0
        elif idx <= 3:  # Slot 0 (auto), 1, 2, 3
            slot = idx  # idx 0 = autosave, idx 1-3 = slots 1-3

            slots = save_manager.list_save_slots()
            if slots.get(slot, {}).get('exists'):
                if save_manager.load_game(slot):
                    slot_name = "Autosave" if slot == 0 else f"Slot {slot}"
                    _add_notification(f"Loaded {slot_name}", title="Load:")
                    state.ui.settings_menu = None
                    state.ui.settings_index = 0
                    state.game.paused = False
                else:
                    _add_notification("Load failed!", title="Error:")
            else:
                _add_notification("Slot is empty!", title="Error:")
    elif menu == 'birdpedia':
        if idx == 0:  # GUIDE
            state.ui.settings_menu = 'guide'
            state.ui.settings_index = 0
        elif idx == 1:  # BIRDPEDIA
            state.ui.settings_menu = 'birdpedia_list'
            state.ui.settings_index = 0
        elif idx == 2:  # BATPEDIA
            state.ui.settings_menu = 'batpedia_list'
            state.ui.settings_index = 0
        elif idx == 3:  # BIOMES
            state.ui.settings_menu = 'biomes_list'
            state.ui.settings_index = 0
        elif idx == 4:  # < BACK
            state.ui.settings_menu = None
            state.ui.settings_index = 0
    elif menu == 'guide':
        if idx == 0:  # HOW TO PLAY
            state.ui.settings_menu = 'guide_howto'
            state.ui.settings_index = 0
        elif idx == 1:  # COMMANDS
            state.ui.settings_menu = 'guide_commands'
            state.ui.settings_index = 0
        elif idx == 2:  # OBSTACLES
            state.ui.settings_menu = 'guide_obstacles'
            state.ui.settings_index = 0
        elif idx == 3:  # ENEMIES
            state.ui.settings_menu = 'guide_enemies'
            state.ui.settings_index = 0
        elif idx == 4:  # < BACK
            state.ui.settings_menu = 'birdpedia'
            state.ui.settings_index = 0
    elif menu in (
        'guide_howto',
        'guide_commands',
        'guide_obstacles',
        'guide_enemies',
        'birdpedia_list',
        'batpedia_list',
        'biomes_list',
    ):
        # Content views - any key goes back
        _handle_settings_back()


def _handle_settings_back():
    """Handle ESC or < BACK in settings menu."""
    menu = state.ui.settings_menu

    if menu == 'main':
        state.ui.settings_menu = None
        state.ui.settings_index = 0
    elif menu in ('sound', 'graphics', 'controls'):
        state.ui.settings_menu = 'main'
        # Return to appropriate index in main menu
        if menu == 'sound':
            state.ui.settings_index = 0
        elif menu == 'graphics':
            state.ui.settings_index = 1
        else:  # controls
            state.ui.settings_index = 2
    elif menu in ('save', 'load') or menu == 'birdpedia':
        # Return directly to pause menu
        state.ui.settings_menu = None
        state.ui.settings_index = 0
    elif menu == 'guide':
        # Return to birdpedia menu
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 0
    elif menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies'):
        # Return to guide menu
        state.ui.settings_menu = 'guide'
        state.ui.settings_index = 0
    elif menu == 'birdpedia_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 1
    elif menu == 'batpedia_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 2
    elif menu == 'biomes_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 3


def _handle_settings_left_right(direction):
    """Handle LEFT/RIGHT for cycling values in settings."""
    menu = state.ui.settings_menu
    idx = state.ui.settings_index
    delta = -1 if direction == 'LEFT' else 1

    if menu == 'main' and idx == 3:  # DIFFICULTY
        _cycle_difficulty(delta)
    elif menu == 'sound':
        if idx == 0:  # SFX
            state.settings.sfx_enabled = not state.settings.sfx_enabled
        elif idx == 1:  # MUSIC
            state.settings.music_enabled = not state.settings.music_enabled
            apply_music_setting()
    elif menu == 'graphics':
        if idx == 0:  # BACKGROUND
            state.settings.background_enabled = not state.settings.background_enabled
        elif idx == 1:  # PARALLAX
            state.settings.parallax_enabled = not state.settings.parallax_enabled
        elif idx == 2:  # ACCESSIBILITY
            _toggle_accessibility()


def _toggle_accessibility():
    """Toggle accessibility mode and apply related settings."""
    state.settings.accessibility_enabled = not state.settings.accessibility_enabled

    if state.settings.accessibility_enabled:
        # Disable background and parallax for clarity
        state.settings.background_enabled = False
        state.settings.parallax_enabled = False


def _cycle_difficulty(delta):
    """Cycle difficulty setting."""
    state.settings.difficulty = (state.settings.difficulty + delta) % 4


def _handle_title_input(key):
    """Handle input on title screen. Returns True if handled."""
    if not state.ui.show_title:
        return False

    if key == 'QUIT':
        state.game.quit_requested = True
        state.game.game_over = True
        return True

    # If in load submenu on title screen
    if state.ui.settings_menu == 'load':
        if key == 'UP':
            state.ui.settings_index = (state.ui.settings_index - 1) % 5  # 4 slots + back
            return True
        if key == 'DOWN':
            state.ui.settings_index = (state.ui.settings_index + 1) % 5
            return True
        if key == 'ESC':
            state.ui.settings_menu = None
            return True
        if key == 'ENTER':
            idx = state.ui.settings_index
            if idx == 4:  # BACK
                state.ui.settings_menu = None
            else:
                # Load slot idx (0=autosave, 1-3=manual)

                if save_manager.load_game(idx):
                    state.ui.show_title = False
                    state.ui.settings_menu = None
            return True
        return True

    # If in settings submenu on title screen
    if state.ui.settings_menu is not None:
        return _handle_title_settings_input(key)

    if key == 'UP':
        state.ui.title_menu_index = (state.ui.title_menu_index - 1) % 6  # 6 options now
        return True

    if key == 'DOWN':
        state.ui.title_menu_index = (state.ui.title_menu_index + 1) % 6
        return True

    # LEFT/RIGHT on NEW GAME changes difficulty
    if key in ('LEFT', 'RIGHT') and state.ui.title_menu_index == 1:
        delta = 1 if key == 'RIGHT' else -1
        state.settings.difficulty = (state.settings.difficulty + delta) % 4
        return True

    if key == 'ENTER':
        idx = state.ui.title_menu_index
        if idx == 0:  # CONTINUE
            # Try to load the most recent save (by timestamp)

            most_recent = save_manager.get_most_recent_save()
            if most_recent is not None and save_manager.load_game(most_recent):
                state.ui.show_title = False
            else:
                # No saves, start new game with default settings

                state.init()
                save_manager.load_default_settings()
                state.ui.show_title = False
        elif idx == 1:  # NEW GAME
            # Save the difficulty selection before init (which doesn't reset settings)
            selected_difficulty = state.settings.difficulty
            # Load difficulty-specific configuration
            constants.reload_for_difficulty(selected_difficulty)
            state.init()
            save_manager.load_default_settings()
            # Restore the difficulty we selected on title screen
            state.settings.difficulty = selected_difficulty
            state.ui.show_title = False
        elif idx == 2:  # LOAD
            state.ui.settings_menu = 'load'
            state.ui.settings_index = 0
        elif idx == 3:  # BIRDPEDIA
            state.ui.settings_menu = 'birdpedia'
            state.ui.settings_index = 0
        elif idx == 4:  # SETTINGS
            state.ui.settings_menu = 'main'
            state.ui.settings_index = 0
        elif idx == 5:  # QUIT
            state.game.quit_requested = True
            state.game.game_over = True
        return True

    return False


def _handle_title_settings_input(key):
    """Handle settings menu input on title screen. Returns True if handled."""

    # Rebinding mode
    if state.ui.rebinding_control is not None:
        if key == 'ESC':
            state.ui.rebinding_control = None
        else:
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
                state.settings.key_bindings[state.ui.rebinding_control] = key.upper() if len(key) == 1 else key
                state.ui.rebinding_control = None
                # Save default settings
                save_manager.save_default_settings()
        return True

    if key == 'ESC':
        _handle_title_settings_back()
        return True

    if key == 'UP':
        count = _get_settings_options_count()
        state.ui.settings_index = (state.ui.settings_index - 1) % count
        return True

    if key == 'DOWN':
        count = _get_settings_options_count()
        state.ui.settings_index = (state.ui.settings_index + 1) % count
        return True

    if key in ('LEFT', 'RIGHT'):
        _handle_title_settings_left_right(key)
        return True

    if key == 'ENTER':
        _handle_title_settings_enter()
        return True

    return True


def _handle_title_settings_back():
    """Handle ESC or < BACK in title settings menu."""

    menu = state.ui.settings_menu

    if menu == 'main':
        state.ui.settings_menu = None
        state.ui.settings_index = 0
        # Save defaults when exiting settings
        save_manager.save_default_settings()
    elif menu in ('sound', 'graphics', 'controls'):
        state.ui.settings_menu = 'main'
        if menu == 'sound':
            state.ui.settings_index = 0
        elif menu == 'graphics':
            state.ui.settings_index = 1
        else:
            state.ui.settings_index = 2
    elif menu == 'birdpedia':
        state.ui.settings_menu = None
        state.ui.settings_index = 0
    elif menu == 'guide':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 0
    elif menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies'):
        state.ui.settings_menu = 'guide'
        state.ui.settings_index = 0
    elif menu == 'birdpedia_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 1
    elif menu == 'batpedia_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 2
    elif menu == 'biomes_list':
        state.ui.settings_menu = 'birdpedia'
        state.ui.settings_index = 3


def _handle_title_settings_left_right(key):
    """Handle LEFT/RIGHT in title settings menu."""

    menu = state.ui.settings_menu
    idx = state.ui.settings_index
    delta = 1 if key == 'RIGHT' else -1

    if menu == 'main' and idx == 3:  # DIFFICULTY
        state.settings.difficulty = (state.settings.difficulty + delta) % 4
        save_manager.save_default_settings()
    elif menu == 'sound':
        if idx == 0:  # SFX
            state.settings.sfx_enabled = not state.settings.sfx_enabled
            save_manager.save_default_settings()
        elif idx == 1:  # MUSIC
            state.settings.music_enabled = not state.settings.music_enabled
            save_manager.save_default_settings()
    elif menu == 'graphics':
        if idx == 0:  # BACKGROUND
            state.settings.background_enabled = not state.settings.background_enabled
            save_manager.save_default_settings()
        elif idx == 1:  # PARALLAX
            state.settings.parallax_enabled = not state.settings.parallax_enabled
            save_manager.save_default_settings()
        elif idx == 2:  # ACCESSIBILITY
            state.settings.accessibility_enabled = not state.settings.accessibility_enabled
            if state.settings.accessibility_enabled:
                state.settings.background_enabled = False
                state.settings.parallax_enabled = False
            save_manager.save_default_settings()


def _handle_title_settings_enter():
    """Handle ENTER in title settings menu."""

    menu = state.ui.settings_menu
    idx = state.ui.settings_index

    if menu == 'main':
        if idx == 0:  # SOUND
            state.ui.settings_menu = 'sound'
            state.ui.settings_index = 0
        elif idx == 1:  # GRAPHICS
            state.ui.settings_menu = 'graphics'
            state.ui.settings_index = 0
        elif idx == 2:  # CONTROLS
            state.ui.settings_menu = 'controls'
            state.ui.settings_index = 0
        elif idx == 3:  # DIFFICULTY (cycle)
            state.settings.difficulty = (state.settings.difficulty + 1) % 4
            save_manager.save_default_settings()
        elif idx == 4:  # < BACK
            _handle_title_settings_back()
    elif menu == 'sound':
        if idx == 0:  # SFX
            state.settings.sfx_enabled = not state.settings.sfx_enabled
            save_manager.save_default_settings()
        elif idx == 1:  # MUSIC
            state.settings.music_enabled = not state.settings.music_enabled
            save_manager.save_default_settings()
        elif idx == 2:  # < BACK
            _handle_title_settings_back()
    elif menu == 'graphics':
        if idx == 0:  # BACKGROUND
            state.settings.background_enabled = not state.settings.background_enabled
            save_manager.save_default_settings()
        elif idx == 1:  # PARALLAX
            state.settings.parallax_enabled = not state.settings.parallax_enabled
            save_manager.save_default_settings()
        elif idx == 2:  # ACCESSIBILITY
            state.settings.accessibility_enabled = not state.settings.accessibility_enabled
            if state.settings.accessibility_enabled:
                state.settings.background_enabled = False
                state.settings.parallax_enabled = False
            save_manager.save_default_settings()
        elif idx == 3:  # < BACK
            _handle_title_settings_back()
    elif menu == 'controls':
        if idx < 5:  # Rebind controls
            control_names = ['MOVE_LEFT', 'MOVE_RIGHT', 'BOUNCE', 'SUCTION', 'SWAP']
            state.ui.rebinding_control = control_names[idx]
        elif idx == 5:  # < BACK
            _handle_title_settings_back()
    elif menu == 'birdpedia':
        if idx == 0:  # GUIDE
            state.ui.settings_menu = 'guide'
            state.ui.settings_index = 0
        elif idx == 1:  # BIRDPEDIA
            state.ui.settings_menu = 'birdpedia_list'
            state.ui.settings_index = 0
        elif idx == 2:  # BATPEDIA
            state.ui.settings_menu = 'batpedia_list'
            state.ui.settings_index = 0
        elif idx == 3:  # BIOMES
            state.ui.settings_menu = 'biomes_list'
            state.ui.settings_index = 0
        elif idx == 4:  # < BACK
            _handle_title_settings_back()
    elif menu == 'guide':
        if idx == 0:  # HOW TO PLAY
            state.ui.settings_menu = 'guide_howto'
            state.ui.settings_index = 0
        elif idx == 1:  # COMMANDS
            state.ui.settings_menu = 'guide_commands'
            state.ui.settings_index = 0
        elif idx == 2:  # OBSTACLES
            state.ui.settings_menu = 'guide_obstacles'
            state.ui.settings_index = 0
        elif idx == 3:  # ENEMIES
            state.ui.settings_menu = 'guide_enemies'
            state.ui.settings_index = 0
        elif idx == 4:  # < BACK
            _handle_title_settings_back()
    elif menu in (
        'guide_howto',
        'guide_commands',
        'guide_obstacles',
        'guide_enemies',
        'birdpedia_list',
        'batpedia_list',
        'biomes_list',
    ):
        # Content views - any key goes back
        _handle_title_settings_back()
