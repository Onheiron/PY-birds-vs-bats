"""Menus: one declarative tree shared by the title screen and the pause menu.

Every screen is a ``Screen`` holding a list of ``Item``s. An item says what it
shows (a name, optionally a value) and what it does: open a submenu, go back,
run an action on ENTER, change a value with LEFT/RIGHT, or rebind a control.
The same tree drives both input (``handle_key``) and drawing
(``src.ui.layers.menus``), so adding an option is a single entry here.

Navigation is a stack kept in ``state.ui.menu_stack``: a list of
``[screen_id, cursor]`` pairs whose first entry is the root, ``'title'`` or
``'pause'``. Going back pops the stack, so the cursor comes back to the item
that opened the submenu.

The two roots share every submenu. They differ only where the context does:
settings changed on the title screen are saved as defaults straight away,
while in the pause menu they apply to the running game.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from src.core import constants, state
from src.engine.actions import handle_pause
from src.engine.notifications import notify
from src.services import save_manager
from src.services.sound import apply_music_setting

TITLE = 'title'
PAUSE = 'pause'

DIFFICULTY_NAMES = ('PEACEFUL', 'ADVENTURE', 'SURVIVAL', 'LEGENDARY')

# Controls that can be rebound, in the order the CONTROLS screen lists them
REBINDABLE_CONTROLS = (
    ('MOVE LEFT', 'MOVE_LEFT'),
    ('MOVE RIGHT', 'MOVE_RIGHT'),
    ('BOUNCE', 'BOUNCE'),
    ('SWAP', 'SWAP'),
)
_NAMED_KEYS = ('LEFT', 'RIGHT', 'UP', 'DOWN', 'SPACE', 'ENTER')
_KEY_SYMBOLS = {'LEFT': '←', 'RIGHT': '→', 'UP': '↑', 'DOWN': '↓', 'SPACE': 'SPC'}


@dataclass(frozen=True)
class Item:
    """One line of a menu.

    kind tells the view how to lay it out:
      'plain'   just the name
      'option'  name followed by "< value >" (toggles, cyclers)
      'binding' name followed by the key bound to a control
      'slot'    a save slot: name followed by its level and date, or "(empty)"
    """

    name: str
    kind: str = 'plain'
    value: Callable[[], object] | None = None
    opens: str | None = None  # submenu opened by ENTER
    back: bool = False  # ENTER goes back
    on_enter: Callable[[], None] | None = None
    on_change: Callable[[int], None] | None = None  # LEFT/RIGHT, delta -1/+1
    rebind: str | None = None  # control rebound by ENTER


@dataclass(frozen=True)
class Screen:
    """A menu screen. ``content`` names a text page instead of a list of items."""

    id: str
    title: str
    items: Callable[[], list] = field(default=list)
    hint: str = 'change'  # 'change', 'select' or 'controls'
    content: str | None = None


# =============================================================================
# CONTEXT
# =============================================================================


def root():
    """'title' or 'pause': which root the menu currently hangs from."""
    stack = state.ui.menu_stack
    return stack[0][0] if stack else None


def _settings_changed():
    """A setting changed: on the title screen it becomes the saved default."""
    if root() == TITLE:
        save_manager.save_default_settings()


# =============================================================================
# ACTIONS
# =============================================================================


def _quit():
    state.game.quit_requested = True
    state.game.game_over = True


def _toggle(name, after=None):
    def change(_delta=0):
        setattr(state.settings, name, not getattr(state.settings, name))
        if after:
            after()
        _settings_changed()

    return change


def _toggle_music_live():
    # Starting or stopping the music only makes sense during a game
    if root() == PAUSE:
        apply_music_setting()


def _accessibility_changed():
    if state.settings.accessibility_enabled:
        # High-contrast mode: drop the scenery behind the playfield
        state.settings.background_enabled = False
        state.settings.parallax_enabled = False


def _cycle_difficulty(delta=1):
    state.settings.difficulty = (state.settings.difficulty + delta) % len(DIFFICULTY_NAMES)
    _settings_changed()


def _difficulty_name():
    return DIFFICULTY_NAMES[state.settings.difficulty]


def _start_game(difficulty):
    """Fresh game state; the selected difficulty survives the reset."""
    state.init()
    save_manager.load_default_settings()
    state.settings.difficulty = difficulty
    state.ui.show_title = False


def _continue():
    """Load the most recent save, or start a new game when there is none."""
    most_recent = save_manager.get_most_recent_save()
    if most_recent is not None and save_manager.load_game(most_recent):
        state.ui.show_title = False
        return
    state.init()
    save_manager.load_default_settings()
    state.ui.show_title = False


def _new_game():
    selected = state.settings.difficulty
    constants.reload_for_difficulty(selected)
    _start_game(selected)


def _change_new_game_difficulty(delta):
    # Picking the difficulty for one game is not a settings change
    state.settings.difficulty = (state.settings.difficulty + delta) % len(DIFFICULTY_NAMES)


def _restart():
    state.init()
    state.game.paused = False
    state.ui.menu_stack = []
    notify("New game!", title="Restart:")


def _main_menu():
    state.game.paused = False
    state.ui.show_title = True
    state.ui.menu_stack = [[TITLE, 0]]
    state.game.game_over = True  # ends the session loop: back to the title screen


def _slot_info(slot):
    """(level text, date text) of a save slot, or None when it is empty."""
    info = save_manager.list_save_slots().get(slot, {})
    if not info.get('exists'):
        return None
    timestamp = info.get('timestamp', '')
    date = save_manager.format_timestamp_display(timestamp) if timestamp else '???'
    return info.get('level_display', '?'), date


def _save_to(slot):
    def save():
        if save_manager.save_game(slot):
            notify(f"Saved to Slot {slot}", title="Save:")
            close_submenus()
        else:
            notify("Save failed!", title="Error:")

    return save


def _load_from(slot):
    def load():
        if root() == TITLE:
            if save_manager.load_game(slot):
                state.ui.show_title = False
                close_submenus()
            return
        if _slot_info(slot) is None:
            notify("Slot is empty!", title="Error:")
        elif save_manager.load_game(slot):
            notify(f"Loaded {'Autosave' if slot == 0 else f'Slot {slot}'}", title="Load:")
            state.ui.menu_stack = [[PAUSE, 0]]
            state.game.paused = False
        else:
            notify("Load failed!", title="Error:")

    return load


def binding_display(control):
    """Text shown for a control's key (blinks while it is being rebound)."""
    if state.ui.rebinding_control == control:
        return "___" if (state.game.frame_count // 5) % 2 == 0 else "   "
    key = state.settings.key_bindings.get(control, '?')
    return _KEY_SYMBOLS.get(key, key)


def _rebind(key):
    """Assign ``key`` to the control waiting for one (ESC cancels)."""
    if key == 'ESC':
        state.ui.rebinding_control = None
        return
    if key in _NAMED_KEYS or (len(key) == 1 and key.isascii() and key.isalnum()):
        state.settings.key_bindings[state.ui.rebinding_control] = key.upper() if len(key) == 1 else key
        state.ui.rebinding_control = None
        _settings_changed()


# =============================================================================
# THE MENU TREE
# =============================================================================


def _back_item():
    return Item('< BACK', back=True)


def _title_items():
    return [
        Item('CONTINUE', on_enter=_continue),
        Item('NEW GAME', value=_difficulty_name, on_enter=_new_game, on_change=_change_new_game_difficulty),
        Item('LOAD', opens='load'),
        Item('BIRDPEDIA', opens='birdpedia'),
        Item('SETTINGS', opens='settings'),
        Item('QUIT', on_enter=_quit),
    ]


def _pause_items():
    return [
        Item('RESUME', on_enter=handle_pause),
        Item('RESTART', on_enter=_restart),
        Item('SAVE', opens='save'),
        Item('LOAD', opens='load'),
        Item('BIRDPEDIA', opens='birdpedia'),
        Item('SETTINGS', opens='settings'),
        Item('MAIN MENU', on_enter=_main_menu),
    ]


def _settings_items():
    return [
        Item('SOUND', opens='sound'),
        Item('GRAPHICS', opens='graphics'),
        Item('CONTROLS', opens='controls'),
        Item('DIFFICULTY', 'option', _difficulty_name, on_enter=_cycle_difficulty, on_change=_cycle_difficulty),
        _back_item(),
    ]


def _option(name, setting, after=None):
    toggle = _toggle(setting, after)
    return Item(
        name,
        'option',
        lambda: 'ON' if getattr(state.settings, setting) else 'OFF',
        on_enter=toggle,
        on_change=toggle,
    )


def _sound_items():
    return [
        _option('SFX', 'sfx_enabled'),
        _option('MUSIC', 'music_enabled', _toggle_music_live),
        _back_item(),
    ]


def _graphics_items():
    return [
        _option('BACKGROUND', 'background_enabled'),
        _option('PARALLAX', 'parallax_enabled'),
        _option('ACCESSIBILITY', 'accessibility_enabled', _accessibility_changed),
        _back_item(),
    ]


def _controls_items():
    items = [
        Item(name, 'binding', (lambda control=control: binding_display(control)), rebind=control)
        for name, control in REBINDABLE_CONTROLS
    ]
    return items + [_back_item()]


def _save_items():
    slots = [
        Item(f'SLOT {slot}', 'slot', (lambda s=slot: _slot_info(s)), on_enter=_save_to(slot)) for slot in (1, 2, 3)
    ]
    return slots + [_back_item()]


def _load_items():
    slots = [
        Item('AUTO' if slot == 0 else f'SLOT {slot}', 'slot', (lambda s=slot: _slot_info(s)), on_enter=_load_from(slot))
        for slot in (0, 1, 2, 3)
    ]
    return slots + [_back_item()]


def _birdpedia_items():
    return [
        Item('GUIDE', opens='guide'),
        Item('BIRD-DEX', opens='birdpedia_list'),
        Item('BAT-DEX', opens='batpedia_list'),
        Item('BIOMES', opens='biomes_list'),
        _back_item(),
    ]


def _guide_items():
    return [
        Item('HOW TO PLAY', opens='guide_howto'),
        Item('COMMANDS', opens='guide_commands'),
        Item('OBSTACLES', opens='guide_obstacles'),
        Item('ENEMIES', opens='guide_enemies'),
        _back_item(),
    ]


def _page(screen_id, content):
    return Screen(screen_id, '', lambda: [_back_item()], content=content)


SCREENS = {
    screen.id: screen
    for screen in (
        Screen(TITLE, '', _title_items),
        Screen(PAUSE, 'PAUSED', _pause_items),
        Screen('settings', 'SETTINGS', _settings_items),
        Screen('sound', 'SOUND', _sound_items),
        Screen('graphics', 'GRAPHICS', _graphics_items),
        Screen('controls', 'CONTROLS', _controls_items, hint='controls'),
        Screen('save', 'SAVE GAME', _save_items, hint='select'),
        Screen('load', 'LOAD GAME', _load_items, hint='select'),
        Screen('birdpedia', 'BIRDPEDIA', _birdpedia_items, hint='select'),
        Screen('guide', 'GUIDE', _guide_items, hint='select'),
        _page('guide_howto', 'howto'),
        _page('guide_commands', 'commands'),
        _page('guide_obstacles', 'obstacles'),
        _page('guide_enemies', 'enemies'),
        _page('birdpedia_list', 'birds'),
        _page('batpedia_list', 'bats'),
        _page('biomes_list', 'biomes'),
    )
}


# =============================================================================
# NAVIGATION
# =============================================================================


def open_title():
    """Show the title menu with the cursor on its first item."""
    state.ui.menu_stack = [[TITLE, 0]]
    state.ui.rebinding_control = None


def ensure_pause_root():
    """Make sure the menu hangs from the pause root (keeping its cursor)."""
    if root() != PAUSE:
        state.ui.menu_stack = [[PAUSE, 0]]


def current_screen():
    return SCREENS[state.ui.menu_stack[-1][0]]


def cursor():
    return state.ui.menu_stack[-1][1]


def depth():
    """1 at the root, more inside submenus."""
    return len(state.ui.menu_stack)


def close_submenus():
    del state.ui.menu_stack[1:]


def _open(screen_id):
    state.ui.menu_stack.append([screen_id, 0])


def _back():
    stack = state.ui.menu_stack
    if len(stack) <= 1:
        return
    leaving = stack.pop()[0]
    if leaving == 'settings':
        # Leaving the settings: on the title screen they become the defaults
        _settings_changed()


def _activate(item):
    if item.back:
        _back()
    elif item.opens:
        _open(item.opens)
    elif item.rebind:
        state.ui.rebinding_control = item.rebind
    elif item.on_enter:
        item.on_enter()


def handle_key(key):
    """Apply one key press to the open menu."""
    if key == 'QUIT':
        _quit()
        return
    if state.ui.rebinding_control is not None:
        _rebind(key)
        return

    entry = state.ui.menu_stack[-1]
    items = SCREENS[entry[0]].items()

    if key in ('UP', 'DOWN'):
        entry[1] = (entry[1] + (1 if key == 'DOWN' else -1)) % len(items)
    elif key in ('LEFT', 'RIGHT'):
        item = items[entry[1]]
        if item.on_change:
            item.on_change(1 if key == 'RIGHT' else -1)
    elif key == 'ENTER':
        _activate(items[entry[1]])
    elif depth() > 1:
        if key == 'ESC':
            _back()
    elif root() == PAUSE and key in ('ESC', 'p', 'P'):
        handle_pause()  # resume
