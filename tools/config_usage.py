#!/usr/bin/env python3
"""Find configuration keys the game never reads.

Every section of the configuration is wrapped so that reads are recorded,
then the bot plays through every biome and boss with every bird type, the
menus are walked and every difficulty is loaded. Keys that were never read
and whose name does not appear anywhere in the source are reported.

Usage: python3 tools/config_usage.py
"""

import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.argv = sys.argv[:1]
os.environ['HOME'] = os.environ['USERPROFILE'] = tempfile.mkdtemp(prefix='bvb-usage-')

READ = set()
TRACKING = [True]  # off while the configuration itself is being (re)applied


class TrackedNamespace(SimpleNamespace):
    def __getattribute__(self, name):
        if TRACKING[0] and not name.startswith('__'):
            path = object.__getattribute__(self, '__dict__').get('_path_', '')
            READ.add(f'{path}.{name}' if path else name)
        return object.__getattribute__(self, name)


class TrackedDict(dict):
    """A table read through .get(), [] or iteration."""

    def _mark(self, key=None):
        if not TRACKING[0]:
            return
        if key is None:
            for k in dict.keys(self):
                READ.add(f'{self._path}.{k}')
        else:
            READ.add(f'{self._path}.{key}')

    def __getitem__(self, key):
        self._mark(key)
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        self._mark(key)
        return dict.get(self, key, default)

    def __contains__(self, key):
        self._mark(key)
        return dict.__contains__(self, key)

    def __iter__(self):
        self._mark()
        return dict.__iter__(self)

    def items(self):
        self._mark()
        return dict.items(self)

    def values(self):
        self._mark()
        return dict.values(self)

    def keys(self):
        self._mark()
        return dict.keys(self)


def track(value, path):
    """Label namespaces with their path and wrap the tables inside them."""
    if isinstance(value, TrackedNamespace):
        attrs = object.__getattribute__(value, '__dict__')
        attrs['_path_'] = path
        for name, item in list(attrs.items()):
            if name != '_path_':
                attrs[name] = track(item, f'{path}.{name}')
        return value
    if isinstance(value, dict) and not isinstance(value, TrackedDict):
        tracked = TrackedDict({k: track(v, f'{path}.{k}') for k, v in value.items()})
        tracked._path = path
        return tracked
    return value


def install():
    from src.core import config as config_loader
    from src.core import constants

    # Every namespace the configuration creates from now on records its reads
    config_loader.SimpleNamespace = TrackedNamespace
    for name in constants.SECTIONS:
        setattr(constants, name, TrackedNamespace())
    original_apply = constants._apply

    def tracked_apply(merged):
        TRACKING[0] = False
        try:
            original_apply(merged)
            for name in constants.SECTIONS:
                track(getattr(constants, name), name)
        finally:
            TRACKING[0] = True

    constants._apply = tracked_apply
    constants.configure(1)


def play_everything():
    from src.core import constants
    from src.entities.bird_types import BIRD_TYPES
    from src.sim.bot import PROFILES
    from src.sim.runner import RunConfig, run
    from tests.harness import Simulation

    birds = list(BIRD_TYPES)
    for difficulty in (0, 1, 2, 3):
        constants.configure(difficulty)
    seed = 1
    for level in (1, 3, 4, 6, 7, 9, 10, 12, 13, 15, 16, 18):
        for k in range(0, len(birds), 9):
            formation = (birds[k : k + 9] * 2)[:9]
            run(
                RunConfig(
                    seed=seed,
                    skill=PROFILES['perfect'],
                    start_level=level,
                    formation=formation,
                    max_minutes=4,
                    stop_at_level=min(18, level + 1),
                )
            )
            seed += 1
    # Menus, pause, saves
    with Simulation(seed=3, level=5) as sim:
        sim.run(100)
        for key in ['p'] + ['DOWN', 'ENTER', 'DOWN', 'ENTER', 'ESC', 'ESC', 'UP'] * 8 + ['ESC']:
            sim.step(key=key)


def source_words():
    words = set()
    for path in (ROOT / 'src').rglob('*.py'):
        words.update(re.findall(r'[A-Za-z_][A-Za-z0-9_]*', path.read_text(encoding='utf-8')))
    return words


def unread_keys(config, words):
    unread = []

    def walk(node, path):
        for key, value in node.items():
            full = f'{path}.{key}' if path else str(key)
            if full in READ:
                if isinstance(value, dict) and all(isinstance(k, str) for k in value):
                    walk(value, full)
                continue
            # Read as a whole table or by a computed name: keep
            if any(r.startswith(full + '.') for r in READ):
                if isinstance(value, dict):
                    walk(value, full)
                continue
            if isinstance(key, str) and key in words and not isinstance(value, dict):
                # Name used somewhere in the code: possibly read in a path we did not play
                unread.append((full, 'not read during play, but the name appears in the code'))
            else:
                unread.append((full, 'never read'))

    walk(config, '')
    return unread


def main():
    install()
    from src.core import constants

    play_everything()
    words = source_words()
    for full, why in unread_keys(constants.config, words):
        print(f'{full:60s} {why}')


if __name__ == '__main__':
    main()
