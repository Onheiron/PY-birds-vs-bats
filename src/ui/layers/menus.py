"""Pause overlay, settings menus and Birdpedia."""

from src.core import constants
from src.core import state
from src.entities.sprites import YELLOW
from src.ui.colors import MENU_ARROW_COLOR, MENU_BORDER_COLOR, MENU_NORMAL_COLOR, MENU_SELECTED_COLOR
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT, SIDE_PANEL_WIDTH


def _fb_render_pause_overlay(fb):
    """Render pause overlay and menu to framebuffer."""
    if not state.game.paused:
        return

    # "PAUSED" text in game area (centered)
    pause_y = constants.layout.height // 2 + HEADER_HEIGHT
    pause_x = max(0, (constants.layout.width // 2) - 3)
    fb.put_string(GAME_X_OFFSET + pause_x, pause_y, "PAUSED", YELLOW)

    # Pause menu in right panel
    right_start = GAME_X_OFFSET + constants.layout.width
    inner_start_x = right_start + 1

    # Menu dimensions - full panel width
    menu_width = SIDE_PANEL_WIDTH - 2
    inner_width = menu_width - 2
    menu_x = inner_start_x

    # Position menu
    panel_start_y = HEADER_HEIGHT
    menu_start_y = panel_start_y + 8

    # Check if we're in a settings submenu
    if state.ui.settings_menu is not None:
        _fb_render_settings_menu(fb, menu_x, menu_start_y, menu_width, inner_width)
    else:
        _fb_render_pause_menu(fb, menu_x, menu_start_y, menu_width, inner_width)


def _fb_render_pause_menu(fb, menu_x, menu_start_y, menu_width, inner_width):
    """Render the main pause menu."""
    PAUSE_MENU_OPTIONS = [
        "RESUME",
        "RESTART",
        "SAVE",
        "LOAD",
        "BIRDPEDIA",
        "SETTINGS",
        "MAIN MENU"
    ]

    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = menu_start_y

    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title_padded = "PAUSED".center(inner_width)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    selected_idx = state.ui.pause_menu_index
    option_text_width = inner_width - 2

    for i, option in enumerate(PAUSE_MENU_OPTIONS):
        fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
        if i == selected_idx:
            fb.put(menu_x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(menu_x + 2, y, f" {option:<{option_text_width}}", MENU_SELECTED_COLOR)
        else:
            fb.put_string(menu_x + 1, y, f"  {option:<{option_text_width}}", MENU_NORMAL_COLOR)
        fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    fb.put_string(menu_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    hint = "↑↓ Navigate  ⏎ Select"
    fb.put_string(menu_x, y, hint[:menu_width], MENU_BORDER_COLOR)


def _fb_render_settings_menu(fb, menu_x, menu_start_y, menu_width, inner_width):
    """Render the settings submenu based on current settings_menu state."""
    # Define all settings menus
    DIFFICULTY_NAMES = ["PEACEFUL", "ADVENTURE", "SURVIVAL", "LEGENDARY"]

    def get_toggle(value):
        return "ON" if value else "OFF"

    def get_difficulty():
        return DIFFICULTY_NAMES[state.settings.difficulty]

    # Build menu options based on current submenu
    if state.ui.settings_menu == 'main':
        title = "SETTINGS"
        options = [
            ("SOUND", "submenu"),
            ("GRAPHICS", "submenu"),
            ("CONTROLS", "submenu"),
            (f"DIFFICULTY      < {get_difficulty()} >", "cycle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'sound':
        title = "SOUND"
        options = [
            (f"SFX             < {get_toggle(state.settings.sfx_enabled)} >", "toggle"),
            (f"MUSIC           < {get_toggle(state.settings.music_enabled)} >", "toggle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'graphics':
        title = "GRAPHICS"
        options = [
            (f"BACKGROUND      < {get_toggle(state.settings.background_enabled)} >", "toggle"),
            (f"PARALLAX        < {get_toggle(state.settings.parallax_enabled)} >", "toggle"),
            (f"ACCESSIBILITY   < {get_toggle(state.settings.accessibility_enabled)} >", "toggle"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'controls':
        title = "CONTROLS"
        # Build options dynamically from key bindings
        bindings = state.settings.key_bindings
        rebinding = state.ui.rebinding_control
        blink_on = (state.game.frame_count // 5) % 2 == 0  # Blink every 5 frames

        def get_key_display(control_name):
            key = bindings.get(control_name, '?')
            # If currently rebinding this control, show blinking or prompt
            if rebinding == control_name:
                return "___" if blink_on else "   "
            # Convert key names to symbols
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
    elif state.ui.settings_menu == 'save':
        title = "SAVE GAME"
        # Get save slot info
        from src.services import save_manager
        slots = save_manager.list_save_slots()

        def get_slot_info(slot_num):
            slot = slots.get(slot_num, {})
            if slot.get('exists'):
                level = slot.get('level_display', '?')
                ts = slot.get('timestamp', '')
                ts_display = save_manager.format_timestamp_display(ts) if ts else '???'
                return f"SLOT {slot_num} Lv{level} {ts_display}"
            return f"SLOT {slot_num}  (empty)"

        options = [
            (get_slot_info(1), "slot"),
            (get_slot_info(2), "slot"),
            (get_slot_info(3), "slot"),
            ("< BACK", "back"),
        ]
    elif state.ui.settings_menu == 'load':
        title = "LOAD GAME"
        # Get save slot info
        from src.services import save_manager
        slots = save_manager.list_save_slots()

        def get_slot_info(slot_num):
            slot = slots.get(slot_num, {})
            label = "AUTO" if slot_num == 0 else f"SLOT {slot_num}"
            if slot.get('exists'):
                level = slot.get('level_display', '?')
                ts = slot.get('timestamp', '')
                ts_display = save_manager.format_timestamp_display(ts) if ts else '???'
                return f"{label} Lv{level} {ts_display}"
            return f"{label}  (empty)"

        options = [
            (get_slot_info(0), "slot"),
            (get_slot_info(1), "slot"),
            (get_slot_info(2), "slot"),
            (get_slot_info(3), "slot"),
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
    elif state.ui.settings_menu == 'guide_howto':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'howto')
        return
    elif state.ui.settings_menu == 'guide_commands':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'commands')
        return
    elif state.ui.settings_menu == 'guide_obstacles':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'obstacles')
        return
    elif state.ui.settings_menu == 'guide_enemies':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'enemies')
        return
    elif state.ui.settings_menu == 'birdpedia_list':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'birds')
        return
    elif state.ui.settings_menu == 'batpedia_list':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'bats')
        return
    elif state.ui.settings_menu == 'biomes_list':
        _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, 'biomes')
        return
    else:
        return

    top_border = "╔" + "═" * (menu_width - 2) + "╗"
    separator_border = "╠" + "═" * (menu_width - 2) + "╣"
    bottom_border = "╚" + "═" * (menu_width - 2) + "╝"

    y = menu_start_y

    fb.put_string(menu_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    fb.put(menu_x, y, '║', MENU_BORDER_COLOR)
    title_padded = title.center(inner_width)
    fb.put_string(menu_x + 1, y, title_padded, YELLOW)
    fb.put(menu_x + menu_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    fb.put_string(menu_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    selected_idx = state.ui.settings_index
    option_text_width = inner_width - 2

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

    # Hint based on menu type and state
    if state.ui.settings_menu == 'controls':
        if state.ui.rebinding_control is not None:
            hint = "Press new key...  ESC Cancel"
        else:
            hint = "↑↓ Navigate  ⏎ Rebind  ESC Back"
    elif state.ui.settings_menu in ('save', 'load'):
        hint = "↑↓ Navigate  ⏎ Select  ESC Back"
    elif state.ui.settings_menu in ('birdpedia', 'guide'):
        hint = "↑↓ Navigate  ⏎ Select  ESC Back"
    else:
        hint = "↑↓ Navigate  ←→ Change  ⏎ Select"
    fb.put_string(menu_x, y, hint[:menu_width], MENU_BORDER_COLOR)


def _fb_render_birdpedia_content(fb, menu_x, menu_start_y, menu_width, inner_width, content_type):
    """Render birdpedia content pages."""
    from src.entities.sprites import (YELLOW, RED, BLUE, WHITE, PURPLE, ORANGE,
                                      STEALTH, CLOCKWORK, GOLD, PATCHWORK,
                                      COOKIE, DINOSAUR, GLITCH)

    # Get discovery state
    discovered_birds = state.discovery.birds
    discovered_bats = state.discovery.bats
    discovered_obstacles = state.discovery.obstacles

    # Bird entries with discovery check
    BIRD_ENTRIES = [
        ('YELLOW', "\x1b[93mYELLOW\x1b[0m - Bounces adjacent birds"),
        ('RED', "\x1b[91mRED\x1b[0m - Fires projectiles"),
        ('BLUE', "\x1b[94mBLUE\x1b[0m - Speed boost"),
        ('WHITE', "\x1b[97mWHITE\x1b[0m - Affects 4 lanes"),
        ('PURPLE', "\x1b[95mPURPLE\x1b[0m - Charge & launch"),
        ('ORANGE', "\x1b[38;5;208mORANGE\x1b[0m - Lays eggs, respawns"),
        ('STEALTH', "\x1b[90mSTEALTH\x1b[0m - Goes invisible"),
        ('CLOCKWORK', "\x1b[38;5;130mCLOCKWORK\x1b[0m - Wind-up speed"),
        ('GOLD', "\x1b[33mGOLD\x1b[0m - Extra points"),
        ('PATCHWORK', "\x1b[38;5;213mPATCHWORK\x1b[0m - Random powers"),
        ('COOKIE', "\x1b[38;5;215mCOOKIE\x1b[0m - Drops XP crumbs"),
        ('DINOSAUR', "\x1b[32mDINOSAUR\x1b[0m - Multi-press bounce"),
        ('GLITCH', "\x1b[38;5;51mGLITCH\x1b[0m - Unpredictable"),
    ]

    # Bat entries with discovery check
    BAT_ENTRIES = [
        ('BASIC', ["BASIC BAT", "  Standard flying enemy.", "  Scares birds on contact.", ""]),
        ('FAST', ["FAST BAT", "  Moves quickly across lanes.", "  Harder to avoid.", ""]),
        ('DIVE', ["DIVE BAT", "  Dives down at birds.", "  Very dangerous!", ""]),
        ('BOSS', ["BOSS BAT", "  Huge and powerful!", "  Requires many hits.", ""]),
    ]

    # Build dynamic bird list
    def get_bird_lines():
        lines = []
        discovered_count = 0
        for name, text in BIRD_ENTRIES:
            if name in discovered_birds:
                lines.append(text)
                discovered_count += 1
            else:
                lines.append("\x1b[90m??? - ???\x1b[0m")
        lines.append("")
        lines.append(f"Discovered: {discovered_count}/{len(BIRD_ENTRIES)}")
        return lines

    # Build dynamic bat list
    def get_bat_lines():
        lines = []
        discovered_count = 0
        for name, entry_lines in BAT_ENTRIES:
            if name in discovered_bats:
                lines.extend(entry_lines)
                discovered_count += 1
            else:
                lines.extend(["\x1b[90m??? BAT\x1b[0m", "  ???", "  ???", ""])
        lines.append(f"Discovered: {discovered_count}/{len(BAT_ENTRIES)}")
        return lines

    # Content definitions
    CONTENT = {
        'howto': {
            'title': 'HOW TO PLAY',
            'lines': [
                "Guide your birds to the finish",
                "line at the top of the screen!",
                "",
                "Birds bounce between the start",
                "and finish lines automatically.",
                "",
                "Press UP when a bird is falling",
                "to bounce it back up.",
                "",
                "Press UP when a bird is rising",
                "to activate its special power!",
                "",
                "Collect loot for score & XP.",
                "Avoid obstacles and enemies.",
                "",
                "Don't let birds fall off the",
                "bottom - you'll lose a life!",
            ]
        },
        'commands': {
            'title': 'COMMANDS',
            'lines': [
                "MOVEMENT:",
                "  LEFT/RIGHT - Move cursor",
                "  UP - Bounce / Power",
                "  DOWN - Suction (if active)",
                "",
                "SELECTION:",
                "  SPACE - Start/Execute swap",
                "",
                "GAME:",
                "  P - Pause game",
                "  X - Toggle XP overlay",
                "  M - Mute/Unmute audio",
                "  Q - Quit game",
                "",
                "Controls can be rebound in",
                "the SETTINGS > CONTROLS menu.",
            ]
        },
        'obstacles': {
            'title': 'OBSTACLES',
            'lines': [
                "TREE - Blocks bird movement." if 'TREE' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Birds bounce off trees." if 'TREE' in discovered_obstacles else "",
                "",
                "ROCK - Stuns birds on contact." if 'ROCK' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Stunned birds can't bounce." if 'ROCK' in discovered_obstacles else "",
                "",
                "CLOUD - Slows bird speed." if 'CLOUD' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Temporary speed reduction." if 'CLOUD' in discovered_obstacles else "",
                "",
                "BARRIER - Right panel hazard." if 'BARRIER' in discovered_obstacles else "\x1b[90m??? - ???\x1b[0m",
                "  Destroys loot on contact." if 'BARRIER' in discovered_obstacles else "",
                "",
                f"Discovered: {len(discovered_obstacles)}/4",
            ]
        },
        'enemies': {
            'title': 'ENEMIES',
            'lines': [
                "BAT - Flying enemy.",
                "  Scares birds on contact!",
                "  Scared birds fall faster",
                "  and cannot be bounced.",
                "",
                "RED projectiles can destroy",
                "bats for bonus points.",
                "",
                "BLUE birds near YELLOW birds",
                "can be cured of fear when",
                "the yellow bird bounces.",
                "",
                "More enemies appear at higher",
                "speed levels.",
            ]
        },
        'birds': {
            'title': 'BIRD-DEX',
            'lines': get_bird_lines()
        },
        'bats': {
            'title': 'BAT-DEX',
            'lines': get_bat_lines()
        },
        'biomes': {
            'title': 'BIOMES',
            'lines': [
                "WINDY WOODS (1-1 to 1-3)",
                "  Dense conifer forest.",
                "  Gentle start, basic obstacles.",
                "",
                "THE BORDERS (2-1 to 2-3)",
                "  Open plains, deciduous trees.",
                "  More space, faster foes.",
                "",
                "ROTTEN MARSHES (3-1 to 3-3)",
                "  Swampy wetlands, reeds.",
                "  Watch for murky waters!",
                "",
                "THE DARK SWAMP (4-1 to 4-3)",
                "  Deep dark swamp, twisted trees.",
                "  Visibility reduced, danger rises.",
                "",
                "THE VOID CAVE (5-1 to 5-3)",
                "  Underground cavern, stalactites.",
                "  No light, maximum peril!",
                "",
                "MOUNTAIN RANGE (6-1 to 6-3)",
                "  High peaks, thin air.",
                "  Cloud banks obscure vision!",
            ]
        }
    }

    content = CONTENT.get(content_type, {'title': 'UNKNOWN', 'lines': []})
    title = content['title']
    lines = content['lines']

    # Calculate height needed (title + separator + content + separator + back + bottom + hint)
    content_height = len(lines) + 7

    # Expand menu width for content
    expanded_width = min(40, menu_width + 10)
    expanded_x = menu_x - 5

    # Clear the entire area first to avoid showing previous menu underneath
    for clear_y in range(menu_start_y, menu_start_y + content_height + 2):
        for clear_x in range(expanded_x - 2, expanded_x + expanded_width + 2):
            if 0 <= clear_x < fb.width and 0 <= clear_y < fb.height:
                fb.put(clear_x, clear_y, ' ', '')

    top_border = "╔" + "═" * (expanded_width - 2) + "╗"
    separator_border = "╠" + "═" * (expanded_width - 2) + "╣"
    bottom_border = "╚" + "═" * (expanded_width - 2) + "╝"

    y = menu_start_y

    # Top border
    fb.put_string(expanded_x, y, top_border, MENU_BORDER_COLOR)
    y += 1

    # Title
    fb.put(expanded_x, y, '║', MENU_BORDER_COLOR)
    title_padded = title.center(expanded_width - 2)
    fb.put_string(expanded_x + 1, y, title_padded, YELLOW)
    fb.put(expanded_x + expanded_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    # Separator
    fb.put_string(expanded_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    # Content lines
    content_width = expanded_width - 4
    for line in lines:
        fb.put(expanded_x, y, '║', MENU_BORDER_COLOR)
        # Handle ANSI color codes - they don't take display width
        display_line = f" {line}"
        if '\x1b[' in line:
            # Line has color codes, write directly
            fb.put_string(expanded_x + 1, y, display_line, MENU_NORMAL_COLOR)
        else:
            # Pad plain lines
            fb.put_string(expanded_x + 1, y, f" {line:<{content_width}}"[:content_width+1], MENU_NORMAL_COLOR)
        fb.put(expanded_x + expanded_width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    # Separator before back
    fb.put_string(expanded_x, y, separator_border, MENU_BORDER_COLOR)
    y += 1

    # Back option (always selected)
    fb.put(expanded_x, y, '║', MENU_BORDER_COLOR)
    back_text = "< BACK"
    fb.put(expanded_x + 1, y, '>', MENU_ARROW_COLOR)
    fb.put_string(expanded_x + 2, y, f" {back_text:<{content_width}}"[:content_width+1], MENU_SELECTED_COLOR)
    fb.put(expanded_x + expanded_width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1

    # Bottom border
    fb.put_string(expanded_x, y, bottom_border, MENU_BORDER_COLOR)
    y += 1

    # Hint
    hint = "⏎ or ESC to go back"
    fb.put_string(expanded_x, y, hint[:expanded_width], MENU_BORDER_COLOR)
