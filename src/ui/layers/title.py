"""Title screen: the home.

    logo                                                        v<version>
    ┌ MAIN MENU ┐ ┌ NEWS ──────────────┐ ┌ LEADERBOARD ───────┐
    │ entries   │ │ version, update,   │ │ this week, the     │
    │ ❖ feathers│ │ what's new         │ │ difficulty chosen  │
    └───────────┘ └────────────────────┘ └────────────────────┘
    ┌ FLOCK ───────────────────────────────────────────────────┐
    │ starting lanes            │ feathers, upgrades, birds    │
    └──────────────────────────────────────────────────────────┘

Every text is cut to its box: nothing ever runs out of it. Submenus open over
the home (src/ui/layers/menus.py).
"""

from src import __version__
from src.core import state
from src.engine import menus
from src.entities.sprites import GREEN, YELLOW
from src.ui import controls, terminal
from src.ui.colors import MENU_BORDER_COLOR, MENU_SELECTED_COLOR
from src.ui.framebuffer import get_framebuffer
from src.ui.layers.menus import draw_screen, hint_text, title_style
from src.ui.layout import TOTAL_HEIGHT, TOTAL_WIDTH

# ASCII art logo for title screen
TITLE_LOGO = [
    "    ▄▄▄                                          ▄▄▄                 ",
    "   ██▀▀█▄            █▄                         ██▀▀█▄       █▄      ",
    "   ██ ▄█▀ ▀▀ ▄       ██                         ██ ▄█▀      ▄██▄     ",
    "   ██▀▀█▄ ██ ████▄▄████ ▄██▀█  ▀█▄ ██▀▄██▀█     ██▀▀█▄ ▄▀▀█▄ ██ ▄██▀█",
    " ▄ ██  ▄█ ██ ██   ██ ██ ▀███▄   ██▄██ ▀███▄   ▄ ██  ▄█ ▄█▀██ ██ ▀███▄",
    " ▀██████▀▄██▄█▀  ▄█▀████▄▄██▀    ▀█▀ █▄▄██▀   ▀██████▀▄▀█▄██▄███▄▄██▀",
]
DIM = '\033[38;5;244m'
TEXT = '\033[38;5;250m'
CYAN = '\033[38;5;80m'
FEATHER = '\033[1;38;5;223m'

LOGO_Y = 1
BOXES_Y = 9
BOXES_H = 15
MENU_X, MENU_W = 1, 31
NEWS_X, NEWS_W = 33, 42
BOARD_X, BOARD_W = 76, 40
STRIP_Y, STRIP_H = 25, 10


def text(fb, x, y, value, width, color=''):
    """``value`` at (x, y), cut to ``width`` columns."""
    if width > 0:
        fb.put_string(x, y, str(value)[:width], color)


def box(fb, x, y, w, h, title):
    fb.put_string(x, y, '╔' + '═' * (w - 2) + '╗', MENU_BORDER_COLOR)
    for row in range(1, h - 1):
        fb.put(x, y + row, '║', MENU_BORDER_COLOR)
        fb.put_string(x + 1, y + row, ' ' * (w - 2))
        fb.put(x + w - 1, y + row, '║', MENU_BORDER_COLOR)
    fb.put_string(x, y + h - 1, '╚' + '═' * (w - 2) + '╝', MENU_BORDER_COLOR)
    label = f' {title} '[: w - 4]
    fb.put_string(x + (w - len(label)) // 2, y, label, YELLOW)


def wrap(line, width):
    words, out, current = str(line).split(), [], ''
    for word in words:
        if current and len(current) + 1 + len(word) > width:
            out.append(current)
            current = word
        else:
            current = f'{current} {word}' if current else word
    if current:
        out.append(current)
    return out


def render_title_screen():
    """Render the home: logo, main menu, news, leaderboard, flock, and any open submenu."""
    fb = get_framebuffer()
    fb.clear()

    logo_width = max(len(line) for line in TITLE_LOGO)
    logo_x = max(0, (TOTAL_WIDTH - logo_width) // 2)
    for i, line in enumerate(TITLE_LOGO):
        fb.put_string(logo_x, LOGO_Y + i, line, YELLOW)
    _draw_version(fb, logo_x + logo_width, LOGO_Y + len(TITLE_LOGO))

    if menus.root() != menus.TITLE:
        menus.open_title()
    stack = state.ui.menu_stack
    selected = stack[0][1]
    _draw_main_menu(fb, selected)
    _draw_news(fb)
    _draw_board(fb)
    _draw_flock(fb)

    items = menus.SCREENS[menus.TITLE].items()
    if len(stack) == 1:
        # LEFT/RIGHT only does something on entries with a value (NEW GAME)
        if items[selected].on_change:
            hint = controls.hint("{navigate} Navigate  {change} Difficulty  {select} Start")
        else:
            hint = hint_text('root')
        text(fb, max(0, (TOTAL_WIDTH - len(hint)) // 2), TOTAL_HEIGHT - 1, hint, TOTAL_WIDTH, MENU_BORDER_COLOR)
    else:
        # Submenus open as an overlay on top of the home
        draw_screen(fb, title_style(BOXES_Y), menus.current_screen(), menus.cursor())

    terminal.write_frame(fb.render())


# --------------------------------------------------------------------------- the version


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
    if state_ == 'check_failed':
        return f'v{__version__}  ·  no update check ({status.get("error") or "offline"})', MENU_BORDER_COLOR
    return f'v{__version__}', MENU_BORDER_COLOR


def _draw_version(fb, right, y):
    value, color = version_line()
    fb.put_string(max(0, right - len(value)), y, value, color)


# --------------------------------------------------------------------------- the boxes


def _draw_main_menu(fb, selected):
    box(fb, MENU_X, BOXES_Y, MENU_W, BOXES_H, 'MAIN MENU')
    inner = MENU_W - 4
    items = menus.SCREENS[menus.TITLE].items()
    for i, item in enumerate(items[: BOXES_H - 4]):
        # A value with LEFT / RIGHT (NEW GAME's difficulty) is shown; others are in the submenus
        label = f'{item.name}  < {item.value()} >' if item.value and item.on_change else item.name
        if item.value and not item.on_change and item.kind == 'option':
            label = f'{item.name}  {item.value()}'  # UPDATING 45%
        on = i == selected
        color = MENU_SELECTED_COLOR if on else TEXT
        text(fb, MENU_X + 2, BOXES_Y + 1 + i, ('▶ ' if on else '  ') + label, inner, color)
    feathers = (state.meta.profile or {}).get('gold', 0)
    text(fb, MENU_X + 2, BOXES_Y + BOXES_H - 2, f'❖ {feathers} feathers', inner, FEATHER)


def _bullet(note, width):
    parts = wrap(note, width - 2)
    return [('• ' if i == 0 else '  ') + part for i, part in enumerate(parts)]


def _draw_news(fb):
    from src.services import updater
    from src.ui import news

    box(fb, NEWS_X, BOXES_Y, NEWS_W, BOXES_H, 'NEWS')
    inner = NEWS_W - 4
    status = updater.status
    lines = []
    if status.get('state') in ('available', 'downloading', 'ready'):
        lines.append((f"v{status['version']} is out: UPDATE", YELLOW))
        for note in status.get('notes') or []:
            lines += [(part, TEXT) for part in _bullet(note, inner)]
        lines.append(('', ''))
    else:
        lines.append((f'v{__version__} · up to date ✓' if updater.enabled() else f'v{__version__}', GREEN))
        lines.append(('', ''))
    lines.append(("WHAT'S NEW", YELLOW))
    for note in news.notes(__version__) or ['See CHANGELOG.md']:
        lines += [(part, TEXT) for part in _bullet(note, inner)]
    for i, (value, color) in enumerate(lines[: BOXES_H - 2]):
        text(fb, NEWS_X + 2, BOXES_Y + 1 + i, value, inner, color)


def _draw_board(fb):
    from src.engine.menus import DIFFICULTY_NAMES
    from src.services import online

    box(fb, BOARD_X, BOXES_Y, BOARD_W, BOXES_H, 'LEADERBOARD')
    inner = BOARD_W - 4
    x, y = BOARD_X + 2, BOXES_Y + 1
    text(fb, x, y, f'THIS WEEK · {DIFFICULTY_NAMES[state.settings.difficulty]}', inner, CYAN)
    entries = online.board('week')
    if entries == 'offline':
        text(fb, x, y + 2, 'Offline: no leaderboard.', inner, DIM)
        text(fb, x, y + 3, 'SETTINGS > ONLINE', inner, DIM)
        return
    if entries is None:
        text(fb, x, y + 2, 'Loading...', inner, DIM)
        return
    if not entries:
        text(fb, x, y + 2, 'Nobody yet this week:', inner, TEXT)
        text(fb, x, y + 3, 'be the first!', inner, TEXT)
        return
    mine = (online.account() or {}).get('uid')
    text(fb, x, y + 1, f"{'#':>3}  {'NAME':<12}{'SCORE':>10}  LV", inner, DIM)
    for rank, entry in enumerate(entries[:9], 1):
        me = entry.get('uid') == mine
        row = f"{'>' if me else ' '}{rank:>2}  {str(entry.get('name', '?'))[:11]:<12}"
        row += f"{int(entry.get('score', 0)):>10,}  {entry.get('level', '')}"
        text(fb, x, y + 1 + rank, row, inner, YELLOW if me else TEXT)
    best = next((i for i, e in enumerate(entries, 1) if e.get('uid') == mine), None)
    if best:
        text(fb, x, BOXES_Y + BOXES_H - 2, f"Your best: #{best} · {int(entries[best - 1]['score']):,}", inner, YELLOW)


def _draw_flock(fb):
    from src.engine import meta
    from src.entities.bird_types import BirdType, get_color_for_bird_type

    box(fb, MENU_X, STRIP_Y, TOTAL_WIDTH - 2, STRIP_H, 'FLOCK')
    profile = state.meta.profile or meta.new_profile()
    lanes = meta.formation() if state.meta.profile else None
    shown = lanes or meta.default_flock()
    text(fb, 3, STRIP_Y + 1, 'STARTING LANES' + ('' if lanes else ' · random'), 55, YELLOW)
    for lane, bird in enumerate(shown):
        x = 4 + lane * 6
        color = get_color_for_bird_type(bird)
        fb.put_string(x, STRIP_Y + 3, ' . ', color)
        fb.put_string(x, STRIP_Y + 4, '/W\\', color)
        fb.put_string(x, STRIP_Y + 6, f' {lane + 1}', DIM)
    text(fb, 3, STRIP_Y + 8, 'FLOCK > FORMATION to set them', 55, DIM)

    x, width = 58, TOTAL_WIDTH - 2 - 58 - 2
    last = profile.get('last_run')
    text(fb, x, STRIP_Y + 1, 'FEATHERS', width, YELLOW)
    text(fb, x, STRIP_Y + 2, f'❖ {profile.get("gold", 0)} to spend', width, FEATHER)
    if last:
        line = f"last run: +{last['reward']} (level {last['level']}, {last['bosses']} bosses, {last['bats']} bats)"
        text(fb, x, STRIP_Y + 3, line, width, TEXT)
    owned = top = 0
    bars = []
    for branch in menus._branches() if state.meta.profile else []:
        ids = menus._upgrade_ids(branch)
        have = sum(meta.level_of(u) for u in ids)
        most = sum(len(meta._as_dict(meta.upgrades()[u]).get('costs', [])) for u in ids)
        owned, top = owned + have, top + most
        filled = round(4 * have / most) if most else 0
        bars.append(f"{branch[:6]:<6} {'█' * filled}{'▒' * (4 - filled)}")
    text(fb, x, STRIP_Y + 5, f'UPGRADES  {owned}/{top} levels', width, YELLOW)
    for row in range(0, min(len(bars), 8), 4):
        text(fb, x, STRIP_Y + 6 + row // 4, '  '.join(bars[row : row + 4]), width, TEXT)
    names = [n for n in dir(BirdType) if n.isupper()]
    found = sum(1 for n in names if getattr(BirdType, n) in set(state.discovery.birds))
    text(fb, x, STRIP_Y + 8, f'BIRDS  {found}/{len(names)} discovered', width, YELLOW)
