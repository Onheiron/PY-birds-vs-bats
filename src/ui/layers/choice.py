"""The card choice drawn over the playfield (egg cards, boss pacts)."""

from src.core import constants, state
from src.engine import cards
from src.entities.sprites import GREEN, RED, YELLOW
from src.ui.colors import MENU_BORDER_COLOR, MENU_NORMAL_COLOR, MENU_SELECTED_COLOR, apply_bold
from src.ui.layout import GAME_X_OFFSET, HEADER_HEIGHT

# Egg and card colours by rarity: grey, green, blue, purple, yellow, white.
# Bright, bold 256-colour shades: the biome backgrounds are dark greens and
# greys, and the theme's own grey and green vanished into them.
RARITY_COLORS = {
    'common': apply_bold('\033[38;5;252m'),
    'uncommon': apply_bold('\033[38;5;83m'),
    'rare': apply_bold('\033[38;5;39m'),
    'epic': apply_bold('\033[38;5;201m'),
    'legendary': apply_bold('\033[38;5;226m'),
    'mythical': apply_bold('\033[38;5;231m'),
}
_KIND_TAGS = {'cursed': ' ☠', 'boost': ' ⏱', 'bird': ' ⬯', 'pact': ''}


def _wrap(text, width):
    words, lines, line = text.split(), [], ''
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f'{line} {word}' if line else word
    if line:
        lines.append(line)
    return lines or ['']


def offer_lines(offer, width):
    """[(text, color, selected)] for an offer, one entry per screen line."""
    out = []
    for index, card in enumerate(offer['cards']):
        selected = index == offer['index']
        color = RARITY_COLORS.get(card['rarity'], MENU_NORMAL_COLOR)
        marker = '▶ ' if selected else '  '
        tag = '' if card['kind'] in ('refuse', 'pact') else f" [{card['rarity'].upper()}]"
        name = f"{marker}{card['name']}{_KIND_TAGS.get(card['kind'], '')}"
        out.append((f'{name:<{width - len(tag)}}{tag}'[:width], MENU_SELECTED_COLOR if selected else color, selected))
        if card['kind'] == 'refuse':
            out.append(('    keep things as they are', MENU_NORMAL_COLOR, False))
        for text, good in cards.card_lines(card):
            for part in _wrap(text, width - 4):
                out.append((f'    {part}', GREEN if good else RED, False))
        out.append(('', MENU_NORMAL_COLOR, False))
    return out


def draw_choice_overlay(fb):
    offer = state.choice.active
    if offer is None or state.game.paused:
        return
    width = constants.layout.width - 2
    inner = width - 2
    x = GAME_X_OFFSET + 1
    lines = offer_lines(offer, inner - 2)
    height = len(lines) + 4
    y = HEADER_HEIGHT + max(0, (constants.layout.height - height) // 2)
    title_color = RARITY_COLORS.get(offer.get('rarity'), YELLOW) if offer['kind'] == 'egg' else RED

    fb.put_string(x, y, '╔' + '═' * inner + '╗', MENU_BORDER_COLOR)
    fb.put(x, y + 1, '║', MENU_BORDER_COLOR)
    fb.put_string(x + 1, y + 1, offer['title'].center(inner), title_color)
    fb.put(x + width - 1, y + 1, '║', MENU_BORDER_COLOR)
    fb.put_string(x, y + 2, '╠' + '═' * inner + '╣', MENU_BORDER_COLOR)
    row = y + 3
    for text, color, _selected in lines[: constants.layout.height - 5]:
        fb.put(x, row, '║', MENU_BORDER_COLOR)
        fb.put_string(x + 1, row, f' {text:<{inner - 1}}'[:inner], color)
        fb.put(x + width - 1, row, '║', MENU_BORDER_COLOR)
        row += 1
    fb.put_string(x, row, '╚' + '═' * inner + '╝', MENU_BORDER_COLOR)
    hint = '↑/↓ choose   ENTER take'
    fb.put_string(x + (width - len(hint)) // 2, row + 1, hint, MENU_BORDER_COLOR)
