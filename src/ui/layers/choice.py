"""The card choice drawn over the playfield (egg cards, boss pacts).

Each card is a small framed sheet:

    ┌─ Glass Wings ☠ ────────── EPIC ─┐
    │ Cursed · Permanent              │
    │ Much more damage, but birds     │
    │ fall faster.                    │
    │ + 52.5% damage                  │
    │ − 7 falling speed               │
    └─────────────────────────────────┘

The selected card is framed in its rarity colour with a ▶ beside it. When
the cards do not all fit, the others are shown as one line each.
"""

from src.core import constants, state
from src.engine import cards, choices
from src.entities.sprites import GREEN, RED, YELLOW
from src.ui import controls
from src.ui.colors import MENU_BORDER_COLOR, MENU_NORMAL_COLOR, apply_bold
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
DIM = '\033[38;5;244m'
TEXT = '\033[38;5;250m'
_KIND_TAGS = {'cursed': ' ☠', 'bird': ' ⬯'}


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
    return lines


def card_rows(card, width, selected):
    """Rows of one framed card: [[(text, color), ...], ...], each row ``width`` wide."""
    info = cards.card_info(card)
    frame = RARITY_COLORS.get(info['rarity'], MENU_BORDER_COLOR) if selected else DIM
    inner = width - 4  # "│ " + text + " │"
    name = f"{info['name']}{_KIND_TAGS.get(card['kind'], '')}"
    tag = '' if card['kind'] in ('refuse', 'pact') else info['rarity'].upper()
    # '┌─ ' name ' ' dashes [' ' tag ' '] '┐' spans exactly width columns
    fill = max(1, width - len(name) - (len(tag) + 7 if tag else 5))
    top = [
        ('┌─ ', frame),
        (name, RARITY_COLORS.get(info['rarity'], TEXT) if card['kind'] != 'refuse' else TEXT),
        (' ' + '─' * fill, frame),
    ]
    top += [(' ' + tag + ' ', RARITY_COLORS.get(info['rarity'], TEXT)), ('┐', frame)] if tag else [('┐', frame)]
    rows = [top]

    def line(text, color):
        rows.append([('│ ', frame), (f'{text:<{inner}}'[:inner], color), (' │', frame)])

    if info['kind'] or info['duration']:
        line(' · '.join(x for x in (info['kind'], info['duration']) if x), YELLOW if selected else DIM)
    for part in _wrap(info['text'], inner):
        line(part, TEXT if selected else DIM)
    for text, good in info['lines']:
        sign, rest = (text[0], text[1:]) if text[:1] in '+−' else ('•', ' ' + text)
        for i, part in enumerate(_wrap(rest.strip(), inner - 2)):
            line(f"{sign if i == 0 else ' '} {part}", GREEN if good else RED)
    rows.append([('└' + '─' * (width - 2) + '┘', frame)])
    return rows


def compact_row(card, width):
    info = cards.card_info(card)
    name = f"{info['name']}{_KIND_TAGS.get(card['kind'], '')}"
    tag = '' if card['kind'] in ('refuse', 'pact') else info['rarity'].upper()
    text = f'  {name:<{width - len(tag) - 3}}{tag} '[:width]
    return [[(text, RARITY_COLORS.get(info['rarity'], MENU_NORMAL_COLOR))]]


def offer_rows(offer, width, max_rows):
    """Rows for every card: all framed if they fit, else only the selected one framed."""
    full = [card_rows(c, width, i == offer['index']) for i, c in enumerate(offer['cards'])]
    if sum(len(r) for r in full) <= max_rows:
        return full
    return [full[i] if i == offer['index'] else compact_row(c, width) for i, c in enumerate(offer['cards'])]


def _put_row(fb, x, y, row):
    for text, color in row:
        fb.put_string(x, y, text, color)
        x += len(text)


def draw_choice_overlay(fb):
    offer = state.choice.active
    if offer is None or state.game.paused:
        return
    width = constants.layout.width - 2
    x = GAME_X_OFFSET + 1
    card_width = width - 4
    footer = 2 if offer['kind'] == 'egg' else 1
    max_rows = constants.layout.height - 4 - footer
    blocks = offer_rows(offer, card_width, max_rows)
    body = sum(len(b) for b in blocks)
    height = body + 3 + footer
    y = HEADER_HEIGHT + max(0, (constants.layout.height - height) // 2)
    title_color = RARITY_COLORS.get(offer.get('rarity'), YELLOW) if offer['kind'] == 'egg' else RED

    # Clear the panel and frame it
    for row in range(y, y + height + 1):
        fb.put_string(x, row, ' ' * width)
    fb.put_string(x, y, '╔' + '═' * (width - 2) + '╗', MENU_BORDER_COLOR)
    fb.put_string(x + 1, y + 1, offer['title'].center(width - 2), title_color)
    fb.put(x, y + 1, '║', MENU_BORDER_COLOR)
    fb.put(x + width - 1, y + 1, '║', MENU_BORDER_COLOR)
    row_y = y + 2
    for index, block in enumerate(blocks):
        selected = index == offer['index']
        for n, row in enumerate(block):
            fb.put(x, row_y, '║', MENU_BORDER_COLOR)
            if selected and n == (0 if len(block) == 1 else 1):
                fb.put(x + 1, row_y, '▶', YELLOW)
            _put_row(fb, x + 2, row_y, row)
            fb.put(x + width - 1, row_y, '║', MENU_BORDER_COLOR)
            row_y += 1
    if offer['kind'] == 'egg':
        status = f'Rerolls {choices.rerolls_left()}   Skips {choices.skips_left()}'
        fb.put(x, row_y, '║', MENU_BORDER_COLOR)
        fb.put_string(x + 1, row_y, status.center(width - 2), DIM)
        fb.put(x + width - 1, row_y, '║', MENU_BORDER_COLOR)
        row_y += 1
    fb.put_string(x, row_y, '╚' + '═' * (width - 2) + '╝', MENU_BORDER_COLOR)
    template = (
        '{navigate} choose  {take} take  {reroll} reroll  {skip} skip'
        if offer['kind'] == 'egg'
        else '{navigate} choose  {take} buy'
        if offer['kind'] == 'merchant'
        else '{navigate} choose  {take} confirm'
    )
    hint = controls.hint(template)
    fb.put_string(x + max(0, (width - len(hint)) // 2), row_y + 1, hint, MENU_BORDER_COLOR)
