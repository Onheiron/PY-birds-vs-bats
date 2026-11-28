"""The tutorial tip drawn over the playfield (src/engine/tutorial.py)."""

from src.core import constants, state
from src.entities.sprites import YELLOW
from src.ui import controls
from src.ui.colors import MENU_BORDER_COLOR
from src.ui.layers.choice import _wrap
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT

TEXT = '\033[38;5;250m'
DIM = '\033[38;5;244m'


def draw_tip(fb):
    tip = state.ui.tip
    if tip is None or state.game.paused:
        return
    width = min(constants.layout.width - 2, 60)
    x = GAME_X_OFFSET + (constants.layout.width - width) // 2
    lines = _wrap(controls.hint(tip['text']), width - 4)
    footer = controls.hint('{ok} got it   {skip} skip the tutorial')
    height = len(lines) + 5
    y = HEADER_HEIGHT + max(1, (constants.layout.height - height) // 3)
    for row in range(y, y + height):
        fb.put_string(x, row, ' ' * width)
    fb.put_string(x, y, '╔' + '═' * (width - 2) + '╗', MENU_BORDER_COLOR)
    rows = [(tip['title'].upper().center(width - 2), YELLOW), ('', TEXT)]
    rows += [(f' {line}'.ljust(width - 2), TEXT) for line in lines]
    rows += [(footer.center(width - 2)[: width - 2], DIM)]
    for n, (text, color) in enumerate(rows, start=1):
        fb.put(x, y + n, '║', MENU_BORDER_COLOR)
        fb.put_string(x + 1, y + n, text[: width - 2].ljust(width - 2), color)
        fb.put(x + width - 1, y + n, '║', MENU_BORDER_COLOR)
    fb.put_string(x, y + len(rows) + 1, '╚' + '═' * (width - 2) + '╝', MENU_BORDER_COLOR)
