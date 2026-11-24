#!/usr/bin/env python3
"""Replay recorded games (~/.bvb/recordings/), study how they were played,
and compare them with the bot on the same seed.

Every game started from NEW GAME is recorded when it ends (src/engine/recorder.py):
seed, difficulty, configuration, settings, upgrades, the time of every frame and
every key. Replaying one runs the very same game again, headless.

Examples:

  python3 tools/replay.py --list
  python3 tools/replay.py                       # the latest recording
  python3 tools/replay.py FILE.json.gz --bot expert --bot average
  python3 tools/replay.py --bot expert --bot-set key_interval=10

The report shows, for the player and for each bot: how long the game lasted,
the level reached, the keys per second (moves and UP apart, and the busiest
second), how far birds had fallen when they were bounced, the time between a
move and the UP that follows it (two hands press both at once), the powers
fired and the swaps, and how the birds were lost.
"""

import argparse
import os
import statistics
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def recordings():
    folder = Path.home() / '.bvb' / 'recordings'
    return sorted(folder.glob('*.json.gz')) if folder.is_dir() else []


class Observer:
    """Keys and bounces seen while a game plays (patched into the input path)."""

    def __init__(self):
        self.keys = []  # (game seconds, key)
        self.bounce_rows = []

    def install(self):
        import time as time_module

        from src.core import state
        from src.engine import actions, input_handler

        self._saved = (input_handler.process_input, actions._bounce_bird_up)
        original_input, original_bounce = self._saved
        start = [None]

        def process_input(key):
            now = time_module.time()
            if start[0] is None:
                start[0] = state.game.start_time
            self.keys.append((now - start[0], key))
            return original_input(key)

        def bounce(i):
            self.bounce_rows.append(state.birds.y[i])
            return original_bounce(i)

        input_handler.process_input = process_input
        actions._bounce_bird_up = bounce
        # the runner imported process_input by module, so patching the module is enough

    def uninstall(self):
        from src.engine import actions, input_handler

        input_handler.process_input, actions._bounce_bird_up = self._saved


def describe(name, summary, observer):
    from src.core import constants

    minutes = summary['minutes'] or 1e-9
    seconds = minutes * 60
    keys = observer.keys
    moves = [t for t, k in keys if k in ('LEFT', 'RIGHT')]
    ups = [t for t, k in keys if k == 'UP']
    swaps = sum(1 for _t, k in keys if k == 'SPACE')
    busiest = max(Counter(int(t) for t, _k in keys).values(), default=0)
    # Time from a move to the UP right after it (two hands: close to zero)
    gaps = []
    j = 0
    for t in ups:
        while j + 1 < len(moves) and moves[j + 1] <= t:
            j += 1
        if moves and moves[j] <= t and t - moves[j] < 1.0:
            gaps.append(t - moves[j])
    floor = constants.layout.height - 1
    rows = observer.bounce_rows
    deaths = Counter(d['cause'] for d in summary.get('deaths', []))
    powers = {k: v for k, v in summary.get('powers', {}).items() if ' ' not in k}
    line = {
        'minutes': f'{minutes:.1f}',
        'level': summary['level'],
        'score': f'{summary["score"]:,}',
        'keys/s': f'{len(keys) / seconds:.2f}',
        'moves/s': f'{len(moves) / seconds:.2f}',
        'UP/s': f'{len(ups) / seconds:.2f}',
        'busiest second (keys)': busiest,
        'move → UP (median ms)': f'{statistics.median(gaps) * 1000:.0f}' if gaps else '-',
        f'bounce row (median, 0 = top, {floor} = floor)': f'{statistics.median(rows):.0f}' if rows else '-',
        'bounces / min': f'{len(rows) / minutes:.0f}',
        'swaps': swaps,
        'powers fired / min': f'{sum(powers.values()) / minutes:.1f}',
        'birds lost': sum(deaths.values()),
        'lost by': ', '.join(f'{c} {n}' for c, n in deaths.most_common()) or '-',
    }
    return name, line


def report(rows):
    names = [name for name, _ in rows]
    fields = list(rows[0][1])
    out = ['| | ' + ' | '.join(names) + ' |', '|---|' + '--:|' * len(names)]
    for field in fields:
        out.append(f'| {field} | ' + ' | '.join(str(line[field]) for _n, line in rows) + ' |')
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('file', nargs='?', help='recording (default: the latest)')
    parser.add_argument('--list', action='store_true', help='list the recordings')
    parser.add_argument('--bot', action='append', default=[], help='also play this bot profile on the same seed')
    parser.add_argument('--bot-set', action='append', default=[], metavar='FIELD=VALUE', help='change a bot field')
    args = parser.parse_args()

    found = recordings()
    if args.list:
        for path in found:
            print(path)
        if not found:
            print('No recordings yet: play a game (python3 game.py) and they appear in ~/.bvb/recordings/')
        return
    path = Path(args.file) if args.file else (found[-1] if found else None)
    if path is None or not path.exists():
        raise SystemExit('No recording found: play a game first (python3 game.py), or give a file.')

    # Simulated games write discoveries under HOME: keep them off the player's
    sys.argv = sys.argv[:1]
    os.environ['HOME'] = os.environ['USERPROFILE'] = tempfile.mkdtemp(prefix='bvb-replay-')
    os.chdir(ROOT)

    from dataclasses import replace

    from src.engine import recorder
    from src.sim import runner
    from src.sim.bot import PROFILES
    from src.sim.options import parse_assignments

    data = recorder.load(path)
    print(f'{path.name}: seed {data["seed"]}, recorded {data.get("date", "?")}, version {data.get("version", "?")}')
    commit = data.get('commit')
    current = recorder.code_commit()
    if commit and current and commit.rstrip('+') != current.rstrip('+'):
        print(f'Recorded with commit {commit}, this code is {current}.')
        print(f'To replay it exactly: git checkout {commit.rstrip("+")}')
    elif commit and commit.endswith('+'):
        print(f'Recorded with local changes on top of commit {commit.rstrip("+")}: the replay may differ.')

    observer = Observer()
    observer.install()
    try:
        stats = runner.replay(data)
    finally:
        observer.uninstall()
    summary = stats.summary()
    recorded = data.get('result', {})
    if recorded:
        same = recorded.get('level') == summary['level'] and recorded.get('score') == summary['score']
        print(
            'Replay matches the recorded game.'
            if same
            else f'Replay differs from the recording (recorded level {recorded.get("level")}, '
            f'score {recorded.get("score")}): the game code or configuration changed since.'
        )
    rows = [describe('you', summary, observer)]

    settings = data['settings']
    assist = 'trigger' if settings.get('trigger_on_enter') else 'bounce' if settings.get('bounce_on_enter') else 'none'
    changes = {}
    for item in args.bot_set:
        changes.update(parse_assignments(item))
    for name in args.bot:
        skill = replace(PROFILES[name], assist=assist, **changes)
        config = runner.RunConfig(
            seed=data['seed'],
            difficulty=data['difficulty'],
            skill=skill,
            base_config=data['config'],
            profile=data['profile'],
            max_minutes=max(1.0, summary['minutes'] * 3),
        )
        observer = Observer()
        observer.install()
        try:
            bot_summary = runner.run(config).summary()
        finally:
            observer.uninstall()
        rows.append(describe(f'bot {name}', bot_summary, observer))
    print()
    print(report(rows))


if __name__ == '__main__':
    main()
