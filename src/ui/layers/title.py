"""Title screen."""

from src.core import state
import sys
from src.entities.sprites import YELLOW
from src.ui.colors import MENU_ARROW_COLOR, MENU_BORDER_COLOR, MENU_NORMAL_COLOR, MENU_SELECTED_COLOR
from src.ui.framebuffer import get_framebuffer
from src.ui.layers.menus import _fb_render_birdpedia_content
from src.ui.layout import TOTAL_WIDTH

# ASCII art logo for title screen
TITLE_LOGO = [
    "    ▄▄▄                                          ▄▄▄                 ",
    "   ██▀▀█▄            █▄                         ██▀▀█▄       █▄      ",
    "   ██ ▄█▀ ▀▀ ▄       ██                         ██ ▄█▀      ▄██▄     ",
    "   ██▀▀█▄ ██ ████▄▄████ ▄██▀█  ▀█▄ ██▀▄██▀█     ██▀▀█▄ ▄▀▀█▄ ██ ▄██▀█",
    " ▄ ██  ▄█ ██ ██   ██ ██ ▀███▄   ██▄██ ▀███▄   ▄ ██  ▄█ ▄█▀██ ██ ▀███▄",
    " ▀██████▀▄██▄█▀  ▄█▀████▄▄██▀    ▀█▀ █▄▄██▀   ▀██████▀▄▀█▄██▄███▄▄██▀",
]

TITLE_MENU_OPTIONS = ["CONTINUE", "NEW GAME", "LOAD", "BIRDPEDIA", "SETTINGS", "QUIT"]


def render_title_screen():
    """Render the title screen with logo and menu."""
    fb = get_framebuffer()

    # Difficulty names for display
    DIFFICULTY_NAMES = ["PEACEFUL", "ADVENTURE", "SURVIVAL", "LEGENDARY"]

    # Clear the screen with dark background
    for y in range(fb.height):
        for x in range(fb.width):
            fb.put(x, y, ' ', '')

    # Calculate centering
    logo_width = max(len(line) for line in TITLE_LOGO)
    logo_x = max(0, (TOTAL_WIDTH - logo_width) // 2)
    logo_y = 3  # Start a few lines from top

    # Render logo
    for i, line in enumerate(TITLE_LOGO):
        fb.put_string(logo_x, logo_y + i, line, YELLOW)

    # Menu area (below logo)
    menu_y = logo_y + len(TITLE_LOGO) + 3
    menu_width = 28  # Wider to fit difficulty selector
    menu_x = (TOTAL_WIDTH - menu_width) // 2

    # Menu box
    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    fb.put_string(menu_x, menu_y, top_border, MENU_BORDER_COLOR)
    menu_y += 1

    selected_idx = state.ui.title_menu_index

    for i, option in enumerate(TITLE_MENU_OPTIONS):
        fb.put(menu_x, menu_y, '║', MENU_BORDER_COLOR)

        # Special handling for NEW GAME - show difficulty selector
        if option == "NEW GAME":
            diff_name = DIFFICULTY_NAMES[state.settings.difficulty]
            option_text = f"NEW GAME  < {diff_name:^6} >"
            option_padded = option_text.center(menu_width - 2)
        else:
            option_padded = option.center(menu_width - 2)

        if i == selected_idx:
            fb.put_string(menu_x + 1, menu_y, option_padded, MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, menu_y, option_padded, MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, menu_y, '║', MENU_BORDER_COLOR)
        menu_y += 1

    fb.put_string(menu_x, menu_y, bottom_border, MENU_BORDER_COLOR)
    menu_y += 1

    # Hint - different when on NEW GAME
    if selected_idx == 1:  # NEW GAME
        hint = "↑↓ Navigate  ←→ Difficulty  ⏎ Start"
    else:
        hint = "↑↓ Navigate  ⏎ Select"
    hint_x = (TOTAL_WIDTH - len(hint)) // 2
    fb.put_string(hint_x, menu_y + 1, hint, MENU_BORDER_COLOR)

    # If in submenu, render overlay
    if state.ui.settings_menu == 'load':
        _fb_render_title_load_menu(fb, logo_y + len(TITLE_LOGO) + 2)
    elif state.ui.settings_menu is not None:
        # Render settings submenu overlay
        _fb_render_title_settings_menu(fb, logo_y + len(TITLE_LOGO) + 2)

    # Generate output and display
    output = fb.render()
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except BlockingIOError:
        pass


def _fb_render_title_load_menu(fb, start_y):
    """Render load menu overlay on title screen."""
    from src.services import save_manager
    slots = save_manager.list_save_slots()

    menu_width = 30
    menu_x = (TOTAL_WIDTH - menu_width) // 2

    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = start_y

    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    # Title
    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title_padded = "LOAD GAME".center(menu_width - 2)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    selected_idx = state.ui.settings_index
    option_text_width = menu_width - 4

    # Slot options: autosave + 3 manual slots + back
    for slot in range(0, 4):  # 0=autosave, 1-3=manual
        slot_info = slots.get(slot, {})
        if slot == 0:
            label = "AUTO"
        else:
            label = f"SLOT {slot}"

        if slot_info.get('exists'):
            level = slot_info.get('level_display', '?')
            ts = slot_info.get('timestamp', '')
            ts_display = save_manager.format_timestamp_display(ts) if ts else '???'
            option_text = f"{label}: Lv{level} {ts_display}"
        else:
            option_text = f"{label}: (empty)"

        fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
        if slot == selected_idx:
            fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(menu_x + 2, y, f" {option_text:<{option_text_width}}"[:option_text_width+1], MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, y, f"  {option_text:<{option_text_width}}"[:option_text_width+2], MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    # BACK option
    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    if 4 == selected_idx:
        fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
        fb.put_string(menu_x + 2, y, f" {'< BACK':<{option_text_width}}"[:option_text_width+1], MENU_SELECTED_COLOR)
    else:
        fb.put_string(menu_x + 1, y, f"  {'< BACK':<{option_text_width}}"[:option_text_width+2], MENU_NORMAL_COLOR)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    hint = "↑↓ Navigate  ⏎ Select  ESC Back"
    hint_x = (TOTAL_WIDTH - len(hint)) // 2
    fb.put_string(hint_x, y, hint, MENU_BORDER_COLOR)


def _fb_render_title_settings_menu(fb, start_y):
    """Render settings menu overlay on title screen."""
    DIFFICULTY_NAMES = ["PEACEFUL", "ADVENTURE", "SURVIVAL", "LEGENDARY"]

    def get_toggle(value):
        return "ON" if value else "OFF"

    def get_difficulty():
        return DIFFICULTY_NAMES[state.settings.difficulty]

    menu_width = 30
    menu_x = (TOTAL_WIDTH - menu_width) // 2

    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = start_y

    # Build menu based on current submenu
    if state.ui.settings_menu == 'main':
        title = "SETTINGS"
        options = [
            ("SOUND", "submenu"),
            ("GRAPHICS", "submenu"),
            ("CONTROLS", "submenu"),
            (f"DIFFICULTY    < {get_difficulty()} >", "cycle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'sound':
        title = "SOUND"
        options = [
            (f"SFX           < {get_toggle(state.settings.sfx_enabled)} >", "toggle"),
            (f"MUSIC         < {get_toggle(state.settings.music_enabled)} >", "toggle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'graphics':
        title = "GRAPHICS"
        options = [
            (f"BACKGROUND    < {get_toggle(state.settings.background_enabled)} >", "toggle"),
            (f"PARALLAX      < {get_toggle(state.settings.parallax_enabled)} >", "toggle"),
            (f"ACCESSIBILITY < {get_toggle(state.settings.accessibility_enabled)} >", "toggle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'controls':
        title = "CONTROLS"
        bindings = state.settings.key_bindings
        rebinding = state.ui.rebinding_control
        blink_on = (state.game.frame_count // 5) % 2 == 0

        def get_key_display(control_name):
            key = bindings.get(control_name, '?')
            if rebinding == control_name:
                return "___" if blink_on else "   "
            symbols = {'LEFT': '←', 'RIGHT': '→', 'UP': '↑', 'DOWN': '↓', 'SPACE': 'SPC'}
            return symbols.get(key, key)

        options = [
            (f"MOVE LEFT       {get_key_display('MOVE_LEFT'):>5}", "rebind"),
            (f"MOVE RIGHT      {get_key_display('MOVE_RIGHT'):>5}", "rebind"),
            (f"BOUNCE          {get_key_display('BOUNCE'):>5}", "rebind"),
            (f"SUCTION         {get_key_display('SUCTION'):>5}", "rebind"),
            (f"SWAP            {get_key_display('SWAP'):>5}", "rebind"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'birdpedia':
        title = "BIRDPEDIA"
        options = [
            ("GUIDE", "submenu"),
            ("BIRD-DEX", "submenu"),
            ("BAT-DEX", "submenu"),
            ("BIOMES", "submenu"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'guide':
        title = "GUIDE"
        options = [
            ("HOW TO PLAY", "submenu"),
            ("COMMANDS", "submenu"),
            ("OBSTACLES", "submenu"),
            ("ENEMIES", "submenu"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu in ('guide_howto', 'guide_commands', 'guide_obstacles', 'guide_enemies',
                                     'birdpedia_list', 'batpedia_list', 'biomes_list'):
        # Render content view using the shared function
        content_map = {
            'guide_howto': 'howto',
            'guide_commands': 'commands',
            'guide_obstacles': 'obstacles',
            'guide_enemies': 'enemies',
            'birdpedia_list': 'birds',
            'batpedia_list': 'bats',
            'biomes_list': 'biomes',
        }
        _fb_render_birdpedia_content(fb, menu_x, start_y, menu_width, menu_width - 2,
                                     content_map[state.ui.settings_menu])
        return
    else:
        return

    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    # Title
    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title_padded = title.center(menu_width - 2)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    selected_idx = state.ui.settings_index
    option_text_width = menu_width - 4

    for i, (option_text, option_type) in enumerate(options):
        fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
        if i == selected_idx:
            fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(menu_x + 2, y, f" {option_text:<{option_text_width}}"[:option_text_width+1], MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, y, f"  {option_text:<{option_text_width}}"[:option_text_width+2], MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    fb.put_string(menu_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    # Hint based on menu type
    if state.ui.settings_menu == 'controls':
        if state.ui.rebinding_control is not None:
            hint = "Press new key...  ESC Cancel"
        else:
            hint = "↑↓ Navigate  ⏎ Rebind  ESC Back"
    elif state.ui.settings_menu in ('birdpedia', 'guide'):
        hint = "↑↓ Navigate  ⏎ Select  ESC Back"
    else:
        hint = "↑↓ Navigate  ←→ Change  ⏎ Select"
    hint_x = (TOTAL_WIDTH - len(hint)) // 2
    fb.put_string(hint_x, y, hint, MENU_BORDER_COLOR)
