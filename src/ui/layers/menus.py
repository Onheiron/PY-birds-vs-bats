"""Menu drawing: one box renderer for every screen of the menu tree.

The tree itself (screens, items, actions) lives in src/engine/menus.py. Here a
``MenuStyle`` describes where a menu sits and how wide its labels are, which
is all that differs between the pause menu (right panel) and the title screen
(centered overlay).
"""

from dataclasses import dataclass, replace

from src.core import constants, state
from src.engine import menus
from src.entities.sprites import YELLOW
from src.ui import pages
from src.ui.colors import MENU_ARROW_COLOR, MENU_BORDER_COLOR, MENU_NORMAL_COLOR, MENU_SELECTED_COLOR
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT, SIDE_PANEL_WIDTH, TOTAL_WIDTH

HINTS = {
    'change': "↑↓ Navigate  ←→ Change  ⏎ Select",
    'select': "↑↓ Navigate  ⏎ Select  ESC Back",
    'controls': "↑↓ Navigate  ⏎ Rebind  ESC Back",
    'rebinding': "Press new key...  ESC Cancel",
    'root': "↑↓ Navigate  ⏎ Select",
    'page': "⏎ or ESC to go back",
}


@dataclass(frozen=True)
class MenuStyle:
    x: int
    y: int
    width: int
    label_width: int  # column where option values ("< ON >") start
    slot_separator: str  # between a slot name and its details
    empty_separator: str  # between a slot name and "(empty)"
    center_hint: bool


def pause_style():
    """Pause menu: fills the right panel below the level signs."""
    right_start = GAME_X_OFFSET + constants.layout.width
    return MenuStyle(
        x=right_start + 1,
        y=HEADER_HEIGHT + 8,
        width=SIDE_PANEL_WIDTH - 2,
        label_width=16,
        slot_separator=' ',
        empty_separator='  ',
        center_hint=False,
    )


def title_style(y):
    """Title screen submenus: a 30-column box centered under the logo."""
    width = 30
    return MenuStyle(
        x=(TOTAL_WIDTH - width) // 2,
        y=y,
        width=width,
        label_width=14,
        slot_separator=': ',
        empty_separator=': ',
        center_hint=True,
    )


def item_text(item, style):
    """The text of a menu line, laid out according to the item kind."""
    if item.kind == 'option':
        return f"{item.name:<{style.label_width}}< {item.value()} >"
    if item.kind == 'binding':
        return f"{item.name:<16}{item.value():>5}"
    if item.kind == 'slot':
        details = item.value()
        if details is None:
            return f"{item.name}{style.empty_separator}(empty)"
        level, date = details
        return f"{item.name}{style.slot_separator}Lv{level} {date}"
    return item.name


def screen_hint(screen):
    if screen.hint == 'controls' and state.ui.rebinding_control is not None:
        return HINTS['rebinding']
    return HINTS[screen.hint]


def _put_hint(fb, style, y, hint):
    if style.center_hint:
        fb.put_string((TOTAL_WIDTH - len(hint)) // 2, y, hint, MENU_BORDER_COLOR)
    else:
        fb.put_string(style.x, y, hint[: style.width], MENU_BORDER_COLOR)


def draw_box(fb, style, title, lines, selected, hint):
    """A bordered menu: title, one line per option (selected one marked), hint."""
    x, y, width = style.x, style.y, style.width
    inner = width - 2
    text_width = width - 4

    fb.put_string(x, y, "╔" + "═" * inner + "╗", MENU_BORDER_COLOR)
    y += 1
    fb.put(x, y, '║', MENU_BORDER_COLOR)
    fb.put_string(x + 1, y, title.center(inner), YELLOW)
    fb.put(x + width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1
    fb.put_string(x, y, "╠" + "═" * inner + "╣", MENU_BORDER_COLOR)
    y += 1

    for i, text in enumerate(lines):
        fb.put(x, y, '║', MENU_BORDER_COLOR)
        if i == selected:
            fb.put(x + 1, y, '>', MENU_ARROW_COLOR)
            fb.put_string(x + 2, y, f" {text:<{text_width}}"[: text_width + 1], MENU_SELECTED_COLOR)
        else:
            fb.put_string(x + 1, y, f"  {text:<{text_width}}"[: text_width + 2], MENU_NORMAL_COLOR)
        fb.put(x + width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    fb.put_string(x, y, "╚" + "═" * inner + "╝", MENU_BORDER_COLOR)
    _put_hint(fb, style, y + 1, hint)


def draw_page(fb, style, content):
    """A text page (guide, Bird-Dex...), drawn wider than the menu it opens from."""
    page = pages.page(content)
    lines = page['lines']

    width = min(40, style.width + 10)
    x = style.x - 5
    y = style.y
    inner = width - 2
    text_width = width - 4

    # Blank the area first so the menu underneath does not show through
    for clear_y in range(y, y + len(lines) + 9):
        fb.fill(x - 2, clear_y, width + 4)

    fb.put_string(x, y, "╔" + "═" * inner + "╗", MENU_BORDER_COLOR)
    y += 1
    fb.put(x, y, '║', MENU_BORDER_COLOR)
    fb.put_string(x + 1, y, page['title'].center(inner), YELLOW)
    fb.put(x + width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1
    fb.put_string(x, y, "╠" + "═" * inner + "╣", MENU_BORDER_COLOR)
    y += 1

    for line in lines:
        fb.put(x, y, '║', MENU_BORDER_COLOR)
        if '\x1b[' in line:
            # Coloured entries: their escape codes take no room on screen
            fb.put_string(x + 1, y, f" {line}", MENU_NORMAL_COLOR)
        else:
            fb.put_string(x + 1, y, f" {line:<{text_width}}"[: text_width + 1], MENU_NORMAL_COLOR)
        fb.put(x + width - 1, y, '║', MENU_BORDER_COLOR)
        y += 1

    fb.put_string(x, y, "╠" + "═" * inner + "╣", MENU_BORDER_COLOR)
    y += 1
    # The only option, always selected
    fb.put(x, y, '║', MENU_BORDER_COLOR)
    fb.put(x + 1, y, '>', MENU_ARROW_COLOR)
    fb.put_string(x + 2, y, f" {'< BACK':<{text_width}}"[: text_width + 1], MENU_SELECTED_COLOR)
    fb.put(x + width - 1, y, '║', MENU_BORDER_COLOR)
    y += 1
    fb.put_string(x, y, "╚" + "═" * inner + "╝", MENU_BORDER_COLOR)
    fb.put_string(x, y + 1, HINTS['page'][:width], MENU_BORDER_COLOR)


def draw_screen(fb, style, screen, selected):
    """Draw any screen of the menu tree with the given style."""
    if screen.content:
        draw_page(fb, style, screen.content)
        return
    items = screen.items()
    # Long option names push every option value of the screen to the same column
    longest = max((len(item.name) + 1 for item in items if item.kind == 'option'), default=0)
    if longest > style.label_width:
        style = replace(style, label_width=longest)
    lines = [item_text(item, style) for item in items]
    draw_box(fb, style, screen.title, lines, selected, screen_hint(screen))


def draw_pause_overlay(fb):
    """'PAUSED' over the playfield and the pause menu in the right panel."""
    if not state.game.paused:
        return

    pause_y = constants.layout.height // 2 + HEADER_HEIGHT
    pause_x = max(0, (constants.layout.width // 2) - 3)
    fb.put_string(GAME_X_OFFSET + pause_x, pause_y, "PAUSED", YELLOW)

    style = pause_style()
    if menus.root() != menus.PAUSE:
        # Paused before the menu opened: show its first page
        draw_box(fb, style, 'PAUSED', [item.name for item in menus.SCREENS[menus.PAUSE].items()], 0, HINTS['root'])
        return

    screen = menus.current_screen()
    if menus.depth() == 1:
        lines = [item.name for item in screen.items()]
        draw_box(fb, style, screen.title, lines, menus.cursor(), HINTS['root'])
    else:
        draw_screen(fb, style, screen, menus.cursor())
