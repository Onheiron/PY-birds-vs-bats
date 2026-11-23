"""Record real games so they can be replayed exactly (tools/replay.py).

A recording holds what the game needs to run again in the same way: the seed,
the difficulty, the configuration, the settings, the meta-progression profile,
the time of every frame and the keys pressed in it.

The play loop shows the game one time per frame: while a frame is processed,
``time.time()`` returns the time the frame started (``FrameTime``), so the
keys, the physics and the timers of one frame all see the same instant, and
the replay can give them that instant again. Pauses and card choices are left
out: the time stands still there and only the frames with keys are kept.

Recordings go to ~/.bvb/recordings/ as gzipped JSON. A game continued from a
save keeps a snapshot of the loaded game (``save``): its replay starts from there.
"""

import copy
import datetime
import gzip
import json
import time
from pathlib import Path

from src.core import constants, state

FORMAT = 1

# Settings that change how the game plays (sound and graphics do not)
GAMEPLAY_SETTINGS = ('bounce_on_enter', 'trigger_on_enter', 'difficulty', 'key_bindings')


def recordings_dir():
    from src.services.save_manager import SAVE_DIR_NAME

    path = Path.home() / SAVE_DIR_NAME / 'recordings'
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = Path.cwd()
    return path


class FrameTime:
    """``time.time`` replacement: the start time of the current frame.

    While the game is held (paused, or a card choice on screen) the time stands
    still: the wall time spent there is left out, so a recording holds no pauses.
    """

    def __init__(self, real=time.time):
        self.real = real
        self.held_total = 0.0  # wall seconds spent held
        self.now = real()
        self._last_real = self.now

    def tick(self, held=False):
        real = self.real()
        if held:
            self.held_total += real - self._last_real
        else:
            self.now = real - self.held_total
        self._last_real = real
        return self.now

    def __call__(self):
        return self.now


class Recorder:
    """Collects one session: header at the start, one entry per frame."""

    def __init__(self, init_time, start_time, profile):
        self.fresh = state.game.frame_count == 0 and state.game.miles == 0
        self.header = {
            'format': FORMAT,
            'version': _version(),
            'date': datetime.datetime.now().isoformat(timespec='seconds'),
            'seed': state.game_seed,
            'difficulty': state.settings.difficulty,
            'settings': {k: copy.deepcopy(getattr(state.settings, k)) for k in GAMEPLAY_SETTINGS},
            'profile': copy.deepcopy(profile),
            'config': copy.deepcopy(constants.config),
            'init_time': init_time,
            'start_time': start_time,
        }
        if not self.fresh:
            from src.services import save_manager

            self.header['save'] = save_manager.snapshot()
        self.times = []  # time of every frame
        self.keys = []  # [frame, [keys]] for the frames with keys

    def frame(self, now, keys, held=False):
        """One frame. A held frame without keys changes nothing in the game: not kept."""
        if held and not keys:
            return
        if keys:
            self.keys.append([len(self.times), list(keys)])
        self.times.append(now)

    def save(self):
        """Write the recording; returns its path (None if nothing to save)."""
        if not self.times:
            return None
        game = state.game
        data = dict(self.header)
        data['result'] = {
            'frames': len(self.times),
            'level': game.level,
            'score': int(game.score),
            'miles': game.miles,
            'lives_left': game.lives,
            'game_over': bool(game.game_over),
        }
        data['times'] = self.times  # exact floats: JSON keeps them bit for bit
        data['keys'] = self.keys
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        path = recordings_dir() / f'{stamp}-seed{self.header["seed"]}-L{game.level}.json.gz'
        try:
            with gzip.open(path, 'wt', encoding='utf-8') as f:
                json.dump(data, f, separators=(',', ':'))
        except OSError:
            return None
        return path


def load(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    if data.get('format') != FORMAT:
        raise ValueError(f'{path}: unknown recording format {data.get("format")}')
    return data


def _version():
    try:
        from src import __version__

        return __version__
    except ImportError:
        return '?'
