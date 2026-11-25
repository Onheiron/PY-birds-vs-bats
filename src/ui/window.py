"""The game in its own window: a small terminal emulator, keyboard and gamepad.

The game draws by writing ANSI text (src/ui/terminal.py). In window mode that
text goes here instead of to a terminal: it is interpreted like a terminal
would (cursor moves, colours, bold, faint, conceal) into a grid of cells, and
the grid is drawn in a window with a monospace font. Keys come from the
window's keyboard and from a gamepad (the Steam Deck's controls included),
turned into the same key names the terminal input gives (src/ui/keyboard.py).

Gamepad layout (Xbox names; on the Steam Deck the same buttons):

  Playing                          Menus, cards, pacts, game over
  D-pad / left stick ← →  move     D-pad / left stick  move the selection
  LB / RB                 move     A  select (ENTER)
  A, D-pad ↑, RT          bounce   B  back (ESC)
  B                       swap     X  reroll (cards)   Y  skip (cards)
  Y                       XP bars  Start  pause / resume
  Start / Select          pause    Select  pause / resume

Typing a name (game over): the D-pad moves on the on-screen keyboard, A types the key,
B deletes, Start confirms.
F11 or Alt+Enter toggles full screen.
"""

import contextlib
import os
import sys
import time
from pathlib import Path

_FONT_DIR = Path(__file__).resolve().parents[2] / 'media' / 'fonts'
ICON = Path(__file__).resolve().parents[2] / 'media' / 'icons' / 'bvb_256.png'
FONT_FILES = ('DejaVuSansMono.ttf', 'DejaVuSansMono-Bold.ttf')

DEFAULT_FG = (204, 204, 204)
BACKGROUND = (0, 0, 0)

# Characters the bundled font lacks, drawn as the closest one it has
SUBSTITUTES = {
    '\u22c0': '\u2227',  # ⋀ -> ∧
    '\u2240': '~',  # ≀
    '\u2322': '\u2312',  # ⌢ -> ⌒
    '\u23dc': '\u2312',  # ⏜ -> ⌒
    '\u26cc': '\u2297',  # ⛌ -> ⊗
    '\u2b2e': '\u25cf',  # ⬮ -> ●
    '\u2b2f': '\u25cb',  # ⬯ -> ○
    '\u3007': '\u25ef',  # 〇 -> ◯
    '\u0f04': '\u2742',  # ༄ -> ❂
    '\U0001f4a7': '\u2666',  # 💧 -> ♦
}

# Box-drawing and block characters fill their whole cell, so lines join up
_FULL_CELL = range(0x2500, 0x25A0)

# Held directions repeat like a keyboard: after this long, this often
REPEAT_DELAY = 0.28
REPEAT_EVERY = 0.075
STICK_DEADZONE = 0.5


def _palette():
    """The 256 xterm colours."""
    base = [
        (0, 0, 0), (205, 49, 49), (13, 188, 121), (229, 229, 16),
        (36, 114, 200), (188, 63, 188), (17, 168, 205), (229, 229, 229),
        (102, 102, 102), (241, 76, 76), (35, 209, 139), (245, 245, 67),
        (59, 142, 234), (214, 112, 214), (41, 184, 219), (255, 255, 255),
    ]  # fmt: skip
    steps = (0, 95, 135, 175, 215, 255)
    cube = [(steps[r], steps[g], steps[b]) for r in range(6) for g in range(6) for b in range(6)]
    greys = [(8 + 10 * i,) * 3 for i in range(24)]
    return base + cube + greys


PALETTE = _palette()


class Cell:
    __slots__ = ('char', 'fg', 'bg', 'bold', 'faint', 'hidden')

    def __init__(self, char=' ', fg=None, bg=None, bold=False, faint=False, hidden=False):
        self.char, self.fg, self.bg, self.bold, self.faint, self.hidden = char, fg, bg, bold, faint, hidden

    def key(self):
        return (self.char, self.fg, self.bg, self.bold, self.faint, self.hidden)


class Screen:
    """A grid of cells fed with ANSI text, like a terminal."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.grid = [[Cell() for _ in range(cols)] for _ in range(rows)]
        self.dirty = set()
        self.x = self.y = 0
        self._reset_style()

    def _reset_style(self):
        self.fg = self.bg = None
        self.bold = self.faint = self.hidden = False

    def clear(self):
        for y, row in enumerate(self.grid):
            for x in range(self.cols):
                row[x] = Cell()
                self.dirty.add((x, y))

    def feed(self, text):
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if ch == '\033' and i + 1 < n and text[i + 1] == '[':
                j = i + 2
                while j < n and not ('@' <= text[j] <= '~'):
                    j += 1
                if j >= n:
                    break
                self._csi(text[i + 2 : j], text[j])
                i = j + 1
                continue
            if ch == '\n':
                self.x, self.y = 0, self.y + 1
            elif ch == '\r':
                self.x = 0
            elif ch >= ' ':
                self._put(ch)
            i += 1

    def _put(self, ch):
        if 0 <= self.y < self.rows and 0 <= self.x < self.cols:
            self.grid[self.y][self.x] = Cell(ch, self.fg, self.bg, self.bold, self.faint, self.hidden)
            self.dirty.add((self.x, self.y))
        self.x += 1

    def _csi(self, params, final):
        if params.startswith('?'):
            return  # private modes: alternate screen, cursor, synchronized output
        if final == 'm':
            self._sgr(params)
        elif final in ('H', 'f'):
            parts = params.split(';') if params else []
            row = int(parts[0]) if parts and parts[0] else 1
            col = int(parts[1]) if len(parts) > 1 and parts[1] else 1
            self.y, self.x = row - 1, col - 1
        elif final == 'J':
            self.clear()
        elif final == 'K':
            for x in range(self.x, self.cols):
                if 0 <= self.y < self.rows:
                    self.grid[self.y][x] = Cell()
                    self.dirty.add((x, self.y))

    def _sgr(self, params):
        codes = [int(p) if p.isdigit() else 0 for p in params.split(';')] if params else [0]
        i = 0
        while i < len(codes):
            c = codes[i]
            if c == 0:
                self._reset_style()
            elif c == 1:
                self.bold = True
            elif c == 2:
                self.faint = True
            elif c == 8:
                self.hidden = True
            elif c == 22:
                self.bold = self.faint = False
            elif c == 28:
                self.hidden = False
            elif c in (38, 48) and i + 1 < len(codes):
                if codes[i + 1] == 5 and i + 2 < len(codes):
                    colour = PALETTE[codes[i + 2] % 256]
                    i += 2
                elif codes[i + 1] == 2 and i + 4 < len(codes):
                    colour = tuple(max(0, min(255, v)) for v in codes[i + 2 : i + 5])
                    i += 4
                else:
                    colour = None
                    i += 1
                if c == 38:
                    self.fg = colour
                else:
                    self.bg = colour
            elif c == 39:
                self.fg = None
            elif c == 49:
                self.bg = None
            elif 30 <= c <= 37:
                self.fg = PALETTE[c - 30]
            elif 90 <= c <= 97:
                self.fg = PALETTE[c - 90 + 8]
            elif 40 <= c <= 47:
                self.bg = PALETTE[c - 40]
            elif 100 <= c <= 107:
                self.bg = PALETTE[c - 100 + 8]
            i += 1


class Window:
    """The window, its fonts and the input devices (pygame)."""

    def __init__(self, cols, rows, fullscreen=False, title='BVB - Birds vs Bats'):
        import pygame

        self.pg = pygame
        os.environ.setdefault('SDL_HINT_JOYSTICK_ALLOW_BACKGROUND_EVENTS', '1')
        pygame.display.init()
        pygame.font.init()
        pygame.joystick.init()
        from pygame._sdl2 import controller

        controller.init()
        self.sdl_controller = controller
        pygame.display.set_caption(title)
        with contextlib.suppress(pygame.error, FileNotFoundError):
            pygame.display.set_icon(pygame.image.load(str(ICON)))  # the Dock, the taskbar
        self.screen = Screen(cols, rows)
        self.fullscreen = fullscreen
        self._open()
        self.controllers = {}
        self._scan_controllers()
        self.held = {}  # direction -> (next repeat time)
        self.last_device = 'keyboard'  # the control profile of the device used last (src/ui/controls.py)
        self.stick = {'x': 0, 'y': 0}
        self.trigger_down = False
        pygame.key.set_repeat(int(REPEAT_DELAY * 1000), int(REPEAT_EVERY * 1000))
        pygame.key.start_text_input()

    # ------------------------------------------------------------------ display

    def _open(self):
        pg = self.pg
        if self.fullscreen:
            self.surface = pg.display.set_mode((0, 0), pg.FULLSCREEN)
        else:
            info = pg.display.Info()
            width = min(1280, int(info.current_w * 0.9) if info.current_w > 0 else 1280)
            height = min(800, int(info.current_h * 0.9) if info.current_h > 0 else 800)
            self.surface = pg.display.set_mode((width, height), pg.RESIZABLE)
        pg.mouse.set_visible(not self.fullscreen)
        self._layout()

    def _layout(self):
        """Cell size and fonts for the window size; everything redrawn."""
        width, height = self.surface.get_size()
        cols, rows = self.screen.cols, self.screen.rows
        self.cw = max(4, width // cols)
        self.ch = max(8, height // rows)
        self.ox = (width - self.cw * cols) // 2
        self.oy = (height - self.ch * rows) // 2
        # The largest font whose glyphs fit the cell
        size = self.ch
        while size > 6:
            font = self._font(False, size)
            advance = font.size('M')[0]
            if advance <= self.cw and font.get_linesize() <= self.ch + 1:
                break
            size -= 1
        self.fonts = {False: self._font(False, size), True: self._font(True, size)}
        self.glyphs = {}
        self.surface.fill(BACKGROUND)
        self.screen.dirty = {(x, y) for y in range(rows) for x in range(cols)}
        self.font_size = size

    def _font(self, bold, size):
        pg = self.pg
        path = _FONT_DIR / FONT_FILES[1 if bold else 0]
        if path.exists():
            return pg.font.Font(str(path), size)
        return pg.font.SysFont('dejavusansmono,monospace', size, bold=bold)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self._open()

    def write(self, text):
        self.screen.feed(text)
        self.present()

    def _glyph(self, cell):
        key = cell.key()
        glyph = self.glyphs.get(key)
        if glyph is not None:
            return glyph
        pg = self.pg
        fg = cell.fg or DEFAULT_FG
        if cell.faint:
            fg = tuple(int(c * 0.55) for c in fg)
        bg = cell.bg or BACKGROUND
        glyph = pg.Surface((self.cw, self.ch))
        glyph.fill(bg)
        if not cell.hidden and cell.char != ' ':
            text = self.fonts[cell.bold].render(SUBSTITUTES.get(cell.char, cell.char), True, fg)
            if ord(cell.char) in _FULL_CELL:
                text = pg.transform.smoothscale(text, (self.cw, self.ch))
                glyph.blit(text, (0, 0))
            else:
                x = (self.cw - text.get_width()) // 2
                y = (self.ch - text.get_height()) // 2
                glyph.blit(text, (x, y))
        self.glyphs[key] = glyph
        return glyph

    def present(self):
        screen = self.screen
        if not screen.dirty:
            return
        blit = self.surface.blit
        grid = screen.grid
        cw, ch, ox, oy = self.cw, self.ch, self.ox, self.oy
        for x, y in screen.dirty:
            blit(self._glyph(grid[y][x]), (ox + x * cw, oy + y * ch))
        screen.dirty = set()
        self.pg.display.flip()

    # ------------------------------------------------------------------ input

    def _scan_controllers(self):
        """Open every connected gamepad SDL knows (Xbox, PlayStation, Steam Deck via Steam Input...)."""
        pg, sdl = self.pg, self.sdl_controller
        for index in range(sdl.get_count()):
            with contextlib.suppress(pg.error):
                if sdl.is_controller(index):
                    pad = sdl.Controller(index)
                    self.controllers[pad.as_joystick().get_instance_id()] = pad

    def _context(self):
        """'play', 'menu' or 'text': what the gamepad buttons mean now."""
        from src.core import state

        if self._text:
            return 'text'
        if state.ui.show_title or state.game.paused or state.choice.active is not None or state.game.game_over:
            return 'menu'
        return 'play'

    # Gamepad buttons and axes (SDL game controller order)
    A, B, X, Y, BACK, GUIDE, START = 0, 1, 2, 3, 4, 5, 6
    LB, RB = 9, 10
    DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT = 11, 12, 13, 14
    AXIS_LEFT_X, AXIS_LEFT_Y, AXIS_RIGHT_TRIGGER = 0, 1, 5

    def _button_key(self, button):
        context = self._context()
        if button in (self.DPAD_LEFT, self.LB):
            return 'LEFT'
        if button in (self.DPAD_RIGHT, self.RB):
            return 'RIGHT'
        if button == self.DPAD_UP:
            return 'UP'
        if button == self.DPAD_DOWN:
            return 'DOWN'
        if button in (self.START, self.BACK):
            return 'p' if context != 'text' else 'ENTER'
        if context == 'text':
            return {self.A: 'PICK', self.B: 'BACKSPACE'}.get(button)  # A types the on-screen key
        if context == 'menu':
            return {self.A: 'ENTER', self.B: 'ESC', self.X: 'r', self.Y: 's'}.get(button)
        return {self.A: 'UP', self.B: 'SPACE', self.Y: 'x'}.get(button)

    def _pad_profile(self, instance_id):
        """Control profile of a gamepad, from its name: playstation, steamdeck or xbox."""
        pad = self.controllers.get(instance_id)
        name = (getattr(pad, 'name', '') or '').lower()
        if any(word in name for word in ('playstation', 'dualshock', 'dualsense', 'ps3', 'ps4', 'ps5', 'sony')):
            return 'playstation'
        if 'steam deck' in name or 'steamdeck' in name:
            return 'steamdeck'
        return 'xbox'

    def _press_direction(self, key, keys):
        keys.append(key)
        self.held[key] = time.monotonic() + REPEAT_DELAY

    def read_keys(self, text=False):
        """Keys pressed since the last call, as key names (see src/ui/keyboard.py)."""
        pg = self.pg
        self._text = text
        keys = []
        for event in pg.event.get():
            if event.type == pg.QUIT:
                keys.append('QUIT')
            elif event.type in (pg.VIDEORESIZE, pg.WINDOWSIZECHANGED) and not self.fullscreen:
                self.surface = pg.display.get_surface()
                self._layout()
            elif event.type in (pg.KEYDOWN, pg.TEXTINPUT):
                self.last_device = 'keyboard'
            if event.type == pg.KEYDOWN:
                if event.key == pg.K_F11 or (event.key == pg.K_RETURN and event.mod & pg.KMOD_ALT):
                    self.toggle_fullscreen()
                    continue
                name = {
                    pg.K_LEFT: 'LEFT',
                    pg.K_RIGHT: 'RIGHT',
                    pg.K_UP: 'UP',
                    pg.K_DOWN: 'DOWN',
                    pg.K_RETURN: 'ENTER',
                    pg.K_KP_ENTER: 'ENTER',
                    pg.K_ESCAPE: 'ESC',
                    pg.K_BACKSPACE: 'BACKSPACE',
                }.get(event.key)
                if name:
                    keys.append(name)
                elif event.key == pg.K_c and event.mod & pg.KMOD_CTRL:
                    keys.append('QUIT')
            elif event.type == pg.TEXTINPUT:
                for char in event.text:
                    if char == ' ':
                        keys.append('SPACE' if not text else ' ')
                    elif char == 'q' and not text:
                        keys.append('QUIT')
                    elif char.isprintable():
                        keys.append(char)
            elif event.type == pg.CONTROLLERDEVICEADDED:
                self._scan_controllers()
            elif event.type == pg.CONTROLLERDEVICEREMOVED:
                self.controllers.pop(event.instance_id, None)
            elif event.type == pg.CONTROLLERBUTTONDOWN:
                self.last_device = self._pad_profile(event.instance_id)
                key = self._button_key(event.button)
                if key in ('LEFT', 'RIGHT', 'UP', 'DOWN'):
                    self._press_direction(key, keys)
                elif key:
                    keys.append(key)
            elif event.type == pg.CONTROLLERBUTTONUP:
                key = self._button_key(event.button)
                self.held.pop(key, None)
            elif event.type == pg.CONTROLLERAXISMOTION:
                self._axis(event.axis, event.value / 32767, keys)
        # Held directions repeat
        now = time.monotonic()
        for key, due in list(self.held.items()):
            if now >= due:
                keys.append(key)
                self.held[key] = now + REPEAT_EVERY
        self.present()
        if text:
            return keys
        collapsed = []
        for key in keys:
            if not collapsed or collapsed[-1] != key:
                collapsed.append(key)
        return collapsed

    _text = False

    def _axis(self, axis, value, keys):
        """Left stick: directions; right trigger: bounce."""
        if axis in (self.AXIS_LEFT_X, self.AXIS_LEFT_Y):
            name = 'x' if axis == 0 else 'y'
            step = -1 if value < -STICK_DEADZONE else 1 if value > STICK_DEADZONE else 0
            if step == self.stick[name]:
                return
            old = self.stick[name]
            self.stick[name] = step
            pairs = ('LEFT', 'RIGHT') if axis == 0 else ('UP', 'DOWN')
            if old:
                self.held.pop(pairs[0] if old < 0 else pairs[1], None)
            if step:
                self._press_direction(pairs[0] if step < 0 else pairs[1], keys)
        elif axis == self.AXIS_RIGHT_TRIGGER:
            down = value > 0.5
            if down and not self.trigger_down and self._context() == 'play':
                keys.append('UP')
            self.trigger_down = down

    def close(self):
        with contextlib.suppress(Exception):
            self.pg.quit()


_window = None


def active():
    return _window is not None


def open_window(fullscreen=False):
    """Open the game window (sized for the game's layout)."""
    global _window
    from src.ui.layout import TOTAL_HEIGHT, TOTAL_WIDTH

    _window = Window(TOTAL_WIDTH, TOTAL_HEIGHT, fullscreen=fullscreen)
    return _window


def get():
    return _window


def close_window():
    global _window
    if _window is not None:
        _window.close()
        _window = None


def frozen():
    """Running as a bundled binary (PyInstaller)?"""
    return getattr(sys, 'frozen', False)
