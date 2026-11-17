"""Headless simulation harness.

Runs the real game loop (input -> miles -> physics -> logic -> render) without a
terminal: the clock is virtual, keys are scripted from a private RNG and the
frame output is fed to a tiny ANSI terminal emulator instead of stdout.

Everything is deterministic for a given (seed, scenario), which makes the
harness usable for replay tests, golden-master comparisons and benchmarks.
"""

import hashlib
import random
import re
import time

FRAME_DT = 1.0 / 60.0
_KEYS = ['LEFT', 'RIGHT', 'UP', 'UP', 'UP', 'DOWN', 'SPACE', None, None, None]
_SGR_OR_CUP = re.compile(r'\033\[([0-9;]*)([Hm]|2J)')
# Private modes (synchronized output, cursor, alternate screen) do not draw anything
_PRIVATE_MODE = re.compile(r'\033\[\?[0-9;]*[hl]')


class FakeClock:
    """Virtual replacement for time.time()."""

    def __init__(self, start=1_700_000_000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


class Screen:
    """Minimal ANSI terminal: cursor positioning, clear and SGR state."""

    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.cells = [[(' ', ()) for _ in range(width)] for _ in range(height)]
        self.x = 0
        self.y = 0
        self.style = ()

    def feed(self, data):
        data = _PRIVATE_MODE.sub('', data)
        pos = 0
        for match in _SGR_OR_CUP.finditer(data):
            self._write(data[pos : match.start()])
            pos = match.end()
            args, kind = match.group(1), match.group(2)
            if kind == 'm':
                self.style = () if args in ('', '0') else self.style + (args,)
            elif kind == 'H':
                if args:
                    row, col = args.split(';')
                    self.y, self.x = int(row) - 1, int(col) - 1
                else:
                    self.y = self.x = 0
            else:  # 2J
                self.cells = [[(' ', ()) for _ in range(self.width)] for _ in range(self.height)]
        self._write(data[pos:])

    def _write(self, text):
        for ch in text:
            if 0 <= self.y < self.height and 0 <= self.x < self.width:
                self.cells[self.y][self.x] = (ch, self.style)
            self.x += 1

    def text(self):
        return '\n'.join(''.join(c for c, _ in row).rstrip() for row in self.cells)

    def digest(self):
        return hashlib.sha256(repr(self.cells).encode()).hexdigest()


class _Sink:
    """Stand-in for sys.stdout that records what the renderer writes."""

    def __init__(self):
        self.chunks = []

    def write(self, data):
        self.chunks.append(data)

    def flush(self):
        pass


def _freeze(value):
    """Order-independent, repr-stable view of a state value."""
    if isinstance(value, dict):
        return sorted((repr(k), _freeze(v)) for k, v in value.items())
    if isinstance(value, (set, frozenset)):
        return sorted(repr(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [_freeze(v) for v in value]
    if isinstance(value, float):
        return round(value, 9)
    return value


# Fields that describe how time is measured, not the world itself
_BOOKKEEPING = {'clock_offset'}


def state_digest():
    from src.core import state

    parts = []
    for name in ('birds', 'special', 'enemies', 'items', 'spells', 'powerups', 'game', 'player'):
        values = {k: v for k, v in vars(getattr(state, name)).items() if k not in _BOOKKEEPING}
        parts.append((name, _freeze(values)))
    return hashlib.sha256(repr(parts).encode()).hexdigest()


class Simulation:
    """One deterministic game session driven frame by frame."""

    def __init__(self, seed=1234, level=1, key_rate=0.35, all_birds=False, near_boss=False):
        from src.core import constants, state
        from src.engine import input_handler, loop, progression
        from src.ui import framebuffer, render

        self.state = state
        self.constants = constants
        self.render = render
        self.input_handler = input_handler
        self.session = loop.Session()

        self.clock = FakeClock()
        self._real_time = time.time
        time.time = self.clock
        self._patch_save_timestamps()

        self.keys = random.Random(seed ^ 0xBEEF)
        self.key_rate = key_rate

        constants.reload_for_difficulty(1)
        state.init(seed)
        state.ui.show_title = False
        state.ui.menu_stack = []
        state.game.start_time = self.clock.now
        state.game.last_mile_update = self.clock.now
        if all_birds:
            self._use_all_bird_types()
        milestones = progression.get_level_milestones()
        if near_boss:
            # Just before the end of the level, where end-of-biome bosses spawn.
            state.game.miles = float(milestones[level - 1]) - 0.5
        elif level > 1:
            state.game.miles = float(milestones[level - 2]) + 0.01
        progression.update_miles(1e-9)

        framebuffer.reset_framebuffer()
        self.fb = framebuffer.get_framebuffer()
        self.screen = Screen(self.fb.width, self.fb.height)
        self.output_bytes = 0
        self.frame = 0
        self._captured = []
        self._real_write = None

    def _use_all_bird_types(self):
        from src.entities.bird_types import BIRD_TYPES, get_color_for_bird_type, get_default_speed

        types = list(BIRD_TYPES)
        for i in range(len(self.state.birds.colors)):
            bird_type = types[i % len(types)]
            self.state.birds.colors[i] = get_color_for_bird_type(bird_type)
            self.state.birds.speeds[i] = get_default_speed(bird_type)

    def _patch_save_timestamps(self):
        """Make save files carry virtual-clock timestamps."""
        import datetime as _dt

        from src.services import save_manager

        clock = self.clock
        epoch = _dt.datetime(2024, 1, 1)
        start = clock.now

        class _FakeDatetime(_dt.datetime):
            @classmethod
            def now(cls, tz=None):
                return epoch + _dt.timedelta(seconds=clock.now - start)

        self._save_manager = save_manager
        self._real_datetime = save_manager.datetime
        save_manager.datetime = _FakeDatetime

    def close(self):
        time.time = self._real_time
        self._save_manager.datetime = self._real_datetime

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def next_key(self):
        if self.keys.random() < self.key_rate:
            return self.keys.choice(_KEYS)
        return None

    def step(self, key='auto', render=True):
        """Advance one 60 FPS frame, mirroring game.run_game()."""
        if key == 'auto':
            key = self.next_key()
        self.input_handler.process_input(key)
        self.session.step()

        if render:
            out = self.render_frame()
            self.output_bytes += len(out)
            self.screen.feed(out)

        self.frame += 1
        self.clock.advance(FRAME_DT)

    def render_frame(self, title=False):
        """Render the current frame and return what would be written to stdout."""
        import sys

        sink = _Sink()
        captured = sink.chunks
        real = sys.stdout
        sys.stdout = sink
        try:
            if title:
                from src.ui.layers.title import render_title_screen

                render_title_screen()
            else:
                self.render.render_game()
        finally:
            sys.stdout = real
        return ''.join(captured)

    def press(self, key, title=False):
        """Send one key outside the simulation loop and redraw (menus, title)."""
        self.input_handler.process_input(key)
        out = self.render_frame(title=title)
        self.output_bytes += len(out)
        self.screen.feed(out)
        self.clock.advance(FRAME_DT)

    def keep_alive(self):
        """Stop the session from ending so long scenarios can run."""
        state = self.state
        state.game.game_over = False
        if state.game.lives < 3:
            state.game.lives = 5

    def run(self, frames, immortal=True, digest_every=0):
        digests = []
        for _ in range(frames):
            self.step()
            if immortal:
                self.keep_alive()
            if digest_every and self.frame % digest_every == 0:
                digests.append((state_digest(), self.screen.digest()))
        return digests
