"""Title screen."""

from src import __version__
from src.core import state
from src.engine import menus
from src.entities.sprites import YELLOW
from src.ui import controls, terminal
from src.ui.colors import MENU_BORDER_COLOR, MENU_NORMAL_COLOR, MENU_SELECTED_COLOR
from src.ui.framebuffer import get_framebuffer
from src.ui.layers.menus import draw_screen, hint_text, title_style
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


def render_title_screen():
    """Render the title screen: logo, main menu and any open submenu."""
    fb = get_framebuffer()
    fb.clear()

    # Logo, centered a few lines from the top
    logo_width = max(len(line) for line in TITLE_LOGO)
    logo_x = max(0, (TOTAL_WIDTH - logo_width) // 2)
    logo_y = 3
    for i, line in enumerate(TITLE_LOGO):
        fb.put_string(logo_x, logo_y + i, line, YELLOW)
    _draw_version(fb, logo_x + logo_width, logo_y + len(TITLE_LOGO))

    if menus.root() != menus.TITLE:
        menus.open_title()
    stack = state.ui.menu_stack
    _draw_main_menu(fb, logo_y + len(TITLE_LOGO) + 3, stack[0][1])

    if len(stack) > 1:
        # Submenus open as an overlay on top of the main menu
        style = title_style(logo_y + len(TITLE_LOGO) + 2)
        draw_screen(fb, style, menus.current_screen(), menus.cursor())

    terminal.write_frame(fb.render())


def version_line():
    """The version running, and where its update is (src/services/updater.py)."""
    from src.services import updater

    status = updater.status
    state_, version = status.get('state'), status.get('version')
    if state_ == 'available':
        return f'v{__version__}  ·  update {version} available', YELLOW
    if state_ == 'downloading':
        return f'v{__version__}  ·  downloading {version}: {int(status.get("progress", 0) * 100)}%', YELLOW
    if state_ == 'ready':
        return f'v{__version__}  ·  {version} ready: RESTART', YELLOW
    if state_ == 'failed':
        return f'v{__version__}  ·  update failed: {status.get("error") or ""}', MENU_BORDER_COLOR
    return f'v{__version__}', MENU_BORDER_COLOR


def _draw_version(fb, right, y):
    text, color = version_line()
    fb.put_string(max(0, right - len(text)), y, text, color)


def _draw_main_menu(fb, menu_y, selected):
    """The title menu: centered entries, NEW GAME shows the difficulty."""
    items = menus.SCREENS[menus.TITLE].items()
    menu_width = 28  # wide enough for the difficulty selector
    menu_x = (TOTAL_WIDTH - menu_width) // 2

    fb.put_string(menu_x, menu_y, "╔" + "═" * (menu_width - 2) + "╗", MENU_BORDER_COLOR)
    menu_y += 1
    for i, item in enumerate(items):
        text = f"{item.name}  < {item.value():^6} >" if item.value else item.name
        color = MENU_SELECTED_COLOR if i == selected else MENU_NORMAL_COLOR
        fb.put(menu_x, menu_y, '║', MENU_BORDER_COLOR)
        fb.put_string(menu_x + 1, menu_y, text.center(menu_width - 2), color)
        fb.put(menu_x + menu_width - 1, menu_y, '║', MENU_BORDER_COLOR)
        menu_y += 1
    fb.put_string(menu_x, menu_y, "╚" + "═" * (menu_width - 2) + "╝", MENU_BORDER_COLOR)

    # LEFT/RIGHT only does something on entries with a value (NEW GAME)
    if items[selected].on_change:
        hint = controls.hint("{navigate} Navigate  {change} Difficulty  {select} Start")
    else:
        hint = hint_text('root')
    fb.put_string((TOTAL_WIDTH - len(hint)) // 2, menu_y + 2, hint, MENU_BORDER_COLOR)
